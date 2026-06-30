#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import datetime
import logging
import argparse
from ftplib import FTP
import dbf

# Configurar ruta absoluta dinámica para poder importar la conexión a Supabase de la app
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.getenv("PROJECT_ROOT", BASE_DIR)
UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, UTILS_DIR)

# Carpeta de datos local
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Configurar Logging
LOG_FILE = os.path.join(DATA_DIR, "ftp_sync.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ftp_sync")

METADATA_FILE = os.path.join(DATA_DIR, "ftp_sync_metadata.json")

def load_secrets():
    """Carga las credenciales de Supabase y FTP desde secrets.toml o Streamlit."""
    # Intentar cargar vía Streamlit si está en contexto
    try:
        import streamlit as st
        if st.secrets:
            return {
                "SUPABASE_URL": st.secrets["SUPABASE_URL"],
                "SUPABASE_KEY": st.secrets["SUPABASE_KEY"],
                "FTP_HOST": st.secrets["FTP_HOST"],
                "FTP_PORT": int(st.secrets["FTP_PORT"]),
                "FTP_USER": st.secrets["FTP_USER"],
                "FTP_PASS": st.secrets["FTP_PASS"],
            }
    except Exception:
        pass

    # Cargar manualmente de secrets.toml
    secrets = {}
    secrets_path = os.path.join(PROJECT_ROOT, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        with open(secrets_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key in ["FTP_PORT"]:
                        secrets[key] = int(val)
                    else:
                        secrets[key] = val
    return secrets

def update_metadata(update_dict):
    """Actualiza de forma segura el archivo JSON de metadatos de sincronización."""
    metadata = {}
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception:
            metadata = {}
    
    metadata.update(update_dict)
    metadata["last_sync_time"] = datetime.datetime.now().isoformat()
    
    try:
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error escribiendo metadatos: {e}")

def get_supabase_client():
    """Inicializa y retorna el cliente de Supabase usando credenciales cargadas."""
    try:
        from modulos.db import supabase
        if supabase is not None:
            return supabase
    except Exception:
        pass
    
    # Si no se puede importar de modulos.db (fuera de Streamlit), crearlo aquí
    secrets = load_secrets()
    url = secrets.get("SUPABASE_URL")
    key = secrets.get("SUPABASE_KEY")
    if url and key:
        from supabase import create_client
        return create_client(url, key)
    return None

def resolve_ftp_host(host):
    """
    Intenta resolver el host de forma robusta:
    1. Usando DNS local (socket.gethostbyname).
    2. Si falla, consulta la API HTTP de Cloudflare DNS (DoH) para obtener el IP.
    3. Si falla, retorna una IP de respaldo si el host es messina.dns-dns.com.
    """
    if not host:
        return host
        
    # Si ya es un IP (v4), no resolver
    if host.replace(".", "").isdigit():
        return host

    import socket
    # 1. Intentar resolución normal
    try:
        ip = socket.gethostbyname(host)
        logger.info(f"DNS local resolvió {host} -> {ip}")
        return ip
    except Exception as e:
        logger.warning(f"DNS local falló para {host} ({e}). Probando Cloudflare DNS-over-HTTPS...")

    # 2. Intentar vía Cloudflare DoH
    try:
        import requests
        url = f"https://cloudflare-dns.com/dns-query?name={host}&type=A"
        response = requests.get(url, headers={"accept": "application/dns-json"}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "Answer" in data and len(data["Answer"]) > 0:
                ip = data["Answer"][0]["data"].strip()
                logger.info(f"Cloudflare DoH resolvió {host} -> {ip}")
                return ip
    except Exception as doh_err:
        logger.error(f"Fallo en Cloudflare DoH: {doh_err}")

    # 3. Respaldo hardcoded si el DNS dinámico está totalmente inaccesible
    if "messina.dns-dns.com" in host.lower():
        fallback_ip = "201.251.249.120"
        logger.warning(f"Usando IP de respaldo fija para messina.dns-dns.com: {fallback_ip}")
        return fallback_ip

    return host

def test_connection():
    """Prueba la conexión al servidor FTP. Retorna (Success, Message)."""
    secrets = load_secrets()
    host = secrets.get("FTP_HOST")
    port = secrets.get("FTP_PORT", 21)
    user = secrets.get("FTP_USER")
    passwd = secrets.get("FTP_PASS")
    
    if not all([host, port, user, passwd]):
        return False, "Faltan credenciales de FTP en los secretos."
        
    try:
        resolved_host = resolve_ftp_host(host)
        ftp = FTP()
        ftp.connect(resolved_host, port, timeout=10)
        ftp.login(user, passwd)
        welcome = ftp.getwelcome()
        ftp.quit()
        return True, f"Conexión exitosa. Servidor: {welcome}"
    except Exception as e:
        return False, str(e)

def upload_exports():
    """Sube archivos exportados (.dbi) de la carpeta local 'data' al FTP."""
    logger.info("Iniciando subida de archivos exportados a FTP...")
    secrets = load_secrets()
    host = secrets.get("FTP_HOST")
    port = secrets.get("FTP_PORT", 21)
    user = secrets.get("FTP_USER")
    passwd = secrets.get("FTP_PASS")
    
    archivos_a_subir = [
        "Clientes_web.dbi",
        "Clientes_web.fpt",
        "domicilios_entrega.txt"
    ]
    
    archivos_encontrados = []
    for f in archivos_a_subir:
        path = os.path.join(DATA_DIR, f)
        if os.path.exists(path):
            archivos_encontrados.append(path)
            
    if not archivos_encontrados:
        msg = "No se encontraron archivos .dbi para subir en data/"
        logger.info(msg)
        update_metadata({
            "last_upload_time": datetime.datetime.now().isoformat(),
            "last_upload_status": "Success",
            "last_upload_error": "No files found to upload"
        })
        return True, msg
        
    try:
        resolved_host = resolve_ftp_host(host)
        ftp = FTP()
        ftp.connect(resolved_host, port, timeout=15)
        ftp.login(user, passwd)
        
        for filepath in archivos_encontrados:
            filename = os.path.basename(filepath)
            logger.info(f"Subiendo {filename} al FTP...")
            with open(filepath, "rb") as file_to_upload:
                ftp.storbinary(f"STOR {filename}", file_to_upload)
            logger.info(f"Subido exitosamente: {filename}")
            
        ftp.quit()
        
        msg = f"Se subieron correctamente {len(archivos_encontrados)} archivos al FTP."
        logger.info(msg)
        update_metadata({
            "last_upload_time": datetime.datetime.now().isoformat(),
            "last_upload_status": "Success",
            "last_upload_error": ""
        })
        return True, msg
    except Exception as e:
        error_msg = f"Error al subir archivos al FTP: {e}"
        logger.error(error_msg)
        update_metadata({
            "last_upload_time": datetime.datetime.now().isoformat(),
            "last_upload_status": "Error",
            "last_upload_error": str(e)
        })
        return False, error_msg

def download_and_import():
    """Descarga CLIENTESPA.DBI y CODIGOSMP.DBI desde el FTP y actualiza la base de datos."""
    logger.info("Iniciando descarga e importación de bases de datos desde FTP...")
    secrets = load_secrets()
    host = secrets.get("FTP_HOST")
    port = secrets.get("FTP_PORT", 21)
    user = secrets.get("FTP_USER")
    passwd = secrets.get("FTP_PASS")
    
    db_files = ["CLIENTESPA.DBI", "CODIGOSMP.DBI"]
    descargados = {}
    
    try:
        resolved_host = resolve_ftp_host(host)
        ftp = FTP()
        ftp.connect(resolved_host, port, timeout=15)
        ftp.login(user, passwd)
        
        # Obtener lista de archivos en FTP para verificar existencia
        ftp_files = []
        ftp.retrlines("NLST", ftp_files.append)
        
        # Filtro de mayúsculas/minúsculas
        ftp_files_lower = [f.lower() for f in ftp_files]
        
        for db_file in db_files:
            if db_file.lower() in ftp_files_lower:
                # Obtener el nombre exacto con el casing correcto
                exact_name = ftp_files[ftp_files_lower.index(db_file.lower())]
                local_path = os.path.join(DATA_DIR, db_file)
                logger.info(f"Descargando {exact_name} desde FTP...")
                with open(local_path, "wb") as f_out:
                    ftp.retrbinary(f"RETR {exact_name}", f_out.write)
                logger.info(f"Descargado: {db_file}")
                descargados[db_file] = local_path
            else:
                logger.warning(f"Archivo {db_file} no se encontró en el FTP.")
                
        ftp.quit()
    except Exception as e:
        error_msg = f"Error de red/FTP durante la descarga: {e}"
        logger.error(error_msg)
        update_metadata({
            "last_download_time": datetime.datetime.now().isoformat(),
            "last_download_status": "Error",
            "last_download_error": error_msg
        })
        return False, error_msg
        
    if not descargados:
        msg = "No se pudo descargar ningún archivo DBI desde el FTP."
        logger.info(msg)
        update_metadata({
            "last_download_time": datetime.datetime.now().isoformat(),
            "last_download_status": "Success",
            "last_download_error": "No files downloaded from FTP"
        })
        return True, msg
        
    supabase = get_supabase_client()
    if supabase is None:
        error_msg = "No se pudo establecer conexión con Supabase para la importación."
        logger.error(error_msg)
        update_metadata({
            "last_download_time": datetime.datetime.now().isoformat(),
            "last_download_status": "Error",
            "last_download_error": error_msg
        })
        return False, error_msg
        
    # --- PROCESAR CLIENTESPA.DBI ---
    if "CLIENTESPA.DBI" in descargados:
        path_clientes = descargados["CLIENTESPA.DBI"]
        logger.info(f"Procesando {path_clientes}...")
        try:
            from dbi_clientes_loader import import_clientespa_module
            import_clientespa_to_supabase, scan_clientespa_metadata = import_clientespa_module()
            max_codigo, vendedores = scan_clientespa_metadata(path_clientes)
            presea_stats = import_clientespa_to_supabase(supabase, path_clientes, logger=logger)
            logger.info(
                "Clientes Presea FTP→Supabase: nuevos=%s actualizados=%s omitidos=%s errores=%s",
                presea_stats.get("importados", 0),
                presea_stats.get("actualizados", 0),
                presea_stats.get("omitidos", 0),
                presea_stats.get("errores", 0),
            )
            
            logger.info(f"--> Máximo Código en CLIENTESPA: {max_codigo}")
            logger.info(f"--> Vendedores en CLIENTESPA: {len(vendedores)}")
            
            # Actualizar secuencia_codigo
            res_seq = supabase.table('secuencia_codigo').select('id').execute()
            if res_seq.data:
                id_seq = res_seq.data[0]['id']
                supabase.table('secuencia_codigo').update({'ultimo_valor': max(39999, max_codigo)}).eq('id', id_seq).execute()
            else:
                supabase.table('secuencia_codigo').insert({'id': 1, 'ultimo_valor': max(39999, max_codigo)}).execute()
            logger.info("Secuencia de código actualizada exitosamente.")
            
            # Importar vendedores
            for vend in sorted(list(vendedores)):
                email = f"vendedor{vend}@presea.com"
                password = f"clave{vend}"
                
                res = supabase.table('usuarios').select('id').eq('email', email).execute()
                if not res.data:
                    data = {
                        "email": email,
                        "password": password,
                        "role": "vendedor",
                        "nombre_vendedor": f"Vendedor {vend}",
                        "codigo_vendedor": vend,
                        "permiso_alta": True,
                        "permiso_validacion": False,
                        "permiso_exportados": True
                    }
                    supabase.table('usuarios').insert(data).execute()
                    logger.info(f"  [CREADO] Vendedor {vend}")
            
        except Exception as e:
            logger.error(f"Error procesando CLIENTESPA.DBI: {e}")
            
    # --- PROCESAR CODIGOSMP.DBI ---
    if "CODIGOSMP.DBI" in descargados:
        path_codigos = descargados["CODIGOSMP.DBI"]
        logger.info(f"Procesando {path_codigos}...")
        try:
            # 1. Obtener códigos postales existentes en Supabase de forma paginada para evitar duplicados
            logger.info("Obteniendo códigos postales existentes en la base de datos...")
            existing_keys = set()
            limit = 1000
            offset = 0
            while True:
                res = supabase.table('codigos_postales').select('cp, localidad, provincia').range(offset, offset + limit - 1).execute()
                if not res.data:
                    break
                for row in res.data:
                    key = f"{row['cp'].strip()}|{row['localidad'].strip().upper()}|{row['provincia'].strip().upper()}"
                    existing_keys.add(key)
                if len(res.data) < limit:
                    break
                offset += limit
            logger.info(f"Se encontraron {len(existing_keys)} registros únicos en Supabase.")
            
            # 2. Leer registros de la tabla DBI y filtrar nuevos
            nuevos_registros = []
            with dbf.Table(path_codigos, codepage='cp1252') as table:
                table.open()
                for row in table:
                    localidad = str(row['LOCALIDAD']).strip()
                    provincia = str(row['PROVINCIA']).strip()
                    cp = str(row['C_POSTAL']).strip()
                    
                    if localidad and provincia and cp:
                        key = f"{cp}|{localidad.upper()}|{provincia.upper()}"
                        if key not in existing_keys:
                            nuevos_registros.append({
                                "localidad": localidad,
                                "provincia": provincia,
                                "cp": cp
                            })
                            # Agregar al set local para evitar duplicados en el propio archivo
                            existing_keys.add(key)
            
            logger.info(f"--> Se detectaron {len(nuevos_registros)} nuevos códigos postales para insertar.")
            
            # 3. Insertar nuevos de a lotes de 1000
            if nuevos_registros:
                batch_size = 1000
                for i in range(0, len(nuevos_registros), batch_size):
                    batch = nuevos_registros[i:i + batch_size]
                    supabase.table('codigos_postales').insert(batch).execute()
                    logger.info(f"  [INSERTADOS] {i + len(batch)} / {len(nuevos_registros)}")
                logger.info("Base de datos de códigos postales sincronizada con éxito.")
            else:
                logger.info("No se encontraron códigos postales nuevos para importar.")
                
        except Exception as e:
            logger.error(f"Error procesando CODIGOSMP.DBI: {e}")
            
    msg = "Sincronización de descarga e importación completada correctamente."
    logger.info(msg)
    update_metadata({
        "last_download_time": datetime.datetime.now().isoformat(),
        "last_download_status": "Success",
        "last_download_error": ""
    })
    return True, msg

def main():
    parser = argparse.ArgumentParser(description="Script de Sincronización Automática con FTP")
    parser.add_argument(
        "--action", 
        choices=["upload", "download", "sync", "test"],
        default="sync",
        help="Acción a realizar: upload (subir exportaciones), download (descargar e importar), sync (ambas) o test (probar conexión)"
    )
    args = parser.parse_args()
    
    logger.info(f"=== Sincronizador FTP - Acción iniciada: {args.action.upper()} ===")
    
    if args.action == "test":
        success, msg = test_connection()
        print(f"Test FTP: {'EXITOSO' if success else 'FALLIDO'} | Detalle: {msg}")
        sys.exit(0 if success else 1)
        
    elif args.action == "upload":
        success, msg = upload_exports()
        sys.exit(0 if success else 1)
        
    elif args.action == "download":
        success, msg = download_and_import()
        sys.exit(0 if success else 1)
        
    elif args.action == "sync":
        # Ejecutar descarga primero e importación de bases
        success_dl, msg_dl = download_and_import()
        # Luego subir las exportaciones locales pendientes
        success_up, msg_up = upload_exports()
        
        if success_dl and success_up:
            logger.info("=== Sincronización completa finalizada con ÉXITO ===")
            sys.exit(0)
        else:
            logger.error("=== Sincronización finalizada con ERRORES ===")
            sys.exit(1)

if __name__ == "__main__":
    main()
