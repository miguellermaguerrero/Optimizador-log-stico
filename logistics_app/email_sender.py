"""
email_sender.py — Envío de correos para recuperación de contraseña.

Configuración necesaria en Streamlit secrets (.streamlit/secrets.toml):

    [email]
    smtp_server   = "smtp.gmail.com"
    smtp_port     = 587
    sender_email  = "tu_correo@gmail.com"
    sender_password = "xxxx xxxx xxxx xxxx"   # contraseña de aplicación de Gmail
    app_url       = "https://tu-app.streamlit.app"

Para crear una contraseña de aplicación en Gmail:
  1. Ve a myaccount.google.com → Seguridad → Verificación en dos pasos (actívala)
  2. Vuelve a Seguridad → Contraseñas de aplicaciones
  3. Genera una para "Correo" / "Otro" y cópiala aquí
"""
from __future__ import annotations
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    import streamlit as st
    def _secret(section: str, key: str, default: str = "") -> str:
        try:
            return st.secrets[section][key]
        except Exception:
            return default
except ImportError:
    def _secret(section: str, key: str, default: str = "") -> str:
        return default


def send_reset_email(to_email: str, token: str) -> tuple[bool, str]:
    """
    Envía un correo con el enlace de recuperación de contraseña.
    Devuelve (ok, mensaje_de_error_o_vacio).
    """
    smtp_server    = _secret("email", "smtp_server",    "smtp.gmail.com")
    smtp_port      = int(_secret("email", "smtp_port",  "587"))
    sender_email   = _secret("email", "sender_email",   "")
    sender_password = _secret("email", "sender_password", "")
    app_url        = _secret("email", "app_url",         "").rstrip("/")

    if not sender_email or not sender_password:
        return False, "El servidor de correo no está configurado. Contacta con el administrador."
    if not app_url:
        return False, "La URL de la aplicación no está configurada en los secretos."

    reset_link = f"{app_url}/?reset_token={token}"

    # ── Construir mensaje ────────────────────────────────────────────────────
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Recuperación de contraseña — Debajo del hórreo"
    msg["From"]    = f"Debajo del hórreo <{sender_email}>"
    msg["To"]      = to_email

    texto_plano = (
        f"Hola,\n\n"
        f"Recibimos una solicitud para restablecer tu contraseña.\n\n"
        f"Haz clic en el siguiente enlace (válido 1 hora):\n{reset_link}\n\n"
        f"Si no solicitaste este cambio, ignora este correo.\n\n"
        f"— Debajo del hórreo"
    )

    texto_html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#EBF2FA;padding:32px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:14px;
              padding:36px 40px;box-shadow:0 4px 20px rgba(26,46,74,0.12);">
    <div style="text-align:center;margin-bottom:24px;">
      <span style="font-size:2rem;">🏪</span>
      <h2 style="color:#1A2E4A;margin:8px 0 4px 0;">Debajo del hórreo</h2>
      <p style="color:#5a7490;font-size:0.9rem;margin:0;">Recuperación de contraseña</p>
    </div>
    <p style="color:#333;line-height:1.6;">
      Recibimos una solicitud para restablecer la contraseña de tu cuenta.<br>
      Haz clic en el botón de abajo para elegir una nueva contraseña.<br>
      <strong>El enlace es válido durante 1 hora.</strong>
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{reset_link}"
         style="background:#1A2E4A;color:#fff;padding:14px 32px;border-radius:8px;
                text-decoration:none;font-weight:700;font-size:1rem;display:inline-block;">
        Cambiar contraseña
      </a>
    </div>
    <p style="color:#888;font-size:0.8rem;text-align:center;">
      Si no solicitaste este cambio, ignora este correo.
    </p>
  </div>
</body>
</html>
"""

    msg.attach(MIMEText(texto_plano, "plain", "utf-8"))
    msg.attach(MIMEText(texto_html,  "html",  "utf-8"))

    # ── Enviar ───────────────────────────────────────────────────────────────
    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación SMTP. Revisa la contraseña de aplicación de Gmail."
    except smtplib.SMTPException as e:
        return False, f"Error al enviar el correo: {e}"
    except Exception as e:
        return False, f"Error inesperado: {e}"
