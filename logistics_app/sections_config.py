"""
sections_config.py — Definición de los apartados de la aplicación.

Para añadir un nuevo apartado, añade un dict a la lista SECTIONS con:
  id          → clave única en snake_case
  nombre      → nombre visible en la tarjeta
  descripcion → subtítulo de la tarjeta
  logos       → lista de archivos de imagen (en la carpeta logistics_app/)
  color       → color principal (hex) de la cabecera del apartado
"""
from __future__ import annotations

SECTIONS: list[dict] = [
    {
        "id":          "prosales_altadis",
        "nombre":      "PROSALES-ALTADIS TR",
        "descripcion": "Tarifas de transporte Prosales · Altadis",
        "logos":       ["logo_prosales.png", "logo_imperial.png", "logo_maydis.png"],
        "color":       "#1A2E4A",
    },
    # Añade aquí futuros apartados:
    # {
    #     "id":          "otro_cliente",
    #     "nombre":      "OTRO CLIENTE",
    #     "descripcion": "Descripción del apartado",
    #     "logos":       ["logo_otro.png", "logo.png"],
    #     "color":       "#2E5F8A",
    # },
]
