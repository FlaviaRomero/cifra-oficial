"""Pobreza monetaria 2024 (INEI, ENAHO) ya procesada y validada.

data/indicadores_enaho_2024.csv sale de la skill limpiando-enaho de la Tarea 4: módulos 34 y 02, residentes
habituales (108,664), ponderado con facpob07; nacional 27.53 % frente a 27.6 % oficial.
Los microdatos no se suben: se publican solo indicadores agregados.
"""
from functools import cache
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).parent
INDICADORES = RAIZ / "data" / "indicadores_enaho_2024.csv"
GEOJSON = RAIZ / "data" / "peru_departamental_simple.geojson"
FUENTE = "INEI, ENAHO 2024 (módulos 34 y 02). Residentes habituales, ponderado con facpob07."
NOMBRES = {"01": "Amazonas", "02": "Áncash", "03": "Apurímac", "04": "Arequipa", "05": "Ayacucho",
           "06": "Cajamarca", "07": "Callao", "08": "Cusco", "09": "Huancavelica", "10": "Huánuco",
           "11": "Ica", "12": "Junín", "13": "La Libertad", "14": "Lambayeque", "15": "Lima",
           "16": "Loreto", "17": "Madre de Dios", "18": "Moquegua", "19": "Pasco", "20": "Piura",
           "21": "Puno", "22": "San Martín", "23": "Tacna", "24": "Tumbes", "25": "Ucayali"}


@cache
def indicadores():
    return pd.read_csv(INDICADORES, dtype={"grupo": str})


def nacional():
    d = indicadores()
    return float(d.loc[d.nivel == "Nacional", "pobreza_pct"].iloc[0])


def por(nivel):
    """nivel: 'Área', 'Sexo', 'Edad' o 'Departamento'. Devuelve grupo y pobreza_pct."""
    d = indicadores().query("nivel == @nivel")[["grupo", "pobreza_pct"]].copy()
    if nivel == "Departamento":
        d.insert(0, "ccdd", d.grupo.str.zfill(2))
        d["grupo"] = d.ccdd.map(NOMBRES)
    return d.reset_index(drop=True)


def departamento(nombre_o_codigo):
    d = por("Departamento")
    q = str(nombre_o_codigo).strip().lower()
    fila = d[(d.ccdd == q.zfill(2)) | (d.grupo.str.lower() == q)]
    if fila.empty:
        raise ValueError(f"No encuentro el departamento {nombre_o_codigo!r}.")
    return fila.iloc[0].to_dict()
