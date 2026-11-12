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


# ---------------------------------------------------------------- detalle por departamento y grupo
DETALLE = RAIZ / "data" / "enaho_2024_detalle.csv"


def hay_detalle():
    return DETALLE.exists()


@cache
def detalle():
    """Pobreza, pobreza extrema, población y número de pobres por departamento (ccdd '00' = Perú) y grupo.
    Sale de scripts/agregar_enaho.py sobre la base validada de la Tarea 4."""
    d = pd.read_csv(DETALLE, dtype={"ccdd": str})
    d["ccdd"] = d.ccdd.str.zfill(2)
    d["departamento"] = d.ccdd.map(NOMBRES).fillna("Perú")
    return d


def ficha_departamento(nombre):
    """Total y cortes (área, sexo, edad) de un departamento, junto con los del Perú para comparar."""
    d = detalle()
    cod = next(k for k, v in NOMBRES.items() if v == nombre)
    return d[d.ccdd == cod], d[d.ccdd == "00"]


@cache
def centroides():
    """Centro aproximado de cada departamento (promedio ponderado por área del anillo exterior más grande)."""
    import json
    geo = json.loads(GEOJSON.read_text(encoding="utf-8"))
    out = {}
    for f in geo["features"]:
        g = f["geometry"]
        poligonos = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        anillo = max((p[0] for p in poligonos), key=len)
        a = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(anillo, anillo[1:] + anillo[:1]):
            c = x0 * y1 - x1 * y0
            a += c
            cx += (x0 + x1) * c
            cy += (y0 + y1) * c
        a *= 0.5
        out[str(f["properties"]["FIRST_IDDP"]).zfill(2)] = (cy / (6 * a), cx / (6 * a))   # (lat, lon)
    return out
