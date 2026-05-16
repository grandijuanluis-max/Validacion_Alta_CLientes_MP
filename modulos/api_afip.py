import requests
import streamlit as st

def consultar_cuit_afip(cuit):
    """
    Consulta un CUIT en la API de AFIP.
    Actualmente devuelve un mock, preparado para conectar la API real mañana.
    """
    # TODO: Mañana conectaremos la API real aquí (WS_SR_PADRON_A5 o un wrapper REST).
    # Esta es la estructura base que usaremos.
    
    # 1. Limpiar el CUIT
    cuit_limpio = str(cuit).replace('-', '').strip()
    
    if len(cuit_limpio) != 11:
        return {"error": "El CUIT debe tener 11 dígitos."}
        
    # --- MOCK DE RESPUESTA HASTA CONECTAR LA API REAL ---
    if cuit_limpio == "30707738240":
        return {
            "nombre": "PRESEA SOFTWARE S.A.",
            "estado": "Activo",
            "domicilio_fiscal": "Av. Corrientes 1234, CABA",
            "condicion_iva": "Responsable Inscripto",
            "iibb": "901-234567-1"
        }
    else:
        # Respuesta genérica para otros CUITS durante pruebas
        return {
            "nombre": f"Empresa de Prueba {cuit_limpio[-4:]}",
            "estado": "Activo",
            "domicilio_fiscal": "Calle Falsa 123",
            "condicion_iva": "Responsable Inscripto",
            "iibb": "000-000000-0"
        }
