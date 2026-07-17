import streamlit as st
import pandas as pd
from modulos.db import supabase
from modulos.ui_validador import MAP_TIPO_RESP
from modulos.api_nosis import consultar_y_evaluar_nosis
from modulos.reporte_pdf import render_nosis_pdf_download, build_nosis_pdf_bytes

@st.dialog("🛡️ Resumen Nosis de Socio")
def mostrar_modal_socio(cuit_socio, rol_socio):
    st.write(f"Consultando información de Nosis para **{rol_socio}** con CUIT: `{cuit_socio}`...")
    user_id = st.session_state.get('user_id', None)
    
    with st.spinner("Conectando con Nosis..."):
        nosis_data = consultar_y_evaluar_nosis(cuit_socio, user_id)
        
    if 'error' in nosis_data:
        st.warning(nosis_data['error'])
    else:
        dictamen = nosis_data.get('dictamen', '')
        st.caption(f"Fuente de datos: {nosis_data.get('origen', '')}")
        
        if dictamen == "RECHAZO AUTOMÁTICO":
            st.error(f"🛑 DICTAMEN: {dictamen}")
        elif dictamen == "REVISIÓN GERENCIAL":
            st.warning(f"⚠️ DICTAMEN: {dictamen}")
        else:
            st.success(f"✅ DICTAMEN: {dictamen}")
            
        st.info(f"💡 **Análisis Narrativo**: {nosis_data.get('explicacion', '')}")
        
        payload = nosis_data.get('payload_crudo', {})
        semaforos = nosis_data.get('semaforos', {})
        
        # Semáforos Principales
        st.markdown("##### 🚦 Semáforos Principales")
        def pinta_semaforo(color):
            if color == "VERDE": return "🟢"
            if color == "AMARILLO": return "🟡"
            return "🔴"
            
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
        col_m1.metric(f"{pinta_semaforo(semaforos.get('score'))} Score", payload.get('score_riesgo', 850))
        col_m2.metric(f"{pinta_semaforo(semaforos.get('bcra'))} BCRA", payload.get('calificacion_bcra', 1))
        col_m3.metric(f"{pinta_semaforo(semaforos.get('cheques'))} Cheques", payload.get('cheques_rechazados', 0))
        col_m4.metric(f"{pinta_semaforo(semaforos.get('juicios'))} Juicios", payload.get('juicios_concursos', 0))
        col_m5.metric(f"{pinta_semaforo(semaforos.get('afip'))} AFIP", payload.get('baches_afip_meses', 0))
        
        # Inteligencia crediticia
        st.markdown("##### 📊 Inteligencia y Estabilidad")
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        col_f1.metric("NSE", payload.get('nse', 'No registrado'))
        col_f2.metric("Antigüedad", f"{payload.get('antiguedad_laboral', 0)} meses")
        deuda = payload.get('deuda_total', 0)
        col_f3.metric("Deuda Bancaria", f"$ {deuda:,.2f}" if deuda else "$ 0.00")
        comp = payload.get('compromiso_mensual', 0)
        col_f4.metric("Compromiso", f"$ {comp:,.2f}" if comp else "$ 0.00")
        
        # Alertas
        st.markdown("##### 🚨 Alertas Impositivas")
        def format_alerta(val):
            if str(val).strip().lower() == "si": return f"⚠️ {val}"
            return f"✅ {val}"
        col_a1, col_a2, col_a3 = st.columns(3)
        col_a1.metric("Apócrifas AFIP", format_alerta(payload.get('facturas_apocrifas', 'No')))
        col_a2.metric("Deuda Fiscal", format_alerta(payload.get('deudas_fiscales', 'No')))
        col_a3.metric("Es Moroso", format_alerta(payload.get('es_moroso', 'No')))
        
        # Botón de Descarga del Reporte PDF para el Socio
        st.markdown("##### 📄 Exportación Oficial")
        render_nosis_pdf_download(
            payload,
            cuit_socio,
            dictamen,
            semaforos,
            nosis_data.get("explicacion", ""),
            label="Generar y descargar Resumen Socio PDF",
            file_name=f"Resumen_Socio_{cuit_socio}.pdf",
            key=f"modal_socio_exp_{cuit_socio}",
        )

def render_exportados_dashboard():
    st.header("📦 Clientes Exportados")
    st.write("Consulta el historial de los clientes que ya fueron exportados a Presea.")
    
    if supabase is None:
        st.error("No hay conexión a la base de datos configurada.")
        return

    try:
        response = supabase.table('clientes_pendientes').select('*, usuarios(codigo_vendedor)').eq('estado', 'Exportado').execute()
        
        if not response.data:
            st.info("No hay clientes exportados aún.")
            return
            
        df = pd.DataFrame(response.data)
        df['tipo_resp_desc'] = df['tipo_resp'].apply(lambda x: MAP_TIPO_RESP.get(str(x), str(x) if x else "N/A"))
        
        display_df = df[['nombre', 'cuit', 'tipo_resp_desc', 'giro_comercial', 'contacto', 'estado']].copy()
        display_df.rename(columns={
            'nombre': 'Razón Social',
            'cuit': 'CUIT',
            'tipo_resp_desc': 'Tipo de Responsable',
            'giro_comercial': 'Giro Comercial',
            'contacto': 'Persona de Contacto',
            'estado': 'Estado'
        }, inplace=True)
        
        # Filtro simple de búsqueda
        search_query = st.text_input("🔍 Buscar por Razón Social o CUIT", "")
        
        if search_query:
            mask = display_df['Razón Social'].str.contains(search_query, case=False, na=False) | \
                   display_df['CUIT'].str.contains(search_query, case=False, na=False)
            filtered_df = display_df[mask]
        else:
            filtered_df = display_df
            
        event = st.dataframe(
            filtered_df, 
            use_container_width=True, 
            selection_mode="single-row", 
            on_select="rerun",
            hide_index=True
        )
        
        st.divider()
        
        if event and len(event.selection.rows) > 0:
            selected_index = event.selection.rows[0]
            if selected_index >= len(filtered_df):
                st.rerun()
            # Usar filtered_df en lugar de df para que el índice coincida con la selección
            client_data = filtered_df.iloc[selected_index]
            
            # Obtener el registro completo original desde el dataframe sin filtrar columnas
            cuit_seleccionado = client_data.get('CUIT', '')
            original_client_data = df[df['cuit'] == cuit_seleccionado].iloc[0]
            
            st.markdown(f"### 📋 Detalle Histórico: {original_client_data.get('nombre', '')}")
            
            # --- SECCIÓN NOSIS (Histórico) ---
            st.markdown("#### 🛡️ Análisis de Riesgo Crediticio (Histórico Nosis)")
            user_id = st.session_state.get('user_id', None)
            with st.spinner("Ejecutando Motor de Reglas Corporativo..."):
                nosis_data = consultar_y_evaluar_nosis(cuit_seleccionado, user_id)
            
            if 'error' in nosis_data:
                st.warning(nosis_data['error'])
            else:
                dictamen = nosis_data.get('dictamen', '')
                st.caption(f"Fuente de datos: {nosis_data.get('origen', '')}")
                
                if dictamen == "RECHAZO AUTOMÁTICO":
                    st.error(f"### 🛑 DICTAMEN HISTÓRICO: {dictamen}")
                elif dictamen == "REVISIÓN GERENCIAL":
                    st.warning(f"### ⚠️ DICTAMEN HISTÓRICO: {dictamen}")
                else:
                    st.success(f"### ✅ DICTAMEN HISTÓRICO: {dictamen}")
                
                # Explicación conversacional del dictamen
                st.info(f"💡 **Análisis Narrativo del Motor**: {nosis_data.get('explicacion', '')}")
                
                payload = nosis_data.get('payload_crudo', {})
                semaforos = nosis_data.get('semaforos', {})
                
                # Función auxiliar para pintar semaforos
                def pinta_semaforo(color):
                    if color == "VERDE": return "🟢"
                    if color == "AMARILLO": return "🟡"
                    return "🔴"
                    
                st.markdown("##### 🚦 Semáforos Principales")
                col_n1, col_n2, col_n3, col_n4, col_n5 = st.columns(5)
                col_n1.metric(f"{pinta_semaforo(semaforos.get('score'))} Score", payload.get('score_riesgo', 850))
                col_n2.metric(f"{pinta_semaforo(semaforos.get('bcra'))} BCRA", payload.get('calificacion_bcra', 1))
                col_n3.metric(f"{pinta_semaforo(semaforos.get('cheques'))} Cheques", payload.get('cheques_rechazados', 0))
                col_n4.metric(f"{pinta_semaforo(semaforos.get('juicios'))} Juicios", payload.get('juicios_concursos', 0))
                col_n5.metric(f"{pinta_semaforo(semaforos.get('afip'))} Deuda AFIP", payload.get('baches_afip_meses', 0))
                
                # Nuevas variables de Nosis
                st.markdown("##### 📊 Inteligencia Crediticia y Estabilidad (Nosis Ampliado)")
                col_e1, col_e2, col_e3, col_e4 = st.columns(4)
                col_e1.metric("Nivel Socioeconómico (NSE)", payload.get('nse', 'No registrado'))
                
                antiguedad = payload.get('antiguedad_laboral', 0)
                col_e2.metric("Antigüedad AFIP/Monotributo", f"{antiguedad} meses" if antiguedad else "No registrado")
                
                deuda = payload.get('deuda_total', 0)
                col_e3.metric("Deuda Bancaria Total", f"$ {deuda:,.2f}" if deuda else "$ 0.00")
                
                comp = payload.get('compromiso_mensual', 0)
                col_e4.metric("Compromiso Mensual", f"$ {comp:,.2f}" if comp else "$ 0.00")
                
                col_p1, col_p2, col_p3, col_p4 = st.columns(4)
                col_p1.metric("Es Empleado Rel. Dep.", payload.get('es_empleado', 'No'))
                col_p2.metric("Bancos Acreedores", payload.get('cant_bancos', 0))
                col_p3.metric("Consultas CUIT (12m)", payload.get('consultas_12m', 0))
                
                emp_rz = payload.get('empleador', 'No registrado')
                col_p4.metric("Empleador Principal", emp_rz[:20] + "..." if len(emp_rz) > 20 else emp_rz)
                
                st.markdown("##### 🚨 Alertas Impositivas y Comercial")
                col_a1, col_a2, col_a3 = st.columns(3)
                
                def format_alerta(val):
                    if str(val).strip().lower() == "si":
                        return f"⚠️ {val}"
                    return f"✅ {val}"
                
                col_a1.metric("Facturas Apócrifas AFIP", format_alerta(payload.get('facturas_apocrifas', 'No')))
                col_a2.metric("Deudas Fiscales AFIP", format_alerta(payload.get('deudas_fiscales', 'No')))
                col_a3.metric("Es Moroso Comercial", format_alerta(payload.get('es_moroso', 'No')))
                
                # Botón de Descarga del Reporte PDF
                st.markdown("##### 📄 Exportación de Reporte Oficial")
                render_nosis_pdf_download(
                    payload,
                    cuit_seleccionado,
                    dictamen,
                    semaforos,
                    nosis_data.get("explicacion", ""),
                    label="Generar y descargar Resumen PDF",
                    file_name=f"Resumen_Riesgo_{cuit_seleccionado}.pdf",
                    key=f"exportados_{cuit_seleccionado}",
                )
                
                with st.expander("ℹ️ ¿Cómo leer estas mediciones? (Glosario Nosis)"):
                    st.markdown("""
                    *   **Score:** Puntaje estadístico que predice la probabilidad de pago. **>700** es Óptimo (Verde), **450-699** es Riesgo Medio (Amarillo), **<450** es Riesgo Alto (Rojo).
                    *   **BCRA:** Situación en la Central de Deudores del Banco Central. **1** es Normal (Verde), **2** es Riesgo Potencial (Amarillo), **3, 4 y 5** indican riesgo alto/incobrable (Rojo).
                    *   **Cheques:** Cantidad de cheques rechazados sin fondos en los últimos 24 meses.
                    *   **Juicios:** Cantidad de juicios comerciales, ejecuciones fiscales o estado de concurso preventivo.
                    *   **Deuda AFIP:** Meses de atraso detectados en el pago de cargas sociales (aportes patronales).
                    *   **NSE (Nivel Socioeconómico):** Clasifica la capacidad de consumo y el poder adquisitivo estimado del deudor de la **A** a la **D2**. **Nota:** En el caso de **Personas Jurídicas (Empresas/Sociedades)**, esta métrica figurará como **NC (No Clasificado)** o **No registrado**, ya que es una segmentación socioeconómica diseñada de manera exclusiva para personas físicas.
                    *   **Es Empleado Rel. Dep.:** Indica si el CUIT consultado registra aportes previsionales vigentes como empleado en relación de dependencia. Si es un trabajador independiente (Autónomo o Monotributista) o una **Persona Jurídica (Empresa)**, esta variable figurará siempre como **No**.
                    *   **Empleador Principal / Empleador (No registrado):** Si la variable *"Es Empleado Rel. Dep."* es **No**, el empleador figurará como *"No registrado"*. Esto es totalmente normal y esperado para trabajadores independientes o en el caso de las empresas/sociedades que son empleadoras en sí mismas, no empleados.
                    *   **Antigüedad Laboral (0 meses):** Representa el tiempo activo de empleo bajo relación de dependencia con el empleador actual. Si todos los consultados figuran con **0 meses**, se debe a que:
                        1. El CUIT consultado es una **Persona Jurídica (Empresa/Sociedad)**: Las empresas no poseen una relación laboral de dependencia, por lo que su antigüedad laboral siempre es cero.
                        2. El CUIT corresponde a un **Monotributista o Autónomo (Trabajador Independiente)**: Al no tener un empleador en relación de dependencia activa, no computan antigüedad laboral tradicional.
                        3. El CUIT de la persona física no registra aportes de empleo dependiente activo en las bases de datos de Nosis (empleo informal, desempleado, jubilado o inactivo).
                    """)
                
            st.divider()
            
            # --- FORMULARIO SOLO LECTURA ---
            st.markdown("#### Datos Exportados (Solo Lectura)")
            
            col1, col2 = st.columns(2)
            col1.text_input("CUIT", value=original_client_data.get('cuit', ''), disabled=True)
            col2.text_input("NOMBRE (Razón Social)", value=original_client_data.get('nombre', ''), disabled=True)
            
            st.markdown("##### Información Impositiva")
            col_t1, col_t2 = st.columns(2)
            col_t1.text_input("Tipo Documento", value=original_client_data.get('tipo_doc', ''), disabled=True)
            col_t2.text_input("Tipo Responsable", value=original_client_data.get('tipo_resp_desc', ''), disabled=True)
            
            st.text_input("Actividad Principal", value=original_client_data.get('actividad', ''), disabled=True)
            col_a1, col_a2, col_a3 = st.columns(3)
            col_a1.text_input("Cod. Actividad", value=original_client_data.get('cod_acti', ''), disabled=True)
            col_a2.text_input("Antigüedad", value=original_client_data.get('antiguedad', ''), disabled=True)
            col_a3.text_input("Mes Cierre", value=original_client_data.get('mes_cierre', ''), disabled=True)
            
            st.markdown("##### Datos Comerciales y Societarios")
            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.text_input("Giro Comercial", value=original_client_data.get('giro_comercial', ''), disabled=True, key=f"giro_exp_{cuit_seleccionado}")
            col_s2.text_input("CUIT Socio 1", value=original_client_data.get('cuit_socio1', ''), disabled=True, key=f"socio1_exp_{cuit_seleccionado}")
            col_s3.text_input("CUIT Socio 2", value=original_client_data.get('cuit_socio2', ''), disabled=True, key=f"socio2_exp_{cuit_seleccionado}")

            # Limpiar e identificar si son CUITs válidos (solo dígitos y exactamente 11)
            cuit_s1_digits = "".join(filter(str.isdigit, str(original_client_data.get('cuit_socio1', ''))))
            cuit_s2_digits = "".join(filter(str.isdigit, str(original_client_data.get('cuit_socio2', ''))))
            
            has_soc1 = len(cuit_s1_digits) == 11
            has_soc2 = len(cuit_s2_digits) == 11
            
            if has_soc1 or has_soc2:
                st.markdown("##### 👥 Consultas Nosis de Socios")
                col_soc1, col_soc2 = st.columns(2)
                
                if has_soc1:
                    with col_soc1:
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(26, 82, 118, 0.05); padding: 12px; border-radius: 8px; border-left: 4px solid #1a5276; margin-bottom: 8px;">
                                <h6 style="margin: 0; color: #1a5276; font-size: 14px; font-weight: bold;">👤 Socio 1</h6>
                                <p style="margin: 3px 0 0 0; font-size: 13px; color: #566573;">CUIT: <b>{cuit_s1_digits}</b></p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        c1, c2 = st.columns(2)
                        if c1.button("🔍 Análisis Nosis", key=f"btn_socio1_analisis_exp_{cuit_s1_digits}", use_container_width=True):
                            mostrar_modal_socio(cuit_s1_digits, "Socio 1")
                            
                        pdf_key_s1 = f"pdf_bytes_socio_exp_{cuit_s1_digits}"
                        if pdf_key_s1 in st.session_state:
                            c2.download_button(
                                label="Descargar resumen CUIT socio",
                                data=st.session_state[pdf_key_s1],
                                file_name=f"Resumen_Socio_{cuit_s1_digits}.pdf",
                                mime="application/pdf",
                                key=f"dl_socio1_ready_exp_{cuit_s1_digits}",
                                use_container_width=True,
                            )
                        else:
                            if c2.button("Generar resumen CUIT socio", key=f"dl_socio1_gen_exp_{cuit_s1_digits}", use_container_width=True):
                                with st.spinner("Generando PDF..."):
                                    user_id = st.session_state.get('user_id', None)
                                    nosis_data = consultar_y_evaluar_nosis(cuit_s1_digits, user_id)
                                    if 'error' not in nosis_data:
                                        try:
                                            st.session_state[pdf_key_s1] = build_nosis_pdf_bytes(
                                                nosis_data.get('payload_crudo', {}),
                                                cuit_s1_digits,
                                                nosis_data.get('dictamen', ''),
                                                nosis_data.get('semaforos', {}),
                                                nosis_data.get('explicacion', ''),
                                            )
                                            st.rerun()
                                        except Exception as pdf_err:
                                            st.error(f"No se pudo generar el PDF del socio: {pdf_err}")
                                    else:
                                        st.error(nosis_data['error'])
                                        
                if has_soc2:
                    with col_soc2:
                        st.markdown(
                            f"""
                            <div style="background-color: rgba(26, 82, 118, 0.05); padding: 12px; border-radius: 8px; border-left: 4px solid #1a5276; margin-bottom: 8px;">
                                <h6 style="margin: 0; color: #1a5276; font-size: 14px; font-weight: bold;">👤 Socio 2</h6>
                                <p style="margin: 3px 0 0 0; font-size: 13px; color: #566573;">CUIT: <b>{cuit_s2_digits}</b></p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        c1_s2, c2_s2 = st.columns(2)
                        if c1_s2.button("🔍 Análisis Nosis", key=f"btn_socio2_analisis_exp_{cuit_s2_digits}", use_container_width=True):
                            mostrar_modal_socio(cuit_s2_digits, "Socio 2")
                            
                        pdf_key_s2 = f"pdf_bytes_socio_exp_{cuit_s2_digits}"
                        if pdf_key_s2 in st.session_state:
                            c2_s2.download_button(
                                label="Descargar resumen CUIT socio",
                                data=st.session_state[pdf_key_s2],
                                file_name=f"Resumen_Socio_{cuit_s2_digits}.pdf",
                                mime="application/pdf",
                                key=f"dl_socio2_ready_exp_{cuit_s2_digits}",
                                use_container_width=True,
                            )
                        else:
                            if c2_s2.button("Generar resumen CUIT socio", key=f"dl_socio2_gen_exp_{cuit_s2_digits}", use_container_width=True):
                                with st.spinner("Generando PDF..."):
                                    user_id = st.session_state.get('user_id', None)
                                    nosis_data = consultar_y_evaluar_nosis(cuit_s2_digits, user_id)
                                    if 'error' not in nosis_data:
                                        try:
                                            st.session_state[pdf_key_s2] = build_nosis_pdf_bytes(
                                                nosis_data.get('payload_crudo', {}),
                                                cuit_s2_digits,
                                                nosis_data.get('dictamen', ''),
                                                nosis_data.get('semaforos', {}),
                                                nosis_data.get('explicacion', ''),
                                            )
                                            st.rerun()
                                        except Exception as pdf_err:
                                            st.error(f"No se pudo generar el PDF del socio: {pdf_err}")
                                    else:
                                        st.error(nosis_data['error'])
            
            st.markdown("##### Domicilio Fiscal (AFIP)")
            st.text_input("Domicilio Fiscal", value=original_client_data.get('domicilio_f', ''), disabled=True)
            col_f1, col_f2, col_f3 = st.columns(3)
            col_f1.text_input("C.P. Fiscal", value=original_client_data.get('c_postal', ''), disabled=True)
            col_f2.text_input("Localidad Fiscal", value=original_client_data.get('localidad', ''), disabled=True)
            col_f3.text_input("Provincia Fiscal", value=original_client_data.get('provincia', ''), disabled=True)

            st.markdown("##### Domicilio de Entrega")
            st.text_input("Domicilio Entrega", value=original_client_data.get('domicilio_e', ''), disabled=True)
            col_e1, col_e2, col_e3 = st.columns(3)
            col_e1.text_input("C.P. Entrega", value=original_client_data.get('cp_ent', ''), disabled=True)
            col_e2.text_input("Localidad Entrega", value=original_client_data.get('local_ent', ''), disabled=True)
            col_e3.text_input("Provincia Entrega", value=original_client_data.get('prov_ent', ''), disabled=True)
            
            st.markdown("##### Contacto")
            col_c1, col_c2 = st.columns(2)
            col_c1.text_input("Persona de Contacto", value=original_client_data.get('contacto', ''), disabled=True)
            col_c2.text_input("Teléfono", value=original_client_data.get('telefono', ''), disabled=True)
            
            val_doc = original_client_data.get('documento', original_client_data.get('Documento', ''))
            if val_doc:
                st.divider()
                st.markdown("#### Observaciones del Vendedor")
                st.text_area("Aclaraciones para Alta Temprana", value=str(val_doc), disabled=True)
                
            # --- VOLVER A EXPORTAR ---
            st.divider()
            st.markdown("#### 🔄 Acciones Especiales")
            if st.button("🔄 Volver a Exportar este Cliente", type="primary", use_container_width=True, key=f"re_export_{cuit_seleccionado}"):
                try:
                    # Cambiar estado a 'A Exportar' en Supabase para permitir volver a exportar
                    supabase.table('clientes_pendientes').update({'estado': 'A Exportar'}).eq('id', str(original_client_data['id'])).execute()
                    st.success("🎉 Cliente marcado para volver a exportar de forma exitosa. Ahora figurará en la sección de 'Validación de Clientes'.")
                    st.rerun()
                except Exception as ex_err:
                    st.error(f"Error al cambiar el estado del cliente: {ex_err}")
        else:
            st.info("👆 Selecciona un cliente de la tabla para ver todos los detalles históricos de su exportación.")
            
    except Exception as e:
        st.error(f"Error al cargar clientes exportados: {e}")
