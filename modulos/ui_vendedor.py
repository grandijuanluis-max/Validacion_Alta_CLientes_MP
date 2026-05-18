import streamlit as st
import pandas as pd
import os
from modulos.api_afip import consultar_cuit_afip
from modulos.db import supabase

def cargar_ramos():
    if supabase is None:
        return ["Kiosco", "Supermercado", "Ferretería"]
    try:
        response = supabase.table('ramos').select('descrip').execute()
        if response.data:
            return sorted([row['descrip'] for row in response.data])
        return ["Kiosco", "Supermercado", "Ferretería"]
    except Exception:
        return ["Kiosco", "Supermercado", "Ferretería"]

@st.cache_data
def buscar_cp(localidad, provincia):
    if not localidad or not provincia or supabase is None:
        return []
        
    loc_upper = str(localidad).upper().strip()
    prov_upper = str(provincia).upper().strip()
    
    try:
        # Búsqueda SQL de alto rendimiento gracias a los índices ILIKE
        response = supabase.table('codigos_postales').select('cp').ilike('localidad', loc_upper).ilike('provincia', prov_upper).execute()
        
        if response.data:
            cps = list(set([str(row['cp']) for row in response.data if row.get('cp')]))
            return sorted(cps)
        return []
    except Exception as e:
        print(f"Error buscando CP en Supabase: {e}")
        return []

def render_vendedor_dashboard():
    st.header("🏢 Alta de Nuevo Cliente")
    
    # Inicializar estado
    if 'modo_carga' not in st.session_state:
        st.session_state['modo_carga'] = None # Puede ser None, 'afip', o 'manual'
        
    if 'afip_data' not in st.session_state:
        st.session_state['afip_data'] = {
            "cuit": "", "nombre": "", "domicilio_f": "", 
            "localidad": "", "provincia": "", "cp": "", "estado": "",
            "tipo_doc_desc": "", "tipo_doc_codigo": "",
            "tipo_resp_desc": "", "tipo_resp_codigo": "",
            "actividad": "", "cod_acti": "",
            "antiguedad": "", "mes_cierre": ""
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
                                st.session_state['afip_data']['localidad'] = resultado.get('localidad', '')
                                st.session_state['afip_data']['provincia'] = resultado.get('provincia', '')
                                st.session_state['afip_data']['estado'] = resultado.get('estado', '')
                                st.session_state['afip_data']['tipo_doc_desc'] = resultado.get('tipo_doc_desc', '')
                                st.session_state['afip_data']['tipo_doc_codigo'] = resultado.get('tipo_doc_codigo', '')
                                st.session_state['afip_data']['tipo_resp_desc'] = resultado.get('tipo_resp_desc', '')
                                st.session_state['afip_data']['tipo_resp_codigo'] = resultado.get('tipo_resp_codigo', '')
                                st.session_state['afip_data']['actividad'] = resultado.get('actividad', '')
                                st.session_state['afip_data']['cod_acti'] = resultado.get('cod_acti', '')
                                st.session_state['afip_data']['antiguedad'] = resultado.get('antiguedad', '')
                                st.session_state['afip_data']['mes_cierre'] = resultado.get('mes_cierre', '')
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
        
        col1, col2 = st.columns(2)
        with col1:
            cuit = st.text_input("CUIT *", value=st.session_state['afip_data']['cuit'])
        with col2:
            nombre = st.text_input("NOMBRE (Razón Social) *", value=st.session_state['afip_data']['nombre'])
            
        st.markdown("##### Información Impositiva (AFIP)")
        col_tdoc, col_tresp, col_acti = st.columns(3)
        with col_tdoc:
            st.text_input("Tipo Documento", value=st.session_state['afip_data'].get('tipo_doc_desc', ''), disabled=True)
        with col_tresp:
            st.text_input("Tipo Responsable", value=st.session_state['afip_data'].get('tipo_resp_desc', ''), disabled=True)
        with col_acti:
            st.text_input("Actividad Principal", value=st.session_state['afip_data'].get('actividad', ''), disabled=True)
            
        col_cacti, col_ant, col_mes = st.columns(3)
        with col_cacti:
            st.text_input("Código Actividad", value=st.session_state['afip_data'].get('cod_acti', ''), disabled=True)
        with col_ant:
            st.text_input("Antigüedad (Fecha)", value=st.session_state['afip_data'].get('antiguedad', ''), disabled=True)
        with col_mes:
            st.text_input("Mes Cierre", value=st.session_state['afip_data'].get('mes_cierre', ''), disabled=True)
            
        st.markdown("##### Domicilio y Contacto")
            
        domicilio_f = st.text_input("Domicilio Fiscal *", value=st.session_state['afip_data']['domicilio_f'])
        domicilio_e = st.text_input("Domicilio Entrega *", value=st.session_state['afip_data']['domicilio_f'])
        
        col_cp, col_loc, col_prov, col_pais = st.columns(4)
        
        with col_loc:
            localidad = st.text_input("LOCALIDAD *", value=st.session_state['afip_data'].get('localidad', ''))
        with col_prov:
            provincia = st.text_input("Provincia *", value=st.session_state['afip_data'].get('provincia', ''))
            
        # Reactividad en tiempo real: Se evalúan los valores tipeados en el momento
        cp_matches = buscar_cp(localidad, provincia)
        
        with col_cp:
            if len(cp_matches) == 1:
                c_postal = st.text_input("Código Postal *", value=cp_matches[0], help="Autocompletado desde Base de Datos")
            elif len(cp_matches) > 1:
                c_postal = st.selectbox("Código Postal *", cp_matches, help="Múltiples opciones encontradas en la Base de Datos")
            else:
                c_postal = st.text_input("Código Postal *", help="No encontrado en Base de Datos. Ingresa manualmente.")
                st.warning("⚠️ Localidad no encontrada. Ingresa el CP a mano.")
                
        with col_pais:
            pais = st.text_input("País *", value="ARGENTINA")
        
        st.subheader("Datos Complementarios")
        n_fantasia = st.text_input("Nombre Fantasia *", value=st.session_state['afip_data']['nombre'])
        contacto = st.text_input("Persona de Contacto *")
        telefono = st.text_input("Telefono de contacto *")
        
        ramos_disponibles = ["Seleccione un ramo..."] + cargar_ramos()
        giro_comercial = st.selectbox("Giro Comercial (Rubro) *", ramos_disponibles)
        
        submit = st.button("Guardar y Enviar a Validación", type="primary", use_container_width=True)
        
        if submit:
            # Validación estricta de TODOS los campos obligatorios
            faltantes = []
            if not cuit.strip(): faltantes.append("CUIT")
            if not nombre.strip(): faltantes.append("NOMBRE (Razón Social)")
            if not domicilio_f.strip(): faltantes.append("Domicilio Fiscal")
            if not domicilio_e.strip(): faltantes.append("Domicilio Entrega")
            if not localidad.strip(): faltantes.append("LOCALIDAD")
            if not provincia.strip(): faltantes.append("Provincia")
            if not str(c_postal).strip(): faltantes.append("Código Postal")
            if not pais.strip(): faltantes.append("País")
            if not n_fantasia.strip(): faltantes.append("Nombre Fantasía")
            if not contacto.strip(): faltantes.append("Persona de Contacto")
            if not telefono.strip(): faltantes.append("Teléfono de Contacto")
            if giro_comercial == "Seleccione un ramo...": faltantes.append("Giro Comercial (Rubro)")
            
            if faltantes:
                st.error(f"❌ Error: Faltan completar los siguientes campos obligatorios: {', '.join(faltantes)}")
            elif supabase is None:
                st.error("No hay conexión a la base de datos configurada.")
            else:
                try:
                    data = {
                        "cuit": cuit.upper() if cuit else "",
                        "nombre": nombre.upper() if nombre else "",
                        "n_fantasia": n_fantasia.upper() if n_fantasia else "",
                        "domicilio_f": domicilio_f.upper() if domicilio_f else "",
                        "domicilio_e": domicilio_e.upper() if domicilio_e else "",
                        "localidad": localidad.upper() if localidad else "",
                        "provincia": provincia.upper() if provincia else "",
                        "c_postal": str(c_postal).upper() if c_postal else "",
                        "pais": pais.upper() if pais else "",
                        "contacto": contacto.upper() if contacto else "",
                        "telefono": telefono.upper() if telefono else "",
                        "giro_comercial": giro_comercial if giro_comercial != "Seleccione un ramo..." else None,
                        "creado_por": st.session_state.get('user_id'),
                        "estado": "Pendiente",
                        "tipo_resp": st.session_state['afip_data'].get('tipo_resp_codigo', ''),
                        "tipo_doc": st.session_state['afip_data'].get('tipo_doc_codigo', ''),
                        "actividad": st.session_state['afip_data'].get('actividad', ''),
                        "cod_acti": st.session_state['afip_data'].get('cod_acti', ''),
                        "antiguedad": st.session_state['afip_data'].get('antiguedad', ''),
                        "mes_cierre": st.session_state['afip_data'].get('mes_cierre', '')
                    }
                    response = supabase.table('clientes_pendientes').insert(data).execute()
                    st.success("¡Cliente guardado exitosamente y en espera de validación!")
                    # Limpiar estado para el próximo cliente
                    st.session_state['afip_data'] = {
                        "cuit": "", "nombre": "", "domicilio_f": "", 
                        "localidad": "", "provincia": "", "cp": "", "estado": "",
                        "tipo_doc_desc": "", "tipo_doc_codigo": "",
                        "tipo_resp_desc": "", "tipo_resp_codigo": "",
                        "actividad": "", "cod_acti": "",
                        "antiguedad": "", "mes_cierre": ""
                    }
                    st.session_state['modo_carga'] = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar el cliente: {e}")
