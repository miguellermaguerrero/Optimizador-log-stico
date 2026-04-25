"""
auth.py — Gestión de usuarios y sesión.
Guarda los usuarios en users.json en la misma carpeta.
Las contraseñas se almacenan como hash SHA-256 (nunca en texto plano).

Estados de cuenta:
  "approved"      → puede entrar
  "pending"       → solicitud de registro en espera de aprobación
  "rejected"      → solicitud rechazada

Campo adicional opcional:
  "pending_reset" → nueva contraseña (hasheada) en espera de aprobación del admin
                    (para el admin, el reset se aplica inmediatamente)
"""
from __future__ import annotations
import json
import hashlib
import re
import secrets
import time
from pathlib import Path

USERS_FILE   = Path(__file__).parent / "users.json"
TOKENS_FILE  = Path(__file__).parent / "reset_tokens.json"
ADMIN_EMAIL  = "lermaguerreromiguel@gmail.com"
TOKEN_TTL    = 3600  # segundos (1 hora)


# ─── Almacenamiento ──────────────────────────────────────────────────────────

def _load_users() -> dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_users(users: dict) -> None:
    USERS_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


# ─── API pública ─────────────────────────────────────────────────────────────

def registrar(email: str, password: str, nombre: str = "") -> tuple[bool, str]:
    """
    Registra un nuevo usuario.
    - El admin queda aprobado automáticamente.
    - El resto quedan en estado 'pending' hasta que el admin los apruebe.
    Devuelve (ok, mensaje).
    """
    email = email.strip().lower()
    if not _valid_email(email):
        return False, "El correo electrónico no es válido."
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    users = _load_users()
    if email in users:
        existing = users[email]
        if existing.get("status") == "pending":
            return False, "Ya existe una solicitud pendiente con este correo."
        if existing.get("status") == "rejected":
            return False, "Esta solicitud fue rechazada. Contacta con el administrador."
        return False, "Este correo ya está registrado."

    status = "approved" if email == ADMIN_EMAIL else "pending"
    users[email] = {
        "password": _hash(password),
        "nombre":   nombre.strip(),
        "status":   status,
    }
    _save_users(users)

    if status == "approved":
        return True, "Cuenta creada. Ya puedes iniciar sesión."
    return True, "Solicitud enviada. El administrador revisará tu cuenta en breve."


def login(email: str, password: str) -> tuple[bool, str]:
    """
    Verifica credenciales y estado de la cuenta.
    Devuelve (ok, nombre_o_mensaje).
    """
    email = email.strip().lower()
    users = _load_users()

    if email not in users:
        return False, "Correo no encontrado."

    user = users[email]

    if user["password"] != _hash(password):
        return False, "Contraseña incorrecta."

    status = user.get("status", "approved")  # retrocompatibilidad
    if status == "pending":
        return False, "Tu cuenta está pendiente de aprobación por el administrador."
    if status == "rejected":
        return False, "Tu solicitud de acceso fue rechazada. Contacta con el administrador."

    nombre = user.get("nombre") or email
    return True, nombre


def is_admin(email: str) -> bool:
    return email.strip().lower() == ADMIN_EMAIL


# ─── Tokens de recuperación por enlace ───────────────────────────────────────

def _load_tokens() -> dict:
    if TOKENS_FILE.exists():
        try:
            return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_tokens(tokens: dict) -> None:
    TOKENS_FILE.write_text(
        json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _purge_expired_tokens(tokens: dict) -> dict:
    now = time.time()
    return {t: d for t, d in tokens.items() if d.get("expires", 0) > now}


def generate_reset_token(email: str) -> tuple[bool, str]:
    """
    Genera un token seguro de un solo uso para recuperar contraseña.
    Devuelve (ok, token_o_mensaje_error).
    """
    email = email.strip().lower()
    users = _load_users()
    if email not in users:
        # Por seguridad devolvemos ok=True para no revelar si el correo existe
        return True, "__not_found__"

    token = secrets.token_urlsafe(32)
    tokens = _load_tokens()
    tokens = _purge_expired_tokens(tokens)
    tokens[token] = {"email": email, "expires": time.time() + TOKEN_TTL}
    _save_tokens(tokens)
    return True, token


def verify_reset_token(token: str) -> tuple[bool, str]:
    """
    Verifica si el token es válido y no ha expirado.
    Devuelve (ok, email_o_mensaje_error).
    """
    tokens = _load_tokens()
    tokens = _purge_expired_tokens(tokens)
    _save_tokens(tokens)

    data = tokens.get(token)
    if not data:
        return False, "El enlace no es válido o ha caducado."
    return True, data["email"]


def consume_reset_token(token: str, new_password: str) -> tuple[bool, str]:
    """
    Aplica la nueva contraseña si el token es válido y lo elimina.
    Devuelve (ok, mensaje).
    """
    if len(new_password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    ok, result = verify_reset_token(token)
    if not ok:
        return False, result

    email = result
    users = _load_users()
    if email not in users:
        return False, "Usuario no encontrado."

    users[email]["password"] = _hash(new_password)
    users[email].pop("pending_reset", None)
    _save_users(users)

    # Invalidar el token
    tokens = _load_tokens()
    tokens.pop(token, None)
    _save_tokens(tokens)

    return True, "Contraseña actualizada correctamente. Ya puedes iniciar sesión."


# ─── Recuperación de contraseña (flujo admin) ────────────────────────────────

def solicitar_reset(email: str, new_password: str) -> tuple[bool, str]:
    """
    Solicita el cambio de contraseña.
    - Admin: se aplica inmediatamente.
    - Otros: queda en espera de aprobación (campo pending_reset).
    Devuelve (ok, mensaje).
    """
    email = email.strip().lower()
    if not _valid_email(email):
        return False, "El correo electrónico no es válido."
    if len(new_password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    users = _load_users()
    if email not in users:
        return False, "No existe ninguna cuenta con ese correo."

    if email == ADMIN_EMAIL:
        # El admin se resetea directamente
        users[email]["password"] = _hash(new_password)
        users[email].pop("pending_reset", None)
        _save_users(users)
        return True, "Contraseña actualizada. Ya puedes iniciar sesión."

    # Para el resto: guardar solicitud en espera
    users[email]["pending_reset"] = _hash(new_password)
    _save_users(users)
    return True, "Solicitud enviada. El administrador aprobará el cambio en breve."


def get_reset_requests() -> list[dict]:
    """Devuelve usuarios que tienen una solicitud de reset pendiente."""
    users = _load_users()
    return [
        {"email": e, "nombre": d.get("nombre", ""), "status": d.get("status", "")}
        for e, d in users.items()
        if "pending_reset" in d
    ]


def approve_reset(email: str) -> bool:
    """Aprueba y aplica la nueva contraseña solicitada. Devuelve True si tuvo éxito."""
    email = email.strip().lower()
    users = _load_users()
    if email not in users or "pending_reset" not in users[email]:
        return False
    users[email]["password"] = users[email].pop("pending_reset")
    _save_users(users)
    return True


def reject_reset(email: str) -> bool:
    """Descarta la solicitud de cambio de contraseña. Devuelve True si tuvo éxito."""
    email = email.strip().lower()
    users = _load_users()
    if email not in users:
        return False
    users[email].pop("pending_reset", None)
    _save_users(users)
    return True


def set_password(email: str, new_password: str) -> bool:
    """
    El admin establece directamente la contraseña de cualquier usuario.
    Devuelve True si tuvo éxito.
    """
    email = email.strip().lower()
    if len(new_password) < 6:
        return False
    users = _load_users()
    if email not in users:
        return False
    users[email]["password"] = _hash(new_password)
    users[email].pop("pending_reset", None)
    _save_users(users)
    return True


# ─── Funciones de administración de usuarios ─────────────────────────────────

def get_pending_users() -> list[dict]:
    """Devuelve la lista de usuarios con status='pending'."""
    users = _load_users()
    return [
        {"email": e, "nombre": d.get("nombre", ""), "status": d.get("status", "")}
        for e, d in users.items()
        if d.get("status") == "pending"
    ]


def get_all_users() -> list[dict]:
    """Devuelve todos los usuarios con sus metadatos (sin contraseña)."""
    users = _load_users()
    return [
        {
            "email":         e,
            "nombre":        d.get("nombre", ""),
            "status":        d.get("status", "approved"),
            "pending_reset": "pending_reset" in d,
        }
        for e, d in users.items()
    ]


def approve_user(email: str) -> bool:
    """Aprueba la cuenta de un usuario. Devuelve True si tuvo éxito."""
    email = email.strip().lower()
    users = _load_users()
    if email not in users:
        return False
    users[email]["status"] = "approved"
    _save_users(users)
    return True


def reject_user(email: str) -> bool:
    """Rechaza la cuenta de un usuario. Devuelve True si tuvo éxito."""
    email = email.strip().lower()
    users = _load_users()
    if email not in users:
        return False
    users[email]["status"] = "rejected"
    _save_users(users)
    return True


def delete_user(email: str) -> bool:
    """Elimina completamente un usuario. Devuelve True si tuvo éxito."""
    email = email.strip().lower()
    if email == ADMIN_EMAIL:
        return False  # No se puede borrar el admin
    users = _load_users()
    if email not in users:
        return False
    del users[email]
    _save_users(users)
    return True


def n_usuarios() -> int:
    return len(_load_users())
