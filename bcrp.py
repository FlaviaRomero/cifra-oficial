"""Núcleo de datos del BCRP: buscar series, descargarlas y resumirlas.

Lo usan la app web (app.py) y el servidor MCP (mcp/server.py): un solo código, dos interfaces.
Las cuentas las hace Python, nunca un modelo de lenguaje: cada cifra sale de una llamada repetible.
"""
import re
import time
import unicodedata
from functools import cache
from pathlib import Path

import httpx
import pandas as pd

RAIZ = Path(__file__).parent
CATALOGO = RAIZ / "data" / "catalogo_bcrp.csv"
URL_CATALOGO = "https://estadisticas.bcrp.gob.pe/estadisticas/series/metadata"
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7,
         "Ago": 8, "Sep": 9, "Set": 9, "Oct": 10, "Nov": 11, "Dic": 12}


class ErrorBCRP(Exception):
    """Error con un mensaje claro para mostrar al usuario."""


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


@cache
def catalogo():
    """Catálogo oficial del BCRP (unas 17 mil series). Se baja una vez y queda en data/."""
    if not CATALOGO.exists():
        CATALOGO.parent.mkdir(exist_ok=True)
        r = httpx.get(URL_CATALOGO, timeout=120)
        r.raise_for_status()
        CATALOGO.write_text(r.content.decode("latin-1"), encoding="utf-8")
    df = pd.read_csv(CATALOGO, sep=";", dtype=str).fillna("")
    df = df.rename(columns={"Código de serie": "codigo", "Categoría de serie": "categoria", "Grupo de serie": "grupo",
                            "Nombre de serie": "nombre", "Frecuencia": "frecuencia",
                            "Fecha de actualización": "actualizada", "Fecha de inicio": "inicio"})
    df["texto"] = (df.categoria + " " + df.grupo + " " + df.nombre).map(_sin_tildes)
    return df


def ficha(codigo):
    fila = catalogo().query("codigo == @codigo")
    if fila.empty:
        raise ErrorBCRP(f"No existe la serie {codigo!r} en el catálogo del BCRP.")
    f = fila.iloc[0]
    return {"codigo": f.codigo, "nombre": f"{f.grupo} - {f.nombre}", "categoria": f.categoria,
            "frecuencia": f.frecuencia, "inicio": f.inicio, "actualizada": f.actualizada}


def buscar(texto, frecuencia=None, limite=10):
    """Series cuyo texto contiene todas las palabras; primero las vigentes y de nombre más corto."""
    df = catalogo()
    m = pd.Series(True, index=df.index)
    for palabra in _sin_tildes(texto).split():
        m &= df.texto.str.contains(re.escape(palabra))
    if frecuencia:
        m &= df.frecuencia.str.lower() == frecuencia.lower()
    sel = df[m]
    orden = sel.assign(vieja=sel.actualizada < "2025", largo=(sel.grupo + sel.nombre).str.len())
    return [ficha(c) for c in orden.sort_values(["vieja", "largo"]).head(limite).codigo]


def _fecha_api(fecha, frecuencia):
    """'2025-01' -> '2025-1' (mensual/trimestral); la diaria va igual; la anual solo el año."""
    f = frecuencia.lower()
    if f == "diaria":
        return fecha
    if f == "anual":
        return fecha[:4]
    anio, resto = fecha.split("-")[:2]
    return f"{anio}-{int(resto.lstrip('T'))}"


def _periodo(nombre, frecuencia):
    """'Ene.2025' -> '2025-01', '01.Oct.26' -> '2026-10-01', 'T1.25' -> '2025-T1'."""
    f = frecuencia.lower()
    if f == "mensual":
        m, a = nombre.split(".")
        return f"{a}-{MESES[m[:3]]:02d}"
    if f == "diaria":
        d, m, a = nombre.split(".")
        return f"20{a}-{MESES[m[:3]]:02d}-{int(d):02d}"
    if f == "trimestral":
        t, a = nombre.split(".")
        return f"20{a}-{t}"
    return nombre


@cache
def _descargar(url):
    for intento in range(4):            # con muchos pedidos seguidos la API responde HTML: esperar y reintentar
        try:
            return httpx.get(url, timeout=60).json()
        except (ValueError, httpx.HTTPError):
            time.sleep(2 * (intento + 1))
    raise ErrorBCRP("El BCRP no respondió con datos; reintenta en unos segundos.")


def serie(codigo, desde, hasta):
    f = ficha(codigo)
    fr = f["frecuencia"]
    url = f"{API}/{codigo}/json/{_fecha_api(desde, fr)}/{_fecha_api(hasta, fr)}"
    datos = [{"periodo": _periodo(p["name"], fr), "valor": float(p["values"][0])}
             for p in _descargar(url).get("periods", []) if p["values"][0] != "n.d."]
    return {**f, "datos": datos, "fuente": url}


def resumen(codigo, desde, hasta):
    s = serie(codigo, desde, hasta)
    d = s["datos"]
    if not d:
        raise ErrorBCRP(f"La serie {codigo} no tiene datos entre {desde} y {hasta}.")
    primero, ultimo = d[0], d[-1]
    cambio = ultimo["valor"] - primero["valor"]
    return {"codigo": codigo, "nombre": s["nombre"], "frecuencia": s["frecuencia"], "desde": desde, "hasta": hasta,
            "primero": primero, "ultimo": ultimo, "cambio": round(cambio, 4),
            "variacion_pct": round(cambio / primero["valor"] * 100, 2) if primero["valor"] else None,
            "promedio": round(sum(x["valor"] for x in d) / len(d), 4),
            "maximo": max(d, key=lambda x: x["valor"]), "minimo": min(d, key=lambda x: x["valor"]),
            "n_periodos": len(d), "fuente": s["fuente"]}
