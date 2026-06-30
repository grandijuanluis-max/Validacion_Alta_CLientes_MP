#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de sincronización para ejecutar localmente en el Servidor Windows (Presea).
Se encarga de:
1. Bajar del FTP los archivos exportados por Streamlit y guardarlos en la carpeta de IMPORTA de Presea.
2. Subir al FTP e importar a Supabase los archivos (CLIENTESPA.DBI, CODIGOSMP.DBI, ramo.csv) depositados en EXPORTA por Presea.
"""

import os
import sys
import json
import csv
import datetime
import logging
from ftplib import FTP
import dbf

def format_sdf_field(val, length, is_numeric=False):
    val_str = str(val) if val is not None else ""
    val_str = val_str.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    if len(val_str) > length:
        val_str = val_str[:length]
    if is_numeric:
        return f"{val_str:>{length}}"
    else:
        return f"{val_str:<{length}}"

# Definir directorios locales por defecto (con claves sensibles pre-encriptadas)
DEFAULT_CONFIG = {
    "FTP_HOST": "messina.dns-dns.com",
    "FTP_PORT": 59921,
    "FTP_USER": "ftppasina",
    "FTP_PASS": "enc:AQAJCgoEf1VBRUNE",
    "SUPABASE_URL": "https://sspjbsbuklqiekvxgdtc.supabase.co",
    "SUPABASE_KEY": "enc:NRg5AQwmLgw8GiMnNCo7VD0MKEF5XGQUMyI6XycKPT0lMCNXTzULLwMGUn9ZfV9rKgUrKwY4ICMJKTonEhkcLx8/CHsGe1hvKgI0GQcCfy9CElsWGTElMwEBD1peaH5zOigaHgcCIFwAKTonVxkfIwYHUwZZfnVrIDgrOAcuJyBAPRMJVR4IDkYqNXdDe1t3ZAIwIFgsJyRGPS0/UB4mDkYoOQIeVURuBScmJjYYOTw0OR4FURFBDgEjJ2sGf0UTGQYcXjYYIDwbFl1XL2gKJA==",
    "IMPORTA_DIR": "F:\\Clientes\\Pasina\\EXPORTACIONES\\Validador\\Importa",
    "EXPORTA_DIR": "F:\\Clientes\\Pasina\\EXPORTACIONES\\Validador\\Exporta",
    "VENTAS_DIR": "F:\\Clientes\\Pasina\\EXPORTACIONES\\Ventas"
}

# Obtener ruta base del ejecutable o del script
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Asegurar imports locales (dbi_clientes, ventas_importer)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

CONFIG_FILE = os.path.join(BASE_DIR, "windows_sync_config.json")
LOG_FILE = os.path.join(BASE_DIR, "windows_sync.log")

# Configurar logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("windows_sync")

import base64

SECRET_SALT = b"PasinaMessinaPresea2026!"

def encrypt_value(value: str) -> str:
    """Cifra un valor usando XOR con un salt y lo codifica en Base64."""
    if not value:
        return ""
    data = value.encode("utf-8")
    encrypted = bytearray()
    for i in range(len(data)):
        encrypted.append(data[i] ^ SECRET_SALT[i % len(SECRET_SALT)])
    return "enc:" + base64.b64encode(encrypted).decode("utf-8")

def decrypt_value(value: str) -> str:
    """Desencripta un valor cifrado con encrypt_value."""
    if not value or not value.startswith("enc:"):
        return value
    try:
        data = base64.b64decode(value[4:])
        decrypted = bytearray()
        for i in range(len(data)):
            decrypted.append(data[i] ^ SECRET_SALT[i % len(SECRET_SALT)])
        return decrypted.decode("utf-8")
    except Exception as e:
        logger.error(f"Error al desencriptar valor: {e}")
        return value

def load_config():
    """Carga la configuración desde el archivo JSON local aplicando cifrado/descifrado transparente."""
    config = DEFAULT_CONFIG.copy()
    sensitive_keys = ["FTP_PASS", "SUPABASE_KEY"]

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                
            needs_rewrite = False
            for k in sensitive_keys:
                if k in loaded:
                    val = loaded[k]
                    # Si no está cifrado (es texto plano o tiene prefijo 'plain:')
                    if not val.startswith("enc:"):
                        if val.startswith("plain:"):
                            val = val[6:]
                        loaded[k] = encrypt_value(val)
                        needs_rewrite = True
                        config[k] = val
                    else:
                        # Si está cifrado, lo guardamos cifrado y luego lo descifraremos al final
                        config[k] = val
                
            # Actualizar otros campos no sensibles (rutas, hosts, etc.)
            for k, v in loaded.items():
                if k not in sensitive_keys:
                    config[k] = v
                    
            if needs_rewrite:
                try:
                    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(loaded, f, indent=2, ensure_ascii=False)
                    logger.info(f"Re-escrita la configuración en {CONFIG_FILE} con credenciales cifradas.")
                except Exception as e:
                    logger.error(f"No se pudo guardar la configuración auto-cifrada: {e}")
                    
        except Exception as e:
            logger.error(f"Error cargando windows_sync_config.json: {e}")
    else:
        logger.info("No se encontró archivo de configuración local. Usando configuración interna embebida.")
        
    # Asegurar que todas las credenciales sensibles queden descifradas en memoria para el programa
    for k in sensitive_keys:
        if k in config and config[k].startswith("enc:"):
            config[k] = decrypt_value(config[k])
            
    return config

def rotate_log_if_needed(log_path, backup_dir):
    """
    Si el archivo de log tiene 90 días o más desde su creación, 
    hace una copia de resguardo en backup_dir y vacía el log original.
    """
    if not os.path.exists(log_path):
        return
    try:
        ctime = os.path.getctime(log_path)
        creation_date = datetime.datetime.fromtimestamp(ctime)
        age = datetime.datetime.now() - creation_date
        if age.days >= 90:
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = creation_date.strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(log_path)
            name, ext = os.path.splitext(filename)
            backup_filename = f"{name}_backup_{timestamp}{ext}"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            import shutil
            shutil.copy2(log_path, backup_path)
            
            # Truncar el archivo original
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"--- Log rotado y vaciado el {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Resguardo: {backup_filename}) ---\n")
            logger.info(f"Log rotado exitosamente: {log_path} -> {backup_filename}")
    except Exception as e:
        logger.error(f"Error rotando log {log_path}: {e}")

def log_exporta(message, config):
    """Escribe un mensaje de registro en exporta_sync.log y maneja su rotación."""
    exporta_dir = config.get("EXPORTA_DIR")
    log_path = os.path.join(exporta_dir, "exporta_sync.log")
    backup_dir = os.path.join(exporta_dir, "Subidos")
    
    rotate_log_if_needed(log_path, backup_dir)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(exporta_dir, exist_ok=True)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        logger.error(f"Error escribiendo en exporta_sync.log: {e}")

def log_importa(message, config):
    """Escribe un mensaje de registro en importa_sync.log y maneja su rotación."""
    importa_dir = config.get("IMPORTA_DIR")
    log_path = os.path.join(importa_dir, "importa_sync.log")
    backup_dir = os.path.join(importa_dir, "No_process")
    
    rotate_log_if_needed(log_path, backup_dir)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(importa_dir, exist_ok=True)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        logger.error(f"Error escribiendo en importa_sync.log: {e}")

def get_supabase_client(config):
    """Inicializa el cliente de Supabase usando la configuración."""
    url = config.get("SUPABASE_URL")
    key = config.get("SUPABASE_KEY")
    if not url or not key:
        logger.error("Error: Faltan las credenciales de Supabase (URL o KEY).")
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        logger.error(f"Error al inicializar el cliente de Supabase: {e}")
        return None

def resolve_ftp_host(host):
    """
    Intenta resolver el host de forma robusta:
    1. Usando DNS local (socket.gethostbyname).
    2. Si falla, consulta la API HTTP de Cloudflare DNS (DoH) para obtener el IP (ignorando la verificación SSL si falla).
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

    # 2. Intentar vía Cloudflare DoH (con bypass SSL por si el OS no tiene root CAs al día)
    try:
        import urllib.request
        import json as json_lib
        import ssl
        url = f"https://cloudflare-dns.com/dns-query?name={host}&type=A"
        req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
            data = json_lib.loads(response.read().decode('utf-8'))
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

def connect_ftp(config):
    """
    Establece conexión al FTP probando secuencialmente múltiples candidatos
    (configuración del usuario, DNS público, IP de respaldo, red local y loopback)
    con puertos comunes (59921, 40093, 21).
    """
    user = config.get("FTP_USER")
    passwd = config.get("FTP_PASS")
    
    # Lista de hosts base
    base_hosts = []
    
    # 1. Configuración de usuario
    user_host = config.get("FTP_HOST")
    if user_host:
        base_hosts.append((user_host, "Configuración del usuario"))
        
    # 2. FTP Público (DNS y puerto oficial)
    base_hosts.append(("messina.dns-dns.com", "FTP Público (DNS)"))
    
    # 3. FTP Público (IP fija de respaldo y puerto oficial)
    base_hosts.append(("201.251.249.120", "FTP Público (IP Fija)"))
    
    # 4. FTP Local histórico
    base_hosts.append(("192.168.196.217", "FTP Local histórico"))
    
    # 5. Localhost (por si el FTP corre en el mismo servidor)
    base_hosts.append(("127.0.0.1", "Localhost"))
    
    # 6. IP local de la propia máquina (detectada de forma dinámica)
    local_ip = None
    try:
        import socket
        local_ip = socket.gethostbyname(socket.gethostname())
        if local_ip and local_ip != "127.0.0.1":
            base_hosts.append((local_ip, f"IP Local de la máquina ({local_ip})"))
            
            # Buscar en la misma subred de la máquina local (ej: .1, .2, .254)
            parts = local_ip.split(".")
            if len(parts) == 4:
                subnet_base = ".".join(parts[:3])
                base_hosts.append((f"{subnet_base}.1", "Puerta de enlace local (.1)"))
                base_hosts.append((f"{subnet_base}.2", "Vecino local (.2)"))
                base_hosts.append((f"{subnet_base}.254", "Puerta de enlace local (.254)"))
    except Exception:
        pass

    # Puertos a intentar para cada host
    ports = [59921, 40093, 21]
    
    tried = set()
    last_error = None
    
    for host_cand, desc in base_hosts:
        # Intentar resolver DNS si aplica
        try:
            resolved_host = resolve_ftp_host(host_cand)
        except Exception:
            resolved_host = host_cand
            
        for port_cand in ports:
            key = (resolved_host, port_cand)
            if key in tried:
                continue
            tried.add(key)
            
            # Elegir timeout inteligente: corto para IPs locales, normal para públicas
            is_local = (
                resolved_host.startswith("192.168.") or 
                resolved_host.startswith("127.") or 
                resolved_host == "localhost"
            )
            timeout_val = 1.5 if is_local else 5.0
            
            logger.info(f"Intentando conectar a {desc}: {resolved_host}:{port_cand} (timeout: {timeout_val}s)...")
            try:
                ftp = FTP()
                ftp.connect(resolved_host, port_cand, timeout=timeout_val)
                ftp.login(user, passwd)
                logger.info(f"¡Conexión establecida con éxito con {desc} ({resolved_host}:{port_cand})!")
                return ftp
            except Exception as e:
                last_error = e
                logger.warning(f"Fallo conexión con {desc} ({resolved_host}:{port_cand}): {e}")
                try:
                    ftp.close()
                except Exception:
                    pass
                
    if last_error:
        raise last_error
    raise Exception("No se pudo establecer conexión con el FTP usando ninguno de los candidatos.")

def sync_ftp_to_importa(config):
    """
    BAJADA: Descarga los archivos generados por el validador desde el FTP
    y los copia en la carpeta IMPORTA del servidor de Presea.
    """
    logger.info("--- Iniciando descarga desde FTP hacia IMPORTA local ---")
    importa_dir = config.get("IMPORTA_DIR")
    os.makedirs(importa_dir, exist_ok=True)
    
    archivos_a_descargar = [
        "Clientes_web.dbi",
        "Clientes_web.fpt",
        "domicilios_entrega.txt"
    ]
    
    try:
        ftp = connect_ftp(config)
        
        # Obtener lista de archivos remotos
        ftp_files = []
        ftp.retrlines("NLST", ftp_files.append)
        ftp_files_lower = [f.lower() for f in ftp_files]
        
        descargados_count = 0
        for f in archivos_a_descargar:
            if f.lower() in ftp_files_lower:
                exact_name = ftp_files[ftp_files_lower.index(f.lower())]
                local_path = os.path.join(importa_dir, f)
                
                # Mover archivo existente si ya existe (sin procesar por Presea)
                if os.path.exists(local_path):
                    noprocess_dir = os.path.join(importa_dir, "No_process")
                    os.makedirs(noprocess_dir, exist_ok=True)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    name, ext = os.path.splitext(f)
                    noprocess_filename = f"{name}_{timestamp}{ext}"
                    noprocess_path = os.path.join(noprocess_dir, noprocess_filename)
                    
                    import shutil
                    try:
                        shutil.move(local_path, noprocess_path)
                        log_importa(f"Archivo existente '{f}' detectado en Importa. Moviendo sin procesar a No_process/{noprocess_filename}", config)
                        logger.info(f"Moviendo archivo existente sin procesar: {f} -> No_process/{noprocess_filename}")
                    except Exception as move_err:
                        logger.error(f"Error moviendo {f} a No_process: {move_err}")
                
                logger.info(f"Descargando {exact_name} a {local_path}...")
                with open(local_path, "wb") as local_f:
                    ftp.retrbinary(f"RETR {exact_name}", local_f.write)
                
                log_importa(f"Descargado con éxito: {exact_name}", config)
                descargados_count += 1
            else:
                logger.debug(f"El archivo {f} no está en el FTP.")
                
        ftp.quit()
        logger.info(f"Descarga finalizada. Se guardaron {descargados_count} archivos en {importa_dir}.")
        return True
    except Exception as e:
        logger.error(f"Error en el proceso de descarga desde FTP: {e}")
        log_importa(f"Error en descarga: {e}", config)
        return False

def sync_exporta_to_ftp_and_supabase(config):
    """
    SUBIDA: Lee los archivos locales de la carpeta EXPORTA de Presea,
    los sube al FTP para respaldo e importa sus datos directamente en Supabase.
    """
    logger.info("--- Iniciando proceso de lectura e importación desde EXPORTA local ---")
    exporta_dir = config.get("EXPORTA_DIR")
    if not os.path.exists(exporta_dir):
        logger.warning(f"La carpeta de exportación {exporta_dir} no existe. Omitiendo subida.")
        return True
        
    supabase = get_supabase_client(config)
    if supabase is None:
        logger.error("No se puede sincronizar con la base de datos sin cliente Supabase.")
        return False
        
    ftp = None
    try:
        # --- 1. PROCESAR CLIENTESPA.DBI (Secuencia y Vendedores) ---
        path_clientes = os.path.join(exporta_dir, "CLIENTESPA.DBI")
        if os.path.exists(path_clientes):
            logger.info("Detectado CLIENTESPA.DBI local. Subiendo al FTP...")
            # Subir al FTP
            ftp = connect_ftp(config)
            with open(path_clientes, "rb") as f_up:
                ftp.storbinary("STOR CLIENTESPA.DBI", f_up)
            # Subir sidecar memo si existe (campo MEMO en el DBI)
            base_cli, _ = os.path.splitext(path_clientes)
            for ext in (".FPT", ".fpt", ".DBT", ".dbt"):
                sidecar = base_cli + ext
                if os.path.exists(sidecar):
                    remote_name = "CLIENTESPA" + ext
                    with open(sidecar, "rb") as f_memo:
                        ftp.storbinary(f"STOR {remote_name}", f_memo)
                    logger.info(f"Subido {remote_name} al FTP.")
            logger.info("Subido CLIENTESPA.DBI al FTP.")
            
            # Procesar datos
            logger.info("Procesando CLIENTESPA.DBI para Supabase...")
            try:
                from dbi_clientes_loader import import_clientespa_module
                import_clientespa_to_supabase, scan_clientespa_metadata = import_clientespa_module()
                max_codigo, vendedores = scan_clientespa_metadata(path_clientes)
                presea_stats = import_clientespa_to_supabase(supabase, path_clientes, logger=logger)
                if presea_stats.get("error_apertura"):
                    raise RuntimeError(presea_stats["error_apertura"])
                log_exporta(
                    f"CLIENTESPA → Supabase: nuevos={presea_stats.get('importados', 0)} "
                    f"actualizados={presea_stats.get('actualizados', 0)} "
                    f"omitidos={presea_stats.get('omitidos', 0)} errores={presea_stats.get('errores', 0)}",
                    config,
                )
                logger.info(
                    "Clientes Presea: nuevos=%s actualizados=%s omitidos=%s (app=%s) errores=%s",
                    presea_stats.get("importados", 0),
                    presea_stats.get("actualizados", 0),
                    presea_stats.get("omitidos", 0),
                    presea_stats.get("omitidos_app", 0),
                    presea_stats.get("errores", 0),
                )
            except Exception as presea_err:
                logger.error(f"Error importando clientes Presea: {presea_err}")
                log_exporta(f"ERROR import CLIENTESPA: {presea_err}", config)
                max_codigo, vendedores = 0, set()
                with dbf.Table(path_clientes, codepage='cp1252') as table:
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
            
            # Actualizar secuencia_codigo
            logger.info(f"Max codigo detectado: {max_codigo}. Actualizando secuencia en la DB...")
            res_seq = supabase.table('secuencia_codigo').select('id').execute()
            if res_seq.data:
                id_seq = res_seq.data[0]['id']
                supabase.table('secuencia_codigo').update({'ultimo_valor': max(39999, max_codigo)}).eq('id', id_seq).execute()
            else:
                supabase.table('secuencia_codigo').insert({'id': 1, 'ultimo_valor': max(39999, max_codigo)}).execute()
                
            # Crear vendedores si no existen
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
                    logger.info(f"  [CREADO] Vendedor {vend} en Supabase")
            
            # Mover archivo procesado a Subidos
            subidos_dir = os.path.join(exporta_dir, "Subidos")
            os.makedirs(subidos_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext("CLIENTESPA.DBI")
            subido_filename = f"{name}_{timestamp}{ext}"
            subido_path = os.path.join(subidos_dir, subido_filename)
            import shutil
            try:
                shutil.move(path_clientes, subido_path)
                log_exporta(f"CLIENTESPA.DBI procesado y subido con éxito a Supabase. Archivo movido a Subidos/{subido_filename}", config)
                logger.info(f"CLIENTESPA.DBI movido a Subidos/{subido_filename}")
            except Exception as move_err:
                logger.error(f"Error moviendo CLIENTESPA.DBI: {move_err}")
                log_exporta(f"Error al mover CLIENTESPA.DBI: {move_err}", config)
                    
        # --- 2. PROCESAR CODIGOSMP.DBI (Códigos Postales) ---
        path_codigos = os.path.join(exporta_dir, "CODIGOSMP.DBI")
        if os.path.exists(path_codigos):
            logger.info("Detectado CODIGOSMP.DBI local. Subiendo al FTP...")
            # Subir al FTP
            if not ftp:
                ftp = connect_ftp(config)
            with open(path_codigos, "rb") as f_up:
                ftp.storbinary("STOR CODIGOSMP.DBI", f_up)
            logger.info("Subido CODIGOSMP.DBI al FTP.")
            
            # Obtener códigos existentes en Supabase
            logger.info("Obteniendo códigos postales de Supabase para evitar duplicados...")
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
            
            # Comparar e importar nuevos
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
                            existing_keys.add(key)
            
            logger.info(f"--> Se detectaron {len(nuevos_registros)} nuevos códigos postales para insertar.")
            if nuevos_registros:
                batch_size = 1000
                for i in range(0, len(nuevos_registros), batch_size):
                    batch = nuevos_registros[i:i + batch_size]
                    supabase.table('codigos_postales').insert(batch).execute()
                logger.info("Base de datos de códigos postales sincronizada.")
            
            # Mover archivo procesado a Subidos
            subidos_dir = os.path.join(exporta_dir, "Subidos")
            os.makedirs(subidos_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext("CODIGOSMP.DBI")
            subido_filename = f"{name}_{timestamp}{ext}"
            subido_path = os.path.join(subidos_dir, subido_filename)
            import shutil
            try:
                shutil.move(path_codigos, subido_path)
                log_exporta(f"CODIGOSMP.DBI procesado y subido con éxito a Supabase. Archivo movido a Subidos/{subido_filename}", config)
                logger.info(f"CODIGOSMP.DBI movido a Subidos/{subido_filename}")
            except Exception as move_err:
                logger.error(f"Error moviendo CODIGOSMP.DBI: {move_err}")
                log_exporta(f"Error al mover CODIGOSMP.DBI: {move_err}", config)
                
        # --- 3. PROCESAR RAMO.CSV (Ramos de clientes) ---
        path_ramos = os.path.join(exporta_dir, "ramo.csv")
        if os.path.exists(path_ramos):
            logger.info("Detectado ramo.csv local. Subiendo al FTP...")
            # Subir al FTP
            if not ftp:
                ftp = connect_ftp(config)
            with open(path_ramos, "rb") as f_up:
                ftp.storbinary("STOR ramo.csv", f_up)
            logger.info("Subido ramo.csv al FTP.")
            
            logger.info("Importando ramos en Supabase...")
            ramos_cargados = 0
            with open(path_ramos, mode='r', encoding='utf-8-sig') as f_csv:
                # Intentar detectar delimitador (; o ,)
                content = f_csv.read(2048)
                f_csv.seek(0)
                delimiter = ';' if ';' in content else ','
                
                reader = csv.DictReader(f_csv, delimiter=delimiter)
                for row in reader:
                    try:
                        ramo_num = int(row['ramo'].strip())
                        descrip_val = row['descrip'].strip()
                        if ramo_num and descrip_val:
                            # Hacer upsert (insertar o actualizar si ya existe la clave primaria)
                            supabase.table('ramos').upsert({
                                "ramo": ramo_num,
                                "descrip": descrip_val
                            }).execute()
                            ramos_cargados += 1
                    except Exception as err_row:
                        logger.error(f"Error procesando fila de ramo: {row}. Detalle: {err_row}")
                        
            logger.info(f"Se sincronizaron {ramos_cargados} ramos impositivos/comerciales.")
            
            # Mover archivo procesado a Subidos
            subidos_dir = os.path.join(exporta_dir, "Subidos")
            os.makedirs(subidos_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext("ramo.csv")
            subido_filename = f"{name}_{timestamp}{ext}"
            subido_path = os.path.join(subidos_dir, subido_filename)
            import shutil
            try:
                shutil.move(path_ramos, subido_path)
                log_exporta(f"ramo.csv procesado y subido con éxito a Supabase. Archivo movido a Subidos/{subido_filename}", config)
                logger.info(f"ramo.csv movido a Subidos/{subido_filename}")
            except Exception as move_err:
                logger.error(f"Error moviendo ramo.csv: {move_err}")
                log_exporta(f"Error al mover ramo.csv: {move_err}", config)

        if ftp:
            ftp.quit()
        logger.info("Proceso de exportación e importación completado con éxito.")
        return True
    except Exception as e:
        if ftp:
            try: ftp.quit()
            except: pass
        logger.error(f"Error en el proceso de carga desde EXPORTA hacia FTP/Supabase: {e}")
        log_exporta(f"Error en proceso de exportación/subida: {e}", config)
        return False

def sync_ventas_to_ftp_and_supabase(config):
    """
    Lee el archivo ventas.dbi local (desde VENTAS_DIR), lo sube al FTP como respaldo,
    e importa/actualiza cada registro de ventas en Supabase de forma incremental
    (usando upsert en base al índice único compuesto fecha+empresa+formulario+numero+cod_clien+cod_alfa+bultos).
    """
    logger.info("--- Iniciando proceso de sincronización de Ventas (DBI) ---")
    import shutil
    
    # Obtener el directorio de ventas
    ventas_dir = config.get("VENTAS_DIR", "F:\\Clientes\\Pasina\\EXPORTACIONES\\Ventas")
    path_ventas = os.path.join(ventas_dir, "ventas.dbi")
    
    if not os.path.exists(path_ventas):
        # Si no existe en la ruta de producción, verificar si existe en la raíz del proyecto para facilitar pruebas locales
        path_test = os.path.join(BASE_DIR, "ventas.dbi")
        path_test_parent = os.path.join(os.path.dirname(BASE_DIR), "ventas.dbi")
        if os.path.exists(path_test):
            path_ventas = path_test
            ventas_dir = BASE_DIR
        elif os.path.exists(path_test_parent):
            path_ventas = path_test_parent
            ventas_dir = os.path.dirname(BASE_DIR)
        else:
            logger.info("No se encontró el archivo ventas.dbi. Omitiendo sincronización de ventas.")
            return True
            
    logger.info(f"Archivo ventas.dbi detectado en: {path_ventas}")
    
    # 1. Conectar a Supabase
    supabase = get_supabase_client(config)
    if supabase is None:
        logger.error("No se puede sincronizar ventas sin cliente Supabase.")
        return False
        
    # 2. Subir copia de ventas.dbi al FTP
    ftp = None
    try:
        logger.info("Subiendo copia de ventas.dbi al FTP...")
        ftp = connect_ftp(config)
        
        # Intentar crear la carpeta Ventas en el FTP
        try:
            ftp.mkd("Ventas")
            logger.info("Carpeta 'Ventas' creada en el FTP.")
        except Exception:
            pass
            
        try:
            ftp.cwd("Ventas")
        except Exception:
            pass
            
        with open(path_ventas, "rb") as f_up:
            ftp.storbinary("STOR ventas.dbi", f_up)
        logger.info("Subida de ventas.dbi al FTP finalizada.")
    except Exception as ftp_err:
        logger.warning(f"No se pudo subir copia de ventas.dbi al FTP (se continúa con la importación a Supabase): {ftp_err}")
    finally:
        if ftp:
            try: ftp.quit()
            except: pass
            
    # 3. Leer e importar datos a Supabase
    logger.info("Importando registros de ventas en la base de datos desde ventas.dbi...")

    try:
        # Importador compartido (misma lógica que la app Streamlit)
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        from ventas_importer import import_ventas_dbi

        stats = import_ventas_dbi(supabase, path_ventas, batch_size=1000, logger=logger)
        total_procesados = stats["importados"]
        logger.info(
            "Importación ventas: %s registros | DBF=%s | sin_fecha=%s | dup_dbf=%s | rango=%s→%s",
            total_procesados,
            stats["total_dbf"],
            stats["sin_fecha"],
            stats["duplicados_dbf"],
            stats.get("min_fecha"),
            stats.get("max_fecha"),
        )
        # 4. Mover el archivo procesado a la carpeta Subidos
        subidos_dir = os.path.join(ventas_dir, "Subidos")
        os.makedirs(subidos_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        subido_filename = f"ventas_{timestamp}.dbi"
        subido_path = os.path.join(subidos_dir, subido_filename)
        
        shutil.move(path_ventas, subido_path)
        logger.info(f"Archivo ventas.dbi procesado e importado con éxito. Archivo movido a Subidos/{subido_filename}")
        
        # Mover también archivos de memo si existen (sean reales o ficticios creados por nosotros)
        base_src, _ = os.path.splitext(path_ventas)
        for ext in [".dbt", ".fpt"]:
            src_memo = base_src + ext
            if os.path.exists(src_memo):
                try:
                    dest_memo = os.path.join(subidos_dir, f"ventas_{timestamp}{ext}")
                    shutil.move(src_memo, dest_memo)
                    logger.info(f"Archivo de memo {ext} movido a Subidos/{f'ventas_{timestamp}{ext}'}")
                except Exception as memo_move_err:
                    logger.warning(f"No se pudo mover el archivo de memo {ext}: {memo_move_err}")
        
        # Registrar log en base local si aplica
        log_exporta(f"Sincronización exitosa de Ventas (DBI): {total_procesados} registros importados. Movido a Subidos/{subido_filename}", config)
        return True
    except Exception as e:
        logger.error(f"Error procesando el archivo de ventas DBI: {e}")
        log_exporta(f"Error procesando ventas.dbi: {e}", config)
        return False

def auto_export_a_exportar_to_importa(config):
    """
    Exportación automática a las 21hs de Argentina (rango de 21:00 a 05:00 hs).
    Si hay clientes en estado 'A Exportar' en Supabase, genera los archivos DBI
    directamente en la carpeta IMPORTA del servidor Windows, los marca como 'Exportado'
    y los sube de respaldo al FTP.
    """
    now = datetime.datetime.now()
    # Rango de ejecución: de 21:00 a 05:00 hs (hora local del servidor de Windows)
    # Si viene el argumento '--force-auto-export', se ignora el rango de hora.
    force_export = "--force-auto-export" in sys.argv
    if not force_export and not (now.hour >= 21 or now.hour < 5):
        return True

    logger.info("--- Iniciando comprobación de exportación automática (rango 21hs a 05hs) ---")
    supabase = get_supabase_client(config)
    if supabase is None:
        logger.error("No se puede realizar la exportación automática sin cliente Supabase.")
        return False

    try:
        # 1. Buscar clientes con estado 'A Exportar'
        response = supabase.table('clientes_pendientes').select('*').eq('estado', 'A Exportar').execute()
        if not response.data:
            logger.info("No hay clientes en estado 'A Exportar' para procesar automáticamente.")
            return True

        clientes_a_exportar = response.data
        logger.info(f"Detectados {len(clientes_a_exportar)} clientes para exportar automáticamente.")

        # 2. Obtener secuencia de códigos
        secuencia_resp = supabase.table('secuencia_codigo').select('ultimo_valor').eq('id', 1).execute()
        ultimo_valor = 0 if not secuencia_resp.data else secuencia_resp.data[0]['ultimo_valor']
        numero_inicio = max(40000, int(ultimo_valor) + 1)

        # 3. Definir directorio de salida IMPORTA
        importa_dir = config.get("IMPORTA_DIR")
        os.makedirs(importa_dir, exist_ok=True)

        ruta_clientes_web = os.path.join(importa_dir, "Clientes_web.dbi")
        ruta_domicilios = os.path.join(importa_dir, "domicilios_entrega.txt")

        # Mover archivos existentes si ya existen en IMPORTA a la carpeta No_process para no pisar
        archivos_generados = [
            "Clientes_web.dbi",
            "Clientes_web.fpt",
            "domicilios_entrega.txt"
        ]
        
        import shutil
        for f in archivos_generados:
            local_path = os.path.join(importa_dir, f)
            if os.path.exists(local_path):
                noprocess_dir = os.path.join(importa_dir, "No_process")
                os.makedirs(noprocess_dir, exist_ok=True)
                timestamp = now.strftime("%Y%m%d_%H%M%S")
                name, ext = os.path.splitext(f)
                noprocess_filename = f"{name}_auto_{timestamp}{ext}"
                noprocess_path = os.path.join(noprocess_dir, noprocess_filename)
                try:
                    shutil.move(local_path, noprocess_path)
                    log_importa(f"Exportación automática: moviendo archivo existente '{f}' a No_process/{noprocess_filename}", config)
                    logger.info(f"Moviendo archivo existente en Importa: {f} -> No_process/{noprocess_filename}")
                except Exception as move_err:
                    logger.error(f"Error moviendo {f} a No_process en exportación automática: {move_err}")

        # 4. Escribir Clientes_web.dbi
        schema_str = (
            "CODIGO N(6,0); NOMBRE C(30); N_FANTASIA C(30); CUIT N(12,0); "
            "DOMICILIO C(50); LOCALIDAD C(35); C_POSTAL C(50); PROVINCIA C(25); "
            "PAIS C(20); CONTACTO C(30); TELEFONO C(40); RUBRO C(30); "
            "TIPO_RESP N(5,1); TIPO_DOC N(2,0); CUIT_S1 N(12,0); CUIT_S2 N(12,0); "
            "TRANSPORTE N(2,0); CONDICION N(2,0); CATEGORIA C(10); LISTAPRE C(10); "
            "VENDEDOR N(6,0); "
            "MEMO M"
        )

        ruta_memo_web = ruta_clientes_web.replace(".dbi", ".fpt")
        if os.path.exists(ruta_memo_web):
            os.remove(ruta_memo_web)

        table = dbf.Table(ruta_clientes_web, schema_str, dbf_type='fp', codepage='cp1252')
        table.open(mode=dbf.READ_WRITE)

        codigo_actual = numero_inicio
        for row in clientes_a_exportar:
            cuit_num = str(row.get('cuit', '0')).replace('-', '').replace(' ', '')
            cuit_num = int(cuit_num) if cuit_num.isdigit() else 0

            cuit_s1_num = str(row.get('cuit_socio1', '0')).replace('-', '').replace(' ', '')
            cuit_s1_num = int(cuit_s1_num) if cuit_s1_num.isdigit() and cuit_s1_num != '' else 0

            cuit_s2_num = str(row.get('cuit_socio2', '0')).replace('-', '').replace(' ', '')
            cuit_s2_num = int(cuit_s2_num) if cuit_s2_num.isdigit() and cuit_s2_num != '' else 0

            try: tipo_resp = float(row.get('tipo_resp', 0.0))
            except: tipo_resp = 0.0

            try: tipo_doc = int(row.get('tipo_doc', 80))
            except: tipo_doc = 80

            try: vendedor_num = int(float(row.get('vendedor', 0))) if row.get('vendedor') is not None else 0
            except: vendedor_num = 0

            registro = (
                codigo_actual,
                str(row.get('nombre', ''))[:30],
                str(row.get('n_fantasia', ''))[:30],
                cuit_num,
                str(row.get('domicilio_f', ''))[:50],
                str(row.get('localidad', ''))[:35],
                str(row.get('c_postal', ''))[:50],
                str(row.get('provincia', ''))[:25],
                str(row.get('pais', ''))[:20],
                str(row.get('contacto', ''))[:30],
                str(row.get('telefono', ''))[:40],
                str(row.get('giro_comercial', ''))[:30],
                tipo_resp,
                tipo_doc,
                cuit_s1_num,
                cuit_s2_num,
                1,
                1,
                "CLI_GRAL",
                "LISTA_UNIC",
                vendedor_num,
                str(row.get('documento', ''))
            )
            table.append(registro)
            codigo_actual += 1

        table.close()


        # Escribir domicilios_entrega.txt
        codigo_actual_dom = numero_inicio
        lineas_dom = []
        for row in clientes_a_exportar:
            codigo_mask = f"{codigo_actual_dom:06d}-000"
            linea_dom = (
                format_sdf_field(codigo_mask, 10, is_numeric=False) +
                format_sdf_field(codigo_actual_dom, 6, is_numeric=True) +
                format_sdf_field(row.get('domicilio_e', ''), 30, is_numeric=False) +
                format_sdf_field(row.get('cp_ent', ''), 5, is_numeric=False) +
                format_sdf_field(row.get('local_ent', ''), 35, is_numeric=False) +
                format_sdf_field(row.get('prov_ent', ''), 25, is_numeric=False) +
                format_sdf_field(row.get('pais', ''), 20, is_numeric=False) +
                format_sdf_field(row.get('local_ent', ''), 35, is_numeric=False)
            )
            lineas_dom.append(linea_dom)
            codigo_actual_dom += 1

        with open(ruta_domicilios, "w", encoding="cp1252", newline="") as f_sdf:
            for line in lineas_dom:
                f_sdf.write(line + "\r\n")

        ultimo_assigned = codigo_actual - 1

        # 5. Actualizar estados en Supabase
        for row in clientes_a_exportar:
            supabase.table('clientes_pendientes').update({'estado': 'Exportado'}).eq('id', row['id']).execute()

        # 6. Actualizar secuencia en Supabase
        if secuencia_resp.data:
            supabase.table('secuencia_codigo').update({'ultimo_valor': ultimo_assigned}).eq('id', 1).execute()
        else:
            supabase.table('secuencia_codigo').insert({'id': 1, 'ultimo_valor': ultimo_assigned}).execute()

        log_importa(f"Procesada exportación automática de {len(clientes_a_exportar)} clientes exitosamente (Cierre del día).", config)
        logger.info(f"Exportación automática finalizada con éxito. Códigos asignados hasta {ultimo_assigned}.")

        # 7. Subir copias al FTP de respaldo
        ftp = None
        try:
            ftp = connect_ftp(config)
            for f in archivos_generados:
                local_path = os.path.join(importa_dir, f)
                if os.path.exists(local_path):
                    with open(local_path, "rb") as f_up:
                        ftp.storbinary(f"STOR {f}", f_up)
            ftp.quit()
            logger.info("Subidas copias de la exportación automática al FTP de respaldo.")
        except Exception as ftp_err:
            logger.warning(f"No se pudieron subir copias al FTP de respaldo (pero los archivos locales se generaron correctamente): {ftp_err}")
            if ftp:
                try: ftp.quit()
                except: pass

        return True
    except Exception as e:
        logger.error(f"Error en el proceso de exportación automática a las 21hs: {e}")
        log_importa(f"Error en exportación automática: {e}", config)
        return False

def main():
    logger.info("=========================================")
    logger.info("Iniciando Sincronizador de Windows Server")
    logger.info("=========================================")
    
    config = load_config()
    
    # 0. Ejecutar exportación automática nocturna si corresponde
    auto_export_a_exportar_to_importa(config)
    
    # 1. Ejecutar descarga desde FTP a carpeta local IMPORTA
    sync_ftp_to_importa(config)
    
    # 2. Ejecutar subida de carpeta local EXPORTA al FTP e importar a Supabase
    sync_exporta_to_ftp_and_supabase(config)
    
    # 3. Importar ventas.dbi desde carpeta Ventas de Presea → Supabase
    sync_ventas_to_ftp_and_supabase(config)
    
    logger.info("Proceso general del Servidor Windows finalizado.")

if __name__ == "__main__":
    main()
