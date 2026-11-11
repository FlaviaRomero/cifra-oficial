"""Interpreta una pregunta corta en español y decide qué cifra mostrar (sin LLM: reglas simples y verificables).

    interpretar("¿cuánta pobreza hay en Puno?")  -> {"tipo": "departamento", "valor": "Puno"}
    interpretar("¿cómo está el dólar?")          -> {"tipo": "serie", "valor": "PD04638PD"}
"""
import unicodedata

import enaho

# Indicadores frecuentes del BCRP (códigos verificados en la Sesión 04 y la Tarea 4)
INDICADORES = {
    "PN01273PM": {"corto": "Inflación", "titulo": "Inflación 12 meses", "unidad": "%", "emoji": "🛒", "claves": ["inflacion", "precios", "ipc"]},
    "PD04638PD": {"corto": "Dólar", "titulo": "Dólar (interbancario venta)", "unidad": "S/ por US$", "emoji": "💵",
                  "claves": ["dolar", "tipo de cambio", "cambio"]},
    "PD04722MM": {"corto": "Tasa BCRP", "titulo": "Tasa de referencia BCRP", "unidad": "%", "emoji": "🏦", "claves": ["tasa", "referencia", "interes"]},
    "PN38784BM": {"corto": "Cobre", "titulo": "Precio del cobre", "unidad": "¢US$ por libra", "emoji": "⛏️", "claves": ["cobre", "metal"]},
    "PN00027MM": {"corto": "Reservas", "titulo": "Reservas internacionales", "unidad": "millones US$", "emoji": "🏛️", "claves": ["reservas", "rin"]},
    "PM04923AA": {"corto": "PBI", "titulo": "Crecimiento del PBI", "unidad": "%", "emoji": "📈", "claves": ["pbi", "crecimiento", "economia"]},
}


def _norm(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


def _departamento(t):
    for nombre in enaho.NOMBRES.values():
        if _norm(nombre) in t:
            return nombre
    return None


def interpretar(texto):
    t = _norm(texto)
    if not t.strip():
        return None
    dep = _departamento(t)
    if "pobre" in t:                                  # pregunta de pobreza: departamento, área o nacional
        if dep:
            return {"tipo": "departamento", "valor": dep}
        if "rural" in t or "urban" in t:
            return {"tipo": "area"}
        return {"tipo": "nacional"}
    for codigo, info in INDICADORES.items():          # indicador económico ("inflación de Lima" es del BCRP)
        if any(c in t for c in info["claves"]):
            return {"tipo": "serie", "valor": codigo}
    if dep:                                           # solo un departamento: su pobreza
        return {"tipo": "departamento", "valor": dep}
    return {"tipo": "buscar", "valor": texto.strip()}
