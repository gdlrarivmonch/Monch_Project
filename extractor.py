Python 3.14.3 (tags/v3.14.3:323c59a, Feb  3 2026, 16:04:56) [MSC v.1944 64 bit (AMD64)] on win32
Enter "help" below or click "Help" above for more information.
help
Type help() for interactive help, or help(object) for help about object.




#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrae StepNum, PartName y Msr_V de archivos ICT (formato con // Header_Data y // Component_Data)
y genera:
  1) un TXT 'largo' con columnas: RunIndex, StepNum, PartName, Msr_V
  2) un TXT 'pivot' donde cada PartName (desambiguado con StepNum si hace falta) es columna
     y en las filas (RunIndex) se listan todas las mediciones Msr_V.

Autor: Ramon-ready
Python: 3.8+
Dependencias: estándar
"""

import os
import re
from collections import OrderedDict, defaultdict

def pedir_ruta_archivo() -> str:
    """
    Pide al usuario la ruta del archivo .txt por input().
    Valida existencia básica.
    """
    ruta = input("Indica la ruta completa del archivo ICT (*.txt): ").strip().strip('"').strip("'")
    if not ruta:
        raise ValueError("No se proporcionó ruta.")
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No se encontró el archivo: {ruta}")
    return ruta

def parsear_ict(ruta_txt: str, col_valor: str = "Msr_V"):
    """
    Parsea el archivo ICT y devuelve:
      - runs: lista de corridas, cada una OrderedDict({ stepnum: (partname, msr_v_str) })
    """
    runs = []
    current_run = None
    en_componentes = False
    col_index = {}

    with open(ruta_txt, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n")

            # Nueva corrida
            if line.startswith("// Header_Data"):
                if current_run is not None:
                    runs.append(current_run)
                current_run = OrderedDict()
                en_componentes = False
                col_index = {}
                continue

            # Sección de componentes
            if line.startswith("// Component_Data"):
                en_componentes = False
                continue

            # Encabezado de la tabla de componentes
            if line.startswith("// StepNum"):
                header = line.lstrip("/ ").strip()
                cols = [c.strip() for c in header.split(",")]
                col_index = {c: i for i, c in enumerate(cols)}
                # Validación de columnas esenciales
                for req in ("StepNum", "PartName", col_valor):
                    if req not in col_index:
                        raise ValueError(f"Falta columna requerida en Component_Data: {req}")
                en_componentes = True
                continue

            # Filas de datos de componentes
            if en_componentes and line and not line.startswith("//"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) <= max(col_index.values()):
                    continue
                # StepNum entero
                try:
                    stepnum = int(parts[col_index["StepNum"]].strip())
                except Exception:
                    continue

                partname = parts[col_index["PartName"]].strip()
                msr_v_raw = parts[col_index[col_valor]].strip()
                # Quitar espacios internos pero conservar unidades (K, M, nF, uF, mF, pF, V, etc.)
                msr_v = re.sub(r"\s+", "", msr_v_raw)
                current_run[stepnum] = (partname, msr_v)

    if current_run is not None:
        runs.append(current_run)

    if not runs:
        raise RuntimeError("No se detectaron corridas con Component_Data en el archivo.")

    return runs

def construir_salidas(runs):
    """
    A partir de 'runs' arma:
      - registros_largos: lista de tuplas (RunIndex, StepNum, PartName, Msr_V)
      - matriz_por_part: dict colname -> lista de valores por RunIndex (alineados)
        * colname = PartName o PartName__Step<StepNum> cuando el mismo PartName aparece en múltiples StepNum
    """
    # Formato largo
    registros_largos = []
    # Para pivot: necesitamos detectar colisiones PartName->varios StepNum
    part_to_steps = defaultdict(set)
    for run in runs:
        for step, (pname, _val) in run.items():
            part_to_steps[pname].add(step)

    # Construir lista estable de "columnas" para pivot
    # colname será:
    #   - "PartName" si solo existe en 1 StepNum en todas las corridas
    #   - "PartName__Step<StepNum>" si aparece en múltiples StepNum
    columnas = []                 # orden determinista por (PartName, StepNum)
    colname_by_key = {}           # (PartName, StepNum) -> colname
    for run in runs:
        for step in sorted(run.keys()):
            pname = run[step][0]
            if len(part_to_steps[pname]) > 1:
                colname = f"{pname}__Step{step}"
            else:
                colname = pname
            key = (pname, step)
            if key not in colname_by_key:
                colname_by_key[key] = colname
                columnas.append((pname, step, colname))

    # Matriz pivot por PartName
    # Creamos un renglón por corrida y lo llenamos
    matriz_por_part = OrderedDict()
    for _p, _s, colname in columnas:
        matriz_por_part[colname] = [""] * len(runs)

    # Llenar estructuras
    for i, run in enumerate(runs, start=1):
        for step, (pname, val) in run.items():
            # largo
            registros_largos.append((i, step, pname, val))
            # pivot
            if len(part_to_steps[pname]) > 1:
                colname = f"{pname}__Step{step}"
            else:
                colname = pname
            # Asegurar columna
            if colname not in matriz_por_part:
                matriz_por_part[colname] = [""] * len(runs)
            matriz_por_part[colname][i - 1] = val

    return registros_largos, matriz_por_part

def escribir_txt_largo(registros, ruta_salida):
    """
    Escribe el formato largo: RunIndex\tStepNum\tPartName\tMsr_V
    """
    with open(ruta_salida, "w", encoding="utf-8", newline="") as out:
        out.write("RunIndex\tStepNum\tPartName\tMsr_V\n")
        for run_idx, step, pname, val in registros:
            out.write(f"{run_idx}\t{step}\t{pname}\t{val}\n")

def escribir_txt_pivot(matriz_por_part, ruta_salida):
    """
...     Escribe el formato pivot:
...       Encabezados: RunIndex, <PartName/PartName__StepN>...
...       Filas: mediciones alineadas por corrida
...     """
...     # Encabezados ordenados alfabéticamente para fácil búsqueda
...     cols = ["RunIndex"] + list(matriz_por_part.keys())
...     n_rows = 0
...     for v in matriz_por_part.values():
...         n_rows = max(n_rows, len(v))
... 
...     with open(ruta_salida, "w", encoding="utf-8", newline="") as out:
...         out.write("\t".join(cols) + "\n")
...         for i in range(n_rows):
...             fila = [str(i + 1)]
...             for col in cols[1:]:
...                 fila.append(matriz_por_part[col][i] if i < len(matriz_por_part[col]) else "")
...             out.write("\t".join(fila) + "\n")
... 
... def main():
...     # 1) Pedir ruta
...     ruta = pedir_ruta_archivo()
... 
...     # 2) Parsear
...     runs = parsear_ict(ruta, col_valor="Msr_V")
... 
...     # 3) Construir estructuras
...     registros_largos, matriz_por_part = construir_salidas(runs)
... 
...     # 4) Escribir resultados junto al archivo de origen
...     base_dir = os.path.dirname(ruta)
...     base_name = os.path.splitext(os.path.basename(ruta))[0]
...     out_long = os.path.join(base_dir, f"ict_long_{base_name}.txt")
...     out_pivot = os.path.join(base_dir, f"ict_by_part_{base_name}.txt")
... 
...     escribir_txt_largo(registros_largos, out_long)
...     escribir_txt_pivot(matriz_por_part, out_pivot)
... 
...     print("Listo ✅")
...     print(f"Corridas detectadas: {len(runs)}")
...     print(f"Salidas generadas:")
...     print(f"  - Formato largo : {out_long}")
...     print(f"  - Por PartName  : {out_pivot}")
...     print("Notas:")
...     print("  * Si un PartName existe en varios StepNum, la columna se nombra como PartName__Step<StepNum>.")
... 
... if __name__ == "__main__":
