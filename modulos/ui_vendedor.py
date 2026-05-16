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
    
    # Inicializar estado
    if 'modo_carga' not in st.session_state:
        st.session_state['modo_carga'] = None # Puede ser None, 'afip', o 'manual'
        
    if 'afip_data' not in st.session_state:
        st.session_state['afip_data'] = {
            "cuit": "", "nombre": "", "domicilio_f": "", 
            "localidad": "", "provincia": "", "cp": "", "estado": ""
        }

    # PASO 1: Selector / Buscador
    if st.session_state['modo_carga'] is None:
        st.info("💡 Paso 1: Busca a tu cliente en AFIP para autocompletar sus datos.")
        
        cuit_busqueda = st.text_input("Ingresa el CUIT a buscar (Ej: 30111111111):", value=st.session_state['afip_data']['cuit'])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Buscar en AFIP", type="primary", use_container_width=True):
                if not cuit_busqueda:
                    st.warning("Escribe un CUIT primero.")
                else:
                    with st.spinner("Consultando Padrón AFIP..."):
                        try:
                            # Hacemos la consulta a AFIP
                            resultado = consultar_cuit_afip(cuit_busqueda)
                            
                            if "error" in resultado:
                                # Fallo de AFIP (Caída o CUIT Inválido)
                                st.error(f"⚠️ Atención: {resultado['error']}")
                                st.warning("AFIP no responde o el CUIT es incorrecto. Puedes reintentar o usar la carga manual.")
                            else:
                                # Éxito en AFIP
                                st.success(f"¡Cliente Encontrado! (Estado: {resultado.get('estado', 'Desconocido')})")
                                st.session_state['afip_data']['cuit'] = cuit_busqueda
                                st.session_state['afip_data']['nombre'] = resultado.get('nombre', '')
                                st.session_state['afip_data']['domicilio_f'] = resultado.get('domicilio_fiscal', '')
                                st.session_state['afip_data']['estado'] = resultado.get('estado', '')
                                st.session_state['modo_carga'] = 'afip'
                                st.rerun()
                        except Exception as e:
                            st.error("Error al conectar con AFIP. El servicio podría estar temporalmente caído.")
                            st.warning("Por favor, utiliza la Carga Manual.")
                            
        with col2:
            if st.button("📝 Cargar Manualmente (Sin AFIP)", use_container_width=True):
                st.session_state['afip_data']['cuit'] = cuit_busqueda # Llevamos el CUIT que haya tipeado, si lo hizo
                st.session_state['modo_carga'] = 'manual'
                st.rerun()

    # PASO 2: Formulario Completo
    else:
        # Cabecera indicando el modo
        if st.session_state['modo_carga'] == 'afip':
            st.success("✅ Completando datos desde AFIP")
        else:
            st.warning("📝 Modo de Carga Manual activado (Sin validación AFIP)")
            
        if st.button("⬅️ Volver a Buscar en AFIP / Cambiar CUIT"):
            st.session_state['modo_carga'] = None
            st.rerun()
            
        st.divider()
        st.subheader("Paso 2: Completar y Enviar")
        
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
            
            submit = st.form_submit_button("Guardar y Enviar a Validación", type="primary")
            
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
                        # Limpiar estado para el próximo cliente
                        st.session_state['afip_data'] = {
                            "cuit": "", "nombre": "", "domicilio_f": "", 
                            "localidad": "", "provincia": "", "cp": "", "estado": ""
                        }
                        st.session_state['modo_carga'] = None
                    except Exception as e:
                        st.error(f"Error al guardar el cliente: {e}")
