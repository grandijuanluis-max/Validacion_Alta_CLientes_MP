"""Consultas y updates para clientes Presea (tolerante a migración pendiente)."""

from __future__ import annotations

import os

MIGRATION_FILE = "supabase_migration_presea_clientes.sql"
PRESEA_EXTRA_COLS = frozenset({
    "codigo", "origen", "vendedor", "validado_arca", "validado_nosis",
})
ESTADOS_ACTIVOS_APP = ("Pendiente", "Modificado", "A Exportar")
SUPABASE_PAGE_SIZE = 1000


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
