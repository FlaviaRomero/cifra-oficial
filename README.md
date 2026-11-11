# 📊 Cifra Oficial

**Demo:** https://cifra-oficial-5mkaf7x9jhsetuowdztefm.streamlit.app/ · **Video de respaldo:** [COMPLETAR] · Proyecto final de la Diplomatura Q-Lab PUCP

## 1. One-liner

**Damos cifras oficiales del Perú, con gráfico y fuente citada, a periodistas y analistas mediante un buscador que consulta en vivo al BCRP y usa la ENAHO del INEI ya validada.**

## 2. Fundadora

Flavia Romero, asistente en RSC, comercio exterior y sostenibilidad

En la Diplomatura construí y validé las dos piezas de este producto:

- Un servidor MCP del BCRP que pasa 10 de 10 pruebas.
- Un pipeline de la ENAHO 2024 que reproduce la pobreza oficial: 27.53 % frente a 27.6 % del INEI, con 108,664 residentes y 25 departamentos.

También medí el problema: sin estas herramientas, un asistente de IA acertó **1 de 10** cifras oficiales; con ellas acertó **10 de 10**.

## 3. Problema

**Quién lo sufre:** periodistas de datos, analistas de consultoras y ONG, tesistas y equipos de gobiernos regionales que necesitan una cifra oficial (inflación, tipo de cambio, pobreza de un departamento) para publicarla o decidir con ella.

**Lo que cuesta hoy:**

- Encontrar la serie correcta entre las ~17,000 del BCRP.
- Descargar el Excel y calcular a mano promedios o variaciones.
- Procesar microdatos de la ENAHO, que requieren Stata o Python, factores de expansión y filtros.
- Si se usa un chatbot, el riesgo es que **invente la cifra**.

Un número equivocado en una nota o en un informe cuesta credibilidad.

**Cómo se resuelve hoy:** se navega a mano por la web del BCRP o del INEI, se descargan Excel, se le pregunta a un colega, o se usan chatbots sin fuente verificable.

**Evidencia, 3 conversaciones con usuarios potenciales:** [`docs/research/`](docs/research/)

- 

## 4. Solución e insight

Una pregunta rápida («pobreza en Puno», «¿cómo está el dólar?», en `consulta.py`) y un buscador web en lenguaje simple ("inflación 12 meses lima", "tasa de referencia") que en segundos devuelve:

1. La serie oficial correcta.
2. Su gráfico.
3. Un resumen calculado con Python: último valor, promedio, máximo, mínimo y variación.
4. **Una frase lista para citar**, con el código de serie, el periodo y el enlace a la fuente.
5. El CSV de los datos.

A eso se suma el mapa y los gráficos de pobreza monetaria 2024 por departamento, área, sexo y edad (ENAHO).

**Insight:** el problema no es que falten datos públicos, sino que **una cifra solo sirve si se puede citar y verificar**. Por eso cada número sale de una llamada repetible a la fuente oficial, nunca de un modelo de lenguaje. La misma capa de datos se ofrece como **servidor MCP**, para que los asistentes de IA que ya usan los periodistas respondan con cifras verificadas en vez de inventarlas.

## 5. Por qué ahora

- **MCP** (Model Context Protocol, 2024–2025) volvió estándar conectar asistentes de IA con fuentes de datos. Hace tres años no existía una forma común de darle herramientas a un modelo.
- Periodistas y analistas ya usan asistentes de IA a diario, pero estos **no conocen cifras recientes**. En mi experimento, sin herramientas respondieron "no sé" en 9 de 10 preguntas.
- El BCRP ofrece una API abierta sin clave, y hoy existen herramientas gratuitas (Streamlit Cloud, uv) para publicar un producto de datos en horas.

## 6. Demo

- **URL pública:** https://cifra-oficial-5mkaf7x9jhsetuowdztefm.streamlit.app/
- **Correr en local:**

  ```bash
  uv sync
  uv run streamlit run app.py      # la app web
  uv run pytest -q                 # pruebas: 5 passed
  ```

- **Capturas:** [COMPLETAR: 3 imágenes en `docs/img/`]

 (docs/img/1.png)
 (docs/img/2.png)
 (docs/img/3.png)

**Arquitectura:**

```
                ┌──────────────┐         ┌──────────────────────┐
  Periodista ──►│  app.py      │         │  mcp/server.py       │◄── Asistente de IA
  (navegador)   │  Streamlit   │         │  (Claude Code, etc.) │    (MCP)
                └──────┬───────┘         └──────────┬───────────┘
                       └──────────┬─────────────────┘
                     ┌────────────▼────────────┐
                     │ bcrp.py   │  enaho.py   │   núcleo compartido: cálculos en Python
                     └─────┬─────┴──────┬──────┘
          API del BCRP (en vivo)   data/indicadores_enaho_2024.csv
                                   (salida validada de la skill limpiando-enaho)
```

**Modelos y APIs:**

- **API del BCRP**: pública y gratuita; es la fuente oficial.
- **ENAHO 2024 del INEI**: microdatos procesados con mis Skills de la Sesión 16. En el repositorio solo se publican indicadores agregados.
- **No uso un LLM dentro de la app web**, y es a propósito: los cálculos los hace Python para que cada cifra sea exacta y repetible. La IA entra por el servidor MCP, que lo usa el asistente del propio usuario.

## 7. Modelo de negocio

| Plan | Para quién | Precio | Incluye |
|---|---|---|---|
| Gratis | Estudiantes y ciudadanos | S/ 0 | Buscador, gráficos, cita y CSV |
| Pro | Periodistas y analistas independientes | **S/ 39 al mes** | Alertas cuando se actualiza una serie, exportación a Excel y PNG, series favoritas |
| Equipos | Medios, consultoras, ONG y gobiernos regionales | **S/ 390 al mes** (hasta 10 usuarios) | Servidor MCP alojado para sus asistentes de IA, indicadores por departamento y soporte |

**Costo por usuario (estimado):**

- **Tokens:** S/ 0 en la app web, porque no llama a un modelo. En el servidor MCP los tokens los paga el asistente del cliente.
- **Servidor:** S/ 0 hoy (Streamlit Community Cloud). Con 1,000 usuarios activos, un servidor de unos US$ 25 al mes cuesta menos de S/ 0.10 por usuario.

## 8. Herramientas del curso

| Herramienta (sesión) | Dónde | Para qué |
|---|---|---|
| **MCP del BCRP** (Sesión 04) | `bcrp.py`, `mcp/server.py` | Buscar, descargar y resumir series; el servidor MCP para asistentes de IA |
| **Mapas interactivos** (Sesión 06) | `app.py`, pestaña «Mapa de pobreza» | Mapa en el que haces clic en un departamento (Plotly/MapLibre) y mapa con capas en Folium |
| **Skills de la ENAHO** (Sesión 16) | `data/indicadores_enaho_2024.csv` | Indicadores de pobreza calculados y validados con `limpiando-enaho` (Tarea 4) |
| Dashboards (Sesión 05) | `app.py` | Interfaz web con Streamlit y Plotly |

## 9. Qué hizo el agente

- **Claude** generó la estructura del proyecto: `bcrp.py`, `enaho.py`, `app.py`, `mcp/server.py`, `tests/` y este README, a partir de mi código de la Tarea 4 (servidor MCP y Skills de la ENAHO).
- **Yo**: elegí el problema, hice las 3 entrevistas, probé la app con datos reales, la publiqué en Streamlit Cloud, ajusté textos y precios, y grabé la demo.]
- Los resultados de la ENAHO y del experimento con IA vienen de mi Tarea 4: https://github.com/FlaviaRomero/Tarea_4

## Limitaciones y próximos pasos

- La pobreza es de 2024, el último año de la ENAHO procesado. El siguiente paso es agregar otros años y otros indicadores del INEI.
- La búsqueda es por palabras. El siguiente paso es una búsqueda semántica (RAG, Sesión 08) para pedidos como "¿cómo va el dólar?".
- Las alertas y el plan de equipos todavía no están construidos.
