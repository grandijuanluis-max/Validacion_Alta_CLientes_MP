#!/usr/bin/env python3
"""
Importa CLIENTESPA.DBI a Supabase (prueba manual).

Uso:
  python3 scripts/import_clientespa.py
  python3 scripts/import_clientespa.py /ruta/a/CLIENTESPA.DBI
  python3 scripts/import_clientespa.py --ftp
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "utils"))
sys.path.insert(0, ROOT)

from dbi_clientes_loader import import_clientespa_module


def load_supabase():
    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    with open(secrets_path, encoding="utf-8") as f:
        content = f.read()
    url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', content).group(1)
    key = re.search(r'SUPABASE_KEY\s*=\s*"([^"]+)"', content).group(1)
    from supabase_http import create_http_client
    return create_http_client(url, key)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=os.path.join(ROOT, "data", "CLIENTESPA.DBI"))
    parser.add_argument("--ftp", action="store_true", help="Descargar desde FTP e importar")
    args = parser.parse_args()

    path = args.path
    if args.ftp:
        from utils.ftp_sync import download_and_import
        ok, msg = download_and_import()
        print(msg)
        sys.exit(0 if ok else 1)

    if not os.path.exists(path):
        print(f"No existe: {path}")
        print("Use --ftp para descargar desde FTP o pase la ruta al DBI.")
        sys.exit(1)

    sb = load_supabase()
    import_fn, scan_fn = import_clientespa_module()
    max_c, vends = scan_fn(path)
    print(f"DBI: max_codigo={max_c}, vendedores={len(vends)}")
    stats = import_fn(sb, path)
    print("Resultado:", stats)


if __name__ == "__main__":
    main()
