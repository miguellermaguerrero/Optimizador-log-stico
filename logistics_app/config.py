"""
config.py — Configuración física y ajustes de la app.
Las tarifas y el catálogo de productos se cargan desde Excel (ver data_loader.py).
Solo edita este archivo para cambiar dimensiones del palé o el umbral de sugerencias.
"""

from pathlib import Path

# ── Rutas a los Excel (relativas a la carpeta del proyecto, un nivel arriba) ───
BASE_DIR = Path(__file__).parent.parent

TARIFAS_PATH  = BASE_DIR / "tarifas_logisticas.xlsx"
CATALOGO_PATH = BASE_DIR / "catalogo_productos.xlsx"

# ── Palé estándar (Europalet) ─────────────────────────────────────────────────
PALE_LARGO_CM    = 120
PALE_ANCHO_CM    = 80
PALE_ALTO_MAX_CM = 170
PALE_PESO_MAX_KG = 1000

# ── Umbral "cerca del óptimo" ─────────────────────────────────────────────────
# Si añadiendo hasta X% más de cajas bajas de tramo, la app sugiere el ajuste.
UMBRAL_CERCANO_PCT = 0.20   # 20 %
