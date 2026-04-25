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
import auth
import email_sender
import uploads_manager

# ─── Configuración de página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Debajo del hórreo",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── AUTENTICACIÓN ────────────────────────────────────────────────────────────
NAVY_AUTH  = "#1A2E4A"
WHITE_AUTH = "#FFFFFF"

def _cabecera_auth(logo_tag: str) -> None:
    """Renderiza el CSS y la caja de cabecera de la pantalla de auth."""
    st.markdown(f"""
<style>
.stApp {{ background: {NAVY_AUTH}; }}
[data-testid="stSidebar"] {{display:none}}
[data-testid="collapsedControl"] {{display:none}}
.auth-box {{
    background: {WHITE_AUTH};
    border-radius: 18px;
    padding: 36px 44px 28px 44px;
    max-width: 440px;
    margin: 50px auto 0 auto;
    box-shadow: 0 8px 40px rgba(0,0,0,0.25);
    text-align: center;
}}
.auth-box h2 {{ color: {NAVY_AUTH}; margin: 0 0 4px 0; font-size: 1.6rem; }}
.auth-box p  {{ color: #5a7490; margin: 0 0 20px 0; font-size: 0.9rem; }}
.stButton > button[kind="primary"] {{
    background: #4A7AB5 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}}
.stButton > button[kind="primary"]:hover {{
    background: #2E5F8A !important;
}}
div[data-testid="stRadio"] label p {{
    color: {WHITE_AUTH} !important;
    font-weight: 600;
    font-size: 1rem;
}}
/* Enlace olvidé contraseña */
.forgot-link button {{
    background: none !important;
    border: none !important;
    color: #4A7AB5 !important;
    font-size: 0.85rem !important;
    padding: 0 !important;
    text-decoration: underline !important;
    cursor: pointer;
    box-shadow: none !important;
}}
</style>
<div class="auth-box">
  {logo_tag}
  <h2>Debajo del hórreo</h2>
  <p>Gestión logística · Acceso privado</p>
</div>
""", unsafe_allow_html=True)


def _pantalla_reset_token(token: str) -> None:
    """Página de cambio de contraseña cuando el usuario llega desde el enlace del email."""
    ok, result = auth.verify_reset_token(token)

    _logo_path = Path(__file__).parent / "logo.png"
    _logo_b64  = base64.b64encode(_logo_path.read_bytes()).decode() if _logo_path.exists() else ""
    _logo_tag  = (f'<img src="data:image/png;base64,{_logo_b64}" '
                  f'style="height:100px;margin-bottom:12px;">') if _logo_b64 else "🏪"
    _cabecera_auth(_logo_tag)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        if not ok:
            st.error(f"⚠️ {result}")
            st.markdown(
                "<p style='color:#fff;text-align:center;font-size:0.9rem;margin-top:12px;'>"
                "Este enlace no es válido o ha caducado (1 hora).<br>"
                "Solicita uno nuevo desde la pantalla de inicio.</p>",
                unsafe_allow_html=True,
            )
        else:
            email = result
            st.markdown(
                f"<p style='color:#fff;text-align:center;font-size:0.9rem;margin-top:8px;'>"
                f"Cambiando contraseña para <b>{email}</b></p>",
                unsafe_allow_html=True,
            )
            np1 = st.text_input("Nueva contraseña", type="password",
                                placeholder="Mínimo 6 caracteres", key="np1")
            np2 = st.text_input("Repite la nueva contraseña", type="password",
                                placeholder="••••••••", key="np2")
            if st.button("Guardar nueva contraseña", use_container_width=True, type="primary"):
                if not np1 or not np2:
                    st.warning("Rellena ambos campos.")
                elif np1 != np2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    ok2, msg2 = auth.consume_reset_token(token, np1)
                    if ok2:
                        st.success(f"✅ {msg2}")
                        # Limpiar el token de la URL y redirigir al login
                        st.query_params.clear()
                    else:
                        st.error(msg2)
    st.stop()


def _pantalla_auth() -> None:
    """Muestra login / registro y detiene la ejecución hasta que el usuario acceda."""
    _logo_path = Path(__file__).parent / "logo.png"
    _logo_b64  = base64.b64encode(_logo_path.read_bytes()).decode() if _logo_path.exists() else ""
    _logo_tag  = (f'<img src="data:image/png;base64,{_logo_b64}" '
                  f'style="height:140px;margin-bottom:16px;">') if _logo_b64 else "🏪"
    _cabecera_auth(_logo_tag)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        _vista = st.session_state.get("auth_vista", "login")

        # ── FORMULARIO DE OLVIDÉ CONTRASEÑA ──────────────────────────────────
        if _vista == "forgot":
            st.markdown(
                f"<p style='color:{WHITE_AUTH};font-weight:700;font-size:1.05rem;"
                f"text-align:center;margin-bottom:4px;'>🔑 Recuperar contraseña</p>"
                f"<p style='color:rgba(255,255,255,0.7);font-size:0.85rem;"
                f"text-align:center;margin-bottom:14px;'>"
                f"Te enviaremos un enlace a tu correo para elegir una nueva contraseña.</p>",
                unsafe_allow_html=True,
            )
            f_email = st.text_input("Tu correo electrónico", placeholder="tu@correo.com",
                                    key="forgot_email")
            _fa, _fb = st.columns([2, 1])
            with _fa:
                if st.button("Enviar enlace", use_container_width=True, type="primary"):
                    if not f_email:
                        st.warning("Introduce tu correo.")
                    else:
                        # Generamos token (siempre decimos que se envió para no revelar emails)
                        _, token_or_dummy = auth.generate_reset_token(f_email)
                        if token_or_dummy != "__not_found__":
                            sent_ok, err = email_sender.send_reset_email(f_email, token_or_dummy)
                            if not sent_ok:
                                st.error(f"No se pudo enviar el correo: {err}")
                            else:
                                st.success("📬 Enlace enviado. Revisa tu bandeja de entrada (y la carpeta de spam).")
                        else:
                            # Igual mostramos éxito para no revelar si el correo existe
                            st.success("📬 Si ese correo está registrado, recibirás el enlace en breve.")
            with _fb:
                if st.button("← Volver", use_container_width=True, key="back_forgot"):
                    st.session_state["auth_vista"] = "login"
                    st.rerun()
            st.stop()

        # ── SELECTOR LOGIN / CREAR CUENTA ─────────────────────────────────────
        _tab = st.radio("", ["Iniciar sesión", "Crear cuenta"],
                        horizontal=True, label_visibility="collapsed",
                        key="auth_tab")
        st.markdown("")

        # ── INICIAR SESIÓN ────────────────────────────────────────────────────
        if _tab == "Iniciar sesión":
            email    = st.text_input("Correo electrónico", placeholder="tu@correo.com",
                                     key="li_email")
            password = st.text_input("Contraseña", type="password",
                                     placeholder="••••••••", key="li_pass")
            if st.button("Entrar", use_container_width=True, type="primary", key="btn_login"):
                if email and password:
                    ok, msg = auth.login(email, password)
                    if ok:
                        st.session_state["usuario"]       = msg
                        st.session_state["usuario_email"] = email.strip().lower()
                        st.session_state.pop("auth_vista", None)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Introduce correo y contraseña.")

            # Enlace sutil "¿Has olvidado la contraseña?"
            st.markdown(
                f"<div style='text-align:center;margin-top:6px;'>",
                unsafe_allow_html=True,
            )
            if st.button("¿Has olvidado la contraseña?", key="btn_forgot"):
                st.session_state["auth_vista"] = "forgot"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # ── CREAR CUENTA ──────────────────────────────────────────────────────
        else:
            nombre    = st.text_input("Nombre", placeholder="Tu nombre", key="reg_nombre")
            email     = st.text_input("Correo electrónico", placeholder="tu@correo.com",
                                      key="reg_email")
            password  = st.text_input("Contraseña", type="password",
                                      placeholder="Mínimo 6 caracteres", key="reg_pass")
            password2 = st.text_input("Repite la contraseña", type="password",
                                      placeholder="••••••••", key="reg_pass2")
            if st.button("Crear cuenta", use_container_width=True, type="primary",
                         key="btn_registro"):
                if not (nombre and email and password and password2):
                    st.warning("Rellena todos los campos.")
                elif password != password2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    ok, msg = auth.registrar(email, password, nombre)
                    if ok:
                        if "pendiente" in msg or "administrador" in msg.lower():
                            st.info(f"✅ {msg}")
                        else:
                            st.success(msg)
                    else:
                        st.error(msg)

    st.stop()


# ── Comprobar si la URL lleva un token de reset ───────────────────────────────
_reset_token = st.query_params.get("reset_token", "")
if _reset_token:
    _pantalla_reset_token(_reset_token)

# ── Comprobar sesión ──────────────────────────────────────────────────────────
if "usuario" not in st.session_state:
    _pantalla_auth()

# Botón de cerrar sesión (esquina superior derecha)
with st.container():
    _, _btn_col = st.columns([8, 1])
    with _btn_col:
        if st.button("Salir 🔒", help="Cerrar sesión"):
            for _k in ["usuario", "usuario_email"]:
                st.session_state.pop(_k, None)
            st.rerun()

# ─── PANEL DE ADMINISTRACIÓN (solo admin) ────────────────────────────────────
_email_sesion = st.session_state.get("usuario_email", "")
if auth.is_admin(_email_sesion):
    st.markdown("---")
    st.markdown(f"""
<div style="background:#1A2E4A;border-radius:14px;padding:18px 28px;margin-bottom:18px;">
  <span style="color:#fff;font-size:1.15rem;font-weight:700;">🔑 Panel de administración</span>
  <span style="color:rgba(255,255,255,0.65);font-size:0.85rem;margin-left:12px;">
    {_email_sesion}
  </span>
</div>
""", unsafe_allow_html=True)

    _tab_pend, _tab_reset, _tab_usuarios = st.tabs([
        "⏳ Solicitudes de acceso",
        "🔑 Recuperaciones de contraseña",
        "👥 Todos los usuarios",
    ])

    # ── Solicitudes pendientes ────────────────────────────────────────────────
    with _tab_pend:
        _pending = auth.get_pending_users()
        if not _pending:
            st.success("✅ No hay solicitudes pendientes.")
        else:
            st.markdown(f"**{len(_pending)} solicitud(es) esperando tu aprobación:**")
            for _u in _pending:
                _col_info, _col_apr, _col_rec = st.columns([3, 1, 1])
                with _col_info:
                    st.markdown(
                        f"**{_u['nombre'] or '(sin nombre)'}**  \n"
                        f"<span style='color:#5a7490;font-size:0.85rem'>{_u['email']}</span>",
                        unsafe_allow_html=True,
                    )
                with _col_apr:
                    if st.button("✅ Aprobar", key=f"apr_{_u['email']}", use_container_width=True):
                        auth.approve_user(_u["email"])
                        st.success(f"Aprobado: {_u['email']}")
                        st.rerun()
                with _col_rec:
                    if st.button("❌ Rechazar", key=f"rec_{_u['email']}", use_container_width=True):
                        auth.reject_user(_u["email"])
                        st.warning(f"Rechazado: {_u['email']}")
                        st.rerun()
                st.divider()

    # ── Recuperaciones de contraseña pendientes ───────────────────────────────
    with _tab_reset:
        _resets = auth.get_reset_requests()
        if not _resets:
            st.success("✅ No hay solicitudes de cambio de contraseña pendientes.")
        else:
            st.markdown(f"**{len(_resets)} solicitud(es) de nueva contraseña:**")
            for _u in _resets:
                _col_info, _col_apr, _col_rec = st.columns([3, 1, 1])
                with _col_info:
                    st.markdown(
                        f"**{_u['nombre'] or '(sin nombre)'}**  \n"
                        f"<span style='color:#5a7490;font-size:0.85rem'>{_u['email']}</span>",
                        unsafe_allow_html=True,
                    )
                with _col_apr:
                    if st.button("✅ Aprobar", key=f"rapr_{_u['email']}", use_container_width=True):
                        auth.approve_reset(_u["email"])
                        st.success(f"Contraseña actualizada: {_u['email']}")
                        st.rerun()
                with _col_rec:
                    if st.button("❌ Rechazar", key=f"rrec_{_u['email']}", use_container_width=True):
                        auth.reject_reset(_u["email"])
                        st.warning(f"Solicitud descartada: {_u['email']}")
                        st.rerun()
                st.divider()

    # ── Todos los usuarios ────────────────────────────────────────────────────
    with _tab_usuarios:
        _all = auth.get_all_users()
        _STATUS_LABEL = {
            "approved": "✅ Aprobado",
            "pending":  "⏳ Pendiente",
            "rejected": "❌ Rechazado",
        }
        if not _all:
            st.info("Aún no hay usuarios registrados.")
        else:
            for _u in _all:
                _is_me = _u["email"] == auth.ADMIN_EMAIL
                _col_i, _col_s, _col_act = st.columns([3, 1.2, 1.4])
                with _col_i:
                    _reset_badge = "  🔑 *reset pendiente*" if _u.get("pending_reset") else ""
                    st.markdown(
                        f"**{_u['nombre'] or '(sin nombre)'}**{_reset_badge}  \n"
                        f"<span style='color:#5a7490;font-size:0.85rem'>{_u['email']}"
                        f"{'  👑 admin' if _is_me else ''}</span>",
                        unsafe_allow_html=True,
                    )
                with _col_s:
                    _sl = _STATUS_LABEL.get(_u["status"], _u["status"])
                    st.markdown(f"<br><span style='font-size:0.9rem'>{_sl}</span>",
                                unsafe_allow_html=True)
                with _col_act:
                    if not _is_me:
                        if _u["status"] == "approved":
                            if st.button("🚫 Suspender", key=f"sus_{_u['email']}", use_container_width=True):
                                auth.reject_user(_u["email"])
                                st.rerun()
                        elif _u["status"] in ("pending", "rejected"):
                            if st.button("✅ Activar", key=f"act_{_u['email']}", use_container_width=True):
                                auth.approve_user(_u["email"])
                                st.rerun()
                        if st.button("🗑️ Eliminar", key=f"del_{_u['email']}", use_container_width=True):
                            auth.delete_user(_u["email"])
                            st.rerun()
                    # Establecer contraseña manual (disponible para todos, incluido admin)
                    with st.expander("🔐 Cambiar contraseña", expanded=False):
                        _np1 = st.text_input("Nueva contraseña", type="password",
                                             key=f"np1_{_u['email']}", placeholder="Mín. 6 caracteres")
                        _np2 = st.text_input("Repite", type="password",
                                             key=f"np2_{_u['email']}", placeholder="••••••••")
                        if st.button("Guardar", key=f"npbtn_{_u['email']}", use_container_width=True):
                            if not _np1 or not _np2:
                                st.warning("Rellena ambos campos.")
                            elif _np1 != _np2:
                                st.error("No coinciden.")
                            elif len(_np1) < 6:
                                st.error("Mínimo 6 caracteres.")
                            else:
                                auth.set_password(_u["email"], _np1)
                                st.success("✅ Contraseña actualizada.")
                                st.rerun()
                st.divider()

    st.markdown("---")

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
    <h1>Debajo del hórreo</h1>
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
    p1, p2 = st.columns([1, 2])
    with p1:
        umbral_sug = st.slider(
            "Margen de ajuste sugerido (%)", 5, 50, 20,
            help=(
                "Si añadiendo hasta este % más de cajas a un envío se consigue "
                "un precio por caja más barato (cambio de tramo), la app lo sugiere. "
                "Con 20% solo propone ajustes de hasta +20% de cajas."
            ),
        )
    with p2:
        if _productos_disponibles:
            _prods_dict   = _datos.get("productos", {})
            _prods_adr    = [p for p in _productos_disponibles if _prods_dict.get(p, {}).get("adr", False)]
            _prods_std    = [p for p in _productos_disponibles if not _prods_dict.get(p, {}).get("adr", False)]
            _tiene_adr    = bool(_prods_adr)
            _tiene_adr_tarifa = "transporte_peso_adr" in _datos

            if _tiene_adr:
                _adr_status = (
                    "✅ Tarifas ADR cargadas" if _tiene_adr_tarifa
                    else "⚠️ Sin tarifas ADR en el Excel — se usarán tarifas estándar"
                )
                st.markdown(
                    f"<span style='background:#C0392B;color:#fff;border-radius:6px;"
                    f"padding:2px 9px;font-size:0.8rem;font-weight:700;'>⚠️ ADR</span>"
                    f"&nbsp; {' · '.join(_prods_adr)}"
                    f"<br><span style='color:#888;font-size:0.78rem;'>{_adr_status}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("")
            if _prods_std:
                st.markdown("**Productos estándar:**")
                st.caption(" · ".join(_prods_std))

valor_caja = None   # se usa el valor_caja del catálogo por producto
logistics.DATOS["umbral_cercano_pct"] = umbral_sug / 100

st.markdown("<br>", unsafe_allow_html=True)

# ─── VISTA PREVIA + GUARDADO DEL STOCK ───────────────────────────────────────
if f_stock:
    st.markdown('<p class="section-title">📦 Vista previa — Stock actual</p>',
                unsafe_allow_html=True)
    _file_bytes = f_stock.read()
    f_stock.seek(0)                         # rebobinar para que pd.read_excel funcione
    _df_prev = pd.read_excel(io.BytesIO(_file_bytes))
    _df_prev.columns = _df_prev.columns.str.strip()
    n_filas, n_cols = _df_prev.shape

    _p1, _p2, _p3 = st.columns(3)
    _p1.metric("Filas (almacenes)", n_filas)
    _p2.metric("Columnas (productos)",
               n_cols - 1 if "ALMACÉN" in _df_prev.columns else n_cols)
    _p3.metric("Total cajas",
               f"{int(_df_prev.select_dtypes('number').sum().sum()):,}")

    st.dataframe(_df_prev, use_container_width=True, height=280)

    # ── Guardar con nombre ────────────────────────────────────────────────────
    st.markdown(f"""
<div style="background:{WHITE};border-radius:12px;padding:18px 22px;
            border:1px solid #D0E4F5;margin-top:12px;">
  <span style="color:{NAVY};font-weight:700;font-size:0.95rem;">
    💾 Guardar esta subida en el historial
  </span>
</div>""", unsafe_allow_html=True)

    _sc1, _sc2 = st.columns([3, 1])
    with _sc1:
        _nombre_subida = st.text_input(
            "Nombre de la subida",
            placeholder='Ej: "Inventario semana 17" o "Cierre abril 2026"',
            key="nombre_subida",
            label_visibility="collapsed",
        )
    with _sc2:
        if st.button("💾 Guardar", use_container_width=True, type="primary",
                     key="btn_guardar_stock"):
            if not _nombre_subida.strip():
                st.warning("Ponle un nombre antes de guardar.")
            else:
                _usuario_actual = st.session_state.get("usuario", "desconocido")
                _entrada = uploads_manager.guardar_subida(
                    _nombre_subida, _usuario_actual, _file_bytes
                )
                st.success(
                    f"✅ Guardado como **{_entrada['nombre']}** "
                    f"({_entrada['fecha']})"
                )

    st.markdown("<br>", unsafe_allow_html=True)

# ─── HISTORIAL DE SUBIDAS DE STOCK ───────────────────────────────────────────
_historial = uploads_manager.get_historial()
if _historial:
    with st.expander(f"🗂️ Historial de subidas de stock ({len(_historial)})", expanded=False):
        for _h in _historial:
            _hc1, _hc2, _hc3, _hc4 = st.columns([3, 1.5, 1, 1])
            with _hc1:
                st.markdown(
                    f"**{_h['nombre']}**  \n"
                    f"<span style='color:#5a7490;font-size:0.82rem;'>"
                    f"👤 {_h['usuario']} &nbsp;·&nbsp; 📅 {_h['fecha']}</span>",
                    unsafe_allow_html=True,
                )
            with _hc2:
                _hbytes = uploads_manager.get_bytes(_h["filename"])
                if _hbytes:
                    st.download_button(
                        "⬇️ Descargar",
                        data=_hbytes,
                        file_name=f"{_h['nombre']}.xlsx",
                        mime=XLSX_MIME,
                        key=f"dl_{_h['id']}",
                        use_container_width=True,
                    )
            with _hc3:
                if st.button("📂 Cargar", key=f"load_{_h['id']}", use_container_width=True,
                             help="Usar este archivo para el análisis"):
                    _hbytes2 = uploads_manager.get_bytes(_h["filename"])
                    if _hbytes2:
                        st.session_state["stock_historial_bytes"] = _hbytes2
                        st.session_state["stock_historial_nombre"] = _h["nombre"]
                        st.rerun()
            with _hc4:
                if auth.is_admin(st.session_state.get("usuario_email", "")):
                    if st.button("🗑️", key=f"del_{_h['id']}", use_container_width=True,
                                 help="Eliminar del historial"):
                        uploads_manager.eliminar_subida(_h["filename"])
                        st.rerun()
            st.divider()

    # Si se ha seleccionado un archivo del historial, usarlo como f_stock activo
    if "stock_historial_bytes" in st.session_state and not f_stock:
        _nombre_hist = st.session_state.get("stock_historial_nombre", "historial")
        st.info(f"📂 Usando subida del historial: **{_nombre_hist}**")
        f_stock = io.BytesIO(st.session_state["stock_historial_bytes"])

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


# ─── VISTA INTEGRADA STOCK ↔ ENVÍOS ─────────────────────────────────────────
if f_stock and f_envios:
    st.markdown('<p class="section-title">🔗 Integración Stock → Envíos</p>',
                unsafe_allow_html=True)

    # Leer ambos archivos para la integración
    _df_stock_int  = leer_stock(f_stock)
    _df_envios_int = leer_envios(f_envios)

    _integ = logistics.integrar_stock_envios(_df_stock_int, _df_envios_int)

    # ── Alertas de stock insuficiente ─────────────────────────────────────────
    if _integ["alertas"]:
        for _al in _integ["alertas"]:
            st.markdown(f"""
<div style="background:#FFF0F0;border-left:4px solid #C0392B;border-radius:10px;
            padding:12px 18px;margin-bottom:6px;">
  ⚠️ <b>{_al['producto']}</b> — Stock disponible: <b>{_al['disponible']:,}</b> cajas ·
  Planificado enviar: <b>{_al['a_enviar']:,}</b> cajas ·
  <span style="color:#C0392B;font-weight:700;">Déficit: {_al['deficit']:,} cajas</span>
</div>""", unsafe_allow_html=True)

    # ── Tabla de stock: disponible → a enviar → restante ─────────────────────
    _prods_con_mov = {p for p in set(_integ["cajas_a_enviar"]) if _integ["cajas_a_enviar"].get(p, 0) > 0}
    if _prods_con_mov:
        _rows_integ = []
        for _p in sorted(_prods_con_mov):
            _disp = _integ["stock_central"].get(_p, 0)
            _env  = _integ["cajas_a_enviar"].get(_p, 0)
            _rest = _integ["stock_restante"].get(_p, 0)
            _rows_integ.append({
                "Producto":         _p,
                "Stock disponible": _disp,
                "A enviar":         _env,
                "Stock restante":   _rest,
                "Estado":           "✅ OK" if _rest >= 0 else f"❌ Faltan {abs(_rest)}",
            })
        _df_integ = pd.DataFrame(_rows_integ)

        def _color_estado(val):
            if "❌" in str(val):
                return "background-color:#FFF0F0;color:#C0392B;font-weight:700"
            return "background-color:#E8F8F2;color:#1A9E6E;font-weight:700"

        st.dataframe(
            _df_integ.style.applymap(_color_estado, subset=["Estado"]),
            use_container_width=True,
            hide_index=True,
        )

    # ── Coste del almacén central (Madrid) sobre stock restante ──────────────
    _dias_alm = st.number_input(
        "Días de almacenaje en Madrid a calcular",
        min_value=1, max_value=90, value=30, step=1,
        key="dias_almacen_central",
        help="Se aplica sobre el stock que QUEDA en Madrid tras los envíos planificados",
    )
    _coste_central = logistics.calcular_coste_almacen_central(
        _integ["stock_restante"], dias=int(_dias_alm), valor_por_caja=None
    )

    if _coste_central["total"] > 0:
        # Coste de los envíos (transport + regional)
        with st.spinner("Calculando coste de envíos…"):
            _df_res_int = logistics.analizar_hoja_envios(_df_envios_int, valor_por_caja=None)
        _coste_envios_total = _df_res_int["Coste_total"].sum()
        _factura_total      = _coste_central["total"] + _coste_envios_total

        st.markdown(f"""
<div style="background:linear-gradient(135deg,{NAVY} 0%,{BLUE} 100%);
            border-radius:14px;padding:22px 28px;margin:14px 0;">
  <div style="color:rgba(255,255,255,0.8);font-size:0.82rem;font-weight:700;
              text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">
    💶 Factura logística total de la semana
  </div>
  <div style="display:flex;gap:32px;flex-wrap:wrap;">
    <div>
      <div style="color:rgba(255,255,255,0.65);font-size:0.8rem;">
        Almacén central Madrid ({_dias_alm} días)
      </div>
      <div style="color:#fff;font-size:1.5rem;font-weight:700;">
        {_coste_central['total']:,.2f} €
      </div>
    </div>
    <div style="color:rgba(255,255,255,0.4);font-size:1.8rem;align-self:center;">+</div>
    <div>
      <div style="color:rgba(255,255,255,0.65);font-size:0.8rem;">
        Transporte + almacén regional
      </div>
      <div style="color:#fff;font-size:1.5rem;font-weight:700;">
        {_coste_envios_total:,.2f} €
      </div>
    </div>
    <div style="color:rgba(255,255,255,0.4);font-size:1.8rem;align-self:center;">=</div>
    <div>
      <div style="color:rgba(255,255,255,0.65);font-size:0.8rem;">TOTAL</div>
      <div style="color:#FFD700;font-size:2rem;font-weight:700;">
        {_factura_total:,.2f} €
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        # Desglose por producto del almacén central
        with st.expander("📦 Desglose coste almacén central por producto", expanded=False):
            _rows_mad = []
            for _p, _d in _coste_central["por_producto"].items():
                _rows_mad.append({
                    "Producto":      _p,
                    "Cajas restantes": _d["cajas"],
                    "Volumen (m³)":  _d["volumen_m3"],
                    "Almacenaje":    f"{_d['almacenaje']:.2f} €",
                    "Recepción":     f"{_d['recepcion']:.2f} €",
                    "Manipulación":  f"{_d['manipulacion']:.2f} €",
                    "Total":         f"{_d['coste_total']:.2f} €",
                })
            if _rows_mad:
                st.dataframe(pd.DataFrame(_rows_mad), use_container_width=True,
                             hide_index=True)
            else:
                st.info("No hay stock restante con coste calculable en Madrid.")
    else:
        st.info("No hay stock restante en Madrid tras los envíos planificados, "
                "o los productos enviados no tienen datos de dimensiones.")

    st.markdown("<br>", unsafe_allow_html=True)

# ─── ANÁLISIS ─────────────────────────────────────────────────────────────────
st.markdown('<p class="section-title">📊 Análisis</p>', unsafe_allow_html=True)
tabs = st.tabs(["📦 Stock", "📥 Llegadas", "📤 Envíos & Optimización", "💰 Comparador de precios"])

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
        df_result = logistics.analizar_hoja_envios(df_envios_raw, valor_por_caja=None)

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
    _hay_adr_envios = df_result["ADR"].any() if "ADR" in df_result.columns else False
    cols_show = (
        ["Fecha", "Producto", "ADR", "Cajas", "Provincia", "Modalidad",
         "Coste_transporte", "Coste_almacen", "Coste_total",
         "Coste_por_caja", "Cerca_de_optimo", "Sugerencia_cajas", "Sugerencia_ahorro"]
        if _hay_adr_envios
        else
        ["Fecha", "Producto", "Cajas", "Provincia", "Modalidad",
         "Coste_transporte", "Coste_almacen", "Coste_total",
         "Coste_por_caja", "Cerca_de_optimo", "Sugerencia_cajas", "Sugerencia_ahorro"]
    )
    df_display = df_result[[c for c in cols_show if c in df_result.columns]].copy()
    if "ADR" in df_display.columns:
        df_display["ADR"] = df_display["ADR"].map({True: "⚠️ ADR", False: ""})

    def color_cerca(val):
        return "background-color: #FFF8E7; color: #7A5200" if val is True else ""

    _fmt = {
        "Coste_transporte":  "{:.2f} €",
        "Coste_almacen":     "{:.2f} €",
        "Coste_total":       "{:.2f} €",
        "Coste_por_caja":    "{:.3f} €",
        "Sugerencia_ahorro": lambda v: f"{v:.2f} €" if pd.notna(v) else "—",
        "Sugerencia_cajas":  lambda v: f"{int(v)}"  if pd.notna(v) else "—",
    }
    styled = df_display.style.format(_fmt).applymap(color_cerca, subset=["Cerca_de_optimo"])
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

            df_nuevo    = logistics.analizar_hoja_envios(df_ajustado, valor_por_caja=None)
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


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — COMPARADOR DE PRECIOS
# ══════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    if not f_envios:
        st.info("Sube el archivo de **envíos planificados** para usar el comparador.")
        st.stop()

    # Reutilizamos el resultado del análisis si ya existe, si no lo calculamos
    if "df_result_cmp" not in st.session_state or st.button(
        "🔄 Recalcular", key="cmp_recalc", help="Vuelve a leer el archivo de envíos"
    ):
        _df_env_cmp = leer_envios(f_envios)
        _df_res_cmp = logistics.analizar_hoja_envios(_df_env_cmp, valor_por_caja=None)
        st.session_state["df_result_cmp"]  = _df_res_cmp
        st.session_state["df_envios_cmp"]  = _df_env_cmp
        st.session_state["cmp_decisiones"] = {}

    df_res_cmp  = st.session_state["df_result_cmp"]
    df_env_cmp  = st.session_state["df_envios_cmp"]

    if "cmp_decisiones" not in st.session_state:
        st.session_state["cmp_decisiones"] = {}

    coste_original = df_res_cmp["Coste_total"].sum()
    cajas_original = df_res_cmp["Cajas"].sum()

    # ── Resumen de la factura semanal ─────────────────────────────────────────
    st.markdown(f"""
<div style="background:linear-gradient(135deg,{NAVY} 0%,{BLUE} 100%);
            border-radius:14px;padding:22px 28px;margin-bottom:20px;">
  <span style="color:rgba(255,255,255,0.8);font-size:0.82rem;font-weight:700;
               text-transform:uppercase;letter-spacing:1px;">
    Factura semanal — plan actual
  </span>
  <div style="display:flex;gap:40px;margin-top:10px;flex-wrap:wrap;">
    <div>
      <div style="color:rgba(255,255,255,0.65);font-size:0.8rem;">Coste total</div>
      <div style="color:#fff;font-size:1.8rem;font-weight:700;">
        {coste_original:,.2f} €
      </div>
    </div>
    <div>
      <div style="color:rgba(255,255,255,0.65);font-size:0.8rem;">Total cajas</div>
      <div style="color:#fff;font-size:1.8rem;font-weight:700;">
        {int(cajas_original):,}
      </div>
    </div>
    <div>
      <div style="color:rgba(255,255,255,0.65);font-size:0.8rem;">Nº de envíos</div>
      <div style="color:#fff;font-size:1.8rem;font-weight:700;">
        {len(df_res_cmp)}
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Filtrar envíos con margen de mejora ───────────────────────────────────
    _mejorables = df_res_cmp[df_res_cmp["Cerca_de_optimo"] == True].copy()
    _ya_optimos = df_res_cmp[df_res_cmp["Cerca_de_optimo"] != True].copy()

    _ahorro_max_total = _mejorables["Sugerencia_ahorro"].fillna(0).sum()

    if _mejorables.empty:
        st.success("✅ Todos los envíos ya están en el tramo óptimo. No hay nada que ajustar.")
        st.stop()

    st.markdown(f"""
<div style="background:#FFF8E7;border-radius:10px;padding:14px 20px;
            border-left:4px solid #F0A500;margin-bottom:16px;">
  Se han detectado <b>{len(_mejorables)} envíos</b> que podrían mejorarse.
  El ahorro potencial máximo es <b>{_ahorro_max_total:,.2f} €</b>
  si aceptas todos los ajustes sugeridos.
</div>
""", unsafe_allow_html=True)

    # ── Revisión uno a uno ────────────────────────────────────────────────────
    st.markdown(f'<p class="section-title">🔍 Revisa cada envío mejorable</p>',
                unsafe_allow_html=True)

    _ahorro_acumulado = 0.0
    _decisiones       = st.session_state["cmp_decisiones"]

    for _pos, (idx, row) in enumerate(_mejorables.iterrows()):
        _sug_list = row.get("_sugerencias_full") or []
        if not _sug_list:
            continue
        _sug     = _sug_list[0]
        _dec_key = f"cmp_{idx}"
        _dec     = _decisiones.get(_dec_key)   # None / "aceptar" / "rechazar" / int(cajas)

        # Calcular ahorro de este envío si se acepta
        _ahorro_este = _sug.get("ahorro_total_estimado", 0)
        if isinstance(_dec, int):
            # Recalcular ahorro con cajas personalizadas
            _pct_extra = (_dec - row["Cajas"]) / max(row["Cajas"], 1)
            _ahorro_este = _ahorro_este * min(_pct_extra / max(
                (_sug["cajas_sugeridas"] - row["Cajas"]) / max(row["Cajas"], 1), 0.001), 1)

        if _dec == "aceptar":
            _ahorro_acumulado += _sug.get("ahorro_total_estimado", 0)
        elif isinstance(_dec, int):
            _ahorro_acumulado += max(_ahorro_este, 0)

        # Color de fondo según decisión
        _bg = ("#E8F8F2" if _dec == "aceptar"
               else "#FFF0F0" if _dec == "rechazar"
               else WHITE)
        _border = ("#1A9E6E" if _dec == "aceptar"
                   else "#C0392B" if _dec == "rechazar"
                   else "#D0E4F5")

        st.markdown(f"""
<div style="background:{_bg};border:1.5px solid {_border};border-radius:12px;
            padding:18px 22px;margin-bottom:4px;">
  <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">
    <div>
      <span style="color:{NAVY};font-weight:700;font-size:1rem;">
        {_pos+1}. {row['Producto']} → {row['Provincia']}
      </span>
      <span style="color:#5a7490;font-size:0.82rem;margin-left:10px;">
        📅 {str(row['Fecha'])[:10]}
      </span>
    </div>
    <div style="text-align:right;">
      <span style="color:{NAVY};font-size:0.85rem;">
        Coste actual: <b>{row['Coste_total']:.2f} €</b>
        ({row['Cajas']} cajas · {row['Coste_por_caja']:.3f} €/caja)
      </span>
    </div>
  </div>
  <div style="margin-top:10px;background:rgba(26,46,74,0.05);
              border-radius:8px;padding:10px 14px;">
    🎯 <b>Sugerencia:</b> aumentar a <b>{_sug['cajas_sugeridas']} cajas</b>
    (+{_sug['cajas_extra']} · +{_sug['pct_mas']:.1f}%) →
    nuevo coste/caja <b>{_sug['coste_por_caja_nuevo']:.3f} €</b> ·
    ahorro <b>{_sug['ahorro_total_estimado']:.2f} €</b><br>
    <span style="color:#5a7490;font-size:0.82rem;">{_sug['motivo']}</span>
  </div>
</div>
""", unsafe_allow_html=True)

        # Botones de decisión
        _ba, _bb, _bc, _bd = st.columns([1.2, 1.2, 2, 1.5])
        with _ba:
            if st.button("✅ Aceptar", key=f"cmp_si_{idx}", use_container_width=True):
                _decisiones[_dec_key] = "aceptar"
                st.session_state["cmp_decisiones"] = _decisiones
                st.rerun()
        with _bb:
            if st.button("❌ Mantener", key=f"cmp_no_{idx}", use_container_width=True):
                _decisiones[_dec_key] = "rechazar"
                st.session_state["cmp_decisiones"] = _decisiones
                st.rerun()
        with _bc:
            _custom_val = st.number_input(
                "Cajas personalizadas:",
                min_value=int(row["Cajas"]),
                max_value=100000,
                value=int(_sug["cajas_sugeridas"]),
                step=1,
                key=f"cmp_custom_{idx}",
                label_visibility="collapsed",
            )
        with _bd:
            if st.button("📐 Usar este número", key=f"cmp_custom_btn_{idx}",
                         use_container_width=True):
                _decisiones[_dec_key] = int(_custom_val)
                st.session_state["cmp_decisiones"] = _decisiones
                st.rerun()

        st.markdown("")

    # ── Resumen en tiempo real ────────────────────────────────────────────────
    _n_revisados  = len([d for d in _decisiones.values() if d is not None])
    _n_aceptados  = len([d for d in _decisiones.values() if d == "aceptar"])
    _n_custom     = len([d for d in _decisiones.values() if isinstance(d, int)])
    _n_rechazados = len([d for d in _decisiones.values() if d == "rechazar"])
    _nuevo_total  = coste_original - _ahorro_acumulado

    st.markdown("---")
    st.markdown(f'<p class="section-title">📊 Resumen de la negociación</p>',
                unsafe_allow_html=True)

    _rc1, _rc2, _rc3, _rc4 = st.columns(4)
    _rc1.metric("Coste original",      f"{coste_original:,.2f} €")
    _rc2.metric("Ahorro conseguido",   f"{_ahorro_acumulado:,.2f} €",
                delta=f"-{_ahorro_acumulado:,.2f} €" if _ahorro_acumulado > 0 else None,
                delta_color="inverse")
    _rc3.metric("Nueva factura",       f"{_nuevo_total:,.2f} €")
    _rc4.metric("Envíos ajustados",    f"{_n_aceptados + _n_custom} de {len(_mejorables)}")

    # Barra de progreso del ahorro
    _pct_ahorro = (_ahorro_acumulado / _ahorro_max_total * 100) if _ahorro_max_total > 0 else 0
    st.markdown(f"""
<div style="margin:8px 0 4px 0;color:{NAVY};font-size:0.85rem;font-weight:600;">
  Ahorro conseguido: {_pct_ahorro:.0f}% del máximo posible ({_ahorro_max_total:,.2f} €)
</div>
<div style="background:#D0E4F5;border-radius:8px;height:12px;overflow:hidden;">
  <div style="background:{LBLUE};width:{min(_pct_ahorro,100):.0f}%;height:100%;
              border-radius:8px;transition:width 0.3s;"></div>
</div>
""", unsafe_allow_html=True)

    # ── Plan ajustado y descarga ──────────────────────────────────────────────
    if _n_aceptados + _n_custom > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        _df_ajustado_cmp = df_env_cmp.copy()
        for _idx2, _dec2 in _decisiones.items():
            _real_idx = int(_idx2.replace("cmp_", ""))
            if _dec2 == "aceptar":
                _sug2 = df_res_cmp.at[_real_idx, "_sugerencias_full"]
                if _sug2:
                    _df_ajustado_cmp.at[_real_idx, "Cajas"] = _sug2[0]["cajas_sugeridas"]
            elif isinstance(_dec2, int):
                _df_ajustado_cmp.at[_real_idx, "Cajas"] = _dec2

        _df_nuevo_cmp = logistics.analizar_hoja_envios(_df_ajustado_cmp, valor_por_caja=None)
        _cols_exp = ["Fecha", "Producto", "Cajas", "Provincia",
                     "Modalidad", "Coste_total", "Coste_por_caja"]

        st.markdown("### 📋 Plan ajustado")
        st.dataframe(
            _df_nuevo_cmp[_cols_exp].style.format({
                "Coste_total":    "{:.2f} €",
                "Coste_por_caja": "{:.3f} €",
            }),
            use_container_width=True,
        )

        _buf_cmp = io.BytesIO()
        with pd.ExcelWriter(_buf_cmp, engine="openpyxl") as _wr:
            _df_nuevo_cmp[_cols_exp].to_excel(_wr, sheet_name="Plan optimizado", index=False)
            df_res_cmp[_cols_exp].to_excel(_wr, sheet_name="Plan original",    index=False)
        _buf_cmp.seek(0)
        st.download_button(
            "📥 Descargar plan optimizado (.xlsx)",
            data=_buf_cmp,
            file_name="plan_comparado_optimizado.xlsx",
            mime=XLSX_MIME,
            use_container_width=True,
        )
