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
VERDE, AZUL, NARANJA, GRIS, ROJO = "#0f766e", "#1d4ed8", "#ea580c", "#6b7280", "#b91c1c"
ESCALA = ["#fef3c7", "#fdba74", "#f97316", "#c2410c", "#7c2d12"]
IPC_MENSUAL = "PN01271PM"     # IPC Lima Metropolitana, variación % mensual (validada en la Tarea 4: marzo 2025 = 0.81)
CONFIG = {"displaylogo": False, "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "cifra_oficial"},
          "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
SIN_BARRA = {"displayModeBar": False}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html, body, [class*="css"], .stMarkdown { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.2rem; max-width: 1280px; }
.hero { background: linear-gradient(120deg, #0f766e 0%, #155e75 55%, #1e3a8a 100%); color: #fff;
        border-radius: 22px; padding: 28px 34px 24px; margin-bottom: 16px; position: relative; overflow: hidden; }
.hero:after { content: ""; position: absolute; right: -60px; top: -60px; width: 260px; height: 260px;
              border-radius: 50%; background: rgba(255,255,255,.08); }
.hero h1 { font-size: 2.4rem; font-weight: 800; margin: 0; color: #fff; letter-spacing: -0.5px; }
.hero p { font-size: 1.05rem; margin: 6px 0 0; opacity: .92; max-width: 780px; }
.pill { display: inline-block; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.25);
        padding: 3px 11px; border-radius: 999px; font-size: .78rem; margin: 12px 6px 0 0; }
.card { background: #fff; border-radius: 16px; padding: 14px 18px; box-shadow: 0 2px 10px rgba(15,23,42,.06);
        border: 1px solid #eef0f3; height: 100%; }
.card .lbl { color: #6b7280; font-size: .78rem; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; }
.card .val { font-size: 1.75rem; font-weight: 800; color: #111827; line-height: 1.15; margin-top: 4px; }
.card .sub { color: #6b7280; font-size: .84rem; margin-top: 2px; }
.up { color: #b91c1c !important; } .down { color: #15803d !important; }
.answer { background: #ecfdf5; border-left: 6px solid #0f766e; border-radius: 14px; padding: 16px 20px; margin: 6px 0 4px; }
.answer .big { font-size: 2.2rem; font-weight: 800; color: #065f46; }
.calc { background: linear-gradient(120deg, #fff7ed, #ffedd5); border-radius: 18px; padding: 20px 24px; border: 1px solid #fed7aa; }
.calc .big { font-size: 2.6rem; font-weight: 800; color: #9a3412; }
.insight { background: #eff6ff; border-left: 6px solid #1d4ed8; border-radius: 12px; padding: 12px 16px; color: #1e3a8a; }
div[data-testid="stTabs"] button p { font-size: 1.0rem; font-weight: 600; }
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


def millones(x):
    return f"{x / 1e6:,.2f} M" if x >= 1e6 else f"{x / 1e3:,.0f} mil"


def fechas(periodos):
    """Convierte los periodos a fechas para el eje (si es trimestral se quedan como texto)."""
    f = pd.to_datetime(periodos, errors="coerce", format="mixed")
    return periodos if f.isna().any() else f


def grafico_serie(df, titulo, unidad, media_movil=False, comparar=None):
    x = fechas(df.periodo)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=df.valor, mode="lines", name=titulo, line=dict(color=VERDE, width=3),
                             fill="tozeroy" if comparar is None else None, fillcolor="rgba(15,118,110,.10)",
                             customdata=df.periodo, hovertemplate="%{customdata}<br><b>%{y:,.2f}</b> " + unidad + "<extra></extra>"))
    if media_movil and len(df) >= 6:
        fig.add_trace(go.Scatter(x=x, y=df.valor.rolling(3).mean(), mode="lines", name="Promedio móvil (3)",
                                 line=dict(color=NARANJA, width=2, dash="dot")))
    imax, imin = df.valor.idxmax(), df.valor.idxmin()
    for i, txt, col in [(imax, "máx", ROJO), (imin, "mín", "#15803d")]:
        fig.add_annotation(x=x[i], y=df.valor[i], text=f"{txt} {df.valor[i]:,.2f}", showarrow=True, arrowhead=2, ax=0,
                           ay=-30 if txt == "máx" else 30, font=dict(color=col, size=12), bgcolor="white", bordercolor=col)
    fig.add_trace(go.Scatter(x=[x[len(df) - 1]], y=[df.valor.iloc[-1]], mode="markers+text",
                             marker=dict(size=11, color=VERDE, line=dict(color="white", width=2)),
                             text=[f"  {df.valor.iloc[-1]:,.2f}"], textposition="middle right", showlegend=False,
                             hoverinfo="skip"))
    if comparar is not None:
        d2, t2 = comparar
        fig.add_trace(go.Scatter(x=fechas(d2.periodo), y=d2.valor, mode="lines", name=t2, yaxis="y2",
                                 line=dict(color=AZUL, width=2.5)))
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, title=t2))
    es_fecha = not isinstance(x, pd.Series) or pd.api.types.is_datetime64_any_dtype(x)
    fig.update_layout(height=470, margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified", plot_bgcolor="white",
                      legend=dict(orientation="h", y=1.1, x=0), yaxis=dict(gridcolor="#eef0f3", title=unidad),
                      xaxis=dict(showgrid=False, rangeslider=dict(visible=True, thickness=0.07)))
    if es_fecha:
        fig.update_xaxes(rangeselector=dict(buttons=[dict(count=6, label="6M", step="month", stepmode="backward"),
                                                     dict(count=1, label="1A", step="year", stepmode="backward"),
                                                     dict(step="all", label="Todo")], x=0.75, y=1.1))
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
    if not sel.empty:
        fig.add_trace(go.Choroplethmap(geojson=geojson(), locations=sel.ccdd, featureidkey="properties.FIRST_IDDP",
                                       z=[1], colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
                                       marker_line_color="#111827", marker_line_width=4, hoverinfo="skip"))
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      coloraxis_colorbar=dict(title=barra, thickness=14, len=0.55, x=0.02, xanchor="left"))
    return fig


def aviso_detalle():
    st.info("Esta vista usa `data/enaho_2024_detalle.csv`, que se genera una vez con `scripts/agregar_enaho.py` "
            "sobre la base validada de la ENAHO (ver README).")


# ------------------------------------------------------------------ portada
nac = enaho.nacional()
deps = enaho.por("Departamento")
st.markdown("""
<div class="hero">
  <h1>📊 Cifra Oficial</h1>
  <p>Cifras oficiales del Perú —BCRP e INEI— con gráfico y <b>fuente citada</b>, en segundos.
  Para periodistas, analistas y equipos públicos que no pueden publicar un número equivocado.</p>
  <span class="pill">🏦 ~17 mil series del BCRP en vivo</span><span class="pill">🗺️ Pobreza ENAHO 2024 validada</span>
  <span class="pill">🧮 Calculadora de inflación</span><span class="pill">🤖 Conectable a asistentes de IA (MCP)</span>
</div>""", unsafe_allow_html=True)

pregunta = st.text_input("💬 Pregunta una cifra", label_visibility="collapsed",
                         placeholder="Ej.: pobreza en Puno · ¿cómo está el dólar? · inflación · tasa de referencia")
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
            res, ser = datos(r["valor"], *rango(ficha(r["valor"])["frecuencia"], "1A"))
            u = res["ultimo"]
            c1, c2 = st.columns([2, 3])
            c1.markdown(f"""<div class="answer"><div class="lbl">{info['emoji']} {info['titulo']}</div>
                <div class="big">{n(u['valor'])}</div>{info['unidad']} · {u['periodo']}<br>
                <small>BCRP, serie {r['valor']}</small></div>""", unsafe_allow_html=True)
            spark = px.area(pd.DataFrame(ser["datos"]), x="periodo", y="valor", height=150)
            spark.update_traces(line_color=VERDE, fillcolor="rgba(15,118,110,.12)")
            spark.update_layout(margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None, yaxis_title=None,
                                plot_bgcolor="white", yaxis=dict(gridcolor="#eef0f3"))
            c2.plotly_chart(spark, width="stretch", config=SIN_BARRA)
        except Exception as e:
            st.error(f"No pude consultar el BCRP: {e}")
    else:
        st.info(f"Busca «{r['valor']}» en la pestaña **Series del BCRP** para ver todas las coincidencias.")

tab_bcrp, tab_calc, tab_mapa, tab_comp, tab_ia = st.tabs(
    ["📈 Series del BCRP", "🧮 Calculadora de inflación", "🗺️ Mapa de pobreza", "⚖️ Comparar departamentos",
     "🤖 Para asistentes de IA"])

# ------------------------------------------------------------------ BCRP
with tab_bcrp:
    st.markdown("##### 🇵🇪 Perú hoy · haz clic en un indicador para abrirlo")
    filas = [list(INDICADORES.items())[:3], list(INDICADORES.items())[3:]]
    for fila in filas:
        cols = st.columns(3)
        for col, (cod, info) in zip(cols, fila):
            with col.container(border=True):
                try:
                    res_k, ser_k = datos(cod, *rango(ficha(cod)["frecuencia"], "1A"))
                    dk = pd.DataFrame(ser_k["datos"])
                    sube = res_k["cambio"] > 0
                    a, b = st.columns([1.1, 1])
                    a.markdown(f"**{info['emoji']} {info['corto']}**<br><span style='font-size:1.6rem;font-weight:800'>"
                               f"{n(res_k['ultimo']['valor'])}</span><br><span style='color:#6b7280;font-size:.8rem'>"
                               f"{info['unidad']} · {res_k['ultimo']['periodo']}</span><br>"
                               f"<span class='{'up' if sube else 'down'}' style='font-size:.85rem;font-weight:600'>"
                               f"{'▲' if sube else '▼'} {n(abs(res_k['cambio']))} en 12 meses</span>",
                               unsafe_allow_html=True)
                    sp = go.Figure(go.Scatter(x=dk.periodo, y=dk.valor, mode="lines", fill="tozeroy",
                                              line=dict(color=ROJO if sube else "#15803d", width=2),
                                              fillcolor="rgba(185,28,28,.08)" if sube else "rgba(21,128,61,.08)",
                                              hovertemplate="%{x}: %{y:,.2f}<extra></extra>"))
                    sp.update_layout(height=95, margin=dict(l=0, r=0, t=4, b=0), xaxis=dict(visible=False),
                                     yaxis=dict(visible=False, range=[dk.valor.min() * 0.98, dk.valor.max() * 1.02]),
                                     plot_bgcolor="white", paper_bgcolor="white")
                    b.plotly_chart(sp, width="stretch", config=SIN_BARRA, key=f"sp_{cod}")
                except Exception:
                    st.markdown(f"**{info['emoji']} {info['corto']}**<br>Sin respuesta del BCRP", unsafe_allow_html=True)
                if st.button("Abrir serie ›", key=f"b_{cod}", width="stretch"):
                    st.session_state["serie"] = cod
                    st.session_state["busqueda"] = ""
    texto = st.text_input("🔎 …o busca cualquier serie del BCRP", key="busqueda",
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
        st.divider()
        st.markdown(f"### {info['emoji']} {f['nombre']}")
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
        st.caption(f"Serie {codigo} · {f['frecuencia']} · {df.periodo.iloc[0]} a {df.periodo.iloc[-1]} · Fuente: BCRP")
        k = st.columns(4)
        k[0].markdown(card(f"Último · {u['periodo']}", n(u["valor"]), info["unidad"]), unsafe_allow_html=True)
        flecha, clase = ("▲", "up") if res["cambio"] > 0 else ("▼", "down")
        k[1].markdown(card("Cambio en el periodo", f"{flecha} {n(abs(res['cambio']))}",
                           f"desde {p0['periodo']} ({n(p0['valor'])})", clase), unsafe_allow_html=True)
        k[2].markdown(card("Promedio", n(res["promedio"]), f"{res['n_periodos']} datos"), unsafe_allow_html=True)
        k[3].markdown(card("Rango", f"{n(res['minimo']['valor'])} – {n(res['maximo']['valor'])}",
                           f"mín {res['minimo']['periodo']} · máx {res['maximo']['periodo']}"), unsafe_allow_html=True)
        comparar = None
        if comp_cod:
            _, ser2 = datos(comp_cod, *rango(ficha(comp_cod)["frecuencia"], preset))
            comparar = (pd.DataFrame(ser2["datos"]), INDICADORES[comp_cod]["titulo"])
        st.plotly_chart(grafico_serie(df, info["titulo"], info["unidad"], movil, comparar), width="stretch", config=CONFIG)
        st.caption("Arrastra la barra inferior para hacer zoom · 📷 en la esquina del gráfico para descargarlo en PNG")
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

# ------------------------------------------------------------------ CALCULADORA
with tab_calc:
    st.markdown("### 🧮 ¿Cuánto vale hoy tu dinero de antes?")
    st.caption("Con la variación mensual oficial del IPC de Lima Metropolitana (BCRP, serie PN01271PM).")
    hoy = date.today()
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"]
    c = st.columns([1.2, 1, 1, 1, 1])
    monto = c[0].number_input("Monto (S/)", min_value=1.0, value=100.0, step=10.0)
    a0 = c[1].selectbox("Desde (año)", list(range(hoy.year, 1999, -1)), index=min(6, hoy.year - 2000))
    m0 = c[2].selectbox("Desde (mes)", meses, index=0)
    a1 = c[3].selectbox("Hasta (año)", list(range(hoy.year, 1999, -1)), index=0)
    m1 = c[4].selectbox("Hasta (mes)", meses, index=hoy.month - 1)
    i0, i1 = a0 * 12 + meses.index(m0), a1 * 12 + meses.index(m1)
    if i1 <= i0:
        st.warning("La fecha final debe ser posterior a la inicial.")
    else:
        sig = i0 + 1   # la inflación se acumula desde el mes siguiente al inicial
        try:
            with st.spinner("Calculando con datos del BCRP…"):
                _, s_ipc = datos(IPC_MENSUAL, f"{sig // 12}-{sig % 12 + 1:02d}", f"{a1}-{meses.index(m1) + 1:02d}")
            d = pd.DataFrame(s_ipc["datos"])
            if d.empty:
                st.error("El BCRP no tiene datos para ese periodo.")
            else:
                d["factor"] = (1 + d.valor / 100).cumprod()
                d["equivale"] = monto * d.factor
                final, acum = d.equivale.iloc[-1], (d.factor.iloc[-1] - 1) * 100
                fin_real = d.periodo.iloc[-1]
                st.markdown(f"""<div class="calc"><div class="lbl">S/ {n(monto)} de {m0}-{a0} equivalen a</div>
                    <div class="big">S/ {n(final)}</div>en {fin_real} · inflación acumulada <b>{acum:.1f} %</b> ·
                    S/ {n(monto)} de hoy compran lo que S/ {n(monto / d.factor.iloc[-1])} en {m0}-{a0}</div>""",
                            unsafe_allow_html=True)
                if fin_real != f"{a1}-{meses.index(m1) + 1:02d}":
                    st.caption(f"El último dato publicado por el BCRP es de {fin_real}.")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=fechas(d.periodo), y=d.equivale, mode="lines+markers" if len(d) <= 24 else "lines",
                                         line=dict(color=NARANJA, width=3),
                                         customdata=d.periodo, name="Equivalente",
                                         hovertemplate="%{customdata}: <b>S/ %{y:,.2f}</b><extra></extra>"))
                fig.add_hline(y=monto, line_dash="dash", line_color=GRIS, annotation_text=f"S/ {n(monto)} iniciales")
                anual = d.assign(anio=d.periodo.str[:4]).groupby("anio").valor.apply(lambda v: ((1 + v / 100).prod() - 1) * 100)
                fig.update_layout(height=380, plot_bgcolor="white", margin=dict(l=0, r=0, t=10, b=0),
                                  yaxis=dict(title="Soles equivalentes", gridcolor="#eef0f3"), hovermode="x unified")
                c1, c2 = st.columns([1.6, 1])
                c1.plotly_chart(fig, width="stretch", config=CONFIG)
                barras = px.bar(x=anual.index, y=anual.values, text=[f"{v:.1f}%" for v in anual.values],
                                color=anual.values, color_continuous_scale=ESCALA, title="Inflación por año del periodo")
                barras.update_layout(height=380, plot_bgcolor="white", coloraxis_showscale=False, xaxis_title=None,
                                     yaxis_title="%", margin=dict(l=0, r=0, t=40, b=0))
                c2.plotly_chart(barras, width="stretch", config=SIN_BARRA)
                st.code(f"Según el IPC de Lima Metropolitana del BCRP (serie {IPC_MENSUAL}), S/ {n(monto)} de {m0}-{a0} "
                        f"equivalen a S/ {n(final)} en {fin_real} (inflación acumulada de {acum:.1f} %). "
                        f"Fuente: {s_ipc['fuente']}", language=None, wrap_lines=True)
        except Exception as e:
            st.error(f"No pude consultar el IPC del BCRP: {e}")

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
    vista = st.segmented_control("Vista", ["📍 Interactivo", "👥 ¿Dónde viven los pobres?", "🗂️ Con capas (Folium)"],
                                 default="📍 Interactivo") or "📍 Interactivo"

    if vista == "📍 Interactivo":
        izq, der = st.columns([1.3, 1])
        with izq:
            modo = st.radio("Colorear por", ["Nivel de pobreza", "Diferencia con el promedio nacional"],
                            horizontal=True, label_visibility="collapsed")
            st.caption("👆 Haz clic en un departamento para ver su ficha.")
            ev = st.plotly_chart(mapa_plotly(deps, modo, st.session_state["dep"]), width="stretch",
                                 on_select="rerun", selection_mode="points", key="mapa",
                                 config={"displayModeBar": False, "scrollZoom": False})
            puntos = getattr(getattr(ev, "selection", None), "points", None) or \
                (ev.get("selection", {}).get("points", []) if isinstance(ev, dict) else [])
            if puntos:
                nuevo = enaho.NOMBRES.get(str(puntos[0].get("location", "")).zfill(2))
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
            t_res, t_grupos = st.tabs(["Resumen", "Por grupos"])
            with t_res:
                gauge = go.Figure(go.Indicator(
                    mode="gauge+number+delta", value=dep["pobreza_pct"], number={"suffix": " %", "font": {"size": 34}},
                    delta={"reference": nac, "suffix": " pp", "increasing": {"color": ROJO}, "decreasing": {"color": "#15803d"}},
                    gauge={"axis": {"range": [0, 50]}, "bar": {"color": "#c2410c"}, "steps": [{"range": [0, nac], "color": "#f1f5f9"}],
                           "threshold": {"line": {"color": "#111827", "width": 3}, "value": nac}},
                    title={"font": {"size": 22}, "text": f"<b>{elegido}</b><br><span style='font-size:13px;color:#6b7280'>"
                                                         f"{rank}.º de 25 · línea negra = Perú {nac:.1f} %</span>"}))
                gauge.update_layout(height=280, margin=dict(l=30, r=30, t=80, b=10), paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(gauge, width="stretch", config=SIN_BARRA)
                if enaho.hay_detalle():
                    fd, _ = enaho.ficha_departamento(elegido)
                    t = fd[fd.corte == "Total"].iloc[0]
                    m = st.columns(3)
                    m[0].markdown(card("Pobreza extrema", f"{t.pobreza_extrema_pct:.1f} %"), unsafe_allow_html=True)
                    m[1].markdown(card("Personas pobres", millones(t.pobres)), unsafe_allow_html=True)
                    m[2].markdown(card("Población", millones(t.poblacion)), unsafe_allow_html=True)
                orden = deps.sort_values("pobreza_pct")
                barras = go.Figure(go.Bar(x=orden.pobreza_pct, y=orden.grupo, orientation="h",
                                          marker_color=[NARANJA if g == elegido else "#cbd5e1" for g in orden.grupo],
                                          hovertemplate="%{y}: %{x:.1f} %<extra></extra>"))
                barras.add_vline(x=nac, line_dash="dash", line_color=GRIS)
                barras.update_layout(height=320, margin=dict(l=0, r=10, t=10, b=0), plot_bgcolor="white",
                                     xaxis=dict(range=[0, 52], gridcolor="#eef0f3"), yaxis=dict(tickfont=dict(size=9)))
                st.plotly_chart(barras, width="stretch", config=SIN_BARRA)
            with t_grupos:
                if not enaho.hay_detalle():
                    aviso_detalle()
                else:
                    fd, fp = enaho.ficha_departamento(elegido)
                    for corte in ["Área", "Sexo", "Edad"]:
                        dd = pd.concat([fd[fd.corte == corte].assign(ambito=elegido), fp[fp.corte == corte].assign(ambito="Perú")])
                        fig = px.bar(dd, x="grupo", y="pobreza_pct", color="ambito", barmode="group", text_auto=".1f",
                                     color_discrete_map={elegido: NARANJA, "Perú": "#94a3b8"}, title=f"Por {corte.lower()}",
                                     custom_data=["n_muestra"])
                        fig.update_traces(hovertemplate="%{x}: %{y:.1f} %<br>encuestados: %{customdata[0]:,}<extra></extra>")
                        fig.update_layout(height=230, margin=dict(l=0, r=0, t=35, b=0), plot_bgcolor="white", legend_title=None,
                                          xaxis_title=None, yaxis=dict(title="%", gridcolor="#eef0f3"),
                                          legend=dict(orientation="h", y=1.15, x=0.5))
                        st.plotly_chart(fig, width="stretch", config=SIN_BARRA)
                    if (fd.n_muestra < 100).any():
                        st.caption("⚠️ Algunos grupos tienen menos de 100 encuestados: la cifra es poco precisa.")
            cita = (f"Según la ENAHO 2024 del INEI, el {dep['pobreza_pct']:.1f} % de la población de {elegido} estaba en "
                    f"pobreza monetaria ({rank}.º de 25 departamentos; Perú: {nac:.1f} %). Fuente: {enaho.FUENTE}")
            st.code(cita, language=None, wrap_lines=True)

    elif vista == "👥 ¿Dónde viven los pobres?":
        if not enaho.hay_detalle():
            aviso_detalle()
        else:
            tot = enaho.detalle().query("corte == 'Total' and ccdd != '00'").copy()
            total_pobres = tot.pobres.sum()
            tot["participacion"] = tot.pobres / total_pobres * 100
            cen = enaho.centroides()
            tot["lat"] = tot.ccdd.map(lambda c: cen[c][0])
            tot["lon"] = tot.ccdd.map(lambda c: cen[c][1])
            mayor = tot.sort_values("pobres").iloc[-1]
            st.markdown(f"""<div class="insight">💡 <b>Una tasa alta no es lo mismo que muchas personas.</b>
                {mayor.departamento} tiene una pobreza de {mayor.pobreza_pct:.1f} %, pero concentra
                <b>{mayor.participacion:.1f} %</b> de los {millones(total_pobres)} de personas pobres del país.</div>""",
                        unsafe_allow_html=True)
            c1, c2 = st.columns([1.1, 1])
            with c1:
                fig = px.choropleth_map(tot, geojson=geojson(), locations="ccdd", featureidkey="properties.FIRST_IDDP",
                                        color="pobreza_pct", color_continuous_scale=ESCALA, range_color=(0, 50), opacity=0.55,
                                        map_style="white-bg", center={"lat": -9.3, "lon": -75.0}, zoom=4.1)
                fig.update_traces(hoverinfo="skip", hovertemplate=None, marker_line_color="white")
                fig.add_trace(go.Scattermap(lat=tot.lat, lon=tot.lon, mode="markers",
                                            marker=dict(size=(tot.pobres / tot.pobres.max()) ** 0.5 * 60 + 6,
                                                        color="#1e3a8a", opacity=0.75),
                                            customdata=tot[["departamento", "pobres", "pobreza_pct", "participacion"]],
                                            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:,.0f} personas pobres"
                                                          "<br>%{customdata[3]:.1f} % del total del país<br>Tasa: %{customdata[2]:.1f} %"
                                                          "<extra></extra>"))
                fig.update_layout(height=620, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                                  coloraxis_colorbar=dict(title="% pobreza", thickness=12, len=0.5, x=0.02, xanchor="left"))
                st.plotly_chart(fig, width="stretch", config=SIN_BARRA)
                st.caption("Color = tasa de pobreza · tamaño del círculo = número de personas pobres")
            with c2:
                tm = px.treemap(tot, path=["departamento"], values="pobres", color="pobreza_pct",
                                color_continuous_scale=ESCALA, range_color=(0, 50), custom_data=["pobreza_pct", "participacion"])
                tm.update_traces(root_color="white", marker_line_color="white", marker_line_width=2, texttemplate="<b>%{label}</b><br>%{value:,.0f}<br>%{customdata[1]:.1f} %",
                                 hovertemplate="<b>%{label}</b><br>%{value:,.0f} personas pobres<br>Tasa %{customdata[0]:.1f} %"
                                               "<extra></extra>")
                tm.update_layout(height=620, margin=dict(l=0, r=0, t=30, b=0), coloraxis_showscale=False,
                                 title="Personas pobres por departamento (tamaño) y tasa (color)")
                st.plotly_chart(tm, width="stretch", config=CONFIG)
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

    st.markdown("##### ¿Quiénes son más pobres en el Perú?")
    g = st.columns(3)
    for col, nivel, titulo in zip(g, ["Área", "Sexo", "Edad"], ["Por área", "Por sexo", "Por edad"]):
        d = enaho.por(nivel)
        fig = px.bar(d, x="grupo", y="pobreza_pct", text=d.pobreza_pct.map(lambda v: f"{v:.1f} %"),
                     color="pobreza_pct", color_continuous_scale=ESCALA, range_color=(0, 50), title=titulo)
        fig.add_hline(y=nac, line_dash="dash", line_color=GRIS)
        fig.update_layout(height=290, margin=dict(l=0, r=0, t=40, b=0), plot_bgcolor="white", coloraxis_showscale=False,
                          xaxis_title=None, yaxis=dict(title="%", range=[0, 45], gridcolor="#eef0f3"))
        col.plotly_chart(fig, width="stretch", config=SIN_BARRA)
    st.caption(f"Fuente: {enaho.FUENTE} Validación propia: 108,664 residentes; 27.53 % nacional (oficial 27.6 %); "
               "25 departamentos a ±0.5 pp de la referencia del curso.")

# ------------------------------------------------------------------ COMPARAR
with tab_comp:
    st.markdown("### ⚖️ Compara departamentos")
    if not enaho.hay_detalle():
        aviso_detalle()
    else:
        det = enaho.detalle()
        nombres = list(enaho.NOMBRES.values())
        c1, c2, c3 = st.columns([2.2, 1, 1])
        elegidos = c1.multiselect("Departamentos (hasta 4)", nombres, default=["Cajamarca", "Lima", "Ica"], max_selections=4)
        corte = c2.segmented_control("Ver por", ["Área", "Sexo", "Edad"], default="Área") or "Área"
        medida = c3.radio("Indicador", ["Pobreza", "Pobreza extrema"], horizontal=True)
        col_m = "pobreza_pct" if medida == "Pobreza" else "pobreza_extrema_pct"
        if elegidos:
            sel = det[det.departamento.isin(elegidos + ["Perú"])]
            tot = sel[sel.corte == "Total"].set_index("departamento").loc[elegidos + ["Perú"]].reset_index()
            k = st.columns(len(tot))
            for col, (_, t) in zip(k, tot.iterrows()):
                col.markdown(card(t.departamento, f"{t[col_m]:.1f} %",
                                  f"{millones(t.pobres)} pobres · {millones(t.poblacion)} hab."), unsafe_allow_html=True)
            st.write("")
            paleta = dict(zip(elegidos, [NARANJA, AZUL, VERDE, "#9333ea"])) | {"Perú": "#94a3b8"}
            dd = sel[sel.corte == corte]
            fig = px.bar(dd, x="grupo", y=col_m, color="departamento", barmode="group", text_auto=".1f",
                         category_orders={"departamento": elegidos + ["Perú"]}, color_discrete_map=paleta,
                         custom_data=["departamento", "n_muestra"])
            fig.update_traces(hovertemplate="<b>%{customdata[0]}</b> · %{x}<br>%{y:.1f} %<br>encuestados: %{customdata[1]:,}<extra></extra>")
            fig.update_layout(height=420, plot_bgcolor="white", legend_title=None, xaxis_title=None,
                              yaxis=dict(title=f"% de personas ({medida.lower()})", gridcolor="#eef0f3"),
                              margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, width="stretch", config=CONFIG)
        st.markdown("##### Todos los departamentos: tasa de pobreza frente a número de pobres")
        todos = det.query("corte == 'Total' and ccdd != '00'")
        sc = px.scatter(todos, x="pobreza_pct", y="pobres", size="poblacion", color="pobreza_extrema_pct",
                        color_continuous_scale=ESCALA, hover_name="departamento", size_max=55, log_y=True,
                        text=todos.departamento.where(todos.departamento.isin(elegidos), ""),
                        labels={"pobreza_pct": "Tasa de pobreza (%)", "pobres": "Personas pobres (escala log)",
                                "pobreza_extrema_pct": "Extrema (%)", "poblacion": "Población"})
        sc.add_vline(x=nac, line_dash="dash", line_color=GRIS, annotation_text=f"Perú {nac:.1f} %")
        sc.update_traces(textposition="top center")
        sc.update_layout(height=470, plot_bgcolor="white", margin=dict(l=0, r=0, t=20, b=0),
                         yaxis=dict(gridcolor="#eef0f3"), xaxis=dict(gridcolor="#eef0f3"))
        st.plotly_chart(sc, width="stretch", config=CONFIG)
        st.caption("Tamaño = población · color = pobreza extrema · pasa el mouse para ver cada departamento. "
                   f"Fuente: {enaho.FUENTE}")

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
        st.plotly_chart(fig, width="stretch", config=SIN_BARRA)
        st.caption("Experimento propio (Tarea 4): mismas preguntas en sesiones independientes; tiempo promedio 8.2 s sin y 25.2 s con.")
