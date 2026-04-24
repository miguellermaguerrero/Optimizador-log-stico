# 🚚 Optimizador Logístico — Instrucciones de Despliegue

## Estructura del proyecto
```
logistics_app/
├── app.py               ← Aplicación principal Streamlit
├── config.py            ← Tarifas y configuración de productos (editar aquí)
├── logistics.py         ← Motor de cálculo (no tocar salvo mejoras)
├── requirements.txt     ← Dependencias Python
├── plantilla_stock.xlsx     ← Plantilla de stock para subir a la app
├── plantilla_llegadas.xlsx  ← Plantilla de llegadas
└── plantilla_envios.xlsx    ← Plantilla de envíos planificados
```

---

## ▶️ Ejecutar en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

Se abrirá el navegador en http://localhost:8501

---

## 🌐 Desplegar gratis en Streamlit Cloud

1. Crea una cuenta en https://share.streamlit.io (gratuita)
2. Sube esta carpeta a un repositorio GitHub público o privado
3. En Streamlit Cloud → "New app" → selecciona el repo → archivo: `app.py`
4. Haz clic en "Deploy" → en ~2 minutos tendrás la URL pública

---

## ⚙️ Personalización

### Cambiar productos reales
Edita `config.py` → diccionario `PRODUCTOS`:
```python
PRODUCTOS = {
    "Nombre real":  {"largo_cm": X, "ancho_cm": X, "alto_cm": X, "peso_kg": X.X, "uds_por_caja": X},
    ...
}
```

### Actualizar tarifas
Edita las tablas `TRANSPORTE_PESO`, `TARIFA_PALE_PROVINCIA`, `TRANSPORTE_MULTIPALE`, etc. en `config.py`.

### Ajustar el umbral de sugerencias
En la app lateral hay un slider, o cámbialo permanentemente en `config.py` → `UMBRAL_CERCANO_PCT`.

---

## 📋 Formato de los archivos Excel

### plantilla_stock.xlsx
| Producto | Almacen_Central | Madrid | Barcelona | ... |
|----------|-----------------|--------|-----------|-----|
| Producto A | 500 | 120 | 80 | ... |

### plantilla_llegadas.xlsx
| Fecha | Producto | Cajas |
|-------|----------|-------|
| 2024-05-01 | Producto A | 300 |

### plantilla_envios.xlsx
| Fecha | Producto | Cajas | Provincia | Zona |
|-------|----------|-------|-----------|------|
| 2024-05-10 | Producto A | 120 | Barcelona | peninsula |

`Zona` puede ser `peninsula` o `baleares`.
