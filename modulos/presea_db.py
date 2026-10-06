"""Consultas y updates para clientes Presea (tolerante a migración pendiente)."""

from __future__ import annotations

import os

MIGRATION_FILE = "supabase_migration_presea_clientes.sql"
PRESEA_EXTRA_COLS = frozenset({
    "codigo", "origen", "vendedor", "validado_arca", "validado_nosis",
})
ESTADOS_ACTIVOS_APP = ("Pendiente", "Modificado", "A Exportar")
SUPABASE_PAGE_SIZE = 1000
APP_CODIGO_MIN = 40000
# Próximo código nuevo a asignar (piso). Ajustar si ERP ya consumió hasta 400016.
APP_CODIGO_PROXIMO_PISO = 40017


def _parse_codigo_app(val) -> int | None:
    if val is None or str(val).strip() in ("", "nan", "None"):
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _map_codigos_app_ocupados(supabase) -> dict[int, str]:
    """codigo (>=40000) → id del cliente que lo tiene en Supabase."""
    mapping: dict[int, str] = {}
    offset = 0
    while True:
        res = (
            supabase.table("clientes_pendientes")
            .select("id, codigo")
            .gte("codigo", APP_CODIGO_MIN)
            .order("codigo")
            .range(offset, offset + SUPABASE_PAGE_SIZE - 1)
            .execute()
        )
        rows = res.data or []
        for row in rows:
            cod = _parse_codigo_app(row.get("codigo"))
            if cod is not None:
                mapping[cod] = str(row["id"])
        if len(rows) < SUPABASE_PAGE_SIZE:
            break
        offset += SUPABASE_PAGE_SIZE
    return mapping


def _siguiente_codigo_libre(desde: int, ocupados: set[int]) -> int:
    c = max(desde, APP_CODIGO_MIN, APP_CODIGO_PROXIMO_PISO)
    while c in ocupados:
        c += 1
    return c


def leer_inicio_secuencia_app(supabase) -> int:
    """
    Próximo código libre para altas web (>= 40000).
    Respeta APP_CODIGO_PROXIMO_PISO y no reutiliza códigos ya en clientes_pendientes.
    """
    ocupados = set(_map_codigos_app_ocupados(supabase).keys())
    res = supabase.table("secuencia_codigo").select("ultimo_valor").eq("id", 1).execute()
    ultimo_tabla = 0 if not res.data else int(res.data[0].get("ultimo_valor") or 0)
    max_ocupado = max(ocupados) if ocupados else APP_CODIGO_MIN - 1
    desde = max(ultimo_tabla, max_ocupado) + 1
    return _siguiente_codigo_libre(desde, ocupados)


def fijar_piso_secuencia_app(supabase, ultimo_asignado: int = APP_CODIGO_PROXIMO_PISO - 1) -> int:
    """
    Asegura secuencia_codigo.ultimo_valor >= ultimo_asignado (ej. 400016 → próximo 400017).
    Retorna el próximo código que usaría leer_inicio_secuencia_app.
    """
    piso = max(int(ultimo_asignado), APP_CODIGO_PROXIMO_PISO - 1)
    res = supabase.table("secuencia_codigo").select("id, ultimo_valor").eq("id", 1).execute()
    if res.data:
        actual = int(res.data[0].get("ultimo_valor") or 0)
        nuevo = max(actual, piso)
        supabase.table("secuencia_codigo").update({"ultimo_valor": nuevo}).eq("id", 1).execute()
    else:
        supabase.table("secuencia_codigo").insert({"id": 1, "ultimo_valor": piso}).execute()
    return leer_inicio_secuencia_app(supabase)


def _row_id(row: dict) -> str:
    return str(row.get("id") or "")


def _es_origen_exportable_app(row: dict) -> bool:
    """Sincronizador Importa: altas web (origen app o legacy sin origen)."""
    origen = (row.get("origen") or "app").strip().lower()
    return origen in ("", "app")


def fetch_a_exportar_diagnostico(supabase) -> list[dict]:
    """Todas las filas en cola A Exportar (cualquier origen), para logs de soporte."""
    query = (
        supabase.table("clientes_pendientes")
        .select("id, nombre, cuit, codigo, origen, estado, created_at")
        .eq("estado", "A Exportar")
        .order("created_at", desc=True)
    )
    return _fetch_paginated(query)


def fetch_clientes_a_exportar(supabase) -> list[dict]:
    """Clientes app listos para exportar (orden: más recientes primero)."""
    query = (
        supabase.table("clientes_pendientes")
        .select("*")
        .eq("estado", "A Exportar")
        .order("created_at", desc=True)
    )
    rows = _fetch_paginated(query)
    out: list[dict] = []
    for row in rows:
        if not _es_origen_exportable_app(row):
            continue
        item = dict(row)
        if not str(item.get("origen") or "").strip():
            item["origen"] = "app"
        out.append(item)
    return out


def actualizar_secuencia_erp(supabase, max_codigo_erp: int) -> None:
    """
    Actualiza piso ERP (< 40000) en secuencia_codigo sin bajar códigos app ya usados (>= 40000).
    """
    piso_erp = max(39999, int(max_codigo_erp or 0))
    res = supabase.table("secuencia_codigo").select("id, ultimo_valor").eq("id", 1).execute()
    if res.data:
        actual = int(res.data[0].get("ultimo_valor") or 0)
        nuevo = max(actual, piso_erp)
        supabase.table("secuencia_codigo").update({"ultimo_valor": nuevo}).eq("id", 1).execute()
    else:
        supabase.table("secuencia_codigo").insert({"id": 1, "ultimo_valor": piso_erp}).execute()


def resolver_codigos_app(
    clientes: list[dict],
    numero_inicio: int,
    supabase=None,
) -> tuple[list[dict], int]:
    """
    Asigna códigos secuenciales sin reutilizar números ya usados por otro cliente.
    Reutiliza el código solo si pertenece al mismo id (re-exportación del mismo alta).
    """
    ocupados_map = _map_codigos_app_ocupados(supabase) if supabase is not None else {}
    ocupados = set(ocupados_map.keys())
    next_codigo = _siguiente_codigo_libre(numero_inicio, ocupados)
    ultimo_usado = next_codigo - 1
    result: list[dict] = []

    for row in clientes:
        item = dict(row)
        rid = str(item.get("id") or "")
        existing = _parse_codigo_app(item.get("codigo"))
        owner = ocupados_map.get(existing) if existing is not None else None
        reuse = (
            existing is not None
            and existing >= APP_CODIGO_PROXIMO_PISO
            and owner == rid
        )
        if reuse:
            item["codigo"] = existing
            ultimo_usado = max(ultimo_usado, existing)
        else:
            next_codigo = _siguiente_codigo_libre(next_codigo, ocupados)
            item["codigo"] = next_codigo
            ocupados.add(next_codigo)
            ocupados_map[next_codigo] = rid
            ultimo_usado = next_codigo
            next_codigo += 1
        result.append(item)

    return result, ultimo_usado


def guardar_exportacion_app(supabase, clientes: list[dict], ultimo_assigned: int) -> None:
    """Persiste codigo + estado Exportado y avanza secuencia_codigo.ultimo_valor."""
    for item in clientes:
        supabase.table("clientes_pendientes").update(
            {"codigo": item["codigo"], "estado": "Exportado"}
        ).eq("id", item["id"]).execute()

    res = supabase.table("secuencia_codigo").select("ultimo_valor").eq("id", 1).execute()
    actual = 0 if not res.data else int(res.data[0].get("ultimo_valor") or 0)
    nuevo_ultimo = max(actual, int(ultimo_assigned))

    if res.data:
        supabase.table("secuencia_codigo").update({"ultimo_valor": nuevo_ultimo}).eq("id", 1).execute()
    else:
        supabase.table("secuencia_codigo").insert({"id": 1, "ultimo_valor": nuevo_ultimo}).execute()


def _err_text(err) -> str:
    if isinstance(err, dict):
        return str(err.get("message", err))
    return str(err)


def _missing_column(err, column: str) -> bool:
    text = _err_text(err).lower()
    return column.lower() in text and ("does not exist" in text or "42703" in str(err))


def migration_sql() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, MIGRATION_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return (
            "ALTER TABLE public.clientes_pendientes\n"
            "  ADD COLUMN IF NOT EXISTS codigo NUMERIC,\n"
            "  ADD COLUMN IF NOT EXISTS origen TEXT DEFAULT 'app',\n"
            "  ADD COLUMN IF NOT EXISTS vendedor TEXT,\n"
            "  ADD COLUMN IF NOT EXISTS validado_arca BOOLEAN DEFAULT FALSE,\n"
            "  ADD COLUMN IF NOT EXISTS validado_nosis BOOLEAN DEFAULT FALSE;"
        )


def _fetch_paginated(query) -> list:
    """Recorre todas las páginas de una consulta Supabase (límite por defecto: 1000 filas)."""
    rows: list = []
    offset = 0
    while True:
        res = query.range(offset, offset + SUPABASE_PAGE_SIZE - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < SUPABASE_PAGE_SIZE:
            break
        offset += SUPABASE_PAGE_SIZE
    return rows


def fetch_app_clientes(
    supabase,
    estados: tuple[str, ...] | list[str] | None = None,
) -> tuple[list, str | None]:
    """
    Clientes dados de alta desde la app (origen=app).
    Retorna (filas, aviso). aviso: None | 'migration_recommended'
    """
    if estados is None:
        estados = ESTADOS_ACTIVOS_APP

    try:
        query = (
            supabase.table("clientes_pendientes")
            .select("*, usuarios(codigo_vendedor)")
            .eq("origen", "app")
            .in_("estado", list(estados))
            .order("created_at", desc=True)
        )
        return _fetch_paginated(query), None
    except Exception as e:
        if not _missing_column(e, "origen"):
            raise

    query = (
        supabase.table("clientes_pendientes")
        .select("*, usuarios(codigo_vendedor)")
        .is_("codigo", "null")
        .in_("estado", list(estados))
        .order("created_at", desc=True)
    )
    return _fetch_paginated(query), "migration_recommended"


def fetch_presea_clientes(supabase) -> tuple[list, str | None]:
    """
    Retorna (filas, aviso).
    aviso: None | 'migration_required' | 'migration_recommended'
    """
    try:
        query = (
            supabase.table("clientes_pendientes")
            .select("*")
            .eq("origen", "presea")
            .order("created_at", desc=True)
        )
        return _fetch_paginated(query), None
    except Exception as e:
        if not _missing_column(e, "origen"):
            raise

    try:
        query = (
            supabase.table("clientes_pendientes")
            .select("*")
            .lt("codigo", 40000)
            .order("created_at", desc=True)
        )
        return _fetch_paginated(query), "migration_recommended"
    except Exception as e:
        if _missing_column(e, "codigo"):
            return [], "migration_required"
        raise


def update_cliente(supabase, client_id: str, datos: dict) -> tuple[bool, str | None]:
    """Actualiza cliente; omite columnas nuevas si la migración no corrió."""
    try:
        supabase.table("clientes_pendientes").update(datos).eq("id", client_id).execute()
        return True, None
    except Exception as e:
        if "42703" not in _err_text(e):
            raise
        safe = {k: v for k, v in datos.items() if k not in PRESEA_EXTRA_COLS}
        if not safe:
            return False, "migration_required"
        supabase.table("clientes_pendientes").update(safe).eq("id", client_id).execute()
        return True, "partial"
