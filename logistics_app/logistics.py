"""
logistics.py — Motor de cálculo logístico
Contiene todas las funciones de coste y optimización.

Los datos de tarifas se inyectan desde fuera mediante set_datos(dict).
Esto permite que app.py cargue los valores desde los archivos Excel sin
necesidad de tocar este módulo.
"""

import math
import numpy as np
import pandas as pd
from config import (
    PALE_LARGO_CM, PALE_ANCHO_CM, PALE_ALTO_MAX_CM, PALE_PESO_MAX_KG,
    UMBRAL_CERCANO_PCT,
)

# ── Dict de datos de tarifas (se rellena al arrancar la app) ──────────────────
DATOS: dict = {}


def set_datos(datos: dict) -> None:
    """Inyecta el dict de tarifas cargado desde Excel. Llamar una vez al inicio."""
    DATOS.clear()
    DATOS.update(datos)


def _datos_ok() -> bool:
    return bool(DATOS)


# ─── Geometría del palé ───────────────────────────────────────────────────────

def cajas_por_pale(producto: dict) -> int:
    cajas_x = max(1, PALE_LARGO_CM // producto["largo_cm"])
    cajas_y = max(1, PALE_ANCHO_CM  // producto["ancho_cm"])
    capas   = max(1, PALE_ALTO_MAX_CM // producto["alto_cm"])
    por_geo  = cajas_x * cajas_y * capas
    por_peso = max(1, int(PALE_PESO_MAX_KG / producto["peso_kg"]))
    return max(1, min(por_geo, por_peso))


def volumen_m3_caja(producto: dict) -> float:
    return (producto["largo_cm"] * producto["ancho_cm"] * producto["alto_cm"]) / 1_000_000


# ─── Transporte ──────────────────────────────────────────────────────────────

def coste_transp_peso(peso_kg: float, zona: str = "peninsula") -> float | None:
    """
    Devuelve el coste de transporte por peso.
    Devuelve None si la zona es 'baleares' y el peso supera el límite de su tabla.
    """
    tabla = DATOS.get("transporte_peso", [])
    if not tabla:
        raise RuntimeError("Datos de tarifas no cargados. Llama a set_datos() primero.")

    # Baleares solo llega hasta baleares_kg_max (normalmente 200 kg)
    baleares_max = DATOS.get("baleares_kg_max", 200.0)
    if zona != "peninsula" and peso_kg > baleares_max:
        return None  # forzar palé — no hay tarifa por peso

    col = 1 if zona == "peninsula" else 2  # índice del precio en cada tramo

    for tramo in tabla:
        if peso_kg <= tramo[0]:
            precio = tramo[col]
            if precio is None:
                return None
            return precio

    # Último tramo (el más pesado)
    precio = tabla[-1][col]
    return precio if precio is not None else None


def coste_pale_unitario(provincia: str) -> float:
    """Devuelve el precio por palé individual para la provincia dada."""
    tarifas = DATOS.get("tarifa_pale_provincia", {})
    if not tarifas:
        raise RuntimeError("Datos de tarifas no cargados. Llama a set_datos() primero.")

    prov_upper = provincia.strip().upper()
    precio = tarifas.get(prov_upper)
    if precio is None:
        # Fallback: media peninsular
        precio = tarifas.get("PENINSULA_MEDIA", 0.0)
    return precio


def coste_multipale(num_pales: int, peso_kg: float, provincia: str = "") -> float | None:
    """
    Tarifa de carga completa (a partir de 5 palés) por provincia.
    Devuelve None si no hay tarifa aplicable o el volumen supera el máximo.
    """
    if num_pales < 5:
        return None

    cargas = DATOS.get("cargas_completas", {})
    if not cargas:
        return None

    prov_upper = provincia.strip().upper()
    prov_data  = cargas.get(prov_upper)

    if not prov_data:
        # Provincia no encontrada en la tabla de cargas completas
        return None

    # Iterar los tramos ordenados por nº de palés (ascendente)
    for n_pales_tier in sorted(prov_data.keys()):
        tier = prov_data[n_pales_tier]
        if num_pales <= n_pales_tier and peso_kg <= tier["kg_max"]:
            return tier["precio"]

    # Supera el mayor tramo → usar el máximo disponible
    max_tier = prov_data[max(prov_data.keys())]
    return max_tier["precio"]


def calcular_transporte(num_cajas: int, producto: dict,
                         provincia: str = "PENINSULA_MEDIA",
                         zona: str = "peninsula") -> dict:
    peso   = num_cajas * producto["peso_kg"]
    cpale  = cajas_por_pale(producto)
    npales = max(1, math.ceil(num_cajas / cpale))
    opciones = {}

    # Opción 1: por peso (solo si el peso está dentro de la tabla)
    tabla = DATOS.get("transporte_peso", [])
    peninsula_kg_max = tabla[-1][0] if tabla else 1000.0
    baleares_kg_max  = DATOS.get("baleares_kg_max", 200.0)
    peso_max_zona    = baleares_kg_max if zona != "peninsula" else peninsula_kg_max

    if peso <= peso_max_zona:
        coste_peso = coste_transp_peso(peso, zona)
        if coste_peso is not None:
            opciones["Por peso"] = coste_peso

    # Opción 2: palés individuales
    opciones["Palés individuales"] = npales * coste_pale_unitario(provincia)

    # Opción 3: carga completa (multi-palé), solo si aplica
    mp = coste_multipale(npales, peso, provincia)
    if mp is not None:
        opciones["Multi-palé"] = mp

    mejor = min(opciones, key=opciones.get)
    return {
        "coste": opciones[mejor],
        "modalidad": mejor,
        "opciones": opciones,
        "num_pales": npales,
        "peso_kg": peso,
        "cajas_por_pale": cpale,
    }


# ─── Almacén regional ────────────────────────────────────────────────────────

def tarifa_regional_por_caja(num_cajas: int) -> float:
    tramos = DATOS.get("almacen_regional_cajas", [])
    if not tramos:
        raise RuntimeError("Datos de tarifas no cargados. Llama a set_datos() primero.")
    for cajas_max, precio in tramos:
        if num_cajas <= cajas_max:
            return precio
    return tramos[-1][1]


def coste_almacen_regional(num_cajas: int, valor_mercancia: float,
                             num_pedidos: int = 1) -> dict:
    tarifa = tarifa_regional_por_caja(num_cajas)
    rec_caja  = DATOS.get("almacen_regional_recepcion_caja", 0.63)
    manip_ped = DATOS.get("almacen_regional_manipulacion_pedido", 8.20)
    seguro_pct = DATOS.get("almacen_regional_seguro_pct", 0.0008)

    alm    = num_cajas * tarifa
    rec    = num_cajas * rec_caja
    manip  = num_pedidos * manip_ped
    seguro = valor_mercancia * seguro_pct
    total  = alm + rec + manip + seguro
    return {
        "total": total,
        "almacenaje": alm,
        "recepcion": rec,
        "manipulacion": manip,
        "seguro": seguro,
        "tarifa_caja": tarifa,
    }


# ─── Almacén Madrid ──────────────────────────────────────────────────────────

def coste_almacen_madrid(num_cajas: int, producto: dict,
                          dias: int = 30, num_pedidos: int = 1) -> dict:
    mad = DATOS.get("almacen_madrid", {})
    if not mad:
        raise RuntimeError("Datos de tarifas no cargados. Llama a set_datos() primero.")

    vol   = volumen_m3_caja(producto) * num_cajas
    peso  = num_cajas * producto["peso_kg"]
    alm   = vol * dias * mad.get("almacenaje_m3_dia", 0.17)
    rec   = peso * mad.get("recepcion_kg", 0.01)
    manip = (num_pedidos * mad.get("manipulados_pedido", 0.53) +
             num_cajas   * mad.get("manipulados_unidad_bulto", 0.12))
    gest  = num_pedidos  * mad.get("gestion_admin_pedido", 0.43)
    total = alm + rec + manip + gest
    return {"total": total, "almacenaje_m3": alm, "recepcion": rec,
            "manipulacion": manip, "gestion": gest, "volumen_m3": vol}


# ─── Coste total de un envío ──────────────────────────────────────────────────

def coste_envio_completo(num_cajas: int, producto: dict,
                          provincia: str, zona: str = "peninsula",
                          valor_por_caja: float = 50.0,
                          num_pedidos: int = 1) -> dict:
    tr  = calcular_transporte(num_cajas, producto, provincia, zona)
    alm = coste_almacen_regional(num_cajas, num_cajas * valor_por_caja, num_pedidos)
    total = tr["coste"] + alm["total"]
    return {
        "total": total,
        "por_caja": total / num_cajas if num_cajas > 0 else 0,
        "transporte": tr,
        "almacen": alm,
    }


# ─── Curva óptima por producto + provincia ────────────────────────────────────

ESCENARIOS = [5, 10, 20, 50, 100, 150, 200, 250, 300, 400,
               500, 700, 1000, 1500, 2000, 3000, 5000, 7000, 10000]


def curva_costes(producto: dict, provincia: str = "PENINSULA_MEDIA",
                 zona: str = "peninsula", valor_por_caja: float = 50.0) -> pd.DataFrame:
    filas = []
    for n in ESCENARIOS:
        r = coste_envio_completo(n, producto, provincia, zona, valor_por_caja)
        filas.append({
            "cajas": n,
            "coste_total": r["total"],
            "coste_por_caja": r["por_caja"],
            "modalidad": r["transporte"]["modalidad"],
            "num_pales": r["transporte"]["num_pales"],
            "tarifa_almacen": r["almacen"]["tarifa_caja"],
        })
    return pd.DataFrame(filas)


def punto_optimo(producto: dict, provincia: str = "PENINSULA_MEDIA",
                 zona: str = "peninsula", valor_por_caja: float = 50.0) -> dict:
    df  = curva_costes(producto, provincia, zona, valor_por_caja)
    idx = df["coste_por_caja"].idxmin()
    row = df.loc[idx]
    return {
        "cajas_optimas": int(row["cajas"]),
        "coste_por_caja": float(row["coste_por_caja"]),
        "coste_total": float(row["coste_total"]),
        "modalidad": row["modalidad"],
        "curva": df,
    }


# ─── Análisis de un envío concreto + sugerencia de ajuste ────────────────────

def analizar_envio(num_cajas: int, nombre_producto: str,
                   provincia: str, zona: str = "peninsula",
                   valor_por_caja: float = 50.0,
                   num_pedidos: int = 1) -> dict:
    """
    Calcula el coste de un envío y detecta si está lejos de un punto óptimo.
    Devuelve: coste actual, comparativa con óptimo, sugerencias de ajuste.
    """
    productos = DATOS.get("productos", {})
    prod = productos.get(nombre_producto)
    if prod is None:
        raise ValueError(
            f"Producto '{nombre_producto}' no encontrado en el catálogo. "
            "Comprueba que el nombre coincide exactamente con el de catalogo_productos.xlsx."
        )

    umbral = DATOS.get("umbral_cercano_pct", UMBRAL_CERCANO_PCT)

    actual = coste_envio_completo(num_cajas, prod, provincia, zona, valor_por_caja, num_pedidos)
    curva  = curva_costes(prod, provincia, zona, valor_por_caja)

    quiebres = _detectar_quiebres(curva)

    sugerencias = []
    for q in quiebres:
        diff_cajas = q["cajas"] - num_cajas
        diff_pct   = diff_cajas / num_cajas if num_cajas > 0 else 0
        if 0 < diff_pct <= umbral:
            ahorro_x_caja = actual["por_caja"] - q["coste_por_caja"]
            ahorro_total  = ahorro_x_caja * q["cajas"]
            sugerencias.append({
                "cajas_sugeridas": q["cajas"],
                "cajas_extra": diff_cajas,
                "pct_mas": diff_pct * 100,
                "coste_por_caja_nuevo": q["coste_por_caja"],
                "ahorro_por_caja": ahorro_x_caja,
                "ahorro_total_estimado": ahorro_total,
                "motivo": q["motivo"],
            })

    opt = punto_optimo(prod, provincia, zona, valor_por_caja)

    return {
        "producto": nombre_producto,
        "cajas": num_cajas,
        "provincia": provincia,
        "actual": actual,
        "optimo_global": opt,
        "sugerencias_ajuste": sugerencias,
        "curva": curva,
    }


def _detectar_quiebres(curva: pd.DataFrame) -> list:
    """Detecta los puntos donde baja coste/caja (cambios de tramo)."""
    quiebres = []
    prev_cporcaja  = None
    prev_tarifa    = None
    prev_modalidad = None

    for _, row in curva.iterrows():
        n   = int(row["cajas"])
        cpc = float(row["coste_por_caja"])
        tar = float(row["tarifa_almacen"])
        mod = row["modalidad"]

        if prev_cporcaja is not None and cpc < prev_cporcaja:
            motivos = []
            if tar < prev_tarifa:
                motivos.append(f"baja tarifa almacén ({prev_tarifa:.3f}→{tar:.3f} €/caja)")
            if mod != prev_modalidad:
                motivos.append(f"cambia transporte a '{mod}'")
            quiebres.append({
                "cajas": n,
                "coste_por_caja": cpc,
                "motivo": "; ".join(motivos) if motivos else "economía de escala",
            })

        prev_cporcaja  = cpc
        prev_tarifa    = tar
        prev_modalidad = mod

    return quiebres


# ─── Análisis de toda la hoja de envíos ──────────────────────────────────────

def analizar_hoja_envios(df_envios: pd.DataFrame,
                          valor_por_caja: float = 50.0) -> pd.DataFrame:
    """
    Recibe el DataFrame de envíos y devuelve uno enriquecido con
    costes, óptimos y alertas de ajuste.
    Columnas esperadas: Fecha, Producto, Cajas, Provincia, [Zona]
    """
    resultados = []
    for _, row in df_envios.iterrows():
        try:
            zona = str(row.get("Zona", "peninsula")).lower()
            res  = analizar_envio(
                num_cajas        = int(row["Cajas"]),
                nombre_producto  = str(row["Producto"]),
                provincia        = str(row["Provincia"]),
                zona             = zona,
                valor_por_caja   = valor_por_caja,
            )
            act  = res["actual"]
            opt  = res["optimo_global"]
            sug  = res["sugerencias_ajuste"]

            resultados.append({
                "Fecha":              row.get("Fecha", ""),
                "Producto":           res["producto"],
                "Cajas":              res["cajas"],
                "Provincia":          res["provincia"],
                "Modalidad":          act["transporte"]["modalidad"],
                "Coste_transporte":   round(act["transporte"]["coste"], 2),
                "Coste_almacen":      round(act["almacen"]["total"], 2),
                "Coste_total":        round(act["total"], 2),
                "Coste_por_caja":     round(act["por_caja"], 3),
                "Optimo_cajas":       opt["cajas_optimas"],
                "Optimo_coste_caja":  round(opt["coste_por_caja"], 3),
                "Ahorro_potencial":   round((act["por_caja"] - opt["coste_por_caja"]) * res["cajas"], 2),
                "Cerca_de_optimo":    len(sug) > 0,
                "Sugerencia_cajas":   sug[0]["cajas_sugeridas"] if sug else None,
                "Sugerencia_ahorro":  round(sug[0]["ahorro_total_estimado"], 2) if sug else None,
                "Sugerencia_motivo":  sug[0]["motivo"] if sug else "",
                "_sugerencias_full":  sug,
                "_curva":             res["curva"],
            })
        except Exception as e:
            resultados.append({
                "Fecha": row.get("Fecha", ""),
                "Producto": row.get("Producto", "?"),
                "Cajas": row.get("Cajas", 0),
                "Provincia": row.get("Provincia", "?"),
                "Modalidad": "ERROR",
                "Coste_transporte": 0, "Coste_almacen": 0, "Coste_total": 0,
                "Coste_por_caja": 0, "Optimo_cajas": 0, "Optimo_coste_caja": 0,
                "Ahorro_potencial": 0, "Cerca_de_optimo": False,
                "Sugerencia_cajas": None, "Sugerencia_ahorro": None,
                "Sugerencia_motivo": str(e),
                "_sugerencias_full": [], "_curva": None,
            })
    return pd.DataFrame(resultados)
