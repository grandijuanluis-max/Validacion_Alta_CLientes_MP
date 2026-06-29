#!/usr/bin/env python3
"""
Verifica e importa ventas.dbi hacia Supabase.

Uso:
  python3 scripts/verify_ventas_sync.py /ruta/a/ventas.dbi
  python3 scripts/verify_ventas_sync.py /ruta/a/ventas.dbi --import
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "utils"))
sys.path.insert(0, ROOT)

from supabase import create_client
from ventas_importer import count_dbf_by_date, import_ventas_dbi


def load_supabase():
    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    with open(secrets_path, encoding="utf-8") as f:
        content = f.read()
    url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', content).group(1)
    key = re.search(r'SUPABASE_KEY\s*=\s*"([^"]+)"', content).group(1)
    return create_client(url, key)


def count_sb_by_dates(sb, dates):
    result = {}
    for d in dates:
        r = sb.table("ventas").select("id", count="exact").eq("fecha", d).limit(1).execute()
        result[d] = r.count
    return result


def main():
    parser = argparse.ArgumentParser(description="Verificar/importar ventas.dbi")
    parser.add_argument("dbi_path", help="Ruta al archivo ventas.dbi")
    parser.add_argument("--import", dest="do_import", action="store_true", help="Importar a Supabase")
    args = parser.parse_args()

    path = args.dbi_path
    if not os.path.exists(path):
        print(f"ERROR: no existe {path}")
        sys.exit(1)

    dbf_counts = count_dbf_by_date(path)
    if not dbf_counts:
        print("ERROR: ventas.dbi sin registros con fecha válida")
        sys.exit(1)

    dates = sorted(dbf_counts.keys())
    print(f"ventas.dbi: {sum(dbf_counts.values())} registros | {dates[0]} → {dates[-1]}")
    print("\nComparación DBF vs Supabase (últimas fechas):")
    sb = load_supabase()
    sb_counts = count_sb_by_dates(sb, dates[-14:])

    gaps = []
    for d in dates[-14:]:
        dbf_n = dbf_counts.get(d, 0)
        sb_n = sb_counts.get(d, 0)
        diff = dbf_n - sb_n
        flag = " OK" if diff == 0 else f" FALTAN {diff}" if diff > 0 else f" SB+{-diff}"
        print(f"  {d}: DBF={dbf_n:5d}  Supabase={sb_n:5d}{flag}")
        if diff > 0:
            gaps.append((d, diff))

    if args.do_import:
        print("\nImportando (upsert incremental, sin duplicar)...")
        stats = import_ventas_dbi(sb, path)
        print(
            f"Listo: {stats['importados']} upserted | "
            f"sin_fecha={stats['sin_fecha']} | dup_dbf={stats['duplicados_dbf']}"
        )
        print("\nRe-verificación post-import:")
        sb_counts2 = count_sb_by_dates(sb, dates[-14:])
        for d in dates[-14:]:
            dbf_n = dbf_counts.get(d, 0)
            sb_n = sb_counts2.get(d, 0)
            diff = dbf_n - sb_n
            flag = " OK" if diff == 0 else f" FALTAN {diff}" if diff > 0 else f" SB+{-diff}"
            print(f"  {d}: DBF={dbf_n:5d}  Supabase={sb_n:5d}{flag}")
    elif gaps:
        print(f"\nHay {len(gaps)} fecha(s) con registros faltantes. Ejecutá con --import para sincronizar.")
        sys.exit(2)
    else:
        print("\nTodo coincide en el rango verificado.")


if __name__ == "__main__":
    main()
