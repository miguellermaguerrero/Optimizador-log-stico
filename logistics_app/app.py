"""
app.py — Aplicación Streamlit de Optimización Logística
Ejecutar: streamlit run app.py
"""
from __future__ import annotations
import sys, os, base64
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import io

from config import TARIFAS_PATH, CATALOGO_PATH, UMBRAL_CERCANO_PCT
from data_loader import cargar_todo, generar_plantilla_stock, generar_plantilla_llegadas, generar_plantilla_envios
import logistics

# ─── Configuración de página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Optimizador Logístico",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Carga de tarifas y catálogo desde Excel (cacheado) ──────────────────────
@st.cache_resource(show_spinner="Cargando tarifas y catálogo…")
def _cargar_datos():
    datos = cargar_todo(TARIFAS_PATH, CATALOGO_PATH)
    datos["umbral_cercano_pct"] = UMBRAL_CERCANO_PCT
    return datos

try:
    _datos = _cargar_datos()
    logistics.set_datos(_datos)
    _datos_ok = True
    _productos_disponibles = list(_datos.get("productos", {}).keys())
except FileNotFoundError as _e:
    _datos_ok = False
    _error_msg = str(_e)
    _productos_disponibles = []
except Exception as _e:
    _datos_ok = False
    _error_msg = f"Error al leer los archivos Excel: {_e}"
    _productos_disponibles = []

# ─── Logo en base64 ───────────────────────────────────────────────────────────
def _logo_b64() -> str:
    logo_path = Path(__file__).parent / "logo.png"
    if logo_path.exists():
        return base64.b64encode(logo_path.read_bytes()).decode()
    return ""

_logo = _logo_b64()
_logo_html = (
    f'<img src="data:image/png;base64,{_logo}" style="height:72px;margin-right:18px;vertical-align:middle;">'
    if _logo else ""
)

# ─── Colores ──────────────────────────────────────────────────────────────────
NAVY    = "#1A2E4A"
NAVY2   = "#243d5e"
BLUE    = "#2E5F8A"
LBLUE   = "#4A7AB5"
WHITE   = "#FFFFFF"
BGLIGHT = "#EBF2FA"
BGCARD  = "#F4F8FD"

PALETTE = [NAVY, BLUE, LBLUE, "#5B9BD5", "#2C7BB6", "#0A3D6B", "#7FB3D3", "#A8C8E8"]

# ─── Estilos CSS ──────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
/* Ocultar sidebar y toggle */
[data-testid="stSidebar"] {{display:none}}
[data-testid="collapsedControl"] {{display:none}}
section[data-testid="stSidebarContent"] {{display:none}}

/* Fondo general */
.stApp {{ background: {BGLIGHT}; }}

/* Header */
.app-header {{
    background: linear-gradient(135deg, {NAVY} 0%, {NAVY2} 60%, {BLUE} 100%);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    box-shadow: 0 4px 20px rgba(26,46,74,0.18);
}}
.app-header h1 {{
    color: {WHITE};
    font-size: 2rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.5px;
}}
.app-header p {{
    color: rgba(255,255,255,0.75);
    margin: 4px 0 0 0;
    font-size: 0.95rem;
}}
.badge {{
    background: rgba(255,255,255,0.15);
    color: {WHITE};
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.78rem;
    margin-top: 8px;
    display: inline-block;
}}

/* Sección */
.section-title {{
    color: {NAVY};
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 0 0 12px 0;
    padding-left: 4px;
    border-left: 3px solid {LBLUE};
    padding-left: 10px;
}}

/* Tarjeta de plantilla */
.template-card {{
    background: {WHITE};
    border-radius: 12px;
    padding: 20px 22px;
    border: 1px solid #D0E4F5;
    box-shadow: 0 2px 8px rgba(26,46,74,0.07);
    height: 100%;
}}
.template-card h4 {{
    color: {NAVY};
    margin: 0 0 6px 0;
    font-size: 1rem;
}}
.template-card p {{
    color: #5a7490;
    font-size: 0.82rem;
    margin: 0 0 14px 0;
}}

/* Upload card */
.upload-card {{
    background: {WHITE};
    border-radius: 12px;
    padding: 18px 20px 10px 20px;
    border: 2px dashed #B8D4EC;
    box-shadow: 0 2px 8px rgba(26,46,74,0.05);
}}
.upload-card h4 {{
    color: {NAVY};
    margin: 0 0 10px 0;
    font-size: 0.95rem;
}}

/* Parámetros */
.params-bar {{
    background: {WHITE};
    border-radius: 12px;
    padding: 16px 24px;
    border: 1px solid #D0E4F5;
    box-shadow: 0 2px 8px rgba(26,46,74,0.05);
    margin-bottom: 8px;
}}

/* Alerta y sugerencia */
.alert-card {{
    background: #FFF8E7;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 6px 0;
    border-left: 4px solid #F0A500;
}}
.ok-card {{
    background: #E8F8F2;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 6px 0;
    border-left: 4px solid #1A9E6E;
}}
.suggestion-box {{
    background: {BGLIGHT};
    border-radius: 10px;
    padding: 16px 20px;
    margin: 8px 0;
    border: 1px solid #B8D4EC;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    background: {WHITE};
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
    box-shadow: 0 1px 4px rgba(26,46,74,0.08);
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px;
    color: {NAVY};
    font-weight: 600;
}}
.stTabs [aria-selected="true"] {{
    background: {NAVY} !important;
    color: {WHITE} !important;
}}

/* Botones de descarga */
.stDownloadButton > button {{
    background: {NAVY} !important;
    color: {WHITE} !important;
    border-radius: 8px !important;
    border: none !important;
    width: 100%;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 10px 0 !important;
    transition: background 0.2s;
}}
.stDownloadButton > button:hover {{
    background: {BLUE} !important;
}}

/* Métricas */
[data-testid="stMetric"] {{
    background: {WHITE};
    border-radius: 10px;
    padding: 14px 18px;
    border: 1px solid #D0E4F5;
    box-shadow: 0 1px 4px rgba(26,46,74,0.06);
}}
</style>
""", unsafe_allow_html=True)


# ─── Alerta si los Excel no se pueden leer ───────────────────────────────────
if not _datos_ok:
    st.error(f"⚠️ **No se pudieron cargar las tarifas**\n\n{_error_msg}")
    st.stop()

n_prov = len([k for k in _datos.get("tarifa_pale_provincia", {}) if k != "PENINSULA_MEDIA"])
n_prod = len(_productos_disponibles)

# ─── CABECERA ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="app-header">
  {_logo_html}
  <div>
    <h1>Optimizador Logístico</h1>
    <p>Análisis y optimización de costes de distribución</p>
    <span class="badge">✅ {n_prov} provincias · {n_prod} productos cargados</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── PLANTILLAS ───────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">📥 Plantillas de datos</p>', unsafe_allow_html=True)
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("""<div class="template-card">
    <h4>📦 Stock</h4>
    <p>Inventario actual por almacén y producto</p></div>""", unsafe_allow_html=True)
    st.download_button("Descargar plantilla Stock",
                       generar_plantilla_stock(_datos),
                       "plantilla_stock.xlsx", mime=XLSX_MIME, use_container_width=True)
with c2:
    st.markdown("""<div class="template-card">
    <h4>📥 Llegadas</h4>
    <p>Entradas al almacén central por fecha</p></div>""", unsafe_allow_html=True)
    st.download_button("Descargar plantilla Llegadas",
                       generar_plantilla_llegadas(_datos),
                       "plantilla_llegadas.xlsx", mime=XLSX_MIME, use_container_width=True)
with c3:
    st.markdown("""<div class="template-card">
    <h4>📤 Envíos</h4>
    <p>Envíos planificados por provincia y producto</p></div>""", unsafe_allow_html=True)
    st.download_button("Descargar plantilla Envíos",
                       generar_plantilla_envios(_datos),
                       "plantilla_envios.xlsx", mime=XLSX_MIME, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── CARGA DE ARCHIVOS ────────────────────────────────────────────────────────
st.markdown('<p class="section-title">📂 Carga de datos</p>', unsafe_allow_html=True)

u1, u2, u3 = st.columns(3)
with u1:
    st.markdown('<div class="upload-card"><h4>1️⃣ Stock actual</h4>', unsafe_allow_html=True)
    f_stock = st.file_uploader("", type=["xlsx"], key="stock", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)
with u2:
    st.markdown('<div class="upload-card"><h4>2️⃣ Llegadas al almacén</h4>', unsafe_allow_html=True)
    f_llegadas = st.file_uploader("", type=["xlsx"], key="llegadas", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)
with u3:
    st.markdown('<div class="upload-card"><h4>3️⃣ Envíos planificados</h4>', unsafe_allow_html=True)
    f_envios = st.file_uploader("", type=["xlsx"], key="envios", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── PARÁMETROS ───────────────────────────────────────────────────────────────
with st.expander("⚙️ Parámetros de análisis", expanded=False):
    p1, p2, p3 = st.columns([1, 1, 2])
    with p1:
        valor_caja = st.number_input("Valor por caja (€)", min_value=1.0,
                                     max_value=5000.0, value=50.0, step=5.0)
    with p2:
        umbral_sug = st.slider("Umbral 'cerca del óptimo' (%)", 5, 50, 20,
                               help="Si añadiendo hasta X% más de cajas se baja de tramo, se sugiere el ajuste")
    with p3:
        if _productos_disponibles:
            st.markdown("**Productos en catálogo:**")
            st.caption(" · ".join(_productos_disponibles))

logistics.DATOS["umbral_cercano_pct"] = umbral_sug / 100

st.markdown("<br>", unsafe_allow_html=True)

# ─── PANTALLA SIN DATOS ───────────────────────────────────────────────────────
if not f_stock and not f_llegadas and not f_envios:
    st.markdown(f"""
<div style="background:{WHITE};border-radius:14px;padding:36px 40px;
            text-align:center;border:1px solid #D0E4F5;
            box-shadow:0 2px 12px rgba(26,46,74,0.07);">
  <p style="font-size:2.5rem;margin:0">📋</p>
  <h3 style="color:{NAVY};margin:8px 0 6px 0;">Descarga las plantillas, rellénalas y súbelas</h3>
  <p style="color:#5a7490;margin:0;font-size:0.95rem;">
    Usa los botones de arriba para obtener las plantillas Excel con tus provincias y productos,<br>
    completa los datos y cárgalos en los tres paneles de subida.
  </p>
</div>
""", unsafe_allow_html=True)
    st.stop()


# ─── Funciones auxiliares de lectura ─────────────────────────────────────────

def leer_stock(f) -> pd.DataFrame:
    df = pd.read_excel(f)
    df.columns = df.columns.str.strip()
    return df


def leer_llegadas(f) -> pd.DataFrame:
    df = pd.read_excel(f)
    df.columns = df.columns.str.strip()
    if "ALMACÉN" in df.columns and "FECHA" in df.columns:
        id_cols   = ["ALMACÉN", "FECHA"]
        prod_cols = [c for c in df.columns if c not in id_cols]
        df_long = df.melt(id_vars=id_cols, value_vars=prod_cols,
                          var_name="Producto", value_name="Cajas")
        df_long = df_long[pd.to_numeric(df_long["Cajas"], errors="coerce").fillna(0) > 0].copy()
        df_long["Fecha"] = pd.to_datetime(df_long["FECHA"], errors="coerce")
        df_long["Cajas"] = pd.to_numeric(df_long["Cajas"], errors="coerce").fillna(0).astype(int)
        return df_long[["Fecha", "Producto", "Cajas"]].reset_index(drop=True)
    else:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        return df


def leer_envios(f) -> pd.DataFrame:
    df = pd.read_excel(f)
    df.columns = df.columns.str.strip()
    if "PROVINCIA" in df.columns and "ZONA" in df.columns:
        id_cols   = ["PROVINCIA", "ZONA", "FECHA"]
        prod_cols = [c for c in df.columns if c not in id_cols]
        df_long = df.melt(id_vars=id_cols, value_vars=prod_cols,
                          var_name="Producto", value_name="Cajas")
        df_long = df_long[pd.to_numeric(df_long["Cajas"], errors="coerce").fillna(0) > 0].copy()
        df_long["Fecha"] = pd.to_datetime(df_long["FECHA"], errors="coerce")
        df_long["Cajas"] = pd.to_numeric(df_long["Cajas"], errors="coerce").fillna(0).astype(int)
        df_long = df_long.rename(columns={"PROVINCIA": "Provincia", "ZONA": "Zona"})
        return df_long[["Fecha", "Producto", "Cajas", "Provincia", "Zona"]].reset_index(drop=True)
    else:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
        df["Cajas"] = pd.to_numeric(df["Cajas"], errors="coerce").fillna(0).astype(int)
        return df


# ─── ANÁLISIS ─────────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">📊 Análisis</p>', unsafe_allow_html=True)
tabs = st.tabs(["📦 Stock", "📥 Llegadas", "📤 Envíos & Optimización"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — STOCK
# ══════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    if not f_stock:
        st.info("Sube el archivo de **stock actual** para ver esta sección.")
        st.stop()

    df_stock = leer_stock(f_stock)
    st.subheader("📦 Stock actual por almacén")
    st.dataframe(df_stock, use_container_width=True)

    almacenes = [c for c in df_stock.columns if c != "Producto"]
    st.markdown("### Resumen por almacén")
    totales   = df_stock[almacenes].sum()
    cols_alm  = st.columns(min(len(almacenes), 5))
    for i, (alm, tot) in enumerate(totales.items()):
        cols_alm[i % len(cols_alm)].metric(alm, f"{int(tot):,} cajas")

    st.markdown("### Distribución de stock")
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor("white")
    x = np.arange(len(df_stock))
    bottom = np.zeros(len(df_stock))
    for i, alm in enumerate(almacenes):
        vals = df_stock[alm].fillna(0).values
        ax.bar(x, vals, bottom=bottom, label=alm,
               color=PALETTE[i % len(PALETTE)], width=0.6)
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels(df_stock["Producto"].tolist(), fontsize=9)
    ax.set_ylabel("Cajas")
    ax.set_title("Stock por producto y almacén", color=NAVY, fontweight="bold")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, axis="y", alpha=0.2)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    st.pyplot(fig)
    plt.close()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LLEGADAS
# ══════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    if not f_llegadas:
        st.info("Sube el archivo de **llegadas** para ver esta sección.")
        st.stop()

    df_llegadas = leer_llegadas(f_llegadas)
    st.subheader("📥 Llegadas al almacén central")
    st.dataframe(df_llegadas, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total cajas recibidas", f"{df_llegadas['Cajas'].sum():,}")
    c2.metric("Número de recepciones", len(df_llegadas))
    c3.metric("Productos distintos", df_llegadas["Producto"].nunique())

    st.markdown("### Entradas por fecha")
    pivot = df_llegadas.pivot_table(index="Fecha", columns="Producto",
                                    values="Cajas", aggfunc="sum").fillna(0)
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor("white")
    for i, col in enumerate(pivot.columns):
        ax.bar(pivot.index, pivot[col], label=col,
               color=PALETTE[i % len(PALETTE)], alpha=0.9,
               bottom=pivot[pivot.columns[:i]].sum(axis=1) if i > 0 else None)
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Cajas")
    ax.set_title("Cajas recibidas por fecha y producto", color=NAVY, fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.autofmt_xdate()
    st.pyplot(fig)
    plt.close()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ENVÍOS & OPTIMIZACIÓN
# ══════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    if not f_envios:
        st.info("Sube el archivo de **envíos planificados** para ver esta sección.")
        st.stop()

    df_envios_raw = leer_envios(f_envios)

    with st.spinner("Calculando costes y optimizaciones…"):
        df_result = logistics.analizar_hoja_envios(df_envios_raw, valor_por_caja=valor_caja)

    total_coste   = df_result["Coste_total"].sum()
    total_cajas_e = df_result["Cajas"].sum()
    num_sug       = df_result["Cerca_de_optimo"].sum()
    ahorro_max    = df_result["Sugerencia_ahorro"].fillna(0).sum()

    st.subheader("📊 Resumen de envíos planificados")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Coste logístico total",    f"{total_coste:,.2f} €")
    col2.metric("Total cajas enviadas",     f"{total_cajas_e:,}")
    col3.metric("Envíos cerca del óptimo",  f"{num_sug} de {len(df_result)}",
                delta="Ajustables" if num_sug > 0 else None,
                delta_color="inverse" if num_sug > 0 else "off")
    col4.metric("Ahorro potencial total",   f"{ahorro_max:,.2f} €",
                delta="si ajustas los envíos" if ahorro_max > 0 else "ya optimizados")

    st.markdown("### Detalle por envío")
    cols_show = ["Fecha", "Producto", "Cajas", "Provincia", "Modalidad",
                 "Coste_transporte", "Coste_almacen", "Coste_total",
                 "Coste_por_caja", "Cerca_de_optimo", "Sugerencia_cajas", "Sugerencia_ahorro"]
    df_display = df_result[cols_show].copy()

    def color_cerca(val):
        return "background-color: #FFF8E7; color: #7A5200" if val is True else ""

    styled = df_display.style\
        .format({
            "Coste_transporte":  "{:.2f} €",
            "Coste_almacen":     "{:.2f} €",
            "Coste_total":       "{:.2f} €",
            "Coste_por_caja":    "{:.3f} €",
            "Sugerencia_ahorro": lambda v: f"{v:.2f} €" if pd.notna(v) else "—",
            "Sugerencia_cajas":  lambda v: f"{int(v)}"  if pd.notna(v) else "—",
        })\
        .applymap(color_cerca, subset=["Cerca_de_optimo"])
    st.dataframe(styled, use_container_width=True)

    # ── Sugerencias ───────────────────────────────────────────────────────────
    envios_con_sug = df_result[df_result["Cerca_de_optimo"] == True]

    if len(envios_con_sug) > 0:
        st.markdown("---")
        st.markdown("## 💡 Sugerencias de ajuste")
        st.markdown(
            f"Se han detectado **{len(envios_con_sug)} envíos** que, aumentando el volumen "
            f"hasta un **{umbral_sug}%**, cambiarían de tramo y reducirían el coste por caja."
        )

        if "ajustes_usuario" not in st.session_state:
            st.session_state.ajustes_usuario = {}

        for i, (idx, row) in enumerate(envios_con_sug.iterrows()):
            sug_list = row["_sugerencias_full"]
            if not sug_list:
                continue
            key_prefix = f"envio_{idx}"
            sug = sug_list[0]

            with st.container():
                st.markdown(f"""
<div class="alert-card">
<b>📦 {row['Producto']}</b> → {row['Provincia']} | Fecha: {str(row['Fecha'])[:10]}<br>
Envío actual: <b>{row['Cajas']} cajas</b> | Coste/caja: <b>{row['Coste_por_caja']:.3f} €</b> |
Coste total: <b>{row['Coste_total']:.2f} €</b>
</div>""", unsafe_allow_html=True)

                st.markdown(f"""
<div class="suggestion-box">
🎯 <b>Sugerencia:</b> Aumentar a <b>{sug['cajas_sugeridas']} cajas</b>
(+{sug['cajas_extra']} cajas, +{sug['pct_mas']:.1f}%)<br>
📉 Nuevo coste/caja: <b>{sug['coste_por_caja_nuevo']:.3f} €</b>
| Ahorro estimado: <b>{sug['ahorro_total_estimado']:.2f} €</b><br>
ℹ️ {sug['motivo']}
</div>""", unsafe_allow_html=True)

                c_si, c_no, c_custom = st.columns([1, 1, 2])
                acepta       = c_si.button("✅ Aplicar", key=f"{key_prefix}_si")
                rechaza      = c_no.button("❌ Mantener", key=f"{key_prefix}_no")
                cajas_custom = c_custom.number_input(
                    "Cajas personalizadas:", min_value=1, max_value=50000,
                    value=sug["cajas_sugeridas"], key=f"{key_prefix}_custom",
                )

                if acepta:
                    st.session_state.ajustes_usuario[idx] = {"cajas_nuevas": sug["cajas_sugeridas"], "decision": "aplicado"}
                elif rechaza:
                    st.session_state.ajustes_usuario[idx] = {"cajas_nuevas": row["Cajas"], "decision": "rechazado"}
                elif key_prefix + "_custom" in st.session_state:
                    st.session_state.ajustes_usuario[idx] = {"cajas_nuevas": cajas_custom, "decision": "personalizado"}

                st.markdown("")

        if st.session_state.get("ajustes_usuario"):
            st.markdown("---")
            st.markdown("### 🔄 Plan de envíos ajustado")
            df_ajustado = df_envios_raw.copy()
            for idx, ajuste in st.session_state.ajustes_usuario.items():
                if ajuste["decision"] != "rechazado":
                    df_ajustado.at[idx, "Cajas"] = ajuste["cajas_nuevas"]

            df_nuevo    = logistics.analizar_hoja_envios(df_ajustado, valor_por_caja=valor_caja)
            nuevo_total = df_nuevo["Coste_total"].sum()
            ahorro_real = total_coste - nuevo_total

            c1, c2, c3 = st.columns(3)
            c1.metric("Nuevo coste total", f"{nuevo_total:,.2f} €",
                      delta=f"-{ahorro_real:,.2f} €", delta_color="inverse")
            c2.metric("Ahorro conseguido", f"{ahorro_real:,.2f} €")
            c3.metric("Reducción %", f"{ahorro_real/total_coste*100:.1f}%" if total_coste > 0 else "—")

            cols_show2 = ["Fecha", "Producto", "Cajas", "Provincia", "Modalidad", "Coste_total", "Coste_por_caja"]
            st.dataframe(df_nuevo[cols_show2].style.format({"Coste_total": "{:.2f} €", "Coste_por_caja": "{:.3f} €"}),
                         use_container_width=True)

            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_nuevo[cols_show2].to_excel(writer, sheet_name="Plan ajustado", index=False)
                df_result[cols_show].to_excel(writer, sheet_name="Plan original", index=False)
            buf.seek(0)
            st.download_button("📥 Descargar plan ajustado (.xlsx)", data=buf,
                               file_name="plan_envios_optimizado.xlsx",
                               mime=XLSX_MIME, use_container_width=True)
    else:
        st.success("✅ Todos los envíos ya están en el tramo óptimo o muy cerca de él.")

    # ── Gráfico coste actual vs óptimo ───────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 Coste/caja actual vs. óptimo por envío")
    labels = [
        f"{r['Producto'][:8]} - {r['Provincia'][:6]}\n{str(r['Fecha'])[:10]}"
        for _, r in df_result.iterrows()
    ]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.2), 5))
    fig.patch.set_facecolor("white")
    ax.bar(x - 0.2, df_result["Coste_por_caja"],   0.35, label="Coste actual/caja",  color=NAVY)
    ax.bar(x + 0.2, df_result["Optimo_coste_caja"], 0.35, label="Óptimo posible/caja", color=LBLUE, alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5, rotation=30, ha="right")
    ax.set_ylabel("€ por caja")
    ax.set_title("Coste logístico actual vs. punto óptimo por envío", color=NAVY, fontweight="bold")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.2f}€"))
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    # ── Curva de coste ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔍 Curva de coste para un envío concreto")
    envio_sel_label = st.selectbox(
        "Selecciona un envío:",
        options=df_result.index.tolist(),
        format_func=lambda i: (
            f"{df_result.at[i,'Producto']} → {df_result.at[i,'Provincia']} "
            f"({int(df_result.at[i,'Cajas'])} cajas, {str(df_result.at[i,'Fecha'])[:10]})"
        ),
    )
    curva_sel = df_result.at[envio_sel_label, "_curva"]
    cajas_sel = df_result.at[envio_sel_label, "Cajas"]

    if curva_sel is not None:
        fig2, ax2 = plt.subplots(figsize=(10, 4))
        fig2.patch.set_facecolor("white")
        ax2.plot(curva_sel["cajas"], curva_sel["coste_por_caja"],
                 "o-", color=NAVY, linewidth=2, markersize=5, label="Coste/caja")
        ax2.axvline(cajas_sel, color="#C0392B", linestyle="--",
                    linewidth=1.8, label=f"Envío actual ({cajas_sel} cajas)")
        opt_idx   = curva_sel["coste_por_caja"].idxmin()
        opt_cajas = int(curva_sel.loc[opt_idx, "cajas"])
        ax2.axvline(opt_cajas, color="#1A9E6E", linestyle="--",
                    linewidth=1.8, label=f"Óptimo global ({opt_cajas} cajas)")
        ax2.set_xlabel("Cajas por envío")
        ax2.set_ylabel("€ por caja")
        ax2.set_title(
            f"Curva de coste — {df_result.at[envio_sel_label,'Producto']} "
            f"→ {df_result.at[envio_sel_label,'Provincia']}",
            color=NAVY, fontweight="bold",
        )
        ax2.legend()
        ax2.grid(True, alpha=0.2)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.2f}€"))
        plt.tight_layout()
        st.pyplot(fig2)
        plt.close()

    # ── Desglose pastel ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🥧 Desglose del coste total")
    tot_tr  = df_result["Coste_transporte"].sum()
    tot_alm = df_result["Coste_almacen"].sum()
    fig3, ax3 = plt.subplots(figsize=(5, 4))
    fig3.patch.set_facecolor("white")
    ax3.pie([tot_tr, tot_alm],
            labels=["Transporte", "Almacén regional"],
            colors=[NAVY, LBLUE],
            autopct="%1.1f%%", startangle=90,
            textprops={"fontsize": 10})
    ax3.set_title("Distribución del coste logístico", color=NAVY, fontweight="bold")
    st.pyplot(fig3)
    plt.close()
