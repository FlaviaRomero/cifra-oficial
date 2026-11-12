"""Genera data/enaho_2024_detalle.csv: pobreza ENAHO 2024 agregada por departamento y grupo (sin datos personales).

Se corre UNA vez en la carpeta de la Tarea 4, donde está la base limpia y validada:

    cd "C:\\tarea 4"
    uv run python ruta\\a\\cifra-oficial\\scripts\\agregar_enaho.py salidas/personas_2024.parquet ruta\\a\\cifra-oficial\\data\\enaho_2024_detalle.csv

Todo va ponderado con facpob07. 'n_muestra' es el número de personas encuestadas detrás de cada cifra:
con menos de 100 la cifra es poco precisa y la app lo avisa.
"""
import sys
from pathlib import Path

import pandas as pd

entrada = Path(sys.argv[1] if len(sys.argv) > 1 else "salidas/personas_2024.parquet")
salida = Path(sys.argv[2] if len(sys.argv) > 2 else "enaho_2024_detalle.csv")
df = pd.read_parquet(entrada, columns=["departamento", "area", "sexo", "grupo_edad", "pobre", "pobre_extremo", "facpob07"])
assert len(df) == 108_664, f"Se esperaban 108,664 residentes y hay {len(df):,}"


def resumir(d):
    peso = d.facpob07
    return pd.Series({"pobreza_pct": (d.pobre * peso).sum() / peso.sum() * 100,
                      "pobreza_extrema_pct": (d.pobre_extremo * peso).sum() / peso.sum() * 100,
                      "poblacion": peso.sum(), "pobres": (d.pobre * peso).sum(), "n_muestra": len(d)})


filas = []
for ambito, d_amb in [("00", df)] + list(df.groupby("departamento")):
    t = resumir(d_amb)
    filas.append({"ccdd": ambito, "corte": "Total", "grupo": "Total", **t})
    for corte, col in [("Área", "area"), ("Sexo", "sexo"), ("Edad", "grupo_edad")]:
        for g, dg in d_amb.groupby(col):
            filas.append({"ccdd": ambito, "corte": corte, "grupo": g, **resumir(dg)})

out = pd.DataFrame(filas)
for c in ["pobreza_pct", "pobreza_extrema_pct"]:
    out[c] = out[c].round(2)
out[["poblacion", "pobres"]] = out[["poblacion", "pobres"]].round(0).astype(int)
out["n_muestra"] = out.n_muestra.astype(int)
out["fuente"] = "INEI, ENAHO 2024; residentes habituales; ponderado con facpob07"

nac = out.query("ccdd == '00' and corte == 'Total'").iloc[0]
assert abs(nac.pobreza_pct - 27.6) <= 0.1, f"La pobreza nacional da {nac.pobreza_pct:.2f} %, no 27.6 %"
assert out.query("corte == 'Total'").ccdd.nunique() == 26, "Faltan departamentos"
salida.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(salida, index=False, encoding="utf-8")
print(f"Guardé {salida} con {len(out)} filas. Perú: pobreza {nac.pobreza_pct:.2f} %, extrema "
      f"{nac.pobreza_extrema_pct:.2f} %, {nac.pobres:,.0f} personas pobres de {nac.poblacion:,.0f}.")
