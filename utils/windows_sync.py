#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de sincronización para ejecutar localmente en el Servidor Windows (Presea).
Programación habitual: lunes a viernes, 09:00 / 13:00 / 17:00 (Task Scheduler).

En cada ejecución:
0. Exportar clientes app en estado 'A Exportar' → carpeta IMPORTA de Presea.
1. Bajar del FTP archivos de Streamlit → IMPORTA.
2. Subir e importar a Supabase lo depositado por Presea en EXPORTA (CLIENTESPA, CODIGOSMP, ramo.csv).
3. Importar ventas.dbi → Supabase.
"""

import os
import sys
import json
import csv
import datetime
import logging
import importlib.util
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

# Asegurar imports locales (dbi_clientes, ventas_importer) y módulos del proyecto
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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

# Importadores empaquetados en el .exe (PyInstaller los incluye vía windows_sync.spec)
try:
    import dbi_clientes
    import ventas_importer
except ImportError:
    dbi_clientes = None
    ventas_importer = None


def _resource_path(filename):
    """Ruta a datos embebidos (onefile) o junto al exe/script."""
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        bundled = os.path.join(sys._MEIPASS, filename)
        if os.path.isfile(bundled):
            return bundled
    return os.path.join(BASE_DIR, filename)


def ensure_config_file():
    """Crea windows_sync_config.json desde la plantilla si no existe."""
    if os.path.exists(CONFIG_FILE):
        return False
    import shutil
    src = _resource_path("windows_sync_config.json.example")
    if os.path.isfile(src):
        shutil.copy2(src, CONFIG_FILE)
        logger.warning(
            "Se creó %s desde la plantilla. Completá FTP_USER, FTP_PASS, SUPABASE_URL y SUPABASE_KEY.",
            CONFIG_FILE,
        )
        return True
    logger.info("No hay %s; se usará configuración embebida.", CONFIG_FILE)
    return False


def _module_search_dirs():
    dirs = [BASE_DIR, os.path.join(BASE_DIR, "utils")]
    if PROJECT_ROOT and PROJECT_ROOT not in dirs:
        dirs.append(PROJECT_ROOT)
        dirs.append(os.path.join(PROJECT_ROOT, "utils"))
    return dirs


def _load_py_module_from_file(filename, module_name=None):
    """Carga un .py desde el directorio del exe o utils/ (compatible con PyInstaller onefile)."""
    mod_name = module_name or filename.replace(".py", "")
    tried = []
    for folder in _module_search_dirs():
        path = os.path.join(folder, filename)
        tried.append(path)
        if not os.path.isfile(path):
            continue
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise ImportError(f"No se encontró {filename}. Buscado en: {tried}")


def _import_clientespa_functions():
    if dbi_clientes is not None:
        return dbi_clientes.import_clientespa_to_supabase, dbi_clientes.scan_clientespa_metadata
    try:
        mod = _load_py_module_from_file("dbi_clientes.py", "dbi_clientes")
        return mod.import_clientespa_to_supabase, mod.scan_clientespa_metadata
    except ImportError:
        pass
    try:
        from dbi_clientes_loader import import_clientespa_module
        return import_clientespa_module()
    except ImportError as e:
        raise ImportError(
            "No se pudo cargar dbi_clientes. Recompile con utils\\compilar_sincronizador.bat "
            "(windows_sync.spec)."
        ) from e


def _import_ventas_dbi_function():
    if ventas_importer is not None:
        return ventas_importer.import_ventas_dbi
    try:
        from ventas_importer_loader import import_ventas_module
        return import_ventas_module()
    except ImportError:
        pass
    try:
        from utils.ventas_importer_loader import import_ventas_module
        return import_ventas_module()
    except ImportError as e:
        raise ImportError(
            "No se pudo cargar ventas_importer. Recompile con utils\\compilar_sincronizador.bat "
            "(windows_sync.spec)."
        ) from e


def _ensure_vendedor_presea(supabase, vend: int) -> None:
    """Crea usuario vendedor si no existe; tolerante a columnas opcionales en Supabase."""
    email = f"vendedor{vend}@presea.com"
    res = supabase.table("usuarios").select("id").eq("email", email).execute()
    if res.data:
        return
    payload = {
        "email": email,
        "password": f"clave{vend}",
        "role": "vendedor",
        "usuario": f"Vendedor {vend}",
        "codigo_vendedor": vend,
        "permiso_alta": True,
        "permiso_validacion": False,
        "permiso_exportados": True,
    }
    try:
        supabase.table("usuarios").insert(payload).execute()
        logger.info("  [CREADO] Vendedor %s en Supabase", vend)
    except Exception as e1:
        err = str(e1).lower()
        if "nombre_vendedor" in err or "42703" in err or "pgrst204" in err:
            payload.pop("usuario", None)
            minimal = {
                "email": email,
                "password": f"clave{vend}",
                "role": "vendedor",
                "codigo_vendedor": vend,
                "permiso_alta": True,
            }
            try:
                supabase.table("usuarios").insert(minimal).execute()
                logger.info("  [CREADO] Vendedor %s (payload mínimo)", vend)
                return
            except Exception as e2:
                logger.warning("No se pudo crear vendedor %s: %s", vend, e2)
        else:
            logger.warning("No se pudo crear vendedor %s: %s", vend, e1)

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
    ensure_config_file()
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
            if config.get("SUPABASE_URL"):
                config["SUPABASE_URL"] = str(config["SUPABASE_URL"]).strip().rstrip("/")
            config = _normalize_supabase_url_in_config(config)
            if config.get("SUPABASE_URL") and loaded.get("SUPABASE_URL") != config.get("SUPABASE_URL"):
                loaded["SUPABASE_URL"] = config["SUPABASE_URL"]
                needs_rewrite = True

            if needs_rewrite:
                try:
                    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(loaded, f, indent=2, ensure_ascii=False)
                    logger.info(f"Re-escrita la configuración en {CONFIG_FILE} con credenciales cifradas.")
                except Exception as e:
                    logger.error(f"No se pudo guardar la configuración auto-cifrada: {e}")
                    
        except Exception as e:
            logger.error(f"Error cargando windows_sync_config.json: {e}")
    elif not os.path.exists(CONFIG_FILE):
        logger.info("No se encontró archivo de configuración local. Usando configuración interna embebida.")
        
    # Asegurar que todas las credenciales sensibles queden descifradas en memoria para el programa
    for k in sensitive_keys:
        if k in config and config[k].startswith("enc:"):
            config[k] = decrypt_value(config[k])
            
    config = _normalize_supabase_url_in_config(config)
    return config


def _normalize_supabase_url_in_config(config):
    """Corrige errores frecuentes en SUPABASE_URL (ej. falta .co)."""
    url = (config.get("SUPABASE_URL") or "").strip().rstrip("/")
    if not url:
        return config
    import re

    fixed = url
    # https://xxxx.supabase  →  https://xxxx.supabase.co
    if re.match(r"^https://[a-z0-9-]+\.supabase$", fixed, re.I):
        fixed = fixed + ".co"
        logger.warning(
            "SUPABASE_URL corregida automáticamente (faltaba .co): %s → %s",
            url,
            fixed,
        )
    if fixed != url:
        config["SUPABASE_URL"] = fixed
    return config


def validate_config(config):
    """Avisa en log si la config sigue siendo plantilla o Supabase no resuelve DNS."""
    url = (config.get("SUPABASE_URL") or "").strip()
    key = (config.get("SUPABASE_KEY") or "").strip()
    placeholders = (
        "TU_PROYECTO",
        "tu_service_role",
        "usuario_ftp",
        "password_ftp",
    )
    for token in placeholders:
        if token in url or token in key:
            logger.error(
                "Config incompleta: editá %s con URL y KEY reales de Supabase (no la plantilla).",
                CONFIG_FILE,
            )
            break
    if url.startswith("https://"):
        host = url.replace("https://", "").split("/")[0].strip()
        if host and "TU_PROYECTO" not in host:
            import socket
            try:
                socket.gethostbyname(host)
            except OSError as e:
                logger.error(
                    "SUPABASE_URL no resuelve DNS (%s): %s — revisá la URL en %s.",
                    host,
                    e,
                    CONFIG_FILE,
                )


def _try_ftp_stor_backup(config, uploads, label="archivos"):
    """
    Sube archivos al FTP como respaldo. No lanza excepción: CLIENTESPA → Supabase es local.
    uploads: lista de (ruta_local, nombre_remoto).
    """
    if not uploads:
        return
    ftp = None
    try:
        ftp = connect_ftp(config)
        for local_path, remote_name in uploads:
            with open(local_path, "rb") as f_up:
                ftp.storbinary(f"STOR {remote_name}", f_up)
            logger.info("Respaldo FTP: subido %s.", remote_name)
        logger.info("Respaldo FTP (%s) OK.", label)
    except Exception as e:
        logger.warning(
            "Respaldo FTP omitido (%s). La importación local a Supabase no depende del FTP: %s",
            label,
            e,
        )
    finally:
        if ftp:
            try:
                ftp.quit()
            except Exception:
                pass


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
    url = (config.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = (config.get("SUPABASE_KEY") or "").strip()
    if not url or not key:
        logger.error("Error: Faltan las credenciales de Supabase (URL o KEY).")
        return None
    try:
        from supabase import create_client

        # Sin ClientOptions: evita incompatibilidad entre versiones empaquetadas en PyInstaller
        return create_client(url, key)
    except Exception as e:
        err = str(e)
        logger.error("Error al inicializar Supabase: %s", err)
        if key.startswith("sb_secret_"):
            logger.error(
                "Clave sb_secret_ requiere supabase-py >= 2.16 en el .exe. "
                "Recompilá con compilar_sincronizador.bat o usá legacy service_role (eyJ...) en SUPABASE_KEY."
            )
        elif "invalid" in err.lower() and "api" in err.lower():
            logger.error(
                "SUPABASE_KEY rechazada. Probá legacy service_role (pestaña Legacy en Supabase) "
                "o regenerá la secret key."
            )
        return None


def probe_supabase(config) -> bool:
    """Prueba URL/KEY antes de importar CLIENTESPA."""
    client = get_supabase_client(config)
    if client is None:
        return False
    try:
        client.table("clientes_pendientes").select("id").limit(1).execute()
        logger.info("Supabase OK: lectura en clientes_pendientes.")
        return True
    except Exception as e:
        logger.error("Supabase conectó pero falló la consulta: %s", e)
        err = str(e).lower()
        if "401" in err or "invalid" in err or "jwt" in err:
            logger.error(
                "Credenciales incorrectas o clave incompatible con este .exe. "
                "Usá service_role legacy (eyJ...) o recompilá el exe con supabase reciente."
            )
        if "origen" in err or "codigo" in err or "42703" in err:
            logger.error("Ejecutá supabase_migration_presea_clientes.sql en el proyecto Supabase.")
        return False

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

def _is_private_host(host: str) -> bool:
    h = (host or "").strip()
    return (
        h.startswith("192.168.")
        or h.startswith("10.")
        or h.startswith("172.16.")
        or h in ("127.0.0.1", "localhost")
    )


def connect_ftp(config):
    """
    Establece conexión al FTP probando secuencialmente múltiples candidatos
    (configuración del usuario, DNS público, IP de respaldo, red local y loopback)
    con puertos comunes (59921, 40093, 21).
    """
    user = config.get("FTP_USER")
    passwd = config.get("FTP_PASS")
    user_host = (config.get("FTP_HOST") or "").strip()
    try:
        preferred_port = int(config.get("FTP_PORT") or 59921)
    except (TypeError, ValueError):
        preferred_port = 59921

    if user_host:
        try:
            resolved = resolve_ftp_host(user_host)
            logger.info(
                "FTP configurado: %s:%s (usuario %s)",
                resolved,
                preferred_port,
                user or "?",
            )
            ftp = FTP()
            ftp.connect(resolved, preferred_port, timeout=8.0)
            ftp.login(user, passwd)
            logger.info("Conexión FTP OK (%s:%s)", resolved, preferred_port)
            return ftp
        except Exception as e:
            logger.warning("FTP configurado falló (%s:%s): %s", user_host, preferred_port, e)
            if _is_private_host(user_host) and not config.get("FTP_SCAN_FALLBACK"):
                raise

    # Lista de hosts base
    base_hosts = []

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

    # Puertos a intentar para cada host (priorizar puerto del JSON)
    ports = [preferred_port]
    for p in (59921, 40093, 21):
        if p not in ports:
            ports.append(p)
    
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

def _resolve_exporta_file(exporta_dir, filename):
    """Busca archivo en Exporta (nombre exacto o sin importar mayúsculas)."""
    if not exporta_dir or not os.path.isdir(exporta_dir):
        return None
    direct = os.path.join(exporta_dir, filename)
    if os.path.isfile(direct):
        return direct
    target = filename.lower()
    try:
        for name in os.listdir(exporta_dir):
            if name.lower() == target:
                return os.path.join(exporta_dir, name)
    except OSError as e:
        logger.warning("No se pudo listar %s: %s", exporta_dir, e)
    return None

def sync_exporta_to_ftp_and_supabase(config):
    """
    SUBIDA: Lee los archivos locales de la carpeta EXPORTA de Presea,
    los sube al FTP para respaldo e importa sus datos directamente en Supabase.
    """
    logger.info("--- Iniciando proceso de lectura e importación desde EXPORTA local ---")
    exporta_dir = config.get("EXPORTA_DIR")
    logger.info("EXPORTA_DIR configurado: %s", exporta_dir)
    if not exporta_dir or not os.path.exists(exporta_dir):
        logger.warning(f"La carpeta de exportación {exporta_dir} no existe. Omitiendo subida.")
        log_exporta(f"ERROR: EXPORTA_DIR no existe: {exporta_dir}", config)
        return True

    log_exporta(f"Inicio sync Exporta → FTP + Supabase (dir={exporta_dir})", config)
        
    supabase = get_supabase_client(config)
    if supabase is None:
        logger.error("No se puede sincronizar con la base de datos sin cliente Supabase.")
        log_exporta("ERROR: Supabase no configurado (URL/KEY); no se importa CLIENTESPA.", config)
        return False
        
    ftp = None
    try:
        # --- 1. PROCESAR CLIENTESPA.DBI (Secuencia y Vendedores) ---
        path_clientes = _resolve_exporta_file(exporta_dir, "CLIENTESPA.DBI")
        if path_clientes:
            logger.info("CLIENTESPA detectado en: %s", path_clientes)
            log_exporta(f"CLIENTESPA detectado: {path_clientes}", config)
            logger.info("Importando CLIENTESPA.DBI a Supabase (lectura local; FTP solo respaldo)...")
            import_ok = False
            presea_stats = {}
            try:
                import_clientespa_to_supabase, scan_clientespa_metadata = _import_clientespa_functions()
                max_codigo, vendedores = scan_clientespa_metadata(path_clientes)
                presea_stats = import_clientespa_to_supabase(supabase, path_clientes, logger=logger)
                if presea_stats.get("error_apertura"):
                    raise RuntimeError(presea_stats["error_apertura"])
                if presea_stats.get("errores", 0) > 0:
                    raise RuntimeError(
                        f"Import CLIENTESPA con {presea_stats['errores']} error(es); "
                        f"nuevos={presea_stats.get('importados', 0)}, "
                        f"pendientes={presea_stats.get('pendientes_insert', 0)}"
                    )
                import_ok = True
                if presea_stats.get("importados", 0) == 0:
                    logger.info(
                        "Sin inserts nuevos: pendientes_insert=%s omitidos_existentes=%s total_dbf=%s",
                        presea_stats.get("pendientes_insert", 0),
                        presea_stats.get("omitidos_existentes", 0),
                        presea_stats.get("total_dbf", 0),
                    )
                log_exporta(
                    f"CLIENTESPA → Supabase: nuevos={presea_stats.get('importados', 0)} "
                    f"omitidos_existentes={presea_stats.get('omitidos_existentes', 0)} "
                    f"omitidos={presea_stats.get('omitidos', 0)} errores={presea_stats.get('errores', 0)}",
                    config,
                )
                logger.info(
                    "Clientes Presea: nuevos=%s omitidos_existentes=%s omitidos=%s (app=%s) errores=%s",
                    presea_stats.get("importados", 0),
                    presea_stats.get("omitidos_existentes", 0),
                    presea_stats.get("omitidos", 0),
                    presea_stats.get("omitidos_app", 0),
                    presea_stats.get("errores", 0),
                )
            except Exception as presea_err:
                logger.error(f"Error importando clientes Presea: {presea_err}")
                log_exporta(f"ERROR import CLIENTESPA: {presea_err}", config)
                max_codigo, vendedores = 0, set()
                try:
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
                _ensure_vendedor_presea(supabase, vend)
            
            # Mover archivo procesado a Subidos solo si el import terminó bien
            subidos_dir = os.path.join(exporta_dir, "Subidos")
            os.makedirs(subidos_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext("CLIENTESPA.DBI")
            subido_filename = f"{name}_{timestamp}{ext}"
            subido_path = os.path.join(subidos_dir, subido_filename)
            import shutil
            if import_ok:
                try:
                    shutil.move(path_clientes, subido_path)
                    base_cli, _ = os.path.splitext(path_clientes)
                    for ext_memo in (".FPT", ".fpt", ".DBT", ".dbt"):
                        sidecar = base_cli + ext_memo
                        if os.path.exists(sidecar):
                            dest = os.path.join(subidos_dir, f"{name}_{timestamp}{ext_memo}")
                            shutil.move(sidecar, dest)
                    log_exporta(
                        f"CLIENTESPA.DBI procesado e importado a Supabase. Movido a Subidos/{subido_filename}",
                        config,
                    )
                    logger.info(f"CLIENTESPA.DBI movido a Subidos/{subido_filename}")
                except Exception as move_err:
                    logger.error(f"Error moviendo CLIENTESPA.DBI: {move_err}")
                    log_exporta(f"Error al mover CLIENTESPA.DBI: {move_err}", config)
            else:
                logger.warning(
                    "CLIENTESPA.DBI NO se movió a Subidos porque falló el import. "
                    "Queda en Exporta para reintento en la próxima corrida."
                )
                log_exporta("CLIENTESPA: import fallido; archivo conservado en Exporta.", config)

            if import_ok:
                base_cli, _ = os.path.splitext(path_clientes)
                ftp_uploads = [(path_clientes, "CLIENTESPA.DBI")]
                for ext in (".FPT", ".fpt", ".DBT", ".dbt"):
                    sidecar = base_cli + ext
                    if os.path.exists(sidecar):
                        ftp_uploads.append((sidecar, "CLIENTESPA" + ext))
                _try_ftp_stor_backup(config, ftp_uploads, label="CLIENTESPA")
        else:
            logger.warning(
                "No hay CLIENTESPA.DBI en %s. Presea debe generarlo ahí; "
                "windows_sync NO lo baja del FTP (solo lo sube como respaldo).",
                exporta_dir,
            )
            try:
                names = [n for n in os.listdir(exporta_dir) if os.path.isfile(os.path.join(exporta_dir, n))]
                if names:
                    logger.info("Archivos en Exporta (raíz): %s", ", ".join(sorted(names)[:30]))
            except OSError:
                pass
            log_exporta(f"CLIENTESPA.DBI no encontrado en {exporta_dir}", config)
                    
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
        import_ventas_dbi = _import_ventas_dbi_function()

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
    Exportación automática en cada ejecución del sincronizador.
    Si hay clientes app en estado 'A Exportar', genera Clientes_web.dbi en IMPORTA,
    persiste códigos en Supabase y sube copia de respaldo al FTP.

    Si IMPORTA ya tiene un Clientes_web.dbi reciente (sin procesar por Presea),
    pospone la exportación para no pisar el lote anterior. Usar --force-auto-export
    para forzar.
    """
    now = datetime.datetime.now()
    force_export = "--force-auto-export" in sys.argv

    logger.info("--- Iniciando exportación automática de clientes 'A Exportar' ---")
    supabase = get_supabase_client(config)
    if supabase is None:
        logger.error("No se puede realizar la exportación automática sin cliente Supabase.")
        return False

    try:
        from modulos.ramos_utils import rubro_export, set_supabase_client
        set_supabase_client(supabase)
    except Exception as import_err:
        logger.warning(f"No se pudo cargar ramos_utils; se exportará giro_comercial tal cual: {import_err}")

        def rubro_export(val):
            return str(val) if val is not None else ""

    try:
        # 1. Buscar clientes app con estado 'A Exportar'
        response = (
            supabase.table("clientes_pendientes")
            .select("*")
            .eq("estado", "A Exportar")
            .eq("origen", "app")
            .execute()
        )
        if not response.data:
            logger.info("No hay clientes en estado 'A Exportar' para procesar automáticamente.")
            return True

        clientes_a_exportar = response.data
        logger.info(f"Detectados {len(clientes_a_exportar)} clientes app para exportar automáticamente.")

        from modulos.presea_db import (
            guardar_exportacion_app,
            leer_inicio_secuencia_app,
            resolver_codigos_app,
        )

        numero_inicio = leer_inicio_secuencia_app(supabase)
        clientes_a_exportar, ultimo_assigned = resolver_codigos_app(clientes_a_exportar, numero_inicio)

        # 2. Definir directorio de salida IMPORTA
        importa_dir = config.get("IMPORTA_DIR")
        os.makedirs(importa_dir, exist_ok=True)

        ruta_clientes_web = os.path.join(importa_dir, "Clientes_web.dbi")
        ruta_domicilios = os.path.join(importa_dir, "domicilios_entrega.txt")

        max_pending_hours = float(config.get("IMPORTA_PENDING_MAX_HOURS", 3))
        if not force_export and os.path.exists(ruta_clientes_web):
            age_hours = (
                now - datetime.datetime.fromtimestamp(os.path.getmtime(ruta_clientes_web))
            ).total_seconds() / 3600
            if age_hours < max_pending_hours:
                msg = (
                    f"Clientes_web.dbi en IMPORTA tiene {age_hours:.1f}h "
                    f"(umbral {max_pending_hours}h). Exportación pospuesta hasta que Presea lo procese."
                )
                logger.info(msg)
                log_importa(msg, config)
                return True

        # Mover archivos viejos en IMPORTA a No_process antes de generar uno nuevo
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

        codigo_por_id = {row["id"]: int(row["codigo"]) for row in clientes_a_exportar}

        table = dbf.Table(ruta_clientes_web, schema_str, dbf_type='fp', codepage='cp1252')
        table.open(mode=dbf.READ_WRITE)

        for row in clientes_a_exportar:
            codigo_actual = codigo_por_id[row["id"]]
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
                rubro_export(row.get('giro_comercial', ''))[:30],
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

        table.close()


        # Escribir domicilios_entrega.txt
        lineas_dom = []
        for row in clientes_a_exportar:
            codigo_dom = codigo_por_id[row["id"]]
            codigo_mask = f"{codigo_dom:06d}-000"
            linea_dom = (
                format_sdf_field(codigo_mask, 10, is_numeric=False) +
                format_sdf_field(codigo_dom, 6, is_numeric=True) +
                format_sdf_field(row.get('domicilio_e', ''), 30, is_numeric=False) +
                format_sdf_field(row.get('cp_ent', ''), 5, is_numeric=False) +
                format_sdf_field(row.get('local_ent', ''), 35, is_numeric=False) +
                format_sdf_field(row.get('prov_ent', ''), 25, is_numeric=False) +
                format_sdf_field(row.get('pais', ''), 20, is_numeric=False) +
                format_sdf_field(row.get('local_ent', ''), 35, is_numeric=False)
            )
            lineas_dom.append(linea_dom)

        with open(ruta_domicilios, "w", encoding="cp1252", newline="") as f_sdf:
            for line in lineas_dom:
                f_sdf.write(line + "\r\n")

        # 5. Persistir codigo, estado Exportado y secuencia en Supabase
        guardar_exportacion_app(supabase, clientes_a_exportar, ultimo_assigned)

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
        logger.error(f"Error en el proceso de exportación automática: {e}")
        log_importa(f"Error en exportación automática: {e}", config)
        return False

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Sincronizador Presea ↔ Supabase")
    parser.add_argument(
        "--solo-exporta",
        action="store_true",
        help="Solo importar CLIENTESPA/CODIGOSMP/ramo desde Exporta (sin FTP ni ventas)",
    )
    args = parser.parse_args()

    logger.info("=========================================")
    logger.info("Iniciando Sincronizador de Windows Server (build CLIENTESPA-local-v3.1)")
    logger.info("=========================================")

    config = load_config()
    url = config.get("SUPABASE_URL") or ""
    logger.info(
        "Config activa: SUPABASE=%s | FTP=%s:%s | EXPORTA=%s",
        url.replace("https://", "")[:60] if url else "(vacío)",
        config.get("FTP_HOST"),
        config.get("FTP_PORT"),
        config.get("EXPORTA_DIR"),
    )
    validate_config(config)

    if not probe_supabase(config):
        logger.error(
            "Supabase no disponible: no se importará CLIENTESPA. "
            "Corregí SUPABASE_URL y SUPABASE_KEY en %s y volvé a ejecutar.",
            CONFIG_FILE,
        )

    sync_exporta_to_ftp_and_supabase(config)
    if args.solo_exporta:
        logger.info("Modo --solo-exporta: fin.")
        return

    auto_export_a_exportar_to_importa(config)
    sync_ftp_to_importa(config)
    sync_ventas_to_ftp_and_supabase(config)

    logger.info("Proceso general del Servidor Windows finalizado.")

if __name__ == "__main__":
    main()
