import streamlit as st
import pandas as pd
from modulos.generador_dbi import generar_archivo_dbi
from modulos.db import supabase
from modulos.api_nosis import consultar_y_evaluar_nosis

MAP_TIPO_RESP = {
    "1.0": "Resp. Inscripto",
    "3.0": "Monotributista",
    "4.0": "IVA Exento",
    "5.0": "Consumidor Final"
}

def render_validador_dashboard():
    st.header("✅ Validación de Clientes")
    
    # Manejar estado de descarga
    if 'archivo_exportado' in st.session_state:
        import os
        if os.path.exists(st.session_state['archivo_exportado']):
            st.success("¡Exportación completada exitosamente! El archivo está listo para descargar.")
            with open(st.session_state['archivo_exportado'], "rb") as f:
                st.download_button(
                    label="⬇️ Descargar Clientes_web.dbi",
                    data=f,
                    file_name="Clientes_web.dbi",
                    mime="application/octet-stream",
                    type="primary"
                )
            if st.button("Cerrar este mensaje"):
                del st.session_state['archivo_exportado']
                st.rerun()
            st.divider()
            
    st.write("A continuación se listan los clientes cargados por los vendedores que esperan validación o exportación.")
    
    if supabase is None:
        st.error("No hay conexión a la base de datos configurada.")
        return

    try:
        # Traer clientes que no estén Exportados
        response = supabase.table('clientes_pendientes').select('*, usuarios(codigo_vendedor)').in_('estado', ['Pendiente', 'Modificado', 'A Exportar']).execute()
        
        if not response.data:
            st.info("No hay clientes pendientes de validación o para exportar.")
            return
            
        df = pd.DataFrame(response.data)
        
        # Mapear tipo responsable
        df['tipo_resp_desc'] = df['tipo_resp'].apply(lambda x: MAP_TIPO_RESP.get(str(x), str(x) if x else "N/A"))
        
        # Preparar tabla para visualización según el orden solicitado
        display_df = df[['nombre', 'cuit', 'tipo_resp_desc', 'giro_comercial', 'contacto', 'estado']].copy()
        display_df.rename(columns={
            'nombre': 'Razón Social',
            'cuit': 'CUIT',
            'tipo_resp_desc': 'Tipo de Responsable',
            'giro_comercial': 'Giro Comercial',
            'contacto': 'Persona de Contacto',
            'estado': 'Estado'
        }, inplace=True)
        
        st.markdown("### Seleccione un cliente para ver sus detalles")
        # Mostrar tabla interactiva (selección simple)
        event = st.dataframe(
            display_df, 
            use_container_width=True, 
            selection_mode="single-row", 
            on_select="rerun",
            hide_index=True
        )
        
        st.divider()
        
        # Si hay una fila seleccionada, mostrar formulario completo
        if event and len(event.selection.rows) > 0:
            selected_index = event.selection.rows[0]
            client_data = df.iloc[selected_index]
            
            st.markdown(f"### 📋 Detalle del Cliente: {client_data.get('nombre', '')}")
            
            # --- SECCIÓN NOSIS ---
            st.markdown("#### 🛡️ Análisis de Riesgo Crediticio (Nosis)")
            user_id = st.session_state.get('user_id', None)
            with st.spinner("Ejecutando Motor de Reglas Corporativo..."):
                nosis_data = consultar_y_evaluar_nosis(client_data.get('cuit', ''), user_id)
            
            if 'error' in nosis_data:
                st.warning(nosis_data['error'])
            else:
                dictamen = nosis_data.get('dictamen', '')
                st.caption(f"Fuente de datos: {nosis_data.get('origen', '')}")
                
                if dictamen == "RECHAZO AUTOMÁTICO":
                    st.error(f"### 🛑 DICTAMEN: {dictamen}")
                    st.markdown("Se sugiere **bloquear** la cuenta o solicitar garantías adicionales.")
                elif dictamen == "REVISIÓN GERENCIAL":
                    st.warning(f"### ⚠️ DICTAMEN: {dictamen}")
                    st.markdown("El cliente presenta alertas amarillas. Requiere supervisión manual.")
                else:
                    st.success(f"### ✅ DICTAMEN: {dictamen}")
                    st.markdown("Perfil crediticio óptimo. Vía libre para operar.")
                
                payload = nosis_data.get('payload_crudo', {})
                semaforos = nosis_data.get('semaforos', {})
                
                # Función auxiliar para pintar semaforos
                def pinta_semaforo(color):
                    if color == "VERDE": return "🟢"
                    if color == "AMARILLO": return "🟡"
                    return "🔴"
                    
                col_n1, col_n2, col_n3, col_n4, col_n5 = st.columns(5)
                col_n1.metric(f"{pinta_semaforo(semaforos.get('score'))} Score", payload.get('score_riesgo'))
                col_n2.metric(f"{pinta_semaforo(semaforos.get('bcra'))} BCRA", payload.get('calificacion_bcra'))
                col_n3.metric(f"{pinta_semaforo(semaforos.get('cheques'))} Cheques", payload.get('cheques_rechazados'))
                col_n4.metric(f"{pinta_semaforo(semaforos.get('juicios'))} Juicios", payload.get('juicios_concursos'))
                col_n5.metric(f"{pinta_semaforo(semaforos.get('afip'))} Deuda AFIP", payload.get('baches_afip_meses'))
                
                with st.expander("ℹ️ ¿Cómo leer estas mediciones? (Glosario Nosis)"):
                    st.markdown("""
                    *   **Score:** Puntaje estadístico que predice la probabilidad de pago. **>700** es Óptimo (Verde), **450-699** es Riesgo Medio (Amarillo), **<450** es Riesgo Alto (Rojo).
                    *   **BCRA:** Situación en la Central de Deudores del Banco Central. **1** es Normal (Verde), **2** es Riesgo Potencial (Amarillo), **3, 4 y 5** indican riesgo alto/incobrable (Rojo).
                    *   **Cheques:** Cantidad de cheques rechazados sin fondos en los últimos 24 meses.
                    *   **Juicios:** Cantidad de juicios comerciales, ejecuciones fiscales o estado de concurso preventivo.
                    *   **Deuda AFIP:** Meses de atraso detectados en el pago de cargas sociales (aportes patronales).
                    """)
                
            st.divider()
            # ----------------------
            
            # Toggle para habilitar edición de campos manuales
            edit_mode = st.toggle("Habilitar modificación de datos manuales", value=False)
            
            # Formulario de lectura (Campos AFIP siempre bloqueados)
            col1, col2 = st.columns(2)
            col1.text_input("CUIT", value=client_data.get('cuit', ''), disabled=True)
            col2.text_input("NOMBRE (Razón Social)", value=client_data.get('nombre', ''), disabled=True)
            
            st.markdown("##### Información Impositiva")
            col_t1, col_t2 = st.columns(2)
            col_t1.text_input("Tipo Documento", value=client_data.get('tipo_doc', ''), disabled=True)
            col_t2.text_input("Tipo Responsable", value=client_data.get('tipo_resp_desc', ''), disabled=True)
            
            st.text_input("Actividad Principal", value=client_data.get('actividad', ''), disabled=True)
            col_a1, col_a2, col_a3 = st.columns(3)
            col_a1.text_input("Cod. Actividad", value=client_data.get('cod_acti', ''), disabled=True)
            col_a2.text_input("Antigüedad", value=client_data.get('antiguedad', ''), disabled=True)
            col_a3.text_input("Mes Cierre", value=client_data.get('mes_cierre', ''), disabled=True)
            
            st.markdown("##### Datos Comerciales y Societarios")
            col_s1, col_s2, col_s3 = st.columns(3)
            giro = col_s1.text_input("Giro Comercial", value=client_data.get('giro_comercial', ''), disabled=not edit_mode)
            socio1 = col_s2.text_input("CUIT Socio 1", value=client_data.get('cuit_socio1', ''), disabled=not edit_mode)
            socio2 = col_s3.text_input("CUIT Socio 2", value=client_data.get('cuit_socio2', ''), disabled=not edit_mode)
            
            st.markdown("##### Domicilio Fiscal (AFIP)")
            dom_f = st.text_input("Domicilio Fiscal", value=client_data.get('domicilio_f', ''), disabled=True)
            col_f1, col_f2, col_f3 = st.columns(3)
            cp_f = col_f1.text_input("C.P. Fiscal", value=client_data.get('c_postal', ''), disabled=True)
            loc_f = col_f2.text_input("Localidad Fiscal", value=client_data.get('localidad', ''), disabled=True)
            prov_f = col_f3.text_input("Provincia Fiscal", value=client_data.get('provincia', ''), disabled=True)

            st.markdown("##### Domicilio de Entrega")
            dom_e = st.text_input("Domicilio Entrega", value=client_data.get('domicilio_e', ''), disabled=not edit_mode)
            col_e1, col_e2, col_e3 = st.columns(3)
            cp_e = col_e1.text_input("C.P. Entrega", value=client_data.get('cp_ent', ''), disabled=not edit_mode)
            loc_e = col_e2.text_input("Localidad Entrega", value=client_data.get('local_ent', ''), disabled=not edit_mode)
            prov_e = col_e3.text_input("Provincia Entrega", value=client_data.get('prov_ent', ''), disabled=not edit_mode)
            
            st.markdown("##### Contacto")
            col_c1, col_c2 = st.columns(2)
            contacto = col_c1.text_input("Persona de Contacto", value=client_data.get('contacto', ''), disabled=not edit_mode)
            telefono = col_c2.text_input("Teléfono", value=client_data.get('telefono', ''), disabled=not edit_mode)
            
            st.divider()
            
            val_doc = client_data.get('documento', client_data.get('Documento', ''))
            if val_doc:
                st.markdown("#### Observaciones del Vendedor")
                st.text_area("Aclaraciones para Alta Temprana", value=str(val_doc), disabled=True)
                st.divider()
            
            st.markdown("#### Acciones de Validación")
            
            col_btn1, col_btn2 = st.columns(2)
            
            # Diccionario con los datos que se pueden actualizar
            datos_actualizados = {
                'giro_comercial': giro,
                'cuit_socio1': socio1,
                'cuit_socio2': socio2,
                'domicilio_e': dom_e,
                'cp_ent': cp_e,
                'local_ent': loc_e,
                'prov_ent': prov_e,
                'contacto': contacto,
                'telefono': telefono
            }
            
            if col_btn1.button("Guardar Cambios Manuales", use_container_width=True):
                datos_actualizados['estado'] = 'Modificado'
                supabase.table('clientes_pendientes').update(datos_actualizados).eq('id', str(client_data['id'])).execute()
                st.success("Datos guardados. Estado cambiado a Modificado.")
                st.rerun()
                
            if col_btn2.button("Marcar para Exportar (Aprobado)", type="primary", use_container_width=True):
                datos_actualizados['estado'] = 'A Exportar'
                supabase.table('clientes_pendientes').update(datos_actualizados).eq('id', str(client_data['id'])).execute()
                st.success(f"Cliente {client_data.get('nombre', '')} marcado para exportar exitosamente.")
                st.rerun()
                
        else:
            st.info("Haz clic en una de las filas de arriba para analizar el cliente en detalle y proceder con la autorización.")
            
        st.divider()
        # Mantenemos el botón de exportación masiva pero solo para los "A Exportar"
        df_a_exportar = df[df['estado'] == 'A Exportar']
        
        if st.button("Exportar todos los A Exportar"):
            if df_a_exportar.empty:
                st.warning("No hay clientes en estado 'A Exportar'.")
            else:
                secuencia_resp = supabase.table('secuencia_codigo').select('ultimo_valor').eq('id', 1).execute()
                ultimo_valor = 0 if not secuencia_resp.data else secuencia_resp.data[0]['ultimo_valor']
                numero_inicio = int(ultimo_valor) + 1
                
                # Pasamos solo los clientes filtrados al generador
                ruta_salida, nuevo_codigo_actual = generar_archivo_dbi(df_a_exportar, numero_inicio_codigo=numero_inicio)
                ultimo_asignado = nuevo_codigo_actual - 1
                
                for index, row in df_a_exportar.iterrows():
                    supabase.table('clientes_pendientes').update({'estado': 'Exportado'}).eq('id', row['id']).execute()
                    
                if secuencia_resp.data:
                    supabase.table('secuencia_codigo').update({'ultimo_valor': ultimo_asignado}).eq('id', 1).execute()
                else:
                    supabase.table('secuencia_codigo').insert({'id': 1, 'ultimo_valor': ultimo_asignado}).execute()
                    
                st.session_state['archivo_exportado'] = ruta_salida
                st.rerun()
            
    except Exception as e:
        st.error(f"Error al interactuar con la base de datos: {e}")
