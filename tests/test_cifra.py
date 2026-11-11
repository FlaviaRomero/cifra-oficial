"""Pruebas sin internet: formatos de fecha del BCRP, resumen e indicadores de la ENAHO.

    uv run pytest -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bcrp   # noqa: E402
import enaho  # noqa: E402


def test_fechas_que_pide_la_api():
    assert bcrp._fecha_api("2025-01", "Mensual") == "2025-1"
    assert bcrp._fecha_api("2026-10-15", "Diaria") == "2026-10-15"
    assert bcrp._fecha_api("2025-03", "Anual") == "2025"


def test_periodos_que_devuelve_la_api():
    assert bcrp._periodo("Ene.2025", "Mensual") == "2025-01"
    assert bcrp._periodo("Set.2024", "Mensual") == "2024-09"          # el BCRP escribe setiembre «Set»
    assert bcrp._periodo("01.Oct.26", "Diaria") == "2026-10-01"
    assert bcrp._periodo("T1.25", "Trimestral") == "2025-T1"


def test_resumen_calcula_con_python(monkeypatch):
    datos = [{"periodo": f"2024-{m:02d}", "valor": v} for m, v in [(1, 3.0), (2, 3.5), (3, 2.0)]]
    monkeypatch.setattr(bcrp, "serie", lambda c, d, h: {"nombre": "IPC", "frecuencia": "Mensual",
                                                         "datos": datos, "fuente": "https://x"})
    r = bcrp.resumen("PN01273PM", "2024-01", "2024-03")
    assert r["cambio"] == -1.0 and r["variacion_pct"] == pytest.approx(-33.33, abs=0.01)
    assert r["maximo"]["periodo"] == "2024-02" and r["minimo"]["valor"] == 2.0
    assert r["promedio"] == pytest.approx(2.8333, abs=1e-3)


def test_enaho_validada():
    assert enaho.nacional() == pytest.approx(27.6, abs=0.1)           # oficial INEI 2024
    deps = enaho.por("Departamento")
    assert len(deps) == 25 and deps.ccdd.tolist() == [f"{i:02d}" for i in range(1, 26)]
    assert enaho.departamento("Cusco")["pobreza_pct"] == pytest.approx(18.5, abs=0.1)
    assert enaho.departamento("06")["grupo"] == "Cajamarca"


def test_pregunta_rapida_entiende_departamentos_y_series():
    from consulta import interpretar
    assert interpretar("¿cuánta pobreza hay en Puno?") == {"tipo": "departamento", "valor": "Puno"}
    assert interpretar("pobreza en el Perú")["tipo"] == "nacional"
    assert interpretar("¿cómo está el dólar?") == {"tipo": "serie", "valor": "PD04638PD"}
    assert interpretar("inflación de lima")["valor"] == "PN01273PM"
    assert interpretar("exportaciones de oro")["tipo"] == "buscar"
    assert interpretar("Cusco") == {"tipo": "departamento", "valor": "Cusco"}
