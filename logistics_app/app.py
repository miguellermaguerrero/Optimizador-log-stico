"""
app.py — Aplicación Streamlit de Optimización Logística
Ejecutar: streamlit run app.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import io

from config import TARIFAS_PATH, CATALOGO_PATH, UMBRAL_CERCANO_PCT
from data_loader import cargar_todo
import logistics

# ─── Configuración de página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Optimizador Logístico",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Carga de tarifas y catálogo desde Excel (cacheado) ──────────────────────
@st.cache_resource(show_spinner="Cargando tarifas y catálogo de productos…")
def _cargar_datos():
    """Lee tarifas_logisticas.xlsx y catalogo_productos.xlsx una sola vez."""
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


# ─── Estilos ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #f0f4ff;
    border-radius: 10px;
    padding: 16px 20px;
    margin: 6px 0;
    border-left: 4px solid #4361ee;
}
.alert-card {
    background: #fff3cd;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 6px 0;
    border-left: 4px solid #ffc107;
}
.ok-card {
    background: #d1fae5;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 6px 0;
    border-left: 4px solid #10b981;
}
.suggestion-box {
    background: #eff6ff;
    border-radius: 10px;
    padding: 16px 20px;
    margin: 8px 0;
    border: 1px solid #bfdbfe;
}
h1 { color: #1e3a5f; }
</style>
""", unsafe_allow_html=True)


# ─── Alerta si los Excel no se pueden leer ───────────────────────────────────
if not _datos_ok:
    st.error(f"⚠️ **No se pudieron cargar las tarifas**\n\n{_error_msg}")
    st.info(
        "Asegúrate de que los archivos **tarifas_logisticas.xlsx** y "
        "**catalogo_productos.xlsx** están en la misma carpeta que esta aplicación "
        "(un nivel arriba de la carpeta `logistics_app`)."
    )
    st.stop()


# ─── Sidebar — carga de archivos ─────────────────────────────────────────────
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2956/2956744.png", width=60)
    st.title("📂 Carga de datos")
    st.markdown("---")

    st.subheader("1️⃣ Stock actual")
    f_stock = st.file_uploader(
        "Stock por almacén (plantilla_stock.xlsx)",
        type=["xlsx"], key="stock",
    )

    st.subheader("2️⃣ Llegadas al almacén central")
    f_llegadas = st.file_uploader(
        "Nuevas entradas por fecha (plantilla_llegadas.xlsx)",
        type=["xlsx"], key="llegadas",
    )

    st.subheader("3️⃣ Envíos planificados")
    f_envios = st.file_uploader(
        "Envíos a realizar (plantilla_envios.xlsx)",
        type=["xlsx"], key="envios",
    )

    st.markdown("---")
    st.subheader("⚙️ Parámetros globales")
    valor_caja = st.number_input("Valor por caja (€)", min_value=1.0,
                                  max_value=5000.0, value=50.0, step=5.0)
    umbral_sug = st.slider("Umbral 'cerca del óptimo' (%)", 5, 50, 20,
                            help="Si añadiendo hasta X% más de cajas bajas de tramo, se sugiere el ajuste")

    # Actualizar umbral en DATOS (se usa en analizar_envio)
    logistics.DATOS["umbral_cercano_pct"] = umbral_sug / 100

    st.markdown("---")

    # Resumen de tarifas cargadas
    n_prov_pale = len([k for k in _datos.get("tarifa_pale_provincia", {}) if k != "PENINSULA_MEDIA"])
    n_prov_carga = len(_datos.get("cargas_completas", {}))
    n_prod = len(_productos_disponibles)
    st.caption(
        f"✅ Tarifas cargadas: {n_prov_pale} provincias · {n_prod} productos activos"
    )

    if _productos_disponibles:
        with st.expander("🗂 Productos en catálogo"):
            for p in _productos_disponibles:
                st.write(f"• {p}")

    st.markdown("---")
    st.caption("Descarga las plantillas de ejemplo ↓")
    st.markdown("[📥 Ver formato esperado](#formato-de-archivos)")


# ─── Funciones auxiliares de lectura ─────────────────────────────────────────

def leer_stock(f) -> pd.DataFrame:
    df = pd.read_excel(f)
    df.columns = df.columns.str.strip()
    return df

def leer_llegadas(f) -> pd.DataFrame:
    df = pd.read_excel(f)
    df.columns = df.columns.str.strip()
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    return df

def leer_envios(f) -> pd.DataFrame:
    df = pd.read_excel(f)
    df.columns = df.columns.str.strip()
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df["Cajas"] = pd.to_numeric(df["Cajas"], errors="coerce").fillna(0).astype(int)
    return df


# ─── Paleta de colores para gráficos ─────────────────────────────────────────
PALETTE = ["#4361ee", "#f72585", "#3a86ff", "#ff6b6b", "#06d6a0",
           "#ffd166", "#8338ec", "#118ab2"]


# ─── CABECERA ─────────────────────────────────────────────────────────────────
st.title("🚚 Optimizador Logístico")
st.caption("Sube los tres archivos Excel desde el panel lateral para comenzar el análisis.")

if not f_stock and not f_llegadas and not f_envios:
    # ── Pantalla de bienvenida con formato esperado ──────────────────────────
    st.markdown("---")
    st.header("📋 Formato de archivos", anchor="formato-de-archivos")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 1️⃣ Stock actual")
        st.dataframe(pd.DataFrame({
            "Producto":        _productos_disponibles[:2] or ["Producto A", "Producto B"],
            "Almacen_Central": [500, 200],
            "Madrid":          [100, 50],
            "Barcelona":       [80, 30],
            "Valencia":        [60, 20],
        }), use_container_width=True)
        st.caption("Una fila por producto. Columnas: almacén central + una por cada almacén provincial.")

    with c2:
        st.markdown("### 2️⃣ Llegadas")
        st.dataframe(pd.DataFrame({
            "Fecha":    ["2024-05-01", "2024-05-08"],
            "Producto": _productos_disponibles[:2] or ["Producto A", "Producto C"],
            "Cajas":    [300, 150],
        }), use_container_width=True)
        st.caption("Una fila por recepción en el almacén central. Fecha en formato YYYY-MM-DD.")

    with c3:
        st.markdown("### 3️⃣ Envíos planificados")
        st.dataframe(pd.DataFrame({
            "Fecha":     ["2024-05-10", "2024-05-12"],
            "Producto":  _productos_disponibles[:2] or ["Producto A", "Producto B"],
            "Cajas":     [120, 80],
            "Provincia": ["Barcelona", "Valencia"],
            "Zona":      ["peninsula", "peninsula"],
        }), use_container_width=True)
        st.caption("Una fila por envío. Zona: 'peninsula' o 'baleares'.")

    st.stop()


# ─── Carga y procesado de datos ──────────────────────────────────────────────
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

    # Columnas de almacenes (todo excepto "Producto")
    almacenes = [c for c in df_stock.columns if c != "Producto"]

    # Totales por almacén
    st.markdown("### Resumen por almacén")
    totales = df_stock[almacenes].sum()
    cols_alm = st.columns(min(len(almacenes), 5))
    for i, (alm, tot) in enumerate(totales.items()):
        cols_alm[i % len(cols_alm)].metric(alm, f"{int(tot):,} cajas")

    # Gráfico de barras apiladas
    st.markdown("### Distribución de stock")
    fig, ax = plt.subplots(figsize=(10, 4))
    x = np.arange(len(df_stock))
    bottom = np.zeros(len(df_stock))
    for i, alm in enumerate(almacenes):
        vals = df_stock[alm].fillna(0).values
        bars = ax.bar(x, vals, bottom=bottom, label=alm,
                      color=PALETTE[i % len(PALETTE)], width=0.6)
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(df_stock["Producto"].tolist(), fontsize=9)
    ax.set_ylabel("Cajas")
    ax.set_title("Stock por producto y almacén")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
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

    # Totales
    total_cajas  = df_llegadas["Cajas"].sum()
    num_recepciones = len(df_llegadas)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total cajas recibidas", f"{total_cajas:,}")
    c2.metric("Número de recepciones", num_recepciones)
    c3.metric("Productos distintos", df_llegadas["Producto"].nunique())

    # Gráfico temporal
    st.markdown("### Entradas por fecha")
    pivot = df_llegadas.pivot_table(index="Fecha", columns="Producto",
                                     values="Cajas", aggfunc="sum").fillna(0)
    fig, ax = plt.subplots(figsize=(10, 4))
    for i, col in enumerate(pivot.columns):
        ax.bar(pivot.index, pivot[col], label=col,
               color=PALETTE[i % len(PALETTE)], alpha=0.85,
               bottom=pivot[pivot.columns[:i]].sum(axis=1) if i > 0 else None)
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Cajas")
    ax.set_title("Cajas recibidas por fecha y producto")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
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

    # ── Análisis logístico ────────────────────────────────────────────────────
    with st.spinner("Calculando costes y optimizaciones…"):
        df_result = logistics.analizar_hoja_envios(df_envios_raw, valor_por_caja=valor_caja)

    # ── KPIs globales ─────────────────────────────────────────────────────────
    st.subheader("📊 Resumen de envíos planificados")
    total_coste   = df_result["Coste_total"].sum()
    total_cajas_e = df_result["Cajas"].sum()
    num_sug       = df_result["Cerca_de_optimo"].sum()
    ahorro_max    = df_result["Sugerencia_ahorro"].fillna(0).sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Coste logístico total", f"{total_coste:,.2f} €")
    col2.metric("Total cajas enviadas",  f"{total_cajas_e:,}")
    col3.metric("Envíos cerca del óptimo", f"{num_sug} de {len(df_result)}",
                delta="Ajustables" if num_sug > 0 else None,
                delta_color="inverse" if num_sug > 0 else "off")
    col4.metric("Ahorro potencial total", f"{ahorro_max:,.2f} €",
                delta="si ajustas los envíos" if ahorro_max > 0 else "ya optimizados")

    # ── Tabla de resultados ───────────────────────────────────────────────────
    st.markdown("### Detalle por envío")
    cols_show = ["Fecha", "Producto", "Cajas", "Provincia", "Modalidad",
                 "Coste_transporte", "Coste_almacen", "Coste_total",
                 "Coste_por_caja", "Cerca_de_optimo", "Sugerencia_cajas", "Sugerencia_ahorro"]
    df_display = df_result[cols_show].copy()

    def color_cerca(val):
        if val is True:
            return "background-color: #fff3cd; color: #856404"
        return ""

    styled = df_display.style\
        .format({
            "Coste_transporte": "{:.2f} €",
            "Coste_almacen":    "{:.2f} €",
            "Coste_total":      "{:.2f} €",
            "Coste_por_caja":   "{:.3f} €",
            "Sugerencia_ahorro":lambda v: f"{v:.2f} €" if pd.notna(v) else "—",
            "Sugerencia_cajas": lambda v: f"{int(v)}" if pd.notna(v) else "—",
        })\
        .applymap(color_cerca, subset=["Cerca_de_optimo"])

    st.dataframe(styled, use_container_width=True)

    # ── Alertas y sugerencias interactivas ────────────────────────────────────
    envios_con_sug = df_result[df_result["Cerca_de_optimo"] == True]

    if len(envios_con_sug) > 0:
        st.markdown("---")
        st.markdown("## 💡 Sugerencias de ajuste")
        st.markdown(
            f"Se han detectado **{len(envios_con_sug)} envíos** que, aumentando el volumen "
            f"hasta un **{umbral_sug}%**, cambiarían de tramo y reducirían el coste por caja. "
            "Revisa cada uno y decide si quieres ajustarlo."
        )

        # Guardar en session_state las decisiones del usuario
        if "ajustes_usuario" not in st.session_state:
            st.session_state.ajustes_usuario = {}

        for i, (idx, row) in enumerate(envios_con_sug.iterrows()):
            sug_list = row["_sugerencias_full"]
            if not sug_list:
                continue

            key_prefix = f"envio_{idx}"
            sug = sug_list[0]   # la sugerencia más cercana

            with st.container():
                st.markdown(f"""
<div class="alert-card">
<b>📦 {row['Producto']}</b> → {row['Provincia']} | Fecha: {str(row['Fecha'])[:10]}<br>
Envío actual: <b>{row['Cajas']} cajas</b> | Coste/caja: <b>{row['Coste_por_caja']:.3f} €</b><br>
Coste total actual: <b>{row['Coste_total']:.2f} €</b>
</div>
""", unsafe_allow_html=True)

                st.markdown(f"""
<div class="suggestion-box">
🎯 <b>Sugerencia:</b> Aumentar a <b>{sug['cajas_sugeridas']} cajas</b>
(+{sug['cajas_extra']} cajas, +{sug['pct_mas']:.1f}%)<br>
📉 Nuevo coste/caja: <b>{sug['coste_por_caja_nuevo']:.3f} €</b>
| Ahorro estimado: <b>{sug['ahorro_total_estimado']:.2f} €</b><br>
ℹ️ Motivo: {sug['motivo']}
</div>
""", unsafe_allow_html=True)

                c_si, c_no, c_custom = st.columns([1, 1, 2])
                acepta = c_si.button("✅ Aplicar sugerencia", key=f"{key_prefix}_si")
                rechaza = c_no.button("❌ Mantener original", key=f"{key_prefix}_no")
                cajas_custom = c_custom.number_input(
                    "O introduce cajas personalizadas:",
                    min_value=1, max_value=50000,
                    value=sug["cajas_sugeridas"],
                    key=f"{key_prefix}_custom",
                )

                if acepta:
                    st.session_state.ajustes_usuario[idx] = {
                        "cajas_nuevas": sug["cajas_sugeridas"],
                        "decision": "aplicado",
                    }
                elif rechaza:
                    st.session_state.ajustes_usuario[idx] = {
                        "cajas_nuevas": row["Cajas"],
                        "decision": "rechazado",
                    }
                elif key_prefix + "_custom" in st.session_state:
                    st.session_state.ajustes_usuario[idx] = {
                        "cajas_nuevas": cajas_custom,
                        "decision": "personalizado",
                    }

                st.markdown("")

        # ── Recalcular con ajustes ────────────────────────────────────────────
        if st.session_state.ajustes_usuario:
            st.markdown("---")
            st.markdown("### 🔄 Plan de envíos ajustado")

            df_ajustado = df_envios_raw.copy()
            for idx, ajuste in st.session_state.ajustes_usuario.items():
                if ajuste["decision"] != "rechazado":
                    df_ajustado.at[idx, "Cajas"] = ajuste["cajas_nuevas"]

            df_nuevo = logistics.analizar_hoja_envios(df_ajustado, valor_por_caja=valor_caja)
            nuevo_total  = df_nuevo["Coste_total"].sum()
            ahorro_real  = total_coste - nuevo_total

            c1, c2, c3 = st.columns(3)
            c1.metric("Nuevo coste total", f"{nuevo_total:,.2f} €",
                      delta=f"-{ahorro_real:,.2f} €", delta_color="inverse")
            c2.metric("Ahorro conseguido", f"{ahorro_real:,.2f} €")
            c3.metric("Reducción %", f"{ahorro_real/total_coste*100:.1f}%" if total_coste > 0 else "—")

            cols_show2 = ["Fecha", "Producto", "Cajas", "Provincia",
                          "Modalidad", "Coste_total", "Coste_por_caja"]
            st.dataframe(
                df_nuevo[cols_show2].style.format({
                    "Coste_total": "{:.2f} €",
                    "Coste_por_caja": "{:.3f} €",
                }),
                use_container_width=True,
            )

            # Exportar plan ajustado
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_nuevo[cols_show2].to_excel(writer, sheet_name="Plan ajustado", index=False)
                df_result[cols_show].to_excel(writer, sheet_name="Plan original", index=False)
            buf.seek(0)
            st.download_button(
                "📥 Descargar plan ajustado (.xlsx)",
                data=buf,
                file_name="plan_envios_optimizado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    else:
        st.success("✅ Todos los envíos ya están en el tramo óptimo o muy cerca de él.")

    # ── Gráfico: coste actual vs óptimo por envío ────────────────────────────
    st.markdown("---")
    st.markdown("### 📈 Coste/caja actual vs. óptimo por envío")

    labels = [
        f"{r['Producto'][:8]} - {r['Provincia'][:6]}\n{str(r['Fecha'])[:10]}"
        for _, r in df_result.iterrows()
    ]
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.2), 5))
    bars = ax.bar(x - 0.2, df_result["Coste_por_caja"], 0.35,
                  label="Coste actual/caja", color="#4361ee")
    ax.bar(x + 0.2, df_result["Optimo_coste_caja"], 0.35,
           label="Óptimo posible/caja", color="#10b981", alpha=0.7)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5, rotation=30, ha="right")
    ax.set_ylabel("€ por caja")
    ax.set_title("Coste logístico actual vs. punto óptimo por envío")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.2f}€"))
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

    # ── Curva de coste para envío seleccionado ───────────────────────────────
    st.markdown("---")
    st.markdown("### 🔍 Curva de coste para un envío concreto")

    envio_sel_label = st.selectbox(
        "Selecciona un envío para ver su curva de costes:",
        options=df_result.index.tolist(),
        format_func=lambda i: (
            f"{df_result.at[i, 'Producto']} → {df_result.at[i, 'Provincia']} "
            f"({int(df_result.at[i, 'Cajas'])} cajas, {str(df_result.at[i, 'Fecha'])[:10]})"
        ),
    )

    curva_sel = df_result.at[envio_sel_label, "_curva"]
    cajas_sel = df_result.at[envio_sel_label, "Cajas"]

    if curva_sel is not None:
        fig2, ax2 = plt.subplots(figsize=(10, 4))
        ax2.plot(curva_sel["cajas"], curva_sel["coste_por_caja"],
                 "o-", color="#4361ee", linewidth=2, markersize=5, label="Coste/caja")
        ax2.axvline(cajas_sel, color="#f72585", linestyle="--",
                    linewidth=1.8, label=f"Envío actual ({cajas_sel} cajas)")
        opt_idx  = curva_sel["coste_por_caja"].idxmin()
        opt_cajas = int(curva_sel.loc[opt_idx, "cajas"])
        ax2.axvline(opt_cajas, color="#10b981", linestyle="--",
                    linewidth=1.8, label=f"Óptimo global ({opt_cajas} cajas)")
        ax2.set_xlabel("Cajas por envío")
        ax2.set_ylabel("€ por caja")
        ax2.set_title(
            f"Curva de coste — {df_result.at[envio_sel_label, 'Producto']} "
            f"→ {df_result.at[envio_sel_label, 'Provincia']}"
        )
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.2f}€"))
        plt.tight_layout()
        st.pyplot(fig2)
        plt.close()

    # ── Desglose coste total (pastel) ────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🥧 Desglose del coste total")
    tot_tr  = df_result["Coste_transporte"].sum()
    tot_alm = df_result["Coste_almacen"].sum()

    fig3, ax3 = plt.subplots(figsize=(5, 4))
    ax3.pie([tot_tr, tot_alm],
            labels=["Transporte", "Almacén regional"],
            colors=["#4361ee", "#f72585"],
            autopct="%1.1f%%", startangle=90,
            textprops={"fontsize": 10})
    ax3.set_title("Distribución del coste logístico total")
    st.pyplot(fig3)
    plt.close()
