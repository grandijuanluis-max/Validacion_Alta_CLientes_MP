import time
import json
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

def consultar_y_evaluar_nosis(cuit: str, user_id: str) -> dict:
    """Flujo completo asíncrono: Caché -> API (Mock) -> Motor de Reglas -> Auditoría"""
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
                
        # 2. Llamada a API (Mock) si no hay caché válido
        if not en_cache:
            time.sleep(0.5) # Simular latencia de red HTTP
            payload_crudo = _simular_payload_nosis(cuit)
            
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
        resultado['origen'] = "CACHÉ (Local)" if en_cache else "API NOSIS (Simulador)"
        
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
