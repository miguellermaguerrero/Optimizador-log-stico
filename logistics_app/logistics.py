"""
logistics.py — Motor de cálculo logístico
Contiene todas las funciones de coste y optimización.

Los datos de tarifas se inyectan desde fuera mediante set_datos(dict).
Esto permite que app.py cargue los valores desde los archivos Excel sin
necesidad de tocar este módulo.
"""
from __future__ import annotations

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

def coste_transp_peso(peso_kg: float, zona: str = "peninsula",
                       es_adr: bool = False) -> float | None:
    """
    Devuelve el coste de transporte por peso.
    Si es_adr=True y existen tarifas ADR cargadas, las usa en lugar de las normales.
    Devuelve None si la zona es 'baleares' y el peso supera el límite de su tabla.
    """
    tabla_key = (
        "transporte_peso_adr"
        if es_adr and "transporte_peso_adr" in DATOS
        else "transporte_peso"
    )
    tabla = DATOS.get(tabla_key, [])
    if not tabla:
        raise RuntimeError("Datos de tarifas no cargados. Llama a set_datos() primero.")

    baleares_key = "baleares_kg_max_adr" if es_adr and "baleares_kg_max_adr" in DATOS else "baleares_kg_max"
    baleares_max = DATOS.get(baleares_key, 200.0)
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


def coste_pale_unitario(provincia: str, es_adr: bool = False) -> float:
    """
    Devuelve el precio por palé individual para la provincia dada.
    Si es_adr=True y existen tarifas de palé ADR, las usa.
    """
    tarifa_key = (
        "tarifa_pale_provincia_adr"
        if es_adr and "tarifa_pale_provincia_adr" in DATOS
        else "tarifa_pale_provincia"
    )
    tarifas = DATOS.get(tarifa_key) or DATOS.get("tarifa_pale_provincia", {})
    if not tarifas:
        raise RuntimeError("Datos de tarifas no cargados. Llama a set_datos() primero.")

    prov_upper = provincia.strip().upper()
    precio = tarifas.get(prov_upper)
    if precio is None:
        # Fallback: media peninsular
        precio = tarifas.get("PENINSULA_MEDIA", 0.0)
    return precio


def coste_multipale(num_pales: int, peso_kg: float, provincia: str = "",
                    es_adr: bool = False) -> float | None:
    """
    Tarifa de carga completa (a partir de 5 palés) por provincia.
    Si es_adr=True y existen tarifas de carga completa ADR, las usa.
    Devuelve None si no hay tarifa aplicable o el volumen supera el máximo.
    """
    if num_pales < 5:
        return None

    cargas_key = (
        "cargas_completas_adr"
        if es_adr and "cargas_completas_adr" in DATOS
        else "cargas_completas"
    )
    cargas = DATOS.get(cargas_key) or DATOS.get("cargas_completas", {})
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
    es_adr = producto.get("adr", False)
    peso   = num_cajas * producto["peso_kg"]
    cpale  = cajas_por_pale(producto)
    npales = max(1, math.ceil(num_cajas / cpale))
    opciones = {}

    # Opción 1: por peso — usa tabla ADR si el producto es ADR
    tabla_key        = "transporte_peso_adr" if es_adr and "transporte_peso_adr" in DATOS else "transporte_peso"
    tabla            = DATOS.get(tabla_key, DATOS.get("transporte_peso", []))
    baleares_key     = "baleares_kg_max_adr" if es_adr and "baleares_kg_max_adr" in DATOS else "baleares_kg_max"
    peninsula_kg_max = tabla[-1][0] if tabla else 1000.0
    baleares_kg_max  = DATOS.get(baleares_key, 200.0)
    peso_max_zona    = baleares_kg_max if zona != "peninsula" else peninsula_kg_max

    if peso <= peso_max_zona:
        coste_peso = coste_transp_peso(peso, zona, es_adr=es_adr)
        if coste_peso is not None:
            opciones["Por peso"] = coste_peso

    # Opción 2: palés individuales
    opciones["Palés individuales"] = npales * coste_pale_unitario(provincia, es_adr=es_adr)

    # Opción 3: carga completa (multi-palé), solo si aplica
    mp = coste_multipale(npales, peso, provincia, es_adr=es_adr)
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
        "es_adr": es_adr,
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
                          valor_por_caja: float | None = None,
                          num_pedidos: int = 1) -> dict:
    # Usar el valor del catálogo si no se pasa uno explícito
    if valor_por_caja is None or valor_por_caja <= 0:
        valor_por_caja = producto.get("valor_caja", 50.0)
    tr  = calcular_transporte(num_cajas, producto, provincia, zona)
    alm = coste_almacen_regional(num_cajas, num_cajas * valor_por_caja, num_pedidos)
    total = tr["coste"] + alm["total"]
    return {
        "total": total,
        "por_caja": total / num_cajas if num_cajas > 0 else 0,
        "transporte": tr,
        "almacen": alm,
        "valor_por_caja": valor_por_caja,
        "es_adr": tr.get("es_adr", False),
    }


# ─── Escenarios inteligentes (basados en quiebres reales de tarifa) ──────────

def _escenarios_relevantes(producto: dict, provincia: str,
                            zona: str, cajas_actuales: int = 0) -> list[int]:
    """
    Calcula los puntos exactos donde cambia la tarifa de transporte o almacén
    para este producto y provincia concreta, asegurando que el optimizador
    evalúa siempre los puntos de quiebre reales y no se los salta.
    """
    puntos: set[int] = set()

    peso_kg = producto.get("peso_kg", 1.0)
    cpale   = cajas_por_pale(producto)

    # ── Base general (puntos sueltos bajos para cobertura mínima) ────────────
    for n in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 25, 30, 40, 50,
              75, 100, 150, 200, 300, 500, 750, 1000, 1500, 2000, 3000,
              5000, 7500, 10000]:
        puntos.add(n)

    # ── Quiebres de transporte por peso → convertir kg_max a cajas ───────────
    tabla = DATOS.get("transporte_peso", [])
    for tramo in tabla:
        kg_max = tramo[0]
        # cajas que llevan exactamente al límite superior del tramo
        cajas_tope  = max(1, math.ceil(kg_max / peso_kg))
        cajas_antes = max(1, math.floor(kg_max / peso_kg))
        for c in [cajas_antes - 1, cajas_antes, cajas_tope, cajas_tope + 1]:
            if c > 0:
                puntos.add(c)

    # ── Quiebres de almacén regional ─────────────────────────────────────────
    for cajas_max, _ in DATOS.get("almacen_regional_cajas", []):
        for delta in [-2, -1, 0, 1, 2]:
            c = cajas_max + delta
            if c > 0:
                puntos.add(c)

    # ── Múltiplos de palé (cambios de nº de palés) ───────────────────────────
    for n_pales in range(1, 16):
        for delta in [-1, 0, 1]:
            c = n_pales * cpale + delta
            if c > 0:
                puntos.add(c)

    # ── Umbral de multi-palé (5 palés) ───────────────────────────────────────
    umbral_mp = 5 * cpale
    for delta in [-2, -1, 0, 1, 2]:
        c = umbral_mp + delta
        if c > 0:
            puntos.add(c)

    # ── Quiebres en cargas completas para esta provincia ─────────────────────
    prov_up   = provincia.strip().upper()
    prov_data = DATOS.get("cargas_completas", {}).get(prov_up, {})
    for n_pales_tier, tier in prov_data.items():
        cajas_tier = n_pales_tier * cpale
        kg_max_tier = tier.get("kg_max", 0)
        cajas_kg    = max(1, math.ceil(kg_max_tier / peso_kg)) if kg_max_tier else 0
        for c in [cajas_tier - 1, cajas_tier, cajas_tier + 1,
                  cajas_kg - 1, cajas_kg, cajas_kg + 1]:
            if c > 0:
                puntos.add(c)

    # ── Asegurar que el valor actual y su entorno siempre están ──────────────
    if cajas_actuales > 0:
        for delta in range(-5, 51):
            c = cajas_actuales + delta
            if c > 0:
                puntos.add(c)
        # Rango hasta +50% con paso 1%
        for pct in range(1, 51):
            c = max(1, round(cajas_actuales * (1 + pct / 100)))
            puntos.add(c)

    return sorted(puntos)


def curva_costes(producto: dict, provincia: str = "PENINSULA_MEDIA",
                 zona: str = "peninsula", valor_por_caja: float | None = None,
                 cajas_actuales: int = 0) -> pd.DataFrame:
    escenarios = _escenarios_relevantes(producto, provincia, zona, cajas_actuales)
    filas = []
    for n in escenarios:
        r = coste_envio_completo(n, producto, provincia, zona, valor_por_caja)
        filas.append({
            "cajas":          n,
            "coste_total":    r["total"],
            "coste_por_caja": r["por_caja"],
            "modalidad":      r["transporte"]["modalidad"],
            "num_pales":      r["transporte"]["num_pales"],
            "tarifa_almacen": r["almacen"]["tarifa_caja"],
        })
    return pd.DataFrame(filas)


def punto_optimo(producto: dict, provincia: str = "PENINSULA_MEDIA",
                 zona: str = "peninsula", valor_por_caja: float | None = None) -> dict:
    df  = curva_costes(producto, provincia, zona, valor_por_caja)
    idx = df["coste_por_caja"].idxmin()
    row = df.loc[idx]
    return {
        "cajas_optimas":  int(row["cajas"]),
        "coste_por_caja": float(row["coste_por_caja"]),
        "coste_total":    float(row["coste_total"]),
        "modalidad":      row["modalidad"],
        "curva":          df,
    }


# ─── Análisis de un envío concreto + sugerencia de ajuste ────────────────────

def analizar_envio(num_cajas: int, nombre_producto: str,
                   provincia: str, zona: str = "peninsula",
                   valor_por_caja: float | None = None,
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
    curva  = curva_costes(prod, provincia, zona, valor_por_caja, cajas_actuales=num_cajas)

    quiebres = _detectar_quiebres(curva, cajas_actuales=num_cajas)

    sugerencias = []
    for q in quiebres:
        diff_cajas = q["cajas"] - num_cajas
        diff_pct   = diff_cajas / num_cajas if num_cajas > 0 else 0
        if 0 < diff_pct <= umbral:
            # Coste real del envío ajustado
            nuevo = coste_envio_completo(
                q["cajas"], prod, provincia, zona, valor_por_caja, num_pedidos
            )
            ahorro_x_caja = actual["por_caja"] - nuevo["por_caja"]
            # Ahorro neto: lo que ahorras en las cajas actuales
            # menos el coste incremental de las cajas extra
            coste_extra_solo = coste_envio_completo(
                diff_cajas, prod, provincia, zona, valor_por_caja, num_pedidos
            )
            ahorro_neto = actual["total"] + coste_extra_solo["total"] - nuevo["total"]

            if ahorro_x_caja > 0:   # solo sugerir si de verdad baja el coste/caja
                sugerencias.append({
                    "cajas_sugeridas":      q["cajas"],
                    "cajas_extra":          diff_cajas,
                    "pct_mas":              diff_pct * 100,
                    "coste_por_caja_nuevo": round(nuevo["por_caja"], 4),
                    "ahorro_por_caja":      round(ahorro_x_caja, 4),
                    "ahorro_total_estimado": round(ahorro_neto, 2),
                    "coste_nuevo_total":    round(nuevo["total"], 2),
                    "motivo":              q["motivo"],
                    "descenso_pct":        round(q["descenso_pct"], 2),
                })

    # Ordenar por ahorro neto descendente
    sugerencias.sort(key=lambda x: x["ahorro_total_estimado"], reverse=True)

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


def _detectar_quiebres(curva: pd.DataFrame, cajas_actuales: int = 0) -> list:
    """
    Detecta todos los puntos donde baja el coste/caja respecto al anterior,
    identificando el motivo del quiebre (tarifa almacén, cambio de modalidad, etc.).
    Solo devuelve quiebres con un descenso mínimo del 0.5% para evitar ruido numérico.
    """
    quiebres      = []
    prev_cporcaja = None
    prev_tarifa   = None
    prev_mod      = None
    prev_n        = None

    for _, row in curva.iterrows():
        n   = int(row["cajas"])
        cpc = float(row["coste_por_caja"])
        tar = float(row["tarifa_almacen"])
        mod = row["modalidad"]

        if prev_cporcaja is not None:
            descenso_pct = (prev_cporcaja - cpc) / prev_cporcaja if prev_cporcaja > 0 else 0
            if cpc < prev_cporcaja and descenso_pct >= 0.005:  # ≥ 0.5% de bajada
                motivos = []
                if tar < (prev_tarifa or 0):
                    motivos.append(
                        f"baja tarifa almacén ({prev_tarifa:.3f} → {tar:.3f} €/caja)"
                    )
                if mod != prev_mod:
                    motivos.append(f"cambia transporte: {prev_mod} → {mod}")
                if not motivos:
                    motivos.append("economía de escala")
                quiebres.append({
                    "cajas":            n,
                    "coste_por_caja":   cpc,
                    "motivo":           "; ".join(motivos),
                    "descenso_pct":     descenso_pct * 100,
                })

        prev_cporcaja = cpc
        prev_tarifa   = tar
        prev_mod      = mod
        prev_n        = n

    return quiebres


# ─── Análisis de toda la hoja de envíos ──────────────────────────────────────

def analizar_hoja_envios(df_envios: pd.DataFrame,
                          valor_por_caja: float | None = None) -> pd.DataFrame:
    """valor_por_caja=None → usa el valor del catálogo de cada producto."""
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
                "Fecha":             row.get("Fecha", ""),
                "Producto":          res["producto"],
                "Cajas":             res["cajas"],
                "Provincia":         res["provincia"],
                "ADR":               act.get("es_adr", False),
                "Modalidad":         act["transporte"]["modalidad"],
                "Coste_transporte":  round(act["transporte"]["coste"], 2),
                "Coste_almacen":     round(act["almacen"]["total"], 2),
                "Coste_total":       round(act["total"], 2),
                "Coste_por_caja":    round(act["por_caja"], 3),
                "Optimo_cajas":      opt["cajas_optimas"],
                "Optimo_coste_caja": round(opt["coste_por_caja"], 3),
                # Ahorro potencial máximo (vs óptimo global) solo sobre las cajas actuales
                "Ahorro_potencial":  round(
                    (act["por_caja"] - opt["coste_por_caja"]) * res["cajas"], 2
                ),
                "Cerca_de_optimo":   len(sug) > 0,
                # La mejor sugerencia (mayor ahorro neto) va primera
                "Sugerencia_cajas":  sug[0]["cajas_sugeridas"] if sug else None,
                "Sugerencia_ahorro": sug[0]["ahorro_total_estimado"] if sug else None,
                "Sugerencia_motivo": sug[0]["motivo"] if sug else "",
                "_sugerencias_full": sug,
                "_curva":            res["curva"],
            })
        except Exception as e:
            resultados.append({
                "Fecha": row.get("Fecha", ""),
                "Producto": row.get("Producto", "?"),
                "Cajas": row.get("Cajas", 0),
                "Provincia": row.get("Provincia", "?"),
                "ADR": False,
                "Modalidad": "ERROR",
                "Coste_transporte": 0, "Coste_almacen": 0, "Coste_total": 0,
                "Coste_por_caja": 0, "Optimo_cajas": 0, "Optimo_coste_caja": 0,
                "Ahorro_potencial": 0, "Cerca_de_optimo": False,
                "Sugerencia_cajas": None, "Sugerencia_ahorro": None,
                "Sugerencia_motivo": str(e),
                "_sugerencias_full": [], "_curva": None,
            })
    return pd.DataFrame(resultados)


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRACIÓN STOCK ↔ ENVÍOS
# ══════════════════════════════════════════════════════════════════════════════

def integrar_stock_envios(df_stock: "pd.DataFrame",
                           df_envios: "pd.DataFrame") -> dict:
    """
    Cruza el stock actual del almacén central con los envíos planificados.

    Parámetros
    ----------
    df_stock  : DataFrame con columna ALMACÉN y una columna por producto.
                La fila de "Central Madrid" (o similar) es la fuente de stock.
    df_envios : DataFrame de envíos con columnas Producto y Cajas.

    Devuelve
    --------
    dict con:
      stock_central      : {producto: cajas disponibles en Central Madrid}
      cajas_a_enviar     : {producto: total cajas planificadas}
      stock_restante     : {producto: stock_central - cajas_a_enviar}
      alertas            : list[dict] con productos donde faltan cajas
      productos_ok       : list[str] con productos con stock suficiente
    """
    # ── Identificar fila del almacén central ─────────────────────────────────
    col_alm = "ALMACÉN" if "ALMACÉN" in df_stock.columns else df_stock.columns[0]
    etiquetas_central = ["central madrid", "madrid", "central", "almacén central"]
    fila_central = None
    for _, fila in df_stock.iterrows():
        etiqueta = str(fila[col_alm]).strip().lower()
        if any(et in etiqueta for et in etiquetas_central):
            fila_central = fila
            break
    if fila_central is None:
        # Fallback: primera fila
        fila_central = df_stock.iloc[0]

    prod_cols = [c for c in df_stock.columns if c != col_alm]
    stock_central: dict[str, int] = {}
    for col in prod_cols:
        v = fila_central.get(col, 0)
        try:
            stock_central[col] = max(0, int(float(v)))
        except (TypeError, ValueError):
            stock_central[col] = 0

    # ── Agregar cajas planificadas por producto ───────────────────────────────
    cajas_a_enviar: dict[str, int] = {}
    if "Producto" in df_envios.columns and "Cajas" in df_envios.columns:
        for prod, grupo in df_envios.groupby("Producto"):
            cajas_a_enviar[str(prod)] = int(grupo["Cajas"].sum())

    # ── Stock restante y alertas ──────────────────────────────────────────────
    todos_prods = set(stock_central) | set(cajas_a_enviar)
    stock_restante: dict[str, int] = {}
    alertas:        list[dict]    = []
    productos_ok:   list[str]     = []

    for prod in sorted(todos_prods):
        disponible = stock_central.get(prod, 0)
        a_enviar   = cajas_a_enviar.get(prod, 0)
        restante   = disponible - a_enviar
        stock_restante[prod] = restante

        if a_enviar == 0:
            continue  # producto no planificado para envío
        if restante < 0:
            alertas.append({
                "producto":   prod,
                "disponible": disponible,
                "a_enviar":   a_enviar,
                "deficit":    abs(restante),
            })
        else:
            productos_ok.append(prod)

    return {
        "stock_central":   stock_central,
        "cajas_a_enviar":  cajas_a_enviar,
        "stock_restante":  stock_restante,
        "alertas":         alertas,
        "productos_ok":    productos_ok,
    }


def calcular_coste_almacen_central(stock_restante: dict[str, int],
                                    dias: int = 30,
                                    valor_por_caja: float | None = None) -> dict:
    """valor_por_caja=None → usa el valor del catálogo de cada producto."""
    """
    Calcula el coste del almacén central de Madrid sobre el stock restante
    tras descontar los envíos planificados.

    Parámetros
    ----------
    stock_restante : {producto: cajas_restantes}  (de integrar_stock_envios)
    dias           : días de almacenaje a considerar (por defecto 30)
    valor_por_caja : valor de la mercancía por caja (para seguro)

    Devuelve
    --------
    dict con:
      total        : coste total del almacén central
      por_producto : {producto: dict con desglose}
      dias         : días usados
    """
    productos_datos = DATOS.get("productos", {})
    por_producto    = {}
    total           = 0.0

    for prod, cajas in stock_restante.items():
        if cajas <= 0:
            continue
        prod_data = productos_datos.get(prod)
        if prod_data is None:
            continue
        try:
            coste = coste_almacen_madrid(
                num_cajas  = cajas,
                producto   = prod_data,
                dias       = dias,
                num_pedidos= 1,
            )
            por_producto[prod] = {
                "cajas":        cajas,
                "coste_total":  round(coste["total"], 2),
                "almacenaje":   round(coste["almacenaje_m3"], 2),
                "recepcion":    round(coste["recepcion"], 2),
                "manipulacion": round(coste["manipulacion"], 2),
                "volumen_m3":   round(coste["volumen_m3"], 3),
            }
            total += coste["total"]
        except Exception:
            pass

    return {
        "total":        round(total, 2),
        "por_producto": por_producto,
        "dias":         dias,
    }
