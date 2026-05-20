import speech_recognition as sr
import io
import streamlit as st
import google.generativeai as genai

# Configurar Gemini si hay API KEY disponible
api_key = None
try:
    api_key = st.secrets.get("GOOGLE_API_KEY", None)
except:
    pass

if api_key:
    genai.configure(api_key=api_key)

def procesar_audio_a_texto(audio_bytes):
    """
    Toma bytes crudos de un archivo de audio (WAV) y devuelve el texto transcrito.
    Usa la API gratuita de Google Web Speech.
    """
    try:
        r = sr.Recognizer()
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            # Eliminar ruido ambiente si es necesario
            r.adjust_for_ambient_noise(source, duration=0.2)
            audio_data = r.record(source)
            # Transcribir en español de Argentina
            texto = r.recognize_google(audio_data, language="es-AR")
            return texto
    except sr.UnknownValueError:
        return "ERROR_NO_ENTENDIDO"
    except sr.RequestError as e:
        return f"ERROR_SERVICIO: {e}"
    except Exception as e:
        return f"ERROR_GENERAL: {e}"

def procesar_texto_con_ia(texto):
    """
    Usa Gemini para extraer estructuradamente los datos de un cliente a partir de un dictado libre.
    Devuelve un diccionario JSON con las claves exactas.
    """
    if not api_key:
        return {"error": "No hay API Key de Gemini configurada."}
        
    prompt = f"""
    Eres un asistente de ventas ágil. Extrae la información del siguiente texto dictado por un vendedor 
    que quiere dar de alta un nuevo cliente. Devuelve ÚNICAMENTE un objeto JSON válido con las siguientes claves 
    (si algún dato no se menciona, devuelve un string vacío ""):
    
    - "cuit": (solo los 11 números, sin guiones ni espacios. Trata de deducirlo si te lo dicen separado)
    - "n_fantasia": (nombre de fantasía o razón social)
    - "contacto": (nombre de la persona de contacto)
    - "telefono": (número de teléfono)
    - "tipo_resp": (tipo de responsable frente al IVA, ej. Responsable Inscripto, Monotributista)
    - "giro_comercial": (rubro, ramo o a qué se dedica el cliente)
    - "cuit_socio1": (cuit del socio 1 si lo mencionan, solo números)
    - "cuit_socio2": (cuit del socio 2 si lo mencionan, solo números)
    - "dom_e": (calle y número del domicilio de entrega)
    - "loc_e": (localidad de entrega)
    - "observaciones": (aclaraciones o notas adicionales)
    
    IMPORTANTE SOBRE DOMICILIO DE ENTREGA: Si el vendedor dice que el domicilio de entrega, localidad o código postal es "igual al fiscal", "el mismo", "el mismo que el de AFIP", debes poner exactamente el valor especial "MISMO_FISCAL" en las claves "dom_e" y "loc_e".
    
    Texto dictado: "{texto}"
    
    Respuesta JSON pura, sin backticks ni formato markdown:
    """
    
    try:
        model = genai.GenerativeModel('gemini-3.5-flash')
        response = model.generate_content(prompt)
        text_resp = response.text.strip()
        
        # Limpiar si el modelo devuelve markdown
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:]
        if text_resp.endswith("```"):
            text_resp = text_resp[:-3]
            
        import json
        datos = json.loads(text_resp.strip())
        return datos
    except Exception as e:
        print(f"Error en Gemini: {e}")
        return {"error": str(e)}
