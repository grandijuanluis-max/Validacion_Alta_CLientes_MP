"""Normalización y búsqueda de CUIT (app + clientes Presea en Supabase)."""

from __future__ import annotations

SUPABASE_PAGE_SIZE = 1000


def normalizar_cuit_digitos(cuit) -> str | None:
    """Devuelve 11 dígitos o None si no hay un CUIT válido."""
    if cuit is None:
        return None
    digits = "".join(c for c in str(cuit) if c.isdigit())
    if not digits or set(digits) == {"0"}:
        return None
    if len(digits) < 11:
        digits = digits.zfill(11)
    elif len(digits) > 11:
        digits = digits[-11:]
    return digits if len(digits) == 11 else None


def cuit_real_desde_campo_erp(val) -> str | None:
    """CUIT del DBF Presea antes de placeholders; None si falta o es inválido."""
    return normalizar_cuit_digitos(val)


def formatear_cuit(cuit_digitos: str) -> str:
    return f"{cuit_digitos[:2]}-{cuit_digitos[2:10]}-{cuit_digitos[10]}"


def origen_cliente_label(row: dict) -> str:
    origen = str(row.get("origen") or "app").lower()
    if origen == "presea":
        codigo = row.get("codigo")
        return f"Presea (código {codigo})" if codigo is not None else "Presea"
    return f"Alta web ({row.get('estado', 'Pendiente')})"


def cuit_existe_en_db(supabase, cuit) -> dict | None:
    """
    Busca CUIT en clientes_pendientes (origen app y presea).
    Compara por dígitos, tolerando formato con o sin guiones.
    """
    if supabase is None:
        return None

    digits = normalizar_cuit_digitos(cuit)
    if not digits:
        return None

    formatted = formatear_cuit(digits)
    cols = "id, nombre, estado, origen, codigo, cuit"

    try:
        res = (
            supabase.table("clientes_pendientes")
            .select(cols)
            .or_(f"cuit.eq.{digits},cuit.eq.{formatted}")
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
    except Exception:
        pass

    offset = 0
    while True:
        try:
            res = (
                supabase.table("clientes_pendientes")
                .select(cols)
                .range(offset, offset + SUPABASE_PAGE_SIZE - 1)
                .execute()
            )
        except Exception:
            return None

        batch = res.data or []
        for row in batch:
            row_digits = normalizar_cuit_digitos(row.get("cuit"))
            if row_digits == digits:
                return row
        if len(batch) < SUPABASE_PAGE_SIZE:
            break
        offset += SUPABASE_PAGE_SIZE

    return None
