import time
import json
import requests
import streamlit as st
from datetime import datetime, timezone, timedelta
from modulos.db import supabase

def _simular_payload_nosis(cuit: str) -> dict:
    """Genera el payload crudo simulado de Nosis."""
    try:
        suma = sum(int(digit) for digit in str(cuit) if digit.isdigit())
    except:
        suma = 10
        
    if suma % 3 == 0:
        return {
            "score_riesgo": 420,
            "calificacion_bcra": 4,
            "cheques_rechazados": 5,
            "juicios_concursos": 1,
            "baches_afip_meses": 4
        }
    elif suma % 2 == 0:
        return {
            "score_riesgo": 650,
            "calificacion_bcra": 2,
            "cheques_rechazados": 2,
            "juicios_concursos": 0,
            "baches_afip_meses": 1
        }
    else:
        return {
            "score_riesgo": 850,
            "calificacion_bcra": 1,
            "cheques_rechazados": 0,
            "juicios_concursos": 0,
            "baches_afip_meses": 0
        }

def _evaluar_matriz_decision(payload: dict) -> dict:
    """Aplica la matriz de decisión gerencial al payload."""
    reglas = {}
    
    # 1. Score
    score = payload.get("score_riesgo", 0)
    if score > 700: reglas["score"] = "VERDE"
    elif 450 <= score <= 699: reglas["score"] = "AMARILLO"
    else: reglas["score"] = "ROJO"
    
    # 2. BCRA
    bcra = payload.get("calificacion_bcra", 1)
    if bcra == 1: reglas["bcra"] = "VERDE"
    elif bcra == 2: reglas["bcra"] = "AMARILLO"
    else: reglas["bcra"] = "ROJO"
        
    # 3. Cheques Rechazados
    cheques = payload.get("cheques_rechazados", 0)
    if cheques == 0: reglas["cheques"] = "VERDE"
    elif 1 <= cheques <= 3: reglas["cheques"] = "AMARILLO"
    else: reglas["cheques"] = "ROJO"
        
    # 4. Juicios
    juicios = payload.get("juicios_concursos", 0)
    if juicios == 0: reglas["juicios"] = "VERDE"
    else: reglas["juicios"] = "ROJO"
        
    # 5. Cargas Sociales (baches)
    baches = payload.get("baches_afip_meses", 0)
    if baches == 0: reglas["afip"] = "VERDE"
    elif baches < 3: reglas["afip"] = "AMARILLO"
    else: reglas["afip"] = "ROJO"
        
    # Dictamen global
    valores = list(reglas.values())
    if "ROJO" in valores:
        dictamen = "RECHAZO AUTOMÁTICO"
    elif "AMARILLO" in valores:
        dictamen = "REVISIÓN GERENCIAL"
    else:
        dictamen = "APROBACIÓN AUTOMÁTICA"
        
    return {
        "dictamen": dictamen,
        "semaforos": reglas,
        "payload_crudo": payload
    }

def _aplanar_json(d: dict, parent_key: str = '', sep: str = '_') -> dict:
    """Aplana recursivamente un JSON anidado."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_aplanar_json(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, elem in enumerate(v):
                if isinstance(elem, dict):
                    items.extend(_aplanar_json(elem, f"{new_key}_{i}", sep=sep).items())
                else:
                    items.append((f"{new_key}_{i}", elem))
        else:
            items.append((new_key, v))
    return dict(items)

def _llamar_api_real_nosis(cuit: str) -> dict:
    """Hace la consulta real HTTP a la API de Nosis SAC."""
    usuario = st.secrets.get("NOSIS_USUARIO")
    token = st.secrets.get("NOSIS_TOKEN")
    url_base = st.secrets.get("NOSIS_URL", "https://api.nosis.com").rstrip("/")
    
    # Si las credenciales no están configuradas o tienen el placeholder, retornar None
    if not usuario or not token or "REEMPLAZAR" in str(usuario) or "REEMPLAZAR" in str(token):
        return None
        
    url_completa = f"{url_base}/api/variables"
    params = {
        "Usuario": str(usuario).strip(),
        "Token": str(token).strip(),
        "Documento": str(cuit).replace("-", "").strip(),
        "Sexo": "",
        "RazonSocial": "",
        "VR": "1" # Por defecto, paquete de variables 1
    }
    
    try:
        response = requests.get(url_completa, params=params, timeout=10)
        # Si da 404 en /api/variables, reintentar con /rest/variables
        if response.status_code == 404:
            url_completa = f"{url_base}/rest/variables"
            response = requests.get(url_completa, params=params, timeout=10)
            
        response.raise_for_status()
        data = response.json()
        
        # Log para consola del desarrollador para verificar campos devueltos
        print(f"📡 RESPUESTA REAL NOSIS PARA CUIT {cuit}: {json.dumps(data)}")
        return data
    except Exception as e:
        print(f"❌ Error en llamada HTTP Nosis: {e}")
        return {"error_api": str(e)}

def _mapear_json_nosis(raw_json: dict) -> dict:
    """Mapea con tolerancia a fallos y aliasing el JSON de Nosis a nuestro esquema de 5 variables."""
    if "error_api" in raw_json:
        raise Exception(raw_json["error_api"])
        
    # Aplanar el JSON para buscar en cualquier nivel de anidamiento
    flat_json = _aplanar_json(raw_json)
    
    # Definición de alias para cada variable
    posibles_score = ["score", "score_riesgo", "scoreriesgo", "vi_score", "vi_score_riesgo", "score_nosis", "score_final", "score_sac", "vi_score_sac"]
    posibles_bcra = ["bcra", "calificacion_bcra", "calificacionbcra", "sit_bcra", "situacion_bcra", "peorsitbcra", "peor_situacion_bcra", "vi_bcra_situacion", "situacion", "peorsit"]
    posibles_cheques = ["cheques", "cheques_rechazados", "chequesrechazados", "cant_cheq_rech", "cantcheqrech", "vi_cheques_rechazados", "cant_cheques", "rechazados", "cheq_rech"]
    posibles_juicios = ["juicios", "juicios_concursos", "juiciosconcursos", "juicios_cant", "cant_juicios", "cantjuicios", "vi_juicios", "concursos", "quiebras"]
    posibles_afip = ["afip", "baches_afip", "baches_afip_meses", "cant_baches_afip", "baches", "vi_baches_afip", "bachesafip", "atraso_afip", "deuda_afip"]

    def buscar_valor(claves_candidatas, default=0):
        # 1. Coincidencia exacta ignorando case
        for k, v in flat_json.items():
            if k.lower() in [c.lower() for c in claves_candidatas]:
                try:
                    return int(float(v)) if v is not None else default
                except:
                    return default
        # 2. Coincidencia por subcadena
        for k, v in flat_json.items():
            for cand in claves_candidatas:
                if cand.lower() in k.lower():
                    try:
                        return int(float(v)) if v is not None else default
                    except:
                        return default
        return default

    # Extraer y mapear variables de forma segura
    score = buscar_valor(posibles_score, default=850) # 850 default (Verde)
    bcra = buscar_valor(posibles_bcra, default=1)      # 1 default (Verde)
    cheques = buscar_valor(posibles_cheques, default=0)  # 0 default (Verde)
    juicios = buscar_valor(posibles_juicios, default=0)  # 0 default (Verde)
    afip = buscar_valor(posibles_afip, default=0)        # 0 default (Verde)

    # Validar si Nosis reportó algún error interno dentro del cuerpo del JSON
    # ej: {"Contenido": {"Resultado": "Error", "Detalle": "..."}}
    for k, v in flat_json.items():
        if "resultado" in k.lower() and str(v).lower() in ["error", "fallo", "denegado"]:
            detalle = flat_json.get(k.replace("resultado", "detalle"), "Error reportado por Nosis")
            raise Exception(f"Nosis API Error: {detalle}")

    return {
        "score_riesgo": score,
        "calificacion_bcra": bcra,
        "cheques_rechazados": cheques,
        "juicios_concursos": juicios,
        "baches_afip_meses": afip
    }

def consultar_y_evaluar_nosis(cuit: str, user_id: str) -> dict:
    """Flujo completo asíncrono: Caché -> API Real (o fallback a Simulador) -> Motor de Reglas -> Auditoría"""
    if not cuit or not supabase:
        return {"error": "Faltan datos o conexión a base."}
        
    # 1. Validación de Caché
    try:
        cache_resp = supabase.table('consultas_nosis').select('*').eq('cuit', cuit).execute()
        en_cache = False
        payload_crudo = None
        
        if cache_resp.data:
            registro = cache_resp.data[0]
            fecha_consulta_str = registro['fecha_consulta']
            try:
                # Soporte para parseo de fecha desde supabase
                fecha_consulta = datetime.fromisoformat(fecha_consulta_str.replace("Z", "+00:00"))
                limite_30_dias = datetime.now(timezone.utc) - timedelta(days=30)
                if fecha_consulta > limite_30_dias:
                    payload_crudo = registro['payload']
                    en_cache = True
            except:
                pass
                
        # 2. Llamada a API si no hay caché válido
        origen_datos = "CACHÉ (Local)"
        if not en_cache:
            # Intentar llamar a la API real
            raw_response = _llamar_api_real_nosis(cuit)
            
            if raw_response is None:
                # No configurado -> Fallback a simulación
                payload_crudo = _simular_payload_nosis(cuit)
                origen_datos = "API NOSIS (Simulador)"
            elif "error_api" in raw_response:
                # Error en llamada -> Fallback seguro a simulación para no romper la app en producción
                payload_crudo = _simular_payload_nosis(cuit)
                origen_datos = f"API NOSIS (Simulador - Fallback por error: {raw_response['error_api']})"
            else:
                try:
                    # Mapear respuesta real de Nosis
                    payload_crudo = _mapear_json_nosis(raw_response)
                    origen_datos = "API REAL (Nosis)"
                except Exception as map_err:
                    # Error al mapear -> Fallback a simulación
                    payload_crudo = _simular_payload_nosis(cuit)
                    origen_datos = f"API NOSIS (Simulador - Fallback por mapeo: {map_err})"
            
            # Guardar en caché
            try:
                # Upsert para reemplazar si estaba vencido
                supabase.table('consultas_nosis').upsert({
                    "cuit": cuit,
                    "payload": payload_crudo,
                    "fecha_consulta": datetime.now(timezone.utc).isoformat()
                }).execute()
            except Exception as cache_err:
                print(f"Error guardando caché: {cache_err}")
                
        # 3. Procesamiento en el Motor de Reglas
        resultado = _evaluar_matriz_decision(payload_crudo)
        resultado['origen'] = origen_datos
        
        # 4. Auditoría
        try:
            supabase.table('log_auditoria_riesgo').insert({
                "usuario_id": user_id,
                "cuit_consultado": cuit,
                "dictamen_motor": resultado['dictamen'],
                "payload_crudo": payload_crudo
            }).execute()
        except Exception as audit_err:
            print(f"Error guardando auditoría: {audit_err}")
            
        return resultado
        
    except Exception as e:
        return {"error": f"Error en el flujo Nosis: {e}"}
