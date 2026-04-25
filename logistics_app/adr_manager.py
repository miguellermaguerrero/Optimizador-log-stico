"""
adr_manager.py — Maestro de productos ADR.

Guarda en logistics_app/adr_config.json qué productos son ADR.
Este fichero sobreescribe lo que venga en el catálogo Excel.
"""
from __future__ import annotations
import json
from pathlib import Path

_CONFIG_FILE = Path(__file__).parent / "adr_config.json"


def _load() -> dict[str, bool]:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict[str, bool]) -> None:
    _CONFIG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_adr_map() -> dict[str, bool]:
    """Devuelve {nombre_producto: es_adr} para todos los productos guardados."""
    return _load()


def set_adr(producto: str, es_adr: bool) -> None:
    """Marca o desmarca un producto como ADR."""
    data = _load()
    data[producto] = es_adr
    _save(data)


def set_adr_bulk(mapping: dict[str, bool]) -> None:
    """Sobreescribe el estado ADR de varios productos a la vez."""
    data = _load()
    data.update(mapping)
    _save(data)


def aplicar_sobre_productos(productos: dict) -> dict:
    """
    Mezcla el maestro ADR (JSON) con el dict de productos cargado del catálogo.
    El JSON tiene prioridad sobre la columna del Excel.
    Devuelve el mismo dict modificado in-place.
    """
    adr_map = _load()
    for nombre, prod in productos.items():
        if nombre in adr_map:
            prod["adr"] = adr_map[nombre]
    return productos
