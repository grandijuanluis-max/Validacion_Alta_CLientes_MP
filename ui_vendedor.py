import streamlit as st
import pandas as pd
import os
from modulos.api_afip import consultar_cuit

def cargar_ramos():
    ruta_ramo = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ramo.csv')
    try:
        df = pd.read_csv(ruta_ramo, sep=';')
        return df['descrip'].tolist()
    except Exception as e:
        return ["Kiosco", "Supermercado", "Ferretería"] # Fallback

def render_vendedor_dashboard():
    st.header("🏢 Alta de Nuevo Cliente")
    
    with st.form("alta_cliente_form"):
        st.subheader("Datos Fiscales")
        col1, col2 = st.columns([1, 2])
        
        with col1:
            cuit = st.text_input("CUIT (Ej: 30-11111111-1)")
            
        with col2:
            st.info("Ingresa el CUIT y los datos se autocompletarán si presionas 'Buscar en AFIP'. (A implementarse)")
            
        st.divider()
        
        # Datos Autocompletados (simulados por ahora)
        nombre = st.text_input("NOMBRE (Razón Social)", disabled=True)
        domicilio_f = st.text_input("Domicilio Fiscal", disabled=True)
        domicilio_e = st.text_input("Domicilio Entrega", disabled=True)
        
        col_loc, col_cp, col_pais = st.columns(3)
        with col_loc:
            localidad = st.text_input("LOCALIDAD", disabled=True)
        with col_cp:
            c_postal = st.text_input("Código Postal", disabled=True)
        with col_pais:
            pais = st.text_input("País", disabled=True)
        
        st.subheader("Datos Complementarios")
        n_fantasia = st.text_input("Nombre Fantasia")
        contacto = st.text_input("Persona de Contacto")
        telefono = st.text_input("Telefono de contacto")
        
        ramos_disponibles = ["Seleccione un ramo..."] + cargar_ramos()
        giro_comercial = st.selectbox("Giro Comercial (Rubro)", ramos_disponibles)
        
        submit = st.form_submit_button("Guardar y Enviar a Validación")
        
        if submit:
            # TODO: Guardar en Supabase usando st.session_state['codigo_vendedor'] y marcar como Pendiente.
            st.success("¡Cliente guardado exitosamente y en espera de validación!")
