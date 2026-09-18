#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parser e importación de CLIENTESPA.DBI (clientes dados de alta en Presea ERP).

Códigos < 40000  → origen Presea (importados a clientes_pendientes)
Códigos >= 40000 → altas desde la aplicación web (se omiten en este import)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import dbf

try:
    from modulos.cuit_utils import cuit_real_desde_campo_erp, normalizar_cuit_digitos
except ImportError:
    cuit_real_desde_campo_erp = None
    normalizar_cuit_digitos = None

CLIENTESPA_SCHEMA = (
    "CODIGO N(6,0); NOMBRE C(30); N_FANTASIA C(30); CUIT N(12,0); "
    "DOMICILIO C(50); LOCALIDAD C(35); C_POSTAL C(50); PROVINCIA C(25); "
    "PAIS C(20); CONTACTO C(30); TELEFONO C(40); RUBRO C(30); "
    "TIPO_RESP N(5,1); TIPO_DOC N(2,0); CUIT_S1 N(12,0); CUIT_S2 N(12,0); "
    "TRANSPORTE N(2,0); CONDICION N(2,0); CATEGORIA C(10); LISTAPRE C(10); "
    "VENDEDOR N(6,0); MEMO M"
)

PRESEA_CODIGO_MAX = 39999
BATCH_SIZE = 100

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


def ensure_memo_sidecar(dbf_path: str) -> None:
    """
    CLIENTESPA.DBI usa campo MEMO → requiere .FPT/.DBT.
    Si solo se descargó el .DBI desde FTP, crear sidecar vacío para poder leer.
    """
    base, _ = os.path.splitext(dbf_path)
    for ext in (".fpt", ".FPT", ".dbt", ".DBT"):
        sidecar = base + ext
        if os.path.exists(sidecar):
            continue
        try:
            with open(sidecar, "wb") as f:
                if ext.lower() == ".dbt":
                    f.write(b"\x01\x00\x00\x00" + b"\x00" * 508)
                else:
                    f.write(b"\x00\x00\x00\x01\x00\x00\x00\x40" + b"\x00" * 504)
        except OSError:
            pass


def _open_clientespa_table(path_dbi: str):
    """Abre CLIENTESPA.DBI con sidecar memo y lectura segura."""
    ensure_memo_sidecar(path_dbi)
    table = dbf.Table(path_dbi, codepage="cp1252")
    table.open()
    if table._meta.memo:
        _orig = table._meta.memo.get_memo

        def _safe_memo(block):
            try:
                return _orig(block)
            except Exception:
                return b""

        table._meta.memo.get_memo = _safe_memo
    return table


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


def _field(rec, name: str, default=None):
    """Lee campo DBF tolerante a columnas ausentes en distintas versiones de Presea."""
    try:
        return getattr(rec, name)
    except Exception:
        return default


def record_to_cliente_dict(rec) -> tuple[Optional[dict], Optional[str]]:
    """
    Convierte registro DBF → dict para clientes_pendientes.
    Retorna (dict, None) o (None, motivo_omision).

    Nota: CLIENTESPA.DBI de Presea puede no incluir CUIT_S1/CUIT_S2/CONDICION/LISTAPRE
    (el export real tiene 18 campos vs 22 del Clientes_web.dbi de la app).
    """
    codigo = _i(_field(rec, "CODIGO"))
    if codigo <= 0:
        return None, "codigo_invalido"
    if codigo > PRESEA_CODIGO_MAX:
        return None, "codigo_app"

    cuit = format_cuit(_field(rec, "CUIT"), codigo)
    domicilio_f = _s(_field(rec, "DOMICILIO"))
    localidad = _s(_field(rec, "LOCALIDAD"))
    provincia = _s(_field(rec, "PROVINCIA"))
    c_postal = _s(_field(rec, "C_POSTAL"))
    pais = _s(_field(rec, "PAIS")) or "ARGENTINA"

    cuit_s1 = _i(_field(rec, "CUIT_S1", 0) or _field(rec, "CUIT_S01", 0))
    cuit_s2 = _i(_field(rec, "CUIT_S2", 0) or _field(rec, "CUIT_S02", 0))
    memo = _s(_field(rec, "MEMO", ""))

    nombre = _s(_field(rec, "NOMBRE")) or _s(_field(rec, "N_FANTASIA")) or f"CLIENTE {codigo}"

    return {
        "codigo": codigo,
        "origen": "presea",
        "estado": "Pendiente",
        "cuit": cuit,
        "nombre": nombre,
        "n_fantasia": _s(_field(rec, "N_FANTASIA")) or nombre,
        "domicilio_f": domicilio_f,
        "domicilio_e": domicilio_f,
        "localidad": localidad,
        "provincia": provincia,
        "c_postal": c_postal,
        "cp_ent": c_postal[:5].strip() if c_postal else "",
        "local_ent": localidad,
        "prov_ent": provincia,
        "pais": pais,
        "contacto": _s(_field(rec, "CONTACTO")),
        "telefono": _s(_field(rec, "TELEFONO")),
        "giro_comercial": _s(_field(rec, "RUBRO")),
        "tipo_resp": str(_f(_field(rec, "TIPO_RESP"))) if _f(_field(rec, "TIPO_RESP")) else "1.0",
        "tipo_doc": str(_i(_field(rec, "TIPO_DOC")) or 80),
        "cuit_socio1": str(cuit_s1) if cuit_s1 else None,
        "cuit_socio2": str(cuit_s2) if cuit_s2 else None,
        "vendedor": str(_i(_field(rec, "VENDEDOR"))) if _i(_field(rec, "VENDEDOR")) else None,
        "documento": memo or None,
        "validado_arca": False,
        "validado_nosis": False,
    }, None


def _schema_supports_presea(supabase, log) -> bool:
    try:
        supabase.table("clientes_pendientes").select("origen,codigo").limit(1).execute()
        return True
    except Exception as e:
        err = str(e).lower()
        if "origen" in err or "codigo" in err:
            log.warning(
                "Columnas origen/codigo ausentes en Supabase. "
                "Ejecute supabase_migration_presea_clientes.sql. Importando sin esas columnas."
            )
            return False
        raise


def _adapt_item_for_schema(item: dict, supports_presea: bool) -> dict:
    if supports_presea:
        return item
    skip = {"origen", "codigo", "validado_arca", "validado_nosis", "vendedor"}
    return {k: v for k, v in item.items() if k not in skip}


def _normalizar_cuit(cuit) -> str | None:
    if normalizar_cuit_digitos is not None:
        return normalizar_cuit_digitos(cuit)
    digits = "".join(c for c in str(cuit) if c.isdigit())
    if not digits or set(digits) == {"0"}:
        return None
    if len(digits) < 11:
        digits = digits.zfill(11)
    elif len(digits) > 11:
        digits = digits[-11:]
    return digits if len(digits) == 11 else None


def _cuit_desde_registro_erp(rec) -> str | None:
    """Solo CUIT real informado en Presea (no placeholder generado por código)."""
    if cuit_real_desde_campo_erp is not None:
        return cuit_real_desde_campo_erp(_field(rec, "CUIT"))
    return _normalizar_cuit(_field(rec, "CUIT"))


def _load_existing_cuit_digits(supabase, log) -> set[str]:
    """CUIT normalizados ya presentes en clientes_pendientes (app y presea)."""
    existing: set[str] = set()
    offset = 0
    page = 1000
    while True:
        res = (
            supabase.table("clientes_pendientes")
            .select("cuit")
            .range(offset, offset + page - 1)
            .execute()
        )
        rows = res.data or []
        for row in rows:
            d = _normalizar_cuit(row.get("cuit"))
            if d:
                existing.add(d)
        if len(rows) < page:
            break
        offset += page
    log.info("CUIT distintos ya en Supabase (clientes_pendientes): %s", len(existing))
    return existing


def _load_existing_codigos_presea(supabase, log, supports_presea: bool = True) -> set[int]:
    """Códigos ERP (< 40000) ya presentes en clientes_pendientes (cualquier origen)."""
    if not supports_presea:
        return set()
    existing: set[int] = set()
    offset = 0
    page = 1000
    while True:
        res = (
            supabase.table("clientes_pendientes")
            .select("codigo")
            .lt("codigo", PRESEA_CODIGO_MAX + 1)
            .not_.is_("codigo", "null")
            .order("codigo")
            .range(offset, offset + page - 1)
            .execute()
        )
        rows = res.data or []
        for row in rows:
            try:
                existing.add(int(float(row["codigo"])))
            except (TypeError, ValueError):
                pass
        if len(rows) < page:
            break
        offset += page
    log.info("Códigos ERP (<40000) ya en Supabase: %s", len(existing))
    return existing


def _load_existing_presea(supabase, log, supports_presea: bool = True) -> dict[int, str]:
    """codigo → id UUID (legacy; preferir _load_existing_codigos_presea para altas)."""
    if not supports_presea:
        return {}
    existing: dict[int, str] = {}
    try:
        offset = 0
        page = 1000
        while True:
            res = (
                supabase.table("clientes_pendientes")
                .select("id, codigo")
                .eq("origen", "presea")
                .lt("codigo", PRESEA_CODIGO_MAX + 1)
                .not_.is_("codigo", "null")
                .order("codigo")
                .range(offset, offset + page - 1)
                .execute()
            )
            rows = res.data or []
            for row in rows:
                if row.get("codigo") is not None:
                    existing[int(float(row["codigo"]))] = row["id"]
            if len(rows) < page:
                break
            offset += page
        log.info("Clientes Presea existentes en Supabase: %s", len(existing))
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


def _prepare_batch(items: list[dict]) -> list[dict]:
    """Unifica claves del lote (PostgREST exige mismas keys en bulk upsert/insert)."""
    cleaned = [_clean_payload(it) for it in items]
    keys = sorted({k for row in cleaned for k in row})
    return [{k: row.get(k) for k in keys} for row in cleaned]


def _insert_batch(supabase, items: list[dict], log) -> tuple[int, int]:
    """Inserta lote; en fallo reintenta fila a fila. Retorna (ok, fail)."""
    if not items:
        return 0, 0
    payload = _prepare_batch(items)
    tbl = supabase.table("clientes_pendientes")
    try:
        tbl.insert(payload).execute()
        return len(payload), 0
    except Exception as e_batch:
        log.warning("Lote de %s falló (%s), reintentando individual...", len(items), str(e_batch)[:200])
        ok = fail = 0
        for item in items:
            if _insert_one(supabase, item, log):
                ok += 1
            else:
                fail += 1
        return ok, fail


def _insert_one(supabase, item: dict, log) -> bool:
    """Inserta un registro; reintenta con columnas mínimas si falla."""
    payload = _clean_payload(item)
    tbl = supabase.table("clientes_pendientes")
    try:
        tbl.insert(payload).execute()
        return True
    except Exception as e1:
        err1 = str(e1)
        if "duplicate key" in err1.lower() or "23505" in err1:
            log.info("Insert omitido (código ya existe) codigo=%s", item.get("codigo"))
            return False
        reduced = {k: v for k, v in payload.items() if k not in OPTIONAL_COLS}
        try:
            tbl.insert(reduced).execute()
            log.warning("Insert OK (payload reducido) codigo=%s: %s", item.get("codigo"), err1[:120])
            return True
        except Exception as e2:
            err2 = str(e2)
            if "duplicate key" in err2.lower() or "23505" in err2:
                log.info("Insert omitido (código ya existe) codigo=%s", item.get("codigo"))
                return False
            minimal = {k: reduced[k] for k in MINIMAL_INSERT_COLS if k in reduced}
            try:
                tbl.insert(minimal).execute()
                log.warning("Insert OK (mínimo) codigo=%s", item.get("codigo"))
                return True
            except Exception as e3:
                log.error(
                    "Insert fallido codigo=%s cuit=%s: %s",
                    item.get("codigo"), item.get("cuit"), e3,
                )
                return False


def _update_one(supabase, row_id: str, item: dict, log) -> bool:
    skip = ("estado", "origen", "validado_arca", "validado_nosis")
    upd = _clean_payload({k: v for k, v in item.items() if k not in skip})
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
    Solo inserta códigos que aún no existen (origen presea); no actualiza existentes.
    """
    log = logger or logging.getLogger("dbi_clientes")
    stats = {
        "total_dbf": 0,
        "importados": 0,
        "actualizados": 0,
        "omitidos": 0,
        "omitidos_existentes": 0,
        "omitidos_app": 0,
        "omitidos_invalidos": 0,
        "omitidos_cuit_duplicado": 0,
        "errores": 0,
    }

    supports_presea = _schema_supports_presea(supabase, log)
    if not supports_presea:
        stats["error_apertura"] = (
            "Faltan columnas origen/codigo en Supabase. Ejecute supabase_migration_presea_clientes.sql"
        )
        log.error(stats["error_apertura"])
        return stats

    existing_codigos = _load_existing_codigos_presea(supabase, log, supports_presea)
    existing_cuits = _load_existing_cuit_digits(supabase, log)
    batch_insert: list[dict] = []
    seen_in_file: set[int] = set()
    seen_cuits_in_file: set[str] = set()

    try:
        table = _open_clientespa_table(path_dbi)
    except Exception as e:
        log.error("No se pudo abrir CLIENTESPA.DBI (%s): %s", path_dbi, e)
        stats["error_apertura"] = str(e)
        return stats

    stats["schema_presea"] = supports_presea

    try:
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

            codigo = int(item["codigo"])
            if codigo in seen_in_file:
                stats["omitidos_existentes"] += 1
                continue
            seen_in_file.add(codigo)

            if codigo in existing_codigos:
                stats["omitidos_existentes"] += 1
                continue

            cuit_digits = _cuit_desde_registro_erp(rec)
            if cuit_digits:
                if cuit_digits in existing_cuits or cuit_digits in seen_cuits_in_file:
                    stats["omitidos_cuit_duplicado"] += 1
                    log.info(
                        "CLIENTESPA omitido por CUIT duplicado: codigo=%s cuit=%s",
                        codigo,
                        cuit_digits,
                    )
                    continue
                seen_cuits_in_file.add(cuit_digits)

            batch_insert.append(_adapt_item_for_schema(item, supports_presea))
    finally:
        table.close()

    stats["pendientes_insert"] = len(batch_insert)
    log.info(
        "CLIENTESPA: leídos=%s → a insertar=%s (omitidos_existentes acumulados en loop=%s)",
        stats["total_dbf"],
        len(batch_insert),
        stats["omitidos_existentes"],
    )

    for i in range(0, len(batch_insert), BATCH_SIZE):
        chunk = batch_insert[i : i + BATCH_SIZE]
        ok, fail = _insert_batch(supabase, chunk, log)
        stats["importados"] += ok
        stats["errores"] += fail
        if ok == len(chunk) and fail == 0:
            for row in chunk:
                try:
                    existing_codigos.add(int(row["codigo"]))
                except (KeyError, TypeError, ValueError):
                    pass
                d = _normalizar_cuit(row.get("cuit"))
                if d:
                    existing_cuits.add(d)
        if ok and (i + BATCH_SIZE) % 500 == 0:
            log.info(
                "Progreso insert Presea: %s/%s",
                min(i + BATCH_SIZE, len(batch_insert)),
                len(batch_insert),
            )

    stats["importados_total"] = stats["importados"]
    log.info(
        "Import Presea: dbf=%s nuevos=%s omitidos_existentes=%s omitidos_cuit=%s "
        "omitidos=%s (app=%s) errores=%s",
        stats["total_dbf"],
        stats["importados"],
        stats["omitidos_existentes"],
        stats["omitidos_cuit_duplicado"],
        stats["omitidos"],
        stats["omitidos_app"],
        stats["errores"],
    )
    return stats


def scan_clientespa_metadata(path_dbi: str) -> tuple[int, set]:
    max_codigo = 0
    vendedores = set()
    table = _open_clientespa_table(path_dbi)
    try:
        for rec in table:
            try:
                codigo = int(_field(rec, "CODIGO"))
                if codigo > max_codigo:
                    max_codigo = codigo
            except Exception:
                pass
            try:
                vend = int(_field(rec, "VENDEDOR"))
                if vend > 0:
                    vendedores.add(vend)
            except Exception:
                pass
    finally:
        table.close()
    return max_codigo, vendedores
