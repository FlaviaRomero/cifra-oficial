"""Cifra Oficial: cifras del BCRP y del INEI con gráfico y fuente citada, en segundos.

    uv run streamlit run app.py
"""
import json
from datetime import date, timedelta

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import bcrp
import enaho
from consulta import INDICADORES, interpretar

st.set_page_config(page_title="Cifra Oficial", page_icon="📊", layout="wide")
VERDE, AZUL, NARANJA, GRIS = "#0f766e", "#1d4ed8", "#ea580c", "#6b7280"
ESCALA = ["#fef3c7", "#fdba74", "#f97316", "#c2410c", "#7c2d12"]

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stText { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.2rem; max-width: 1250px; }
.hero { background: linear-gradient(120deg, #0f766e 0%, #155e75 55%, #1e3a8a 100%); color: #fff;
        border-radius: 22px; padding: 30px 34px 26px; margin-bottom: 18px; position: relative; overflow: hidden; }
.hero:after { content: ""; position: absolute; right: -60px; top: -60px; width: 260px; height: 260px;
              border-radius: 50%; background: rgba(255,255,255,.08); }
.hero h1 { font-size: 2.5rem; font-weight: 800; margin: 0; color: #fff; letter-spacing: -0.5px; }
.hero p { font-size: 1.08rem; margin: 6px 0 0; opacity: .92; max-width: 760px; }
.pill { display: inline-block; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.25);
        padding: 3px 11px; border-radius: 999px; font-size: .78rem; margin: 12px 6px 0 0; }
.card { background: #fff; border-radius: 16px; padding: 16px 18px; box-shadow: 0 2px 10px rgba(15,23,42,.06);
        border: 1px solid #eef0f3; height: 100%; }
.card .lbl { color: #6b7280; font-size: .82rem; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; }
.card .val { font-size: 1.9rem; font-weight: 800; color: #111827; line-height: 1.15; margin-top: 4px; }
.card .sub { color: #6b7280; font-size: .85rem; margin-top: 2px; }
.up { color: #b91c1c; } .down { color: #15803d; }
.answer { background: #ecfdf5; border-left: 6px solid #0f766e; border-radius: 14px; padding: 16px 20px; margin: 6px 0 4px; }
.answer .big { font-size: 2.2rem; font-weight: 800; color: #065f46; }
.cite { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 12px; padding: 12px 14px; font-size: .9rem; color: #334155; }
div[data-testid="stTabs"] button p { font-size: 1.02rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ datos con caché
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def buscar(texto):
    return bcrp.buscar(texto, limite=15)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def ficha(codigo):
    return bcrp.ficha(codigo)


@st.cache_data(ttl=3600, show_spinner=False)
def datos(codigo, desde, hasta):
    return bcrp.resumen(codigo, desde, hasta), bcrp.serie(codigo, desde, hasta)


@st.cache_data(show_spinner=False)
def geojson():
    return json.loads(enaho.GEOJSON.read_text(encoding="utf-8"))


def rango(frecuencia, preset):
    """Fechas 'desde' y 'hasta' para un preset (1A, 3A, 5A, 10A) según la frecuencia de la serie."""
    hoy = date.today()
    anios = {"1A": 1, "3A": 3, "5A": 5, "10A": 10}[preset]
    f = frecuencia.lower()
    if f == "diaria":
        dias = {"1A": 30, "3A": 90, "5A": 180, "10A": 365}[preset]      # la diaria pesa más: meses en vez de años
        return (hoy - timedelta(days=dias)).isoformat(), hoy.isoformat()
    if f == "anual":
        return str(hoy.year - max(anios, 5)), str(hoy.year)
    return f"{hoy.year - anios}-{hoy.month:02d}", f"{hoy.year}-{hoy.month:02d}"


def card(lbl, val, sub="", clase=""):
    return f'<div class="card"><div class="lbl">{lbl}</div><div class="val">{val}</div><div class="sub {clase}">{sub}</div></div>'


def n(x, d=2):
    return f"{x:,.{d}f}"


def grafico_serie(df, titulo, unidad, media_movil=False, comparar=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.periodo, y=df.valor, mode="lines", name=titulo, line=dict(color=VERDE, width=3),
                             fill="tozeroy" if comparar is None else None, fillcolor="rgba(15,118,110,.10)",
                             hovertemplate="%{x}<br><b>%{y:,.2f}</b> " + unidad + "<extra></extra>"))
    if media_movil and len(df) >= 6:
        fig.add_trace(go.Scatter(x=df.periodo, y=df.valor.rolling(3).mean(), mode="lines", name="Promedio móvil (3)",
                                 line=dict(color=NARANJA, width=2, dash="dot")))
    imax, imin = df.valor.idxmax(), df.valor.idxmin()
    for i, txt, col in [(imax, "máx", "#b91c1c"), (imin, "mín", "#15803d")]:
        fig.add_annotation(x=df.periodo[i], y=df.valor[i], text=f"{txt} {df.valor[i]:,.2f}", showarrow=True,
                           arrowhead=2, ax=0, ay=-30 if txt == "máx" else 30, font=dict(color=col, size=12),
                           bgcolor="white", bordercolor=col)
    fig.add_trace(go.Scatter(x=[df.periodo.iloc[-1]], y=[df.valor.iloc[-1]], mode="markers+text",
                             marker=dict(size=11, color=VERDE, line=dict(color="white", width=2)),
                             text=[f"  {df.valor.iloc[-1]:,.2f}"], textposition="middle right", showlegend=False,
                             hoverinfo="skip"))
    if comparar is not None:
        d2, t2 = comparar
        fig.add_trace(go.Scatter(x=d2.periodo, y=d2.valor, mode="lines", name=t2, yaxis="y2",
                                 line=dict(color=AZUL, width=2.5)))
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, title=t2))
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified", plot_bgcolor="white",
                      legend=dict(orientation="h", y=1.08, x=0), yaxis=dict(gridcolor="#eef0f3", title=unidad),
                      xaxis=dict(showgrid=False))
    return fig


def mapa_plotly(deps, modo, seleccionado):
    """Mapa interactivo (MapLibre, incluido en Plotly): no descarga teselas ni mapas de internet."""
    nac = enaho.nacional()
    d = deps.copy()
    d["dif"] = d.pobreza_pct - nac
    if modo == "Nivel de pobreza":
        color, escala, rango_c, barra = "pobreza_pct", ESCALA, (0, 50), "% de personas<br>en pobreza"
    else:
        color, escala, rango_c, barra = "dif", "RdBu_r", (-25, 25), f"pp frente a<br>Perú ({nac:.1f} %)"
    fig = px.choropleth_map(d, geojson=geojson(), locations="ccdd", featureidkey="properties.FIRST_IDDP",
                            color=color, color_continuous_scale=escala, range_color=rango_c, opacity=0.9,
                            custom_data=["grupo", "pobreza_pct", "dif"], map_style="white-bg",
                            center={"lat": -9.3, "lon": -75.0}, zoom=4.1)
    fig.update_traces(marker_line_color="white", marker_line_width=1,
                      hovertemplate="<b>%{customdata[0]}</b><br>Pobreza: %{customdata[1]:.1f} %"
                                    "<br>Frente a Perú: %{customdata[2]:+.1f} pp<extra></extra>")
    sel = d[d.grupo == seleccionado]
    if not sel.empty:   # resalta el departamento elegido con un borde negro grueso
        fig.add_trace(go.Choroplethmap(geojson=geojson(), locations=sel.ccdd, featureidkey="properties.FIRST_IDDP",
                                       z=[1], colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
                                       marker_line_color="#111827", marker_line_width=4, hoverinfo="skip"))
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      coloraxis_colorbar=dict(title=barra, thickness=14, len=0.55, x=0.02, xanchor="left"))
    return fig


# ------------------------------------------------------------------ portada
nac = enaho.nacional()
deps = enaho.por("Departamento")
st.markdown(f"""
<div class="hero">
  <h1>📊 Cifra Oficial</h1>
  <p>Cifras oficiales del Perú —BCRP e INEI— con gráfico y <b>fuente citada</b>, en segundos.
  Para periodistas, analistas y equipos públicos que no pueden publicar un número equivocado.</p>
  <span class="pill">🏦 ~17 mil series del BCRP en vivo</span><span class="pill">🗺️ Pobreza ENAHO 2024 validada</span>
  <span class="pill">🤖 Conectable a asistentes de IA (MCP)</span>
</div>""", unsafe_allow_html=True)

# Pregunta rápida
pregunta = st.text_input("💬 Pregunta una cifra", placeholder="Ej.: pobreza en Puno · ¿cómo está el dólar? · inflación · tasa de referencia",
                         label_visibility="collapsed")
r = interpretar(pregunta) if pregunta else None
if r:
    if r["tipo"] == "departamento":
        dep = enaho.departamento(r["valor"])
        rank = int((deps.pobreza_pct > dep["pobreza_pct"]).sum()) + 1
        st.markdown(f"""<div class="answer"><div class="lbl">Pobreza monetaria en {r['valor']}, 2024</div>
            <div class="big">{dep['pobreza_pct']:.1f} %</div>
            {rank}.º de 25 departamentos · Perú: {nac:.1f} % ({dep['pobreza_pct'] - nac:+.1f} pp)<br>
            <small>Fuente: {enaho.FUENTE}</small></div>""", unsafe_allow_html=True)
        st.session_state["dep"] = r["valor"]
    elif r["tipo"] in ("nacional", "area"):
        a = enaho.por("Área").set_index("grupo").pobreza_pct
        st.markdown(f"""<div class="answer"><div class="lbl">Pobreza monetaria en el Perú, 2024</div>
            <div class="big">{nac:.1f} %</div>Rural {a['Rural']:.1f} % · Urbana {a['Urbana']:.1f} % (brecha
            {a['Rural'] - a['Urbana']:.1f} pp)<br><small>Fuente: {enaho.FUENTE}</small></div>""", unsafe_allow_html=True)
    elif r["tipo"] == "serie":
        info = INDICADORES[r["valor"]]
        try:
            fr = ficha(r["valor"])["frecuencia"]
            res, ser = datos(r["valor"], *rango(fr, "1A"))
            u = res["ultimo"]
            c1, c2 = st.columns([2, 3])
            c1.markdown(f"""<div class="answer"><div class="lbl">{info['emoji']} {info['titulo']}</div>
                <div class="big">{n(u['valor'])}</div>{info['unidad']} · {u['periodo']}<br>
                <small>BCRP, serie {r['valor']}</small></div>""", unsafe_allow_html=True)
            spark = px.area(pd.DataFrame(ser["datos"]), x="periodo", y="valor", height=150)
            spark.update_traces(line_color=VERDE, fillcolor="rgba(15,118,110,.12)")
            spark.update_layout(margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None, yaxis_title=None,
                                plot_bgcolor="white", yaxis=dict(gridcolor="#eef0f3"))
            c2.plotly_chart(spark, width="stretch", config={"displayModeBar": False})
        except Exception as e:
            st.error(f"No pude consultar el BCRP: {e}")
    else:
        st.info(f"Busca «{r['valor']}» en la pestaña **Series del BCRP** para ver todas las coincidencias.")

tab_bcrp, tab_mapa, tab_ia = st.tabs(["📈 Series del BCRP", "🗺️ Mapa de pobreza", "🤖 Para asistentes de IA"])

# ------------------------------------------------------------------ BCRP
with tab_bcrp:
    st.markdown("##### Indicadores frecuentes")
    cols = st.columns(len(INDICADORES))
    for col, (cod, info) in zip(cols, INDICADORES.items()):
        if col.button(f"{info['emoji']} {info['corto']}", help=info["titulo"], key=f"b_{cod}", width="stretch"):
            st.session_state["serie"] = cod
            st.session_state["busqueda"] = ""
    texto = st.text_input("…o busca cualquier serie del BCRP", key="busqueda",
                          placeholder="Ej.: exportaciones tradicionales, crédito al sector privado, oro precio")
    if texto.strip():
        try:
            res_busqueda = buscar(texto.strip())
        except Exception as e:
            res_busqueda = []
            st.error(f"No pude leer el catálogo del BCRP: {e}")
        if res_busqueda:
            opciones = {f"{x['nombre']} · {x['frecuencia']} · {x['codigo']}": x["codigo"] for x in res_busqueda}
            st.session_state["serie"] = opciones[st.selectbox("Resultados", list(opciones))]
        else:
            st.warning("Sin resultados. Prueba con menos palabras.")
    codigo = st.session_state.get("serie", "PN01273PM")

    try:
        f = ficha(codigo)
        info = INDICADORES.get(codigo, {"titulo": f["nombre"], "unidad": "", "emoji": "📊"})
        c1, c2, c3 = st.columns([2, 1.2, 1.4])
        preset = c1.segmented_control("Periodo", ["1A", "3A", "5A", "10A"], default="3A") or "3A"
        movil = c2.toggle("Promedio móvil", value=False)
        otras = {"—": None} | {v["titulo"]: k for k, v in INDICADORES.items() if k != codigo}
        comp_cod = otras[c3.selectbox("Comparar con", list(otras))]
        desde, hasta = rango(f["frecuencia"], preset)
        with st.spinner("Consultando la API del BCRP…"):
            res, ser = datos(codigo, desde, hasta)
        df = pd.DataFrame(ser["datos"])
        u, p0 = res["ultimo"], res["primero"]
        st.markdown(f"### {info['emoji']} {f['nombre']}")
        st.caption(f"Serie {codigo} · {f['frecuencia']} · {df.periodo.iloc[0]} a {df.periodo.iloc[-1]} · Fuente: BCRP")
        k = st.columns(4)
        k[0].markdown(card(f"Último · {u['periodo']}", n(u["valor"]), info["unidad"]), unsafe_allow_html=True)
        flecha, clase = ("▲", "up") if res["cambio"] > 0 else ("▼", "down")
        k[1].markdown(card("Cambio en el periodo", f"{flecha} {n(abs(res['cambio']))}", f"desde {p0['periodo']} ({n(p0['valor'])})",
                           clase), unsafe_allow_html=True)
        k[2].markdown(card("Promedio", n(res["promedio"]), f"{res['n_periodos']} datos"), unsafe_allow_html=True)
        k[3].markdown(card("Rango", f"{n(res['minimo']['valor'])} – {n(res['maximo']['valor'])}",
                           f"mín {res['minimo']['periodo']} · máx {res['maximo']['periodo']}"), unsafe_allow_html=True)
        comparar = None
        if comp_cod:
            _, ser2 = datos(comp_cod, *rango(ficha(comp_cod)["frecuencia"], preset))
            comparar = (pd.DataFrame(ser2["datos"]), INDICADORES[comp_cod]["titulo"])
        st.plotly_chart(grafico_serie(df, info["titulo"], info["unidad"], movil, comparar), width="stretch")
        cita = (f"Según el BCRP (serie {codigo}), «{f['nombre']}» fue {n(u['valor'])} en {u['periodo']}; "
                f"el promedio entre {df.periodo.iloc[0]} y {df.periodo.iloc[-1]} fue {n(res['promedio'])}. Fuente: {res['fuente']}")
        c1, c2 = st.columns([4, 1])
        c1.markdown("**Cítalo así**")
        c1.code(cita, language=None, wrap_lines=True)
        c2.markdown("&nbsp;")
        c2.download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8"), f"{codigo}_{desde}_{hasta}.csv",
                           "text/csv", width="stretch")
    except Exception as e:
        st.error(f"No pude consultar la serie {codigo}: {e}")

# ------------------------------------------------------------------ MAPA
with tab_mapa:
    if "dep" not in st.session_state:
        st.session_state["dep"] = deps.sort_values("pobreza_pct").iloc[-1].grupo
    area = enaho.por("Área").set_index("grupo").pobreza_pct
    k = st.columns(4)
    top, low = deps.sort_values("pobreza_pct").iloc[-1], deps.sort_values("pobreza_pct").iloc[0]
    k[0].markdown(card("Pobreza Perú 2024", f"{nac:.1f} %", "Oficial INEI: 27.6 %"), unsafe_allow_html=True)
    k[1].markdown(card("Más pobre", top.grupo, f"{top.pobreza_pct:.1f} %", "up"), unsafe_allow_html=True)
    k[2].markdown(card("Menos pobre", low.grupo, f"{low.pobreza_pct:.1f} %", "down"), unsafe_allow_html=True)
    k[3].markdown(card("Brecha rural – urbana", f"{area['Rural'] - area['Urbana']:.1f} pp",
                       f"Rural {area['Rural']:.1f} % · Urbana {area['Urbana']:.1f} %"), unsafe_allow_html=True)
    st.write("")
    vista = st.segmented_control("Vista del mapa", ["Interactivo", "Con capas (Folium)"], default="Interactivo") or "Interactivo"

    if vista == "Interactivo":
        izq, der = st.columns([1.35, 1])
        with izq:
            modo = st.radio("Colorear por", ["Nivel de pobreza", "Diferencia con el promedio nacional"],
                            horizontal=True, label_visibility="collapsed")
            st.caption("👆 Haz clic en un departamento para ver su ficha.")
            ev = st.plotly_chart(mapa_plotly(deps, modo, st.session_state["dep"]), width="stretch",
                                 on_select="rerun", selection_mode="points", key="mapa",
                                 config={"displayModeBar": False, "scrollZoom": False})
            puntos = (ev or {}).get("selection", {}).get("points", []) if isinstance(ev, dict) else \
                getattr(getattr(ev, "selection", None), "points", [])
            if puntos:
                cod = str(puntos[0].get("location", "")).zfill(2)
                nuevo = enaho.NOMBRES.get(cod)
                if nuevo and nuevo != st.session_state["dep"]:
                    st.session_state["dep"] = nuevo
                    st.rerun()
        with der:
            nombres = list(enaho.NOMBRES.values())
            elegido = st.selectbox("Departamento", nombres, index=nombres.index(st.session_state["dep"]))
            if elegido != st.session_state["dep"]:
                st.session_state["dep"] = elegido
                st.rerun()
            dep = enaho.departamento(elegido)
            rank = int((deps.pobreza_pct > dep["pobreza_pct"]).sum()) + 1
            dif = dep["pobreza_pct"] - nac
            gauge = go.Figure(go.Indicator(mode="gauge+number+delta", value=dep["pobreza_pct"],
                              number={"suffix": " %", "font": {"size": 34}},
                              delta={"reference": nac, "suffix": " pp", "increasing": {"color": "#b91c1c"},
                                     "decreasing": {"color": "#15803d"}},
                              gauge={"axis": {"range": [0, 50]}, "bar": {"color": "#c2410c"},
                                     "steps": [{"range": [0, nac], "color": "#f1f5f9"}],
                                     "threshold": {"line": {"color": "#111827", "width": 3}, "value": nac}},
                              title={"font": {"size": 22}, "text": f"<b>{elegido}</b><br><span style='font-size:13px;color:#6b7280'>"
                                             f"{rank}.º de 25 · línea negra = Perú {nac:.1f} %</span>"}))
            gauge.update_layout(height=290, margin=dict(l=30, r=30, t=80, b=10), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(gauge, width="stretch", config={"displayModeBar": False})
            orden = deps.sort_values("pobreza_pct")
            colores = [NARANJA if g == elegido else "#cbd5e1" for g in orden.grupo]
            barras = go.Figure(go.Bar(x=orden.pobreza_pct, y=orden.grupo, orientation="h", marker_color=colores,
                                      text=[f"{v:.1f}" if g == elegido else "" for v, g in zip(orden.pobreza_pct, orden.grupo)],
                                      textposition="outside", hovertemplate="%{y}: %{x:.1f} %<extra></extra>"))
            barras.add_vline(x=nac, line_dash="dash", line_color=GRIS)
            barras.update_layout(height=330, margin=dict(l=0, r=10, t=0, b=0), plot_bgcolor="white",
                                 xaxis=dict(range=[0, 52], gridcolor="#eef0f3"), yaxis=dict(tickfont=dict(size=9)))
            st.plotly_chart(barras, width="stretch", config={"displayModeBar": False})
            cita = (f"Según la ENAHO 2024 del INEI, el {dep['pobreza_pct']:.1f} % de la población de {elegido} estaba en "
                    f"pobreza monetaria ({rank}.º de 25 departamentos; Perú: {nac:.1f} %). Fuente: {enaho.FUENTE}")
            st.code(cita, language=None, wrap_lines=True)
    else:
        st.caption("Mapa con capas: activa o desactiva la pobreza y los límites desde el control de la esquina.")
        geo = geojson()
        valores = deps.set_index("ccdd").pobreza_pct.to_dict()
        for ft in geo["features"]:
            cod = str(ft["properties"]["FIRST_IDDP"]).zfill(2)
            ft["properties"]["pobreza"] = f"{valores.get(cod, float('nan')):.1f} %"
            ft["properties"]["nombre"] = enaho.NOMBRES.get(cod, cod)
        m = folium.Map(location=[-9.2, -75], zoom_start=5, tiles="OpenStreetMap")
        folium.Choropleth(geo_data=geo, data=deps, columns=["ccdd", "pobreza_pct"], key_on="feature.properties.FIRST_IDDP",
                          fill_color="YlOrRd", fill_opacity=0.75, line_opacity=0.4, bins=[0, 10, 20, 30, 40, 50],
                          legend_name="% de personas en pobreza monetaria, 2024", name="Pobreza 2024").add_to(m)
        folium.GeoJson(geo, name="Límites y datos", style_function=lambda _: {"fillOpacity": 0, "weight": 0.6, "color": "#334155"},
                       highlight_function=lambda _: {"weight": 3, "color": "#111827"},
                       tooltip=folium.GeoJsonTooltip(["nombre", "pobreza"], aliases=["Departamento", "Pobreza"])).add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)
        st_folium(m, height=600, use_container_width=True, returned_objects=[])

    st.markdown("##### ¿Quiénes son más pobres?")
    g = st.columns(3)
    for col, nivel, titulo in zip(g, ["Área", "Sexo", "Edad"], ["Por área", "Por sexo", "Por edad"]):
        d = enaho.por(nivel)
        fig = px.bar(d, x="grupo", y="pobreza_pct", text=d.pobreza_pct.map(lambda v: f"{v:.1f} %"),
                     color="pobreza_pct", color_continuous_scale=ESCALA, range_color=(0, 50), title=titulo)
        fig.add_hline(y=nac, line_dash="dash", line_color=GRIS)
        fig.update_layout(height=290, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor="white", coloraxis_showscale=False,
                          xaxis_title=None, yaxis=dict(title="%", range=[0, 45], gridcolor="#eef0f3"))
        col.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(f"Fuente: {enaho.FUENTE} Validación propia: 108,664 residentes; 27.53 % nacional (oficial 27.6 %); "
               "25 departamentos a ±0.5 pp de la referencia del curso.")

# ------------------------------------------------------------------ IA
with tab_ia:
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.markdown("### Los asistentes de IA no saben (o inventan) cifras recientes.")
        st.markdown("Cifra Oficial también es un **servidor MCP**: cualquier asistente compatible, como Claude Code, "
                    "busca la serie oficial y calcula con Python, citando código, periodo y fuente.")
        st.code('{\n  "mcpServers": {\n    "cifra-oficial": {\n      "type": "stdio",\n      "command": "uv",\n'
                '      "args": ["run", "mcp/server.py"]\n    }\n  }\n}', language="json")
        st.caption("Herramientas: buscar_series · serie · resumen · pobreza_departamento")
    with c2:
        ev = pd.DataFrame({"Asistente": ["Sin Cifra Oficial", "Con Cifra Oficial"], "Correctas": [1, 10], "Sin respuesta": [9, 0]})
        fig = go.Figure([go.Bar(name="Correctas", x=ev.Asistente, y=ev.Correctas, marker_color=VERDE, text=ev.Correctas),
                         go.Bar(name="«No sé»", x=ev.Asistente, y=ev["Sin respuesta"], marker_color="#cbd5e1",
                                text=ev["Sin respuesta"])])
        fig.update_layout(barmode="stack", height=360, title="10 preguntas oficiales (BCRP + ENAHO), Claude Haiku",
                          plot_bgcolor="white", yaxis=dict(range=[0, 10.5], gridcolor="#eef0f3"),
                          margin=dict(l=0, r=0, t=50, b=0), legend=dict(orientation="h", y=-0.12))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption("Experimento propio (Tarea 4): mismas preguntas en sesiones independientes; tiempo promedio 8.2 s sin y 25.2 s con.")
