"""
auth.py — Gestión de usuarios y sesión.
Guarda los usuarios en users.json en la misma carpeta.
Las contraseñas se almacenan como hash SHA-256 (nunca en texto plano).
"""
from __future__ import annotations
import json
import hashlib
import re
from pathlib import Path

USERS_FILE = Path(__file__).parent / "users.json"


def _load_users() -> dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_users(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def registrar(email: str, password: str, nombre: str = "") -> tuple[bool, str]:
    """Registra un nuevo usuario. Devuelve (ok, mensaje)."""
    email = email.strip().lower()
    if not _valid_email(email):
        return False, "El correo electrónico no es válido."
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."
    users = _load_users()
    if email in users:
        return False, "Este correo ya está registrado."
    users[email] = {"password": _hash(password), "nombre": nombre.strip()}
    _save_users(users)
    return True, "Cuenta creada correctamente. Ya puedes iniciar sesión."


def login(email: str, password: str) -> tuple[bool, str]:
    """Verifica credenciales. Devuelve (ok, nombre_o_mensaje)."""
    email = email.strip().lower()
    users = _load_users()
    if email not in users:
        return False, "Correo no encontrado."
    if users[email]["password"] != _hash(password):
        return False, "Contraseña incorrecta."
    nombre = users[email].get("nombre") or email
    return True, nombre


def n_usuarios() -> int:
    return len(_load_users())
