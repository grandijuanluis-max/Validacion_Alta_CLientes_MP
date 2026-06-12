import os
import time
import json
import base64
import requests
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# --- CONFIGURACIÓN AFIP PRODUCCIÓN ---
# CAMBIA ESTO SEGÚN EL PADRÓN QUE AFIP TE PERMITA DELEGAR (a4, a5, a10, a13)
PADRON_VERSION = "a13" 

WSAA_URL = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
WS_PADRON_URL = f"https://aws.afip.gov.ar/sr-padron/webservices/personaService{PADRON_VERSION.upper()}"
CERT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "certs", "certificado.crt")
KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "certs", "afip.key")
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "afip_auth.json")

def _generar_tra(service_name):
    """Genera el Ticket de Requerimiento de Acceso (TRA) en XML para el servicio especificado"""
    ahora = datetime.utcnow() - timedelta(minutes=5)
    expiracion = ahora + timedelta(hours=12)
    
    unique_id = str(int(time.time()))
    
    tra_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{ahora.strftime('%Y-%m-%dT%H:%M:%S-00:00')}</generationTime>
    <expirationTime>{expiracion.strftime('%Y-%m-%dT%H:%M:%S-00:00')}</expirationTime>
  </header>
  <service>{service_name}</service>
</loginTicketRequest>"""
    return tra_xml

def _firmar_tra(tra_xml):
    """Firma el TRA usando OpenSSL (PKCS#7 / CMS)"""
    import tempfile
    import streamlit as st
    
    # Guardamos temporalmente el TRA
    tmp_tra = "/tmp/tra.xml"
    with open(tmp_tra, "w") as f:
        f.write(tra_xml)
        
    # Lógica de seguridad para no exponer certificados en GitHub
    cert_file_path = CERT_PATH
    key_file_path = KEY_PATH
    
    archivos_temporales = []
    
    # Si estamos en la nube y los archivos no existen físicamente, leemos de los Secretos
    if not os.path.exists(CERT_PATH) or not os.path.exists(KEY_PATH):
        try:
            cert_content = st.secrets["AFIP_CRT"]
            key_content = st.secrets["AFIP_KEY"]
            
            # Creamos archivos temporales seguros
            fd_cert, cert_file_path = tempfile.mkstemp(text=True)
            fd_key, key_file_path = tempfile.mkstemp(text=True)
            
            with os.fdopen(fd_cert, 'w') as f: f.write(cert_content)
            with os.fdopen(fd_key, 'w') as f: f.write(key_content)
            
            archivos_temporales.extend([cert_file_path, key_file_path])
        except Exception:
            return None # Fallará y mostrará el mensaje de error normal
            
    # Ejecutamos OpenSSL para firmar
    cmd = [
        "openssl", "cms", "-sign", "-in", tmp_tra,
        "-signer", cert_file_path, "-inkey", key_file_path,
        "-nodetach", "-outform", "PEM"
    ]
    
    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Limpiar salida (quitar cabeceras PEM para dejar solo base64)
        cms_b64 = ""
        in_cert = False
        for line in resultado.stdout.splitlines():
            if "-----BEGIN CMS-----" in line:
                in_cert = True
                continue
            if "-----END CMS-----" in line:
                break
            if in_cert:
                cms_b64 += line.strip()
        
        return cms_b64
    except subprocess.CalledProcessError as e:
        print(f"Error OpenSSL: {e.stderr}")
        return None
    finally:
        if os.path.exists(tmp_tra):
            os.remove(tmp_tra)
        for tmp_file in archivos_temporales:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

def _obtener_token_wsaa(service_name=None):
    """Obtiene el Token y Sign del WSAA usando caché si está vigente para el servicio solicitado"""
    if service_name is None:
        service_name = f"ws_sr_padron_{PADRON_VERSION.lower()}"
        
    cache_data = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache_data = json.load(f)
                service_cache = cache_data.get(service_name)
                if service_cache and (time.time() - service_cache.get("timestamp", 0) < 40000): # ~11 horas
                    return service_cache["token"], service_cache["sign"]
        except Exception:
            pass

    # Si no hay caché o expiró, generamos nuevo
    tra_xml = _generar_tra(service_name)
    cms_b64 = _firmar_tra(tra_xml)
    
    if not cms_b64:
        raise Exception(f"No se pudo firmar el Ticket para {service_name} (revisa certificado.crt y afip.key).")

    # Petición SOAP al WSAA
    soap_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:wsaa="http://wsaa.view.sua.dvadac.desas.afip.gov">
   <soapenv:Header/>
   <soapenv:Body>
      <wsaa:loginCms>
         <wsaa:in0>{cms_b64}</wsaa:in0>
      </wsaa:loginCms>
   </soapenv:Body>
</soapenv:Envelope>"""

    headers = {'Content-Type': 'text/xml;charset=UTF-8', 'SOAPAction': ''}
    resp = requests.post(WSAA_URL, data=soap_request, headers=headers)
    
    if resp.status_code == 200:
        root = ET.fromstring(resp.text)
        login_cms_return = None
        for elem in root.iter():
            if 'loginCmsReturn' in elem.tag:
                login_cms_return = elem.text
                break
                
        if not login_cms_return:
            raise Exception(f"Error al procesar XML del WSAA para {service_name}: no se encontró loginCmsReturn.")
            
        return_root = ET.fromstring(login_cms_return)
        token = return_root.find('.//token').text
        sign = return_root.find('.//sign').text
        
        # Guardamos en caché indexado por servicio
        cache_data[service_name] = {"token": token, "sign": sign, "timestamp": time.time()}
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(cache_data, f)
        except Exception:
            pass
            
        return token, sign
    else:
        if "notAuthorized" in resp.text or "Computador no autorizado" in resp.text:
            raise Exception(f"Tu certificado digital es válido, pero aún no tiene permisos para '{service_name}'. Debes ingresar a ARCA (AFIP) -> Administrador de Relaciones de Clave Fiscal -> Nueva Relación, elegir el servicio '{service_name}' y vincularlo al alias de tu computador. Si ya lo hiciste, recuerda que ARCA tarda hasta 1 hora en habilitarlo.")
        raise Exception(f"Fallo Login AFIP ({service_name}): {resp.text}")

def consultar_cuit_afip(cuit, cuit_representante="20234022041"):
    """
    Consulta un CUIT en el servicio Padrón dinámico de AFIP.
    cuit_representante: Es el CUIT de Juan Luis (dueño del certificado).
    """
    cuit_limpio = str(cuit).replace('-', '').strip()
    if len(cuit_limpio) != 11:
        return {"error": "El CUIT debe tener 11 dígitos."}
        
    try:
        ns = PADRON_VERSION.lower()
        token, sign = _obtener_token_wsaa(f"ws_sr_padron_{ns}")
        
        # Petición SOAP al Padrón dinámico
        soap_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:{ns}="http://{ns}.soap.ws.server.puc.sr/">
   <soapenv:Header/>
   <soapenv:Body>
      <{ns}:getPersona>
         <token>{token}</token>
         <sign>{sign}</sign>
         <cuitRepresentada>{cuit_representante}</cuitRepresentada>
         <idPersona>{cuit_limpio}</idPersona>
      </{ns}:getPersona>
   </soapenv:Body>
</soapenv:Envelope>"""

        headers = {'Content-Type': 'text/xml;charset=UTF-8', 'SOAPAction': ''}
        resp = requests.post(WS_PADRON_URL, data=soap_request, headers=headers)
        
        if resp.status_code != 200:
            return {"error": f"Error del servidor AFIP: {resp.status_code}"}
            
        root = ET.fromstring(resp.text)
        
        # Búsqueda agnóstica de namespaces
        def get_node(node, tag_name):
            if node is None: return None
            for elem in node.iter():
                local_tag = elem.tag.split('}')[-1]
                if local_tag == tag_name:
                    return elem
            return None
            
        def get_text(node, tag_name):
            elem = get_node(node, tag_name)
            return elem.text if elem is not None else None

        error_node = get_node(root, 'errorConstancia')
        if error_node is not None:
            err_msg = get_text(error_node, 'error')
            return {"error": err_msg or "Error desconocido en Padrón"}
            
        persona = get_node(root, 'personaReturn')
        if persona is None:
            return {"error": f"CUIT no encontrado en el Padrón {PADRON_VERSION.upper()}."}
            
        datos = {
            "nombre": "",
            "estado": "Inactivo",
            "domicilio_fiscal": "",
            "localidad": "",
            "provincia": "",
            "tipo_doc_desc": "",
            "tipo_doc_codigo": "",
            "tipo_resp_desc": "",
            "tipo_resp_codigo": "",
            "tipo_resp_error": "",
            "actividad": "",
            "cod_acti": "",
            "antiguedad": "",
            "mes_cierre": ""
        }
        
        razon_social = get_text(persona, 'razonSocial')
        nombre = get_text(persona, 'nombre')
        apellido = get_text(persona, 'apellido')
        
        if razon_social:
            datos["nombre"] = razon_social
        elif nombre and apellido:
            datos["nombre"] = f"{apellido} {nombre}"
            
        estado_clave = get_text(persona, 'estadoClave')
        if estado_clave == "ACTIVO":
            datos["estado"] = "Activo"
            
        tipo_clave = get_text(persona, 'tipoClave')
        if tipo_clave in ["CUIT", "CUIL"]:
            datos["tipo_doc_desc"] = tipo_clave
            datos["tipo_doc_codigo"] = "80"
            
        actividad_principal = get_text(persona, 'descripcionActividadPrincipal')
        id_actividad = get_text(persona, 'idActividadPrincipal')
        datos["actividad"] = actividad_principal if actividad_principal else ""
        datos["cod_acti"] = id_actividad if id_actividad else ""
        
        fecha_inscripcion = get_text(persona, 'fechaInscripcion')
        fecha_contrato = get_text(persona, 'fechaContratoSocial')
        # Utilizamos fechaContratoSocial si existe, si no fechaInscripcion
        datos["antiguedad"] = fecha_contrato if fecha_contrato else (fecha_inscripcion if fecha_inscripcion else "")
        if datos["antiguedad"] and "T" in datos["antiguedad"]:
            datos["antiguedad"] = datos["antiguedad"].split("T")[0]
            
        mes_cierre = get_text(persona, 'mesCierre')
        datos["mes_cierre"] = mes_cierre if mes_cierre else ""
            
        domicilio = get_node(persona, 'domicilio')
        if domicilio is not None:
            direccion = get_text(domicilio, 'direccion')
            localidad = get_text(domicilio, 'localidad')
            provincia = get_text(domicilio, 'descripcionProvincia')
            
            datos["domicilio_fiscal"] = direccion if direccion else ""
            datos["localidad"] = localidad if localidad else ""
            datos["provincia"] = provincia if provincia else ""
            
        # Consulta complementaria de impuestos a ws_sr_constancia_inscripcion (A5)
        if tipo_clave == "CUIL":
            datos["tipo_resp_desc"] = "Consumidor Final"
            datos["tipo_resp_codigo"] = "5.0"
            datos["tipo_resp_error"] = "El CUIT corresponde a un CUIL (persona física no inscripta comercialmente)."
        else:
            try:
                token_a5, sign_a5 = _obtener_token_wsaa("ws_sr_constancia_inscripcion")
                soap_request_a5 = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:a5="http://a5.soap.ws.server.puc.sr/">
   <soapenv:Header/>
   <soapenv:Body>
      <a5:getPersona>
         <token>{token_a5}</token>
         <sign>{sign_a5}</sign>
         <cuitRepresentada>{cuit_representante}</cuitRepresentada>
         <idPersona>{cuit_limpio}</idPersona>
      </a5:getPersona>
   </soapenv:Body>
</soapenv:Envelope>"""
                
                resp_a5 = requests.post("https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5", data=soap_request_a5, headers=headers)
                if resp_a5.status_code == 200:
                    root_a5 = ET.fromstring(resp_a5.text)
                    error_node_a5 = get_node(root_a5, 'errorConstancia')
                    if error_node_a5 is not None:
                        err_msg = get_text(error_node_a5, 'error')
                        datos["tipo_resp_error"] = err_msg or "Error en el servicio de constancia de inscripción de AFIP."
                    else:
                        tiene_ri = False
                        tiene_mono = False
                        tiene_exento = False
                        
                        for imp in root_a5.iter():
                            if 'impuesto' in imp.tag:
                                id_imp = get_text(imp, 'idImpuesto')
                                estado_imp = get_text(imp, 'estadoImpuesto')
                                if estado_imp == 'AC':
                                    if id_imp in ['20', '21', '22']:
                                        tiene_mono = True
                                    elif id_imp == '32':
                                        tiene_exento = True
                                    elif id_imp == '30':
                                        tiene_ri = True
                                    
                        if tiene_exento:
                            datos["tipo_resp_desc"] = "Exento"
                            datos["tipo_resp_codigo"] = "4.0"
                        elif tiene_mono:
                            datos["tipo_resp_desc"] = "Monotributista"
                            datos["tipo_resp_codigo"] = "3.0"
                        elif tiene_ri:
                            datos["tipo_resp_desc"] = "Responsable Inscripto"
                            datos["tipo_resp_codigo"] = "1.0"
                        else:
                            registra_ganancias = False
                            for imp in root_a5.iter():
                                if 'impuesto' in imp.tag:
                                    id_imp = get_text(imp, 'idImpuesto')
                                    estado_imp = get_text(imp, 'estadoImpuesto')
                                    if id_imp in ['10', '11'] and estado_imp == 'AC':
                                        registra_ganancias = True
                                        break
                            if registra_ganancias:
                                datos["tipo_resp_error"] = "Registra Ganancias activo pero no IVA ni Monotributo."
                            else:
                                datos["tipo_resp_error"] = "No se encontraron impuestos de IVA o Monotributo activos."
                else:
                    datos["tipo_resp_error"] = f"Error del servidor de constancias de AFIP: {resp_a5.status_code}"
            except Exception as e5:
                datos["tipo_resp_error"] = f"No se pudo consultar impuestos de AFIP: {str(e5)}"
                
        return datos

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Prueba rápida
    print("Iniciando prueba con AFIP...")
    resultado = consultar_cuit_afip("30707738240")
    print(resultado)
