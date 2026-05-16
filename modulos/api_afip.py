import os
import time
import json
import base64
import requests
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# --- CONFIGURACIÓN AFIP PRODUCCIÓN ---
WSAA_URL = "https://wsaa.afip.gov.ar/ws/services/LoginCms"
WS_PADRON_URL = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5"
CERT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "certs", "certificado.crt")
KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "certs", "afip.key")
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "afip_auth.json")

def _generar_tra():
    """Genera el Ticket de Requerimiento de Acceso (TRA) en XML"""
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
  <service>ws_sr_padron_a5</service>
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

def _obtener_token_wsaa():
    """Obtiene el Token y Sign del WSAA usando caché si está vigente"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            # Verificamos si expiró (guardamos timestamp de cuando se pidió)
            if time.time() - data.get("timestamp", 0) < 40000: # ~11 horas
                return data["token"], data["sign"]

    # Si no hay caché o expiró, generamos nuevo
    tra_xml = _generar_tra()
    cms_b64 = _firmar_tra(tra_xml)
    
    if not cms_b64:
        raise Exception("No se pudo firmar el Ticket (revisa certificado.crt y afip.key).")

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
        login_cms_return = root.find('.//loginCmsReturn').text
        # La respuesta es otro XML anidado
        return_root = ET.fromstring(login_cms_return)
        token = return_root.find('.//token').text
        sign = return_root.find('.//sign').text
        
        # Guardamos en caché
        with open(CACHE_FILE, "w") as f:
            json.dump({"token": token, "sign": sign, "timestamp": time.time()}, f)
            
        return token, sign
    else:
        raise Exception(f"Fallo Login AFIP: {resp.text}")

def consultar_cuit_afip(cuit, cuit_representante="20234022041"):
    """
    Consulta un CUIT en el servicio Padrón A5 de AFIP.
    cuit_representante: Es el CUIT de Juan Luis (dueño del certificado).
    """
    cuit_limpio = str(cuit).replace('-', '').strip()
    if len(cuit_limpio) != 11:
        return {"error": "El CUIT debe tener 11 dígitos."}
        
    try:
        token, sign = _obtener_token_wsaa()
        
        # Petición SOAP a Padrón A5
        soap_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:a5="http://a5.soap.ws.server.puc.sr/">
   <soapenv:Header/>
   <soapenv:Body>
      <a5:getPersona>
         <token>{token}</token>
         <sign>{sign}</sign>
         <cuitRepresentada>{cuit_representante}</cuitRepresentada>
         <idPersona>{cuit_limpio}</idPersona>
      </a5:getPersona>
   </soapenv:Body>
</soapenv:Envelope>"""

        headers = {'Content-Type': 'text/xml;charset=UTF-8', 'SOAPAction': ''}
        resp = requests.post(WS_PADRON_URL, data=soap_request, headers=headers)
        
        if resp.status_code != 200:
            return {"error": f"Error del servidor AFIP: {resp.status_code}"}
            
        root = ET.fromstring(resp.text)
        
        # Parseo de errores si existen
        error_node = root.find('.//errorConstancia')
        if error_node is not None:
            err_msg = error_node.find('error').text
            return {"error": err_msg}
            
        persona = root.find('.//personaReturn')
        if persona is None:
            return {"error": "CUIT no encontrado en el Padrón A5."}
            
        # Extracción de datos
        datos = {
            "nombre": "",
            "estado": "Inactivo",
            "domicilio_fiscal": "",
            "condicion_iva": "Exento / Monotributo"
        }
        
        # Nombre (puede estar en nombre, apellido o razonSocial)
        razon_social = persona.find('.//razonSocial')
        nombre = persona.find('.//nombre')
        apellido = persona.find('.//apellido')
        
        if razon_social is not None and razon_social.text:
            datos["nombre"] = razon_social.text
        elif nombre is not None and apellido is not None:
            datos["nombre"] = f"{apellido.text} {nombre.text}"
            
        # Estado
        estado_clave = persona.find('.//estadoClave')
        if estado_clave is not None and estado_clave.text == "ACTIVO":
            datos["estado"] = "Activo"
            
        # Domicilio
        domicilio = persona.find('.//domicilio')
        if domicilio is not None:
            direccion = domicilio.find('.//direccion')
            localidad = domicilio.find('.//localidad')
            provincia = domicilio.find('.//descripcionProvincia')
            cp = domicilio.find('.//codPostal')
            
            partes_domicilio = []
            if direccion is not None and direccion.text: partes_domicilio.append(direccion.text)
            if localidad is not None and localidad.text: partes_domicilio.append(localidad.text)
            if provincia is not None and provincia.text: partes_domicilio.append(provincia.text)
            
            datos["domicilio_fiscal"] = ", ".join(partes_domicilio)
            
        # Impuestos (IVA = 30)
        impuestos = persona.findall('.//impuesto')
        for imp in impuestos:
            id_impuesto = imp.find('idImpuesto')
            if id_impuesto is not None and id_impuesto.text == '30':
                datos["condicion_iva"] = "Responsable Inscripto"
                break
                
        return datos

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Prueba rápida
    print("Iniciando prueba con AFIP...")
    resultado = consultar_cuit_afip("30707738240")
    print(resultado)
