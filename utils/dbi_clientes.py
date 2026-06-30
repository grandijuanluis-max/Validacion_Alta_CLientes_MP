#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parser e importación de CLIENTESPA.DBI (clientes dados de alta en Presea ERP).

Códigos < 40000  → origen Presea (importados a clientes_pendientes)
Códigos >= 40000 → altas desde la aplicación web (se omiten en este import)
"""

from __future__ import annotations

import logging
from typing import Optional

import dbf

CLIENTESPA_SCHEMA = (
    "CODIGO N(6,0); NOMBRE C(30); N_FANTASIA C(30); CUIT N(12,0); "
    "DOMICILIO C(50); LOCALIDAD C(35); C_POSTAL C(50); PROVINCIA C(25); "
    "PAIS C(20); CONTACTO C(30); TELEFONO C(40); RUBRO C(30); "
    "TIPO_RESP N(5,1); TIPO_DOC N(2,0); CUIT_S1 N(12,0); CUIT_S2 N(12,0); "
    "TRANSPORTE N(2,0); CONDICION N(2,0); CATEGORIA C(10); LISTAPRE C(10); "
    "VENDEDOR N(6,0); MEMO M"
)

PRESEA_CODIGO_MAX = 39999

# Columnas mínimas para insert si falla el payload completo
MINIMAL_INSERT_COLS = (
    "codigo", "origen", "estado", "cuit", "nombre", "n_fantasia",
    "domicilio_f", "localidad", "provincia", "c_postal", "pais",
)

# Columnas opcionales que pueden no existir aún en Supabase
OPTIONAL_COLS = (
    "cp_ent", "local_ent", "prov_ent", "vendedor",
    "validado_arca", "validado_nosis", "documento",
    "cuit_socio1", "cuit_socio2", "tipo_resp", "tipo_doc",
    "domicilio_e", "contacto", "telefono", "giro_comercial",
)


def _s(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _i(val) -> int:
    try:
        return int(float(val))
    except Exception:
        return 0


def _f(val) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def format_cuit(val, codigo: int = 0) -> str:
    """Normaliza CUIT; si falta o es 0, genera placeholder único por código Presea."""
    digits = "".join(c for c in str(val) if c.isdigit())
    if digits and set(digits) != {"0"}:
        if len(digits) < 11:
            digits = digits.zfill(11)
        elif len(digits) > 11:
            digits = digits[-11:]
        if len(digits) == 11:
            return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"
    return f"00-{str(codigo).zfill(8)}-0"


def record_to_cliente_dict(rec) -> tuple[Optional[dict], Optional[str]]:
    """
    Convierte registro DBF → dict para clientes_pendientes.
    Retorna (dict, None) o (None, motivo_omision).
    """
    codigo = _i(rec.CODIGO)
    if codigo <= 0:
        return None, "codigo_invalido"
    if codigo > PRESEA_CODIGO_MAX:
        return None, "codigo_app"

    cuit = format_cuit(rec.CUIT, codigo)
    domicilio_f = _s(rec.DOMICILIO)
    localidad = _s(rec.LOCALIDAD)
    provincia = _s(rec.PROVINCIA)
    c_postal = _s(rec.C_POSTAL)
    pais = _s(rec.PAIS) or "ARGENTINA"

    cuit_s1 = _i(rec.CUIT_S1)
    cuit_s2 = _i(rec.CUIT_S2)
    memo = _s(rec.MEMO) if hasattr(rec, "MEMO") else ""

    nombre = _s(rec.NOMBRE) or _s(rec.N_FANTASIA) or f"CLIENTE {codigo}"

    return {
        "codigo": codigo,
        "origen": "presea",
        "estado": "Pendiente",
        "cuit": cuit,
        "nombre": nombre,
        "n_fantasia": _s(rec.N_FANTASIA) or nombre,
        "domicilio_f": domicilio_f,
        "domicilio_e": domicilio_f,
        "localidad": localidad,
        "provincia": provincia,
        "c_postal": c_postal,
        "cp_ent": c_postal[:5] if c_postal else "",
        "local_ent": localidad,
        "prov_ent": provincia,
        "pais": pais,
        "contacto": _s(rec.CONTACTO),
        "telefono": _s(rec.TELEFONO),
        "giro_comercial": _s(rec.RUBRO),
        "tipo_resp": str(_f(rec.TIPO_RESP)) if _f(rec.TIPO_RESP) else "1.0",
        "tipo_doc": str(_i(rec.TIPO_DOC) or 80),
        "cuit_socio1": str(cuit_s1) if cuit_s1 else None,
        "cuit_socio2": str(cuit_s2) if cuit_s2 else None,
        "vendedor": str(_i(rec.VENDEDOR)) if _i(rec.VENDEDOR) else None,
        "documento": memo or None,
        "validado_arca": False,
        "validado_nosis": False,
    }, None


def _load_existing_presea(supabase, log) -> dict[int, str]:
    """codigo → id UUID de clientes Presea ya en Supabase."""
    existing: dict[int, str] = {}
    try:
        offset = 0
        page = 1000
        while True:
            res = (
                supabase.table("clientes_pendientes")
                .select("id, codigo")
                .eq("origen", "presea")
                .range(offset, offset + page - 1)
                .execute()
            )
            rows = res.data or []
            for row in rows:
                if row.get("codigo") is not None:
                    existing[int(row["codigo"])] = row["id"]
            if len(rows) < page:
                break
            offset += page
        return existing
    except Exception as e:
        err = str(e).lower()
        if "origen" in err and ("42703" in err or "does not exist" in err):
            log.warning("Columna origen ausente; no se puede hacer upsert por codigo.")
            return {}
        raise


def _clean_payload(item: dict) -> dict:
    """Quita None y strings vacíos en campos opcionales."""
    out = {}
    for k, v in item.items():
        if v is None:
            continue
        if k in OPTIONAL_COLS and str(v).strip() == "":
            continue
        out[k] = v
    return out


def _insert_one(supabase, item: dict, log) -> bool:
    """Inserta un registro; reintenta con columnas mínimas si falla."""
    payload = _clean_payload(item)
    try:
        supabase.table("clientes_pendientes").insert(payload).execute()
        return True
    except Exception as e1:
        err1 = str(e1)
        # Quitar columnas opcionales y reintentar
        reduced = {k: v for k, v in payload.items() if k not in OPTIONAL_COLS}
        try:
            supabase.table("clientes_pendientes").insert(reduced).execute()
            log.warning("Insert OK (payload reducido) codigo=%s: %s", item.get("codigo"), err1[:120])
            return True
        except Exception as e2:
            minimal = {k: reduced[k] for k in MINIMAL_INSERT_COLS if k in reduced}
            try:
                supabase.table("clientes_pendientes").insert(minimal).execute()
                log.warning("Insert OK (mínimo) codigo=%s", item.get("codigo"))
                return True
            except Exception as e3:
                log.error(
                    "Insert fallido codigo=%s cuit=%s: %s",
                    item.get("codigo"), item.get("cuit"), e3,
                )
                return False


def _update_one(supabase, row_id: str, item: dict, log) -> bool:
    upd = _clean_payload({k: v for k, v in item.items() if k not in ("estado", "origen")})
    try:
        supabase.table("clientes_pendientes").update(upd).eq("id", row_id).execute()
        return True
    except Exception as e1:
        reduced = {k: v for k, v in upd.items() if k not in OPTIONAL_COLS}
        try:
            supabase.table("clientes_pendientes").update(reduced).eq("id", row_id).execute()
            return True
        except Exception as e2:
            log.error("Update fallido id=%s codigo=%s: %s", row_id, item.get("codigo"), e2)
            return False


def import_clientespa_to_supabase(supabase, path_dbi: str, logger=None) -> dict:
    """
    Importa clientes con CODIGO < 40000 desde CLIENTESPA.DBI a clientes_pendientes.
    """
    log = logger or logging.getLogger("dbi_clientes")
    stats = {
        "total_dbf": 0,
        "importados": 0,
        "actualizados": 0,
        "omitidos": 0,
        "omitidos_app": 0,
        "omitidos_invalidos": 0,
        "errores": 0,
    }

    existing_by_codigo = _load_existing_presea(supabase, log)
    batch_insert: list[dict] = []
    batch_update: list[tuple[str, dict]] = []

    with dbf.Table(path_dbi, codepage="cp1252") as table:
        table.open()
        if table._meta.memo:
            _orig = table._meta.memo.get_memo

            def _safe_memo(block):
                try:
                    return _orig(block)
                except Exception:
                    return b""

            table._meta.memo.get_memo = _safe_memo

        for rec in table:
            stats["total_dbf"] += 1
            item, motivo = record_to_cliente_dict(rec)
            if not item:
                stats["omitidos"] += 1
                if motivo == "codigo_app":
                    stats["omitidos_app"] += 1
                else:
                    stats["omitidos_invalidos"] += 1
                continue

            codigo = item["codigo"]
            if codigo in existing_by_codigo:
                batch_update.append((existing_by_codigo[codigo], item))
            else:
                batch_insert.append(item)

    for row_id, item in batch_update:
        if _update_one(supabase, row_id, item, log):
            stats["actualizados"] += 1
        else:
            stats["errores"] += 1

    for item in batch_insert:
        if _insert_one(supabase, item, log):
            stats["importados"] += 1
        else:
            stats["errores"] += 1

    stats["importados_total"] = stats["importados"] + stats["actualizados"]
    log.info(
        "Import Presea: dbf=%s nuevos=%s actualizados=%s omitidos=%s (app=%s) errores=%s",
        stats["total_dbf"], stats["importados"], stats["actualizados"],
        stats["omitidos"], stats["omitidos_app"], stats["errores"],
    )
    return stats


def scan_clientespa_metadata(path_dbi: str) -> tuple[int, set]:
    max_codigo = 0
    vendedores = set()
    with dbf.Table(path_dbi, codepage="cp1252") as table:
        table.open()
        for rec in table:
            try:
                codigo = int(rec.CODIGO)
                if codigo > max_codigo:
                    max_codigo = codigo
            except Exception:
                pass
            try:
                vend = int(rec.VENDEDOR)
                if vend > 0:
                    vendedores.add(vend)
            except Exception:
                pass
    return max_codigo, vendedores
