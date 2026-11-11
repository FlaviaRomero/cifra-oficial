"""Cifra Oficial: cifras del BCRP y del INEI con gráfico y fuente citada, en segundos.

    uv run streamlit run app.py
"""
from datetime import date, timedelta

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

import bcrp
import enaho

st.set_page_config(page_title="Cifra Oficial", page_icon="📊", layout="wide")
AZUL = "#2b6c8f"
EJEMPLOS = ["inflación 12 meses lima", "tipo de cambio interbancario venta", "tasa de referencia",
            "cobre precio", "reservas internacionales netas"]


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def buscar(texto):
    return bcrp.buscar(texto, limite=15)


@st.cache_data(ttl=3600, show_spinner=False)
def resumen_y_serie(codigo, desde, hasta):
    return bcrp.resumen(codigo, desde, hasta), bcrp.serie(codigo, desde, hasta)


def rango_por_defecto(frecuencia):
    hoy = date.today()
    f = frecuencia.lower()
    if f == "diaria":
        return (hoy - timedelta(days=60)).isoformat(), hoy.isoformat()
    if f == "anual":
        return str(hoy.year - 10), str(hoy.year)
    return f"{hoy.year - 2}-{hoy.month:02d}", f"{hoy.year}-{hoy.month:02d}"


def fmt(x):
    return f"{x:,.2f}"


st.title("📊 Cifra Oficial")
st.markdown("**Cifras oficiales del Perú, con gráfico y fuente citada, en segundos.** "
            "Para periodistas, analistas y equipos públicos que no pueden publicar un número equivocado.")

tab_bcrp, tab_pobreza, tab_ia = st.tabs(["🔎 Buscar una cifra del BCRP", "🗺️ Pobreza en el Perú (ENAHO 2024)",
                                         "🤖 Conecta tu asistente de IA"])

# ---------------------------------------------------------------- BCRP
with tab_bcrp:
    st.caption("Busca entre las ~17 mil series del Banco Central de Reserva del Perú. Los datos se consultan en vivo a su API.")
    c1, c2 = st.columns([3, 2])
    ejemplo = c2.selectbox("Ejemplos", ["—"] + EJEMPLOS, label_visibility="collapsed")
    texto = c1.text_input("¿Qué cifra buscas?", value="" if ejemplo == "—" else ejemplo,
                          placeholder="Ej.: inflación 12 meses lima", label_visibility="collapsed")
    if texto.strip():
        try:
            with st.spinner("Buscando en el catálogo del BCRP..."):
                resultados = buscar(texto.strip())
        except Exception as e:                        # catálogo inaccesible
            st.error(f"No pude leer el catálogo del BCRP: {e}")
            resultados = []
        if not resultados:
            st.warning("No hay series con todas esas palabras. Prueba con menos palabras.")
        else:
            etiquetas = {f"{r['nombre']} · {r['frecuencia']} · {r['codigo']}": r for r in resultados}
            elegida = etiquetas[st.selectbox("Series encontradas", list(etiquetas))]
            d0, d1 = rango_por_defecto(elegida["frecuencia"])
            ayuda = {"diaria": "AAAA-MM-DD", "anual": "AAAA"}.get(elegida["frecuencia"].lower(), "AAAA-MM")
            c3, c4 = st.columns(2)
            desde = c3.text_input(f"Desde ({ayuda})", d0)
            hasta = c4.text_input(f"Hasta ({ayuda})", d1)
            try:
                with st.spinner("Consultando la API del BCRP..."):
                    res, ser = resumen_y_serie(elegida["codigo"], desde.strip(), hasta.strip())
                u = res["ultimo"]
                k = st.columns(5)
                k[0].metric(f"Último ({u['periodo']})", fmt(u["valor"]),
                            f"{res['cambio']:+,.2f} desde {res['primero']['periodo']}", delta_color="off", delta_arrow="off")
                k[1].metric("Promedio", fmt(res["promedio"]))
                k[2].metric(f"Máximo ({res['maximo']['periodo']})", fmt(res["maximo"]["valor"]))
                k[3].metric(f"Mínimo ({res['minimo']['periodo']})", fmt(res["minimo"]["valor"]))
                k[4].metric("Variación %", "—" if res["variacion_pct"] is None else f"{res['variacion_pct']:+.2f} %")

                df = pd.DataFrame(ser["datos"])
                fig = px.line(df, x="periodo", y="valor", markers=len(df) <= 40,
                              title=f"{res['nombre']}<br><sup>Serie {res['codigo']} · {df.periodo.iloc[0]} a "
                                    f"{df.periodo.iloc[-1]} · Fuente: BCRP</sup>")
                fig.update_traces(line_color=AZUL)
                fig.update_layout(xaxis_title=None, yaxis_title=None, height=420, margin=dict(t=80))
                st.plotly_chart(fig, width="stretch")

                cita = (f"Según el BCRP (serie {res['codigo']}), «{res['nombre']}» fue {fmt(u['valor'])} en "
                        f"{u['periodo']}; el promedio entre {df.periodo.iloc[0]} y {df.periodo.iloc[-1]} fue "
                        f"{fmt(res['promedio'])}. Fuente: {res['fuente']}")
                st.markdown("**Cítalo así** (cópialo a tu nota o informe):")
                st.code(cita, language=None, wrap_lines=True)
                st.download_button("⬇️ Descargar datos (CSV)", df.to_csv(index=False).encode("utf-8"),
                                   f"{res['codigo']}_{desde}_{hasta}.csv", "text/csv")
            except Exception as e:
                st.error(f"{e}")
    else:
        st.info("Escribe una cifra o elige un ejemplo para empezar.")

# ---------------------------------------------------------------- ENAHO
with tab_pobreza:
    nac = enaho.nacional()
    deps = enaho.por("Departamento").sort_values("pobreza_pct", ascending=False)
    k = st.columns(4)
    k[0].metric("Pobreza monetaria, Perú 2024", f"{nac:.1f} %", "Oficial INEI: 27.6 %", delta_color="off", delta_arrow="off")
    k[1].metric("Más pobre", f"{deps.iloc[0].grupo}", f"{deps.iloc[0].pobreza_pct:.1f} %", delta_color="off", delta_arrow="off")
    k[2].metric("Menos pobre", f"{deps.iloc[-1].grupo}", f"{deps.iloc[-1].pobreza_pct:.1f} %", delta_color="off", delta_arrow="off")
    area = enaho.por("Área").set_index("grupo").pobreza_pct
    k[3].metric("Brecha rural – urbana", f"{area['Rural'] - area['Urbana']:.1f} pp",
                f"Rural {area['Rural']:.1f} % · Urbana {area['Urbana']:.1f} %", delta_color="off", delta_arrow="off")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**Pobreza monetaria por departamento, 2024** (% de personas)")
        geo = __import__("json").loads(enaho.GEOJSON.read_text(encoding="utf-8"))
        valores = deps.set_index("ccdd").pobreza_pct.to_dict()
        for f in geo["features"]:
            cod = str(f["properties"]["FIRST_IDDP"]).zfill(2)
            f["properties"]["pobreza"] = f"{valores.get(cod, float('nan')):.1f} %"
            f["properties"]["nombre"] = enaho.NOMBRES.get(cod, cod)
        m = folium.Map(location=[-9.2, -75], zoom_start=5, tiles="OpenStreetMap")
        folium.Choropleth(geo_data=geo, data=deps, columns=["ccdd", "pobreza_pct"], key_on="feature.properties.FIRST_IDDP",
                          fill_color="Reds", fill_opacity=0.8, line_opacity=0.4, bins=[0, 10, 20, 30, 40, 50],
                          legend_name="% de personas en pobreza monetaria").add_to(m)
        folium.GeoJson(geo, style_function=lambda _: {"fillOpacity": 0, "weight": 0},
                       tooltip=folium.GeoJsonTooltip(["nombre", "pobreza"], aliases=["Departamento", "Pobreza"])).add_to(m)
        st_folium(m, height=520, use_container_width=True, returned_objects=[])
    with c2:
        nivel = st.radio("Comparar por", ["Área", "Sexo", "Edad", "Departamento"], horizontal=True)
        d = enaho.por(nivel)
        if nivel != "Edad":
            d = d.sort_values("pobreza_pct")
        fig = px.bar(d, x="pobreza_pct", y="grupo", orientation="h", text=d.pobreza_pct.map(lambda v: f"{v:.1f} %"),
                     color_discrete_sequence=[AZUL])
        fig.add_vline(x=nac, line_dash="dash", line_color="#555", annotation_text=f"Perú {nac:.1f} %")
        fig.update_layout(xaxis_title="% de personas en pobreza monetaria", yaxis_title=None,
                          height=520 if nivel == "Departamento" else 300, margin=dict(t=20), xaxis_range=[0, 52])
        st.plotly_chart(fig, width="stretch")
        elegido = st.selectbox("Cifra de un departamento", list(enaho.NOMBRES.values()), index=7)
        dep = enaho.departamento(elegido)
        rank = int((deps.pobreza_pct > dep["pobreza_pct"]).sum()) + 1
        cita = (f"Según la ENAHO 2024 del INEI, el {dep['pobreza_pct']:.1f} % de la población de {elegido} estaba en "
                f"pobreza monetaria ({rank}.º de 25 departamentos; Perú: {nac:.1f} %). Fuente: {enaho.FUENTE}")
        st.code(cita, language=None, wrap_lines=True)
    st.caption(f"Fuente: {enaho.FUENTE} Cálculo propio validado: 108,664 residentes y 27.53 % nacional "
               "(oficial 27.6 %); 25 departamentos a ±0.5 pp de la referencia.")

# ---------------------------------------------------------------- IA
with tab_ia:
    st.markdown("""
### Los asistentes de IA inventan o no saben cifras recientes. Cifra Oficial se las da verificadas.

Cifra Oficial también funciona como **servidor MCP** (Model Context Protocol): cualquier asistente compatible,
como Claude Code, puede buscar series del BCRP y resumirlas con Python, citando código, periodo y fuente.

**Evidencia (experimento propio, 10 preguntas oficiales, Claude Haiku):**
""")
    st.dataframe(pd.DataFrame({"Asistente": ["Sin Cifra Oficial", "Con Cifra Oficial"],
                               "Respuestas correctas": ["1 de 10", "10 de 10"],
                               "Sin respuesta («no sé»)": [9, 0], "Segundos promedio": [8.2, 25.2]}),
                 hide_index=True, width="stretch")
    st.markdown("**Conéctalo** en tu proyecto (archivo `.mcp.json`):")
    st.code('{\n  "mcpServers": {\n    "cifra-oficial": {\n      "type": "stdio",\n      "command": "uv",\n'
            '      "args": ["run", "mcp/server.py"]\n    }\n  }\n}', language="json")
    st.markdown("Herramientas que ofrece: `buscar_series`, `serie`, `resumen`, `pobreza_departamento`.")
