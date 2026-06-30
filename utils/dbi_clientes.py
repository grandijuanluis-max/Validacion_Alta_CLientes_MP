#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parser e importación de CLIENTESPA.DBI (clientes dados de alta en Presea ERP).

Códigos < 40000  → origen Presea (importados a clientes_pendientes)
Códigos >= 40000 → altas desde la aplicación web
"""

from __future__ import annotations

import logging
from typing import Optional

import dbf

# Esquema dBASE idéntico al de generador_dbi.py / Presea
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


def _s(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _i(val) -> int:
    try:
        return int(val)
    except Exception:
        return 0


def _f(val) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def format_cuit(val) -> str:
    digits = "".join(c for c in str(val) if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"
    return digits or ""


def record_to_cliente_dict(rec) -> Optional[dict]:
    """Convierte un registro DBF a dict para clientes_pendientes. None si código inválido."""
    codigo = _i(rec.CODIGO)
    if codigo <= 0 or codigo > PRESEA_CODIGO_MAX:
        return None

    cuit = format_cuit(rec.CUIT)
    if not cuit:
        return None

    domicilio_f = _s(rec.DOMICILIO)
    localidad = _s(rec.LOCALIDAD)
    provincia = _s(rec.PROVINCIA)
    c_postal = _s(rec.C_POSTAL)
    pais = _s(rec.PAIS) or "ARGENTINA"

    cuit_s1 = _i(rec.CUIT_S1)
    cuit_s2 = _i(rec.CUIT_S2)

    memo = _s(rec.MEMO) if hasattr(rec, "MEMO") else ""

    return {
        "codigo": codigo,
        "origen": "presea",
        "estado": "Pendiente",
        "cuit": cuit,
        "nombre": _s(rec.NOMBRE) or "Sin nombre",
        "n_fantasia": _s(rec.N_FANTASIA) or _s(rec.NOMBRE),
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
        "tipo_resp": str(_f(rec.TIPO_RESP)),
        "tipo_doc": str(_i(rec.TIPO_DOC) or 80),
        "cuit_socio1": str(cuit_s1) if cuit_s1 else "",
        "cuit_socio2": str(cuit_s2) if cuit_s2 else "",
        "vendedor": str(_i(rec.VENDEDOR)),
        "documento": memo,
    }


def import_clientespa_to_supabase(supabase, path_dbi: str, logger=None) -> dict:
    """
    Importa clientes con CODIGO < 40000 desde CLIENTESPA.DBI a clientes_pendientes.
    Upsert por codigo + origen='presea'.
    """
    log = logger or logging.getLogger("dbi_clientes")
    stats = {"total_dbf": 0, "importados": 0, "omitidos": 0, "errores": 0}

    existing_by_codigo = {}
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
        if not res.data:
            break
        for row in res.data:
            if row.get("codigo") is not None:
                existing_by_codigo[int(row["codigo"])] = row["id"]
        if len(res.data) < page:
            break
        offset += page

    batch_insert = []
    batch_update = []

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
            item = record_to_cliente_dict(rec)
            if not item:
                stats["omitidos"] += 1
                continue

            codigo = item["codigo"]
            if codigo in existing_by_codigo:
                upd = {k: v for k, v in item.items() if k not in ("estado",)}
                upd["id"] = existing_by_codigo[codigo]
                batch_update.append(upd)
            else:
                batch_insert.append(item)

    for item in batch_update:
        row_id = item.pop("id")
        try:
            supabase.table("clientes_pendientes").update(item).eq("id", row_id).execute()
            stats["importados"] += 1
        except Exception as e:
            log.error("Error actualizando cliente Presea %s: %s", item.get("codigo"), e)
            stats["errores"] += 1

    for i in range(0, len(batch_insert), BATCH_SIZE):
        chunk = batch_insert[i : i + BATCH_SIZE]
        try:
            supabase.table("clientes_pendientes").insert(chunk).execute()
            stats["importados"] += len(chunk)
        except Exception as e:
            log.error("Error insertando lote Presea: %s", e)
            stats["errores"] += len(chunk)

    log.info(
        "Import Presea: total=%s importados=%s omitidos=%s errores=%s",
        stats["total_dbf"], stats["importados"], stats["omitidos"], stats["errores"],
    )
    return stats


def scan_clientespa_metadata(path_dbi: str) -> tuple[int, set]:
    """Retorna (max_codigo, set de vendedores) desde CLIENTESPA.DBI."""
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
