import speech_recognition as sr
import io

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
