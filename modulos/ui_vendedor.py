import streamlit as st
import pandas as pd
import os
from modulos.api_afip import consultar_cuit_afip
from modulos.db import supabase

def cargar_ramos():
    ruta_ramo = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ramo.csv')
    try:
        df = pd.read_csv(ruta_ramo, sep=';')
        return df['descrip'].tolist()
    except Exception as e:
        return ["Kiosco", "Supermercado", "Ferretería"] # Fallback

def render_vendedor_dashboard():
    st.header("🏢 Alta de Nuevo Cliente")
    
    # Inicializar estado para los campos si no existen
    if 'afip_data' not in st.session_state:
        st.session_state['afip_data'] = {
            "cuit": "", "nombre": "", "domicilio_f": "", 
            "localidad": "", "provincia": "", "cp": "", "estado": ""
        }

    st.subheader("1. Buscar en AFIP")
    col_cuit, col_btn = st.columns([2, 1])
    
    with col_cuit:
        cuit_busqueda = st.text_input("Ingresa el CUIT (Ej: 30111111111)", value=st.session_state['afip_data']['cuit'])
        
    with col_btn:
        st.write("") # Espaciador
        st.write("") # Espaciador
        if st.button("🔍 Buscar Datos"):
            if not cuit_busqueda:
                st.warning("Escribe un CUIT primero.")
            else:
                with st.spinner("Consultando Padrón AFIP..."):
                    from modulos.api_afip import consultar_cuit_afip
                    resultado = consultar_cuit_afip(cuit_busqueda)
                    
                    if "error" in resultado:
                        st.error(resultado["error"])
                    else:
                        st.success(f"¡Encontrado! Estado: {resultado.get('estado', 'Desconocido')}")
                        st.session_state['afip_data']['cuit'] = cuit_busqueda
                        st.session_state['afip_data']['nombre'] = resultado.get('nombre', '')
                        
                        # Extraer CP, Localidad, Provincia del domicilio si es posible
                        domicilio_completo = resultado.get('domicilio_fiscal', '')
                        st.session_state['afip_data']['domicilio_f'] = domicilio_completo
                        st.session_state['afip_data']['estado'] = resultado.get('estado', '')
                        st.rerun()

    st.divider()
    st.subheader("2. Completar Datos del Cliente")
    
    with st.form("alta_cliente_form"):
        col1, col2 = st.columns(2)
        with col1:
            cuit = st.text_input("CUIT *", value=st.session_state['afip_data']['cuit'])
        with col2:
            nombre = st.text_input("NOMBRE (Razón Social) *", value=st.session_state['afip_data']['nombre'])
            
        domicilio_f = st.text_input("Domicilio Fiscal", value=st.session_state['afip_data']['domicilio_f'])
        domicilio_e = st.text_input("Domicilio Entrega")
        
        col_loc, col_cp, col_pais = st.columns(3)
        with col_loc:
            localidad = st.text_input("LOCALIDAD")
        with col_cp:
            c_postal = st.text_input("Código Postal")
        with col_pais:
            pais = st.text_input("País", value="Argentina")
        
        st.subheader("Datos Complementarios")
        n_fantasia = st.text_input("Nombre Fantasia")
        contacto = st.text_input("Persona de Contacto")
        telefono = st.text_input("Telefono de contacto")
        
        ramos_disponibles = ["Seleccione un ramo..."] + cargar_ramos()
        giro_comercial = st.selectbox("Giro Comercial (Rubro)", ramos_disponibles)
        
        submit = st.form_submit_button("Guardar y Enviar a Validación")
        
        if submit:
            if not cuit or not nombre:
                st.error("Por favor completa el CUIT y la Razón Social.")
            elif supabase is None:
                st.error("No hay conexión a la base de datos configurada.")
            else:
                try:
                    data = {
                        "cuit": cuit,
                        "nombre": nombre,
                        "n_fantasia": n_fantasia,
                        "domicilio_f": domicilio_f,
                        "domicilio_e": domicilio_e,
                        "localidad": localidad,
                        "c_postal": c_postal,
                        "pais": pais,
                        "contacto": contacto,
                        "telefono": telefono,
                        "giro_comercial": giro_comercial if giro_comercial != "Seleccione un ramo..." else None,
                        "creado_por": st.session_state.get('user_id'),
                        "estado": "Pendiente"
                    }
                    response = supabase.table('clientes_pendientes').insert(data).execute()
                    st.success("¡Cliente guardado exitosamente y en espera de validación!")
                    # Limpiar estado
                    st.session_state['afip_data'] = {
                        "cuit": "", "nombre": "", "domicilio_f": "", 
                        "localidad": "", "provincia": "", "cp": "", "estado": ""
                    }
                except Exception as e:
                    st.error(f"Error al guardar el cliente: {e}")
