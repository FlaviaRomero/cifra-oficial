"""Servidor MCP de Cifra Oficial: el mismo núcleo de la app web, para asistentes de IA.

    uv run mcp/server.py                                              # por stdio
    claude mcp add --scope project cifra-oficial -- uv run mcp/server.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP                       # noqa: E402
from fastmcp.exceptions import ToolError          # noqa: E402

import bcrp                                       # noqa: E402
import enaho                                      # noqa: E402

SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}
mcp = FastMCP("cifra-oficial", instructions=(
    "Cifras oficiales del Perú. Para el BCRP busca primero el código con buscar_series y luego usa resumen o serie; "
    "para pobreza 2024 usa pobreza_departamento. No calcules a mano: cita siempre código, periodo y fuente."))


def _seguro(f, *a):
    try:
        return f(*a)
    except bcrp.ErrorBCRP as e:
        raise ToolError(str(e)) from e


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_series(texto: str, frecuencia: str | None = None, limite: int = 10) -> list[dict]:
    """Busca series del BCRP por palabras (todas deben aparecer). Ej.: "ipc 12 meses", "tasa de referencia".
    frecuencia: "Diaria", "Mensual", "Trimestral" o "Anual"."""
    return bcrp.buscar(texto, frecuencia, limite)


@mcp.tool(annotations=SOLO_LECTURA)
def serie(codigo: str, desde: str, hasta: str) -> dict:
    """Datos de una serie del BCRP. Fechas: '2025-01' (mensual), '2025-01-15' (diaria), '2025' (anual)."""
    return _seguro(bcrp.serie, codigo, desde, hasta)


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(codigo: str, desde: str, hasta: str) -> dict:
    """Primero, último, cambio, variación %, promedio, máximo y mínimo de una serie del BCRP. Úsala en vez de calcular."""
    return _seguro(bcrp.resumen, codigo, desde, hasta)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def pobreza_departamento(departamento: str) -> dict:
    """Pobreza monetaria 2024 (INEI, ENAHO, ponderada) de un departamento por nombre ('Cusco') o código ('08')."""
    try:
        d = enaho.departamento(departamento)
    except ValueError as e:
        raise ToolError(str(e)) from e
    return {**d, "nacional_pct": enaho.nacional(), "fuente": enaho.FUENTE}


@mcp.resource("cifra://serie/{codigo}")
def ficha_serie(codigo: str) -> dict:
    """Ficha de una serie del BCRP: nombre, categoría, frecuencia y desde cuándo hay datos."""
    return _seguro(bcrp.ficha, codigo)


if __name__ == "__main__":
    mcp.run()
