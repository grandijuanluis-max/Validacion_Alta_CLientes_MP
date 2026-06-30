"""Consultas y updates para clientes Presea (tolerante a migración pendiente)."""

from __future__ import annotations

import os

MIGRATION_FILE = "supabase_migration_presea_clientes.sql"
PRESEA_EXTRA_COLS = frozenset({
    "codigo", "origen", "vendedor", "validado_arca", "validado_nosis",
})


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


def fetch_presea_clientes(supabase) -> tuple[list, str | None]:
    """
    Retorna (filas, aviso).
    aviso: None | 'migration_required' | 'migration_recommended'
    """
    try:
        res = supabase.table("clientes_pendientes").select("*").eq("origen", "presea").execute()
        return res.data or [], None
    except Exception as e:
        if not _missing_column(e, "origen"):
            raise

    try:
        res = (
            supabase.table("clientes_pendientes")
            .select("*")
            .lt("codigo", 40000)
            .execute()
        )
        return res.data or [], "migration_recommended"
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
