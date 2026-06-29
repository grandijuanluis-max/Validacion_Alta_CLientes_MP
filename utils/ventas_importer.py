#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importación incremental de ventas.dbi → Supabase.
Usado por windows_sync.py y modulos/ui_gestion.py.

Clave única (8 campos): fecha, empresa, formulario, numero, cod_clien, cod_alfa, bultos, impo
Requiere constraint ventas_unique_item en Supabase (ver supabase_fix_ventas_constraint.sql).
"""

from __future__ import annotations

import datetime
import logging
from typing import Callable, Optional

import dbf

# Debe coincidir EXACTAMENTE con el UNIQUE constraint en Supabase
VENTAS_CONFLICT_COLS = (
    "fecha", "empresa", "formulario", "numero",
    "cod_clien", "cod_alfa", "bultos", "impo",
)
VENTAS_UPSERT_ON_CONFLICT = ",".join(VENTAS_CONFLICT_COLS)


def parse_dbf_int(val) -> int:
    if val is None:
        return 0
    try:
        return int(val)
    except Exception:
        return 0


def parse_dbf_float(val, decimals: int = 6) -> float:
    if val is None:
        return 0.0
    try:
        return round(float(val), decimals)
    except Exception:
        return 0.0


def parse_dbf_str(val) -> str:
    if val is None:
        return ""
    try:
        return str(val).strip()
    except Exception:
        return ""


def parse_dbf_date(val) -> Optional[str]:
    if not val:
        return None
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime("%Y-%m-%d")
    val_str = str(val).strip()
    if len(val_str) >= 10 and val_str[4] == "-" and val_str[7] == "-":
        return val_str[:10]
    try:
        parts = val_str.split("/")
        if len(parts) == 3:
            d, m, y = parts
            return f"{y.zfill(4)}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        pass
    return None


def venta_item_from_record(rec) -> Optional[dict]:
    """Convierte un registro DBF a dict listo para upsert. None si fecha inválida."""
    fecha_iso = parse_dbf_date(rec.FECHA)
    if not fecha_iso:
        return None

    return {
        "rubro": parse_dbf_str(rec.RUBRO),
        "fecha": fecha_iso,
        "empresa": parse_dbf_str(rec.EMPRESA) or "0",
        "subrubro": parse_dbf_str(rec.SUBRUBRO),
        "numero": parse_dbf_int(rec.NUMERO),
        "localidad": parse_dbf_str(rec.LOCALIDAD),
        "provincia": parse_dbf_str(rec.PROVINCIA),
        "formulario": parse_dbf_str(rec.FORMULARIO),
        "e_mail": parse_dbf_str(rec.E_MAIL),
        "telefono": parse_dbf_str(rec.TELEFONO),
        "pais": parse_dbf_str(rec.PAIS),
        "codigo": parse_dbf_int(rec.CODIGO),
        "cod_alfa": parse_dbf_str(rec.COD_ALFA),
        "unidades": parse_dbf_float(rec.UNIDADES, 6),
        "codigocomp": parse_dbf_int(rec.CODIGOCOMP),
        "tipo": parse_dbf_int(rec.TIPO),
        "dto": parse_dbf_float(rec.DTO, 4),
        "dto1": parse_dbf_float(rec.DTO1, 4),
        "dto2": parse_dbf_float(rec.DTO2, 4),
        "alt_bonifi": parse_dbf_str(rec.ALT_BONIFI),
        "grupo": parse_dbf_str(rec.GRUPO),
        "sinonimo": parse_dbf_str(rec.SINONIMO),
        "ean": parse_dbf_str(rec.EAN),
        "clien": parse_dbf_str(rec.CLIEN),
        "cod_clien": parse_dbf_int(rec.COD_CLIEN),
        "producto": parse_dbf_str(rec.PRODUCTO),
        "vendedo": parse_dbf_str(rec.VENDEDO),
        "domicilio": parse_dbf_str(rec.DOMICILIO),
        "deposito": parse_dbf_str(rec.DEPOSITO),
        "bultos": parse_dbf_float(rec.BULTOS, 6),
        "impo": parse_dbf_float(rec.IMPO, 2),
    }


def venta_conflict_key(item: dict) -> tuple:
    """Clave de deduplicación alineada al constraint UNIQUE de Supabase."""
    return tuple(item[col] for col in VENTAS_CONFLICT_COLS)


def create_dummy_memo_files(dbf_path: str) -> None:
    import os
    base, _ = os.path.splitext(dbf_path)
    for ext in [".dbt", ".fpt", ".DBT", ".FPT"]:
        p = base + ext
        if not os.path.exists(p):
            try:
                with open(p, "wb") as f:
                    if ext.lower() == ".dbt":
                        f.write(b"\x01\x00\x00\x00" + b"\x00" * 508)
                    else:
                        f.write(b"\x00\x00\x00\x01\x00\x00\x00\x40" + b"\x00" * 504)
            except Exception:
                pass


def iter_ventas_from_dbi(path_ventas: str):
    """
    Genera items válidos desde ventas.dbi.
    Retorna (item, stats_updates) donde stats_updates es un dict parcial.
    """
    create_dummy_memo_files(path_ventas)
    stats = {"total_dbf": 0, "sin_fecha": 0, "duplicados_dbf": 0}

    with dbf.Table(path_ventas, codepage="cp1252") as table:
        table.open()
        if table._meta.memo:
            original_get_memo = table._meta.memo.get_memo

            def safe_get_memo(block):
                try:
                    return original_get_memo(block)
                except Exception:
                    return b""

            table._meta.memo.get_memo = safe_get_memo

        seen_keys: set = set()
        stats["total_dbf"] = len(table)

        for rec in table:
            item = venta_item_from_record(rec)
            if item is None:
                stats["sin_fecha"] += 1
                continue

            key = venta_conflict_key(item)
            if key in seen_keys:
                stats["duplicados_dbf"] += 1
                continue

            seen_keys.add(key)
            yield item

    return stats


def upsert_ventas_batch(supabase, items: list[dict]) -> None:
    """Upsert de un lote, con deduplicación final por clave de conflicto."""
    if not items:
        return

    deduped: dict = {}
    for item in items:
        deduped[venta_conflict_key(item)] = item

    supabase.table("ventas").upsert(
        list(deduped.values()),
        on_conflict=VENTAS_UPSERT_ON_CONFLICT,
    ).execute()


def import_ventas_dbi(
    supabase,
    path_ventas: str,
    batch_size: int = 1000,
    logger: Optional[logging.Logger] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> dict:
    """
    Importa ventas.dbi a Supabase en lotes incrementales (sin duplicar).
    Retorna estadísticas del proceso.
    """
    log = logger or logging.getLogger("ventas_importer")
    stats = {
        "total_dbf": 0,
        "sin_fecha": 0,
        "duplicados_dbf": 0,
        "importados": 0,
        "lotes": 0,
        "max_fecha": None,
        "min_fecha": None,
        "fechas": {},
    }

    create_dummy_memo_files(path_ventas)
    batch: list[dict] = []

    with dbf.Table(path_ventas, codepage="cp1252") as table:
        table.open()
        if table._meta.memo:
            original_get_memo = table._meta.memo.get_memo

            def safe_get_memo(block):
                try:
                    return original_get_memo(block)
                except Exception:
                    return b""

            table._meta.memo.get_memo = safe_get_memo

        seen_keys: set = set()
        stats["total_dbf"] = len(table)

        for rec in table:
            item = venta_item_from_record(rec)
            if item is None:
                stats["sin_fecha"] += 1
                continue

            key = venta_conflict_key(item)
            if key in seen_keys:
                stats["duplicados_dbf"] += 1
                continue

            seen_keys.add(key)
            batch.append(item)
            fd = item["fecha"]
            stats["fechas"][fd] = stats["fechas"].get(fd, 0) + 1
            stats["max_fecha"] = fd if not stats["max_fecha"] or fd > stats["max_fecha"] else stats["max_fecha"]
            stats["min_fecha"] = fd if not stats["min_fecha"] or fd < stats["min_fecha"] else stats["min_fecha"]

            if len(batch) >= batch_size:
                upsert_ventas_batch(supabase, batch)
                stats["importados"] += len(batch)
                stats["lotes"] += 1
                log.info("  Upsert lote %s: %s registros (acumulado %s)", stats["lotes"], len(batch), stats["importados"])
                if on_progress:
                    on_progress(stats["importados"], stats["total_dbf"])
                batch = []

        if batch:
            upsert_ventas_batch(supabase, batch)
            stats["importados"] += len(batch)
            stats["lotes"] += 1
            log.info("  Upsert lote final: %s registros (total %s)", len(batch), stats["importados"])
            if on_progress:
                on_progress(stats["importados"], stats["total_dbf"])

    return stats


def count_dbf_by_date(path_ventas: str) -> dict:
    """Cuenta registros por fecha en un ventas.dbi (sin importar)."""
    counts: dict = {}
    create_dummy_memo_files(path_ventas)
    with dbf.Table(path_ventas, codepage="cp1252") as table:
        table.open()
        for rec in table:
            fd = parse_dbf_date(rec.FECHA)
            if fd:
                counts[fd] = counts.get(fd, 0) + 1
    return counts
