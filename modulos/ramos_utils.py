"""Utilidades para ramos: guardar código `ramo`, mostrar/buscar por `descrip`."""

from __future__ import annotations

_FALLBACK_RAMOS = (
    (7, "KIOSCOS Y EE.SS"),
    (6, "FARMACIAS"),
    (5, "FERRETERIAS"),
    (1, "AUTOSERVICIOS CHICOS"),
)

_catalog_cache: tuple[dict[str, str], list[str], dict[str, str]] | None = None
_supabase_override = None


def set_supabase_client(client) -> None:
    """Permite inyectar cliente Supabase (p. ej. windows_sync sin Streamlit)."""
    global _supabase_override, _catalog_cache
    _supabase_override = client
    _catalog_cache = None


def _get_supabase():
    if _supabase_override is not None:
        return _supabase_override
    try:
        from modulos.db import supabase
        return supabase
    except Exception:
        return None


def _norm_code(val) -> str | None:
    if val is None:
        return None
    text = str(val).strip()
    if not text or text.lower() in {"none", "nan", "null"}:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    try:
        num = int(float(text))
        return str(num)
    except (ValueError, TypeError):
        return None


def load_ramos_catalog(force: bool = False) -> tuple[dict[str, str], list[str], dict[str, str]]:
    """
    Retorna (ramo_to_descrip, opciones_descrip_ordenadas, descrip_to_ramo).
    descrip_to_ramo indexa por texto exacto y por MAYÚSCULAS.
    """
    global _catalog_cache
    if _catalog_cache is not None and not force:
        return _catalog_cache

    ramo_to_descrip: dict[str, str] = {}
    descrip_to_ramo: dict[str, str] = {}
    opciones: list[str] = []

    rows = []
    client = _get_supabase()
    if client is not None:
        try:
            res = client.table("ramos").select("ramo, descrip").execute()
            rows = res.data or []
        except Exception:
            rows = []

    if not rows:
        rows = [{"ramo": c, "descrip": d} for c, d in _FALLBACK_RAMOS]

    rows.sort(key=lambda r: str(r.get("descrip", "")).upper())
    for row in rows:
        code = _norm_code(row.get("ramo"))
        desc = str(row.get("descrip", "")).strip()
        if not code or not desc:
            continue
        ramo_to_descrip[code] = desc
        descrip_to_ramo[desc] = code
        descrip_to_ramo[desc.upper()] = code
        opciones.append(desc)

    _catalog_cache = (ramo_to_descrip, opciones, descrip_to_ramo)
    return _catalog_cache


def get_ramos_select_options() -> list[str]:
    _, opciones, _ = load_ramos_catalog()
    return opciones


def giro_display(val) -> str:
    """Convierte código almacenado (o descrip legacy) a descrip para la UI."""
    if val is None or str(val).strip() == "":
        return ""

    ramo_to_descrip, _, descrip_to_ramo = load_ramos_catalog()
    text = str(val).strip()

    code = _norm_code(text)
    if code and code in ramo_to_descrip:
        return ramo_to_descrip[code]

    if text in descrip_to_ramo:
        code = descrip_to_ramo[text]
        return ramo_to_descrip.get(code, text)

    upper = text.upper()
    if upper in descrip_to_ramo:
        code = descrip_to_ramo[upper]
        return ramo_to_descrip.get(code, text)

    return text


def giro_to_storage(val) -> str | None:
    """Convierte selección UI (descrip o código) al código `ramo` para Supabase."""
    if val is None or str(val).strip() == "":
        return None

    _, _, descrip_to_ramo = load_ramos_catalog()
    text = str(val).strip()

    code = _norm_code(text)
    if code:
        return code

    if text in descrip_to_ramo:
        return descrip_to_ramo[text]

    upper = text.upper()
    if upper in descrip_to_ramo:
        return descrip_to_ramo[upper]

    return text


def rubro_export(val) -> str:
    """Valor para campo RUBRO del DBI (código numérico como texto)."""
    stored = giro_to_storage(val)
    if stored is None:
        return ""
    code = _norm_code(stored)
    return code if code else str(stored)[:30]


def giro_selectbox_index(current_val, opciones: list[str]) -> int:
    display = giro_display(current_val)
    if display in opciones:
        return opciones.index(display)
    return 0
