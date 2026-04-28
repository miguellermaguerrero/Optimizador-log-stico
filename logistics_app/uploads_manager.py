"""
uploads_manager.py — Gestión del historial de subidas de archivos.

Guarda cada archivo subido en:
  logistics_app/stock_uploads/<timestamp>_<slug>.xlsx

Y un registro en:
  logistics_app/stock_uploads/log.json

con campos: id, nombre, fecha, usuario, filename, seccion, tipo
tipo puede ser: "stock", "llegadas" o "envios"
"""
from __future__ import annotations
import json
import re
import time
from datetime import datetime
from pathlib import Path

UPLOADS_DIR = Path(__file__).parent / "stock_uploads"
LOG_FILE    = UPLOADS_DIR / "log.json"


def _ensure_dir() -> None:
    UPLOADS_DIR.mkdir(exist_ok=True)


def _slug(texto: str) -> str:
    """Convierte un nombre libre en un slug seguro para usar como nombre de archivo."""
    texto = texto.strip().lower()
    texto = re.sub(r"[^\w\s-]", "", texto, flags=re.UNICODE)
    texto = re.sub(r"[\s_]+", "_", texto)
    return texto[:40] or "sin_nombre"


def _load_log() -> list[dict]:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_log(entries: list[dict]) -> None:
    _ensure_dir()
    LOG_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─── API pública ─────────────────────────────────────────────────────────────

def guardar_subida(nombre: str, usuario: str, file_bytes: bytes,
                   seccion: str = "", tipo: str = "stock") -> dict:
    """
    Guarda el archivo xlsx y registra la subida en el log.
    tipo puede ser: "stock", "llegadas" o "envios"
    Devuelve el diccionario de la entrada creada.
    """
    _ensure_dir()
    ts       = int(time.time())
    slug     = _slug(nombre)
    filename = f"{ts}_{slug}.xlsx"
    filepath = UPLOADS_DIR / filename

    filepath.write_bytes(file_bytes)

    entrada = {
        "id":       ts,
        "nombre":   nombre.strip(),
        "usuario":  usuario,
        "fecha":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "filename": filename,
        "seccion":  seccion,
        "tipo":     tipo,
    }
    entries = _load_log()
    entries.insert(0, entrada)   # más reciente primero
    _save_log(entries)
    return entrada


def get_historial() -> list[dict]:
    """Devuelve todas las subidas registradas, de más reciente a más antigua."""
    return _load_log()


def get_historial_seccion(seccion: str) -> list[dict]:
    """Devuelve las subidas de una sección concreta, de más reciente a más antigua."""
    return [e for e in _load_log() if e.get("seccion", "") == seccion]


def get_historial_seccion_tipo(seccion: str, tipo: str) -> list[dict]:
    """Devuelve las subidas de una sección y tipo concretos."""
    return [e for e in _load_log()
            if e.get("seccion", "") == seccion and e.get("tipo", "stock") == tipo]


def get_fechas_subida_seccion(seccion: str) -> set[str]:
    """Devuelve el conjunto de fechas (YYYY-MM-DD) con subidas para una sección."""
    fechas = set()
    for e in get_historial_seccion(seccion):
        try:
            fechas.add(e["fecha"][:10])
        except Exception:
            pass
    return fechas


def get_bytes(filename: str) -> bytes | None:
    """Devuelve los bytes del archivo guardado, o None si no existe."""
    path = UPLOADS_DIR / filename
    if path.exists():
        return path.read_bytes()
    return None


def eliminar_subida(filename: str) -> bool:
    """Elimina un archivo y su entrada del log. Devuelve True si tuvo éxito."""
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()

    entries = [e for e in _load_log() if e.get("filename") != filename]
    _save_log(entries)
    return True
