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
        try:
            from modulos.reporte_pdf import generar_pdf_reporte_nosis
            path_pdf = generar_pdf_reporte_nosis(payload, cuit_socio, dictamen, semaforos, nosis_data.get('explicacion', ''))
            with open(path_pdf, "rb") as pdf_file:
                st.download_button(
                    label="📥 Descargar Resumen Socio PDF",
                    data=pdf_file,
                    file_name=f"Resumen_Socio_{cuit_socio}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"dl_pdf_socio_{cuit_socio}"
                )
        except Exception as pdf_err:
            st.caption(f"Error generando PDF del socio: {pdf_err}")

def render_validador_dashboard():
    st.header("✅ Validación de Clientes")
    
    # Manejar estado de descarga
    if 'archivo_exportado' in st.session_state:
        import os
        if os.path.exists(st.session_state['archivo_exportado']):
            if st.session_state.get('descarga_completada', False):
                st.info("ℹ️ El archivo ya fue descargado de forma exitosa. Se habilitará un nuevo botón de descarga la próxima vez que exportes nuevos clientes.")
                if st.button("Cerrar este mensaje", key="close_msg_download_done"):
                    del st.session_state['archivo_exportado']
                    st.session_state['descarga_completada'] = False
                    st.rerun()
            else:
                st.success("¡Exportación completada exitosamente! El archivo está listo para descargar.")
                with open(st.session_state['archivo_exportado'], "rb") as f:
                    def registrar_descarga():
                        st.session_state['descarga_completada'] = True
                    st.download_button(
                        label="⬇️ Descargar Clientes_web.dbi",
                        data=f,
                        file_name="Clientes_web.dbi",
                        mime="application/octet-stream",
                        type="primary",
                        on_click=registrar_descarga,
                        key="btn_download_dbi_ready"
                    )
                if st.button("Cerrar este mensaje", key="close_msg_download_pending"):
                    del st.session_state['archivo_exportado']
                    st.rerun()
            st.divider()
            
    if supabase is None:
        st.error("No hay conexión a la base de datos configurada.")
        return

    # Crear pestañas para organizar la UI
    tab_pendientes, tab_rechazados = st.tabs([
        "📋 Clientes Pendientes",
        "🛑 Clientes Rechazados"
    ])
    
    with tab_pendientes:
        render_clientes_pendientes()
        
    with tab_rechazados:
        render_clientes_rechazados()


def render_clientes_pendientes():
    st.write("A continuación se listan los clientes cargados por los vendedores que esperan validación o exportación.")
    
    try:
        # Traer clientes en estados activos ('Pendiente', 'Modificado', 'A Exportar')
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
            hide_index=True,
            key="tabla_pendientes"
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
                
                # Nuevas variables estratégicas de Nosis en un contenedor visualmente agradable
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
                try:
                    from modulos.reporte_pdf import generar_pdf_reporte_nosis
                    path_pdf = generar_pdf_reporte_nosis(payload, client_data.get('cuit', ''), dictamen, semaforos, nosis_data.get('explicacion', ''))
                    with open(path_pdf, "rb") as pdf_file:
                        st.download_button(
                            label="📥 Descargar Resumen PDF",
                            data=pdf_file,
                            file_name=f"Resumen_Riesgo_{client_data.get('cuit', '')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            type="secondary",
                            key=f"dl_pdf_pendientes_{client_data.get('cuit', '')}"
                        )
                except Exception as pdf_err:
                    st.caption(f"No se pudo generar el resumen PDF automáticamente: {pdf_err}")
                
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
                    *   **Compromiso Mensual:** Estimación de cuánto dinero debe pagar por mes para cubrir cuotas, préstamos y tarjetas.
                    """)
                
            st.divider()
            
            # Toggle para habilitar edición de campos manuales
            edit_mode = st.toggle("Habilitar modificación de datos manuales", value=False, key=f"toggle_edit_{client_data['id']}")
            
            # Formulario de lectura (Campos AFIP siempre bloqueados)
            col1, col2 = st.columns(2)
            col1.text_input("CUIT", value=client_data.get('cuit', ''), disabled=True, key=f"p_cuit_{client_data['id']}")
            col2.text_input("NOMBRE (Razón Social)", value=client_data.get('nombre', ''), disabled=True, key=f"p_nombre_{client_data['id']}")
            
            st.markdown("##### Información Impositiva")
            col_t1, col_t2 = st.columns(2)
            col_t1.text_input("Tipo Documento", value=client_data.get('tipo_doc', ''), disabled=True, key=f"p_tipodoc_{client_data['id']}")
            col_t2.text_input("Tipo Responsable", value=client_data.get('tipo_resp_desc', ''), disabled=True, key=f"p_tiporesp_{client_data['id']}")
            
            st.text_input("Actividad Principal", value=client_data.get('actividad', ''), disabled=True, key=f"p_actividad_{client_data['id']}")
            col_a1, col_a2, col_a3 = st.columns(3)
            col_a1.text_input("Cod. Actividad", value=client_data.get('cod_acti', ''), disabled=True, key=f"p_codacti_{client_data['id']}")
            col_a2.text_input("Antigüedad", value=client_data.get('antiguedad', ''), disabled=True, key=f"p_antiguedad_{client_data['id']}")
            col_a3.text_input("Mes Cierre", value=client_data.get('mes_cierre', ''), disabled=True, key=f"p_mescierre_{client_data['id']}")
            
            st.markdown("##### Datos Comerciales y Societarios")
            col_s1, col_s2, col_s3 = st.columns(3)
            
            def _limpiar_cuit_db(val):
                if val is None:
                    return ""
                val_str = str(val).strip()
                if val_str.lower() in ["", "nan", "none"]:
                    return ""
                if val_str.endswith(".0"):
                    val_str = val_str[:-2]
                return val_str
                
            val_socio1 = _limpiar_cuit_db(client_data.get('cuit_socio1', ''))
            val_socio2 = _limpiar_cuit_db(client_data.get('cuit_socio2', ''))
            
            client_id = str(client_data.get('id', 'default'))
            giro = col_s1.text_input("Giro Comercial", value=client_data.get('giro_comercial', ''), disabled=not edit_mode, key=f"giro_{client_id}")
            socio1 = col_s2.text_input("CUIT Socio 1", value=val_socio1, disabled=not edit_mode, key=f"socio1_{client_id}")
            socio2 = col_s3.text_input("CUIT Socio 2", value=val_socio2, disabled=not edit_mode, key=f"socio2_{client_id}")
            
            cuit_s1_digits = "".join(filter(str.isdigit, str(socio1)))
            cuit_s2_digits = "".join(filter(str.isdigit, str(socio2)))
            
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
                        if c1.button("🔍 Análisis Nosis", key=f"btn_socio1_analisis_new_{client_id}", use_container_width=True):
                            mostrar_modal_socio(cuit_s1_digits, "Socio 1")
                            
                        pdf_key_s1 = f"pdf_path_socio_{cuit_s1_digits}"
                        import os
                        if pdf_key_s1 in st.session_state and os.path.exists(st.session_state[pdf_key_s1]):
                            with open(st.session_state[pdf_key_s1], "rb") as f:
                                c2.download_button(
                                    label="📥 descarga de resumen Cuit socio",
                                    data=f,
                                    file_name=f"Resumen_Socio_{cuit_s1_digits}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_socio1_ready_new_{cuit_s1_digits}_{client_id}",
                                    use_container_width=True
                                )
                        else:
                            if c2.button("📥 descarga de resumen Cuit socio", key=f"dl_socio1_gen_new_{cuit_s1_digits}_{client_id}", use_container_width=True):
                                with st.spinner("Generando PDF..."):
                                    user_id = st.session_state.get('user_id', None)
                                    nosis_data = consultar_y_evaluar_nosis(cuit_s1_digits, user_id)
                                    if 'error' not in nosis_data:
                                        payload = nosis_data.get('payload_crudo', {})
                                        dictamen = nosis_data.get('dictamen', '')
                                        semaforos = nosis_data.get('semaforos', {})
                                        explicacion = nosis_data.get('explicacion', '')
                                        from modulos.reporte_pdf import generar_pdf_reporte_nosis
                                        path_pdf = generar_pdf_reporte_nosis(payload, cuit_s1_digits, dictamen, semaforos, explicacion)
                                        st.session_state[pdf_key_s1] = path_pdf
                                        st.rerun()
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
                        if c1_s2.button("🔍 Análisis Nosis", key=f"btn_socio2_analisis_new_{client_id}", use_container_width=True):
                            mostrar_modal_socio(cuit_s2_digits, "Socio 2")
                            
                        pdf_key_s2 = f"pdf_path_socio_{cuit_s2_digits}"
                        import os
                        if pdf_key_s2 in st.session_state and os.path.exists(st.session_state[pdf_key_s2]):
                            with open(st.session_state[pdf_key_s2], "rb") as f:
                                c2_s2.download_button(
                                    label="📥 descarga de resumen Cuit socio",
                                    data=f,
                                    file_name=f"Resumen_Socio_{cuit_s2_digits}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_socio2_ready_new_{cuit_s2_digits}_{client_id}",
                                    use_container_width=True
                                )
                        else:
                            if c2_s2.button("📥 descarga de resumen Cuit socio", key=f"dl_socio2_gen_new_{cuit_s2_digits}_{client_id}", use_container_width=True):
                                with st.spinner("Generando PDF..."):
                                    user_id = st.session_state.get('user_id', None)
                                    nosis_data = consultar_y_evaluar_nosis(cuit_s2_digits, user_id)
                                    if 'error' not in nosis_data:
                                        payload = nosis_data.get('payload_crudo', {})
                                        dictamen = nosis_data.get('dictamen', '')
                                        semaforos = nosis_data.get('semaforos', {})
                                        explicacion = nosis_data.get('explicacion', '')
                                        from modulos.reporte_pdf import generar_pdf_reporte_nosis
                                        path_pdf = generar_pdf_reporte_nosis(payload, cuit_s2_digits, dictamen, semaforos, explicacion)
                                        st.session_state[pdf_key_s2] = path_pdf
                                        st.rerun()
                                    else:
                                        st.error(nosis_data['error'])
            
            st.markdown("##### Domicilio Fiscal (AFIP)")
            st.text_input("Domicilio Fiscal", value=client_data.get('domicilio_f', ''), disabled=True, key=f"dom_f_{client_id}")
            col_f1, col_f2, col_f3 = st.columns(3)
            cp_f = col_f1.text_input("C.P. Fiscal", value=client_data.get('c_postal', ''), disabled=True, key=f"cp_f_{client_id}")
            loc_f = col_f2.text_input("Localidad Fiscal", value=client_data.get('localidad', ''), disabled=True, key=f"loc_f_{client_id}")
            prov_f = col_f3.text_input("Provincia Fiscal", value=client_data.get('provincia', ''), disabled=True, key=f"prov_f_{client_id}")

            st.markdown("##### Domicilio de Entrega")
            dom_e = st.text_input("Domicilio Entrega", value=client_data.get('domicilio_e', ''), disabled=not edit_mode, key=f"dom_e_{client_id}")
            col_e1, col_e2, col_e3 = st.columns(3)
            cp_e = col_e1.text_input("C.P. Entrega", value=client_data.get('cp_ent', ''), disabled=not edit_mode, key=f"cp_e_{client_id}")
            loc_e = col_e2.text_input("Localidad Entrega", value=client_data.get('local_ent', ''), disabled=not edit_mode, key=f"loc_e_{client_id}")
            prov_e = col_e3.text_input("Provincia Entrega", value=client_data.get('prov_ent', ''), disabled=not edit_mode, key=f"prov_e_{client_id}")
            
            st.markdown("##### Contacto")
            col_c1, col_c2 = st.columns(2)
            contacto = col_c1.text_input("Persona de Contacto", value=client_data.get('contacto', ''), disabled=not edit_mode, key=f"contacto_{client_id}")
            telefono = col_c2.text_input("Teléfono", value=client_data.get('telefono', ''), disabled=not edit_mode, key=f"telefono_{client_id}")
            
            st.divider()
            
            val_doc = client_data.get('documento', client_data.get('Documento', ''))
            if val_doc:
                st.markdown("#### Observaciones del Vendedor")
                st.text_area("Aclaraciones para Alta Temprana", value=str(val_doc), disabled=True, key=f"p_obs_{client_id}")
                st.divider()
            
            st.markdown("#### Acciones de Validación")
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
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
            
            if col_btn1.button("Guardar Cambios Manuales", use_container_width=True, key=f"btn_save_{client_id}"):
                datos_actualizados['estado'] = 'Modificado'
                supabase.table('clientes_pendientes').update(datos_actualizados).eq('id', str(client_data['id'])).execute()
                st.success("Datos guardados. Estado cambiado a Modificado.")
                st.rerun()
                
            if col_btn2.button("Marcar para Exportar (Aprobado)", type="primary", use_container_width=True, key=f"btn_approve_{client_id}"):
                datos_actualizados['estado'] = 'A Exportar'
                supabase.table('clientes_pendientes').update(datos_actualizados).eq('id', str(client_data['id'])).execute()
                st.success(f"Cliente {client_data.get('nombre', '')} marcado para exportar exitosamente.")
                st.rerun()

            if col_btn3.button("🛑 Rechazar Alta", type="secondary", use_container_width=True, key=f"btn_reject_{client_id}"):
                datos_actualizados['estado'] = 'Validado'  # Guardamos como 'Validado' por la restricción CHECK en Supabase, se mostrará como 'Rechazado' en la UI
                supabase.table('clientes_pendientes').update(datos_actualizados).eq('id', str(client_data['id'])).execute()
                st.warning(f"El alta del cliente {client_data.get('nombre', '')} ha sido rechazada.")
                st.rerun()
                
        else:
            st.info("Haz clic en una de las filas de arriba para analizar el cliente en detalle y proceder con la autorización.")
            
        st.divider()
        # Mantenemos el botón de exportación masiva pero solo para los "A Exportar"
        df_a_exportar = df[df['estado'] == 'A Exportar']
        
        if st.button("Exportar todos los A Exportar", key="btn_export_all"):
            if df_a_exportar.empty:
                st.warning("No hay clientes en estado 'A Exportar'.")
            else:
                secuencia_resp = supabase.table('secuencia_codigo').select('ultimo_valor').eq('id', 1).execute()
                ultimo_valor = 0 if not secuencia_resp.data else secuencia_resp.data[0]['ultimo_valor']
                numero_inicio = max(40000, int(ultimo_valor) + 1)
                
                # Pasamos solo los clientes filtrados al generador
                ruta_salida, nuevo_codigo_actual = generar_archivo_dbi(df_a_exportar, numero_inicio_codigo=numero_inicio)
                ultimo_assigned = nuevo_codigo_actual - 1
                
                for index, row in df_a_exportar.iterrows():
                    supabase.table('clientes_pendientes').update({'estado': 'Exportado'}).eq('id', row['id']).execute()
                    
                if secuencia_resp.data:
                    supabase.table('secuencia_codigo').update({'ultimo_valor': ultimo_assigned}).eq('id', 1).execute()
                else:
                    supabase.table('secuencia_codigo').insert({'id': 1, 'ultimo_valor': ultimo_assigned}).execute()
                    
                st.session_state['archivo_exportado'] = ruta_salida
                st.session_state['descarga_completada'] = False
                st.rerun()
            
    except Exception as e:
        st.error(f"Error al interactuar con la base de datos: {e}")


def render_clientes_rechazados():
    st.write("A continuación se listan los clientes cuyo alta ha sido rechazada. Puede consultar sus detalles o recuperarlos para la cola de evaluación.")
    
    try:
        # Traer clientes con estado 'Validado' (que representa 'Rechazado' en la UI)
        response = supabase.table('clientes_pendientes').select('*, usuarios(codigo_vendedor)').eq('estado', 'Validado').execute()
        
        if not response.data:
            st.info("No hay clientes rechazados en este momento.")
            return
            
        df = pd.DataFrame(response.data)
        
        # Mapear tipo responsable
        df['tipo_resp_desc'] = df['tipo_resp'].apply(lambda x: MAP_TIPO_RESP.get(str(x), str(x) if x else "N/A"))
        
        # Preparar tabla para visualización con estado display 'Rechazado'
        df['estado_display'] = 'Rechazado'
        display_df = df[['nombre', 'cuit', 'tipo_resp_desc', 'giro_comercial', 'contacto', 'estado_display']].copy()
        display_df.rename(columns={
            'nombre': 'Razón Social',
            'cuit': 'CUIT',
            'tipo_resp_desc': 'Tipo de Responsable',
            'giro_comercial': 'Giro Comercial',
            'contacto': 'Persona de Contacto',
            'estado_display': 'Estado'
        }, inplace=True)
        
        st.markdown("### Seleccione un cliente rechazado para ver sus detalles")
        # Mostrar tabla interactiva (selección simple)
        event = st.dataframe(
            display_df, 
            use_container_width=True, 
            selection_mode="single-row", 
            on_select="rerun",
            hide_index=True,
            key="tabla_rechazados"
        )
        
        st.divider()
        
        # Si hay una fila seleccionada, mostrar detalle en modo lectura
        if event and len(event.selection.rows) > 0:
            selected_index = event.selection.rows[0]
            client_data = df.iloc[selected_index]
            
            st.markdown(f"### 📋 Detalle del Cliente Rechazado: {client_data.get('nombre', '')}")
            
            # --- SECCIÓN NOSIS ---
            st.markdown("#### 🛡️ Análisis de Riesgo Crediticio (Nosis) - Histórico")
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
                elif dictamen == "REVISIÓN GERENCIAL":
                    st.warning(f"### ⚠️ DICTAMEN: {dictamen}")
                else:
                    st.success(f"### ✅ DICTAMEN: {dictamen}")
                
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
                col_n1.metric(f"{pinta_semaforo(semaforos.get('score'))} Score", payload.get('score_riesgo', 850), key=f"r_score_{client_data['id']}")
                col_n2.metric(f"{pinta_semaforo(semaforos.get('bcra'))} BCRA", payload.get('calificacion_bcra', 1), key=f"r_bcra_{client_data['id']}")
                col_n3.metric(f"{pinta_semaforo(semaforos.get('cheques'))} Cheques", payload.get('cheques_rechazados', 0), key=f"r_cheques_{client_data['id']}")
                col_n4.metric(f"{pinta_semaforo(semaforos.get('juicios'))} Juicios", payload.get('juicios_concursos', 0), key=f"r_juicios_{client_data['id']}")
                col_n5.metric(f"{pinta_semaforo(semaforos.get('afip'))} Deuda AFIP", payload.get('baches_afip_meses', 0), key=f"r_afip_{client_data['id']}")
                
                # Nuevas variables estratégicas de Nosis en un contenedor visualmente agradable
                st.markdown("##### 📊 Inteligencia Crediticia y Estabilidad (Nosis Ampliado)")
                
                col_e1, col_e2, col_e3, col_e4 = st.columns(4)
                col_e1.metric("Nivel Socioeconómico (NSE)", payload.get('nse', 'No registrado'), key=f"r_nse_{client_data['id']}")
                
                antiguedad = payload.get('antiguedad_laboral', 0)
                col_e2.metric("Antigüedad AFIP/Monotributo", f"{antiguedad} meses" if antiguedad else "No registrado", key=f"r_antig_{client_data['id']}")
                
                deuda = payload.get('deuda_total', 0)
                col_e3.metric("Deuda Bancaria Total", f"$ {deuda:,.2f}" if deuda else "$ 0.00", key=f"r_deuda_{client_data['id']}")
                
                comp = payload.get('compromiso_mensual', 0)
                col_e4.metric("Compromiso Mensual", f"$ {comp:,.2f}" if comp else "$ 0.00", key=f"r_comp_{client_data['id']}")
                
                col_p1, col_p2, col_p3, col_p4 = st.columns(4)
                col_p1.metric("Es Empleado Rel. Dep.", payload.get('es_empleado', 'No'), key=f"r_emp_{client_data['id']}")
                col_p2.metric("Bancos Acreedores", payload.get('cant_bancos', 0), key=f"r_banks_{client_data['id']}")
                col_p3.metric("Consultas CUIT (12m)", payload.get('consultas_12m', 0), key=f"r_queries_{client_data['id']}")
                
                emp_rz = payload.get('empleador', 'No registrado')
                col_p4.metric("Empleador Principal", emp_rz[:20] + "..." if len(emp_rz) > 20 else emp_rz, key=f"r_empl_{client_data['id']}")
                
                st.markdown("##### 🚨 Alertas Impositivas y Comercial")
                col_a1, col_a2, col_a3 = st.columns(3)
                
                def format_alerta(val):
                    if str(val).strip().lower() == "si":
                        return f"⚠️ {val}"
                    return f"✅ {val}"
                
                col_a1.metric("Facturas Apócrifas AFIP", format_alerta(payload.get('facturas_apocrifas', 'No')), key=f"r_apocrifas_{client_data['id']}")
                col_a2.metric("Deudas Fiscales AFIP", format_alerta(payload.get('deudas_fiscales', 'No')), key=f"r_dfiscales_{client_data['id']}")
                col_a3.metric("Es Moroso Comercial", format_alerta(payload.get('es_moroso', 'No')), key=f"r_moroso_{client_data['id']}")
                
                # Botón de Descarga del Reporte PDF
                st.markdown("##### 📄 Exportación de Reporte Oficial")
                try:
                    from modulos.reporte_pdf import generar_pdf_reporte_nosis
                    path_pdf = generar_pdf_reporte_nosis(payload, client_data.get('cuit', ''), dictamen, semaforos, nosis_data.get('explicacion', ''))
                    with open(path_pdf, "rb") as pdf_file:
                        st.download_button(
                            label="📥 Descargar Resumen PDF",
                            data=pdf_file,
                            file_name=f"Resumen_Riesgo_{client_data.get('cuit', '')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            type="secondary",
                            key=f"r_dl_pdf_{client_data.get('cuit', '')}"
                        )
                except Exception as pdf_err:
                    st.caption(f"No se pudo generar el resumen PDF automáticamente: {pdf_err}")
            
            st.divider()
            
            # Formulario en modo de solo lectura (todo deshabilitado)
            col1, col2 = st.columns(2)
            col1.text_input("CUIT", value=client_data.get('cuit', ''), disabled=True, key=f"r_cuit_{client_data['id']}")
            col2.text_input("NOMBRE (Razón Social)", value=client_data.get('nombre', ''), disabled=True, key=f"r_nombre_{client_data['id']}")
            
            st.markdown("##### Información Impositiva")
            col_t1, col_t2 = st.columns(2)
            col_t1.text_input("Tipo Documento", value=client_data.get('tipo_doc', ''), disabled=True, key=f"r_tipodoc_{client_data['id']}")
            col_t2.text_input("Tipo Responsable", value=client_data.get('tipo_resp_desc', ''), disabled=True, key=f"r_tiporesp_{client_data['id']}")
            
            st.text_input("Actividad Principal", value=client_data.get('actividad', ''), disabled=True, key=f"r_actividad_{client_data['id']}")
            col_a1, col_a2, col_a3 = st.columns(3)
            col_a1.text_input("Cod. Actividad", value=client_data.get('cod_acti', ''), disabled=True, key=f"r_codacti_{client_data['id']}")
            col_a2.text_input("Antigüedad", value=client_data.get('antiguedad', ''), disabled=True, key=f"r_antiguedad_{client_data['id']}")
            col_a3.text_input("Mes Cierre", value=client_data.get('mes_cierre', ''), disabled=True, key=f"r_mescierre_{client_data['id']}")
            
            st.markdown("##### Datos Comerciales y Societarios")
            col_s1, col_s2, col_s3 = st.columns(3)
            
            def _limpiar_cuit_db(val):
                if val is None:
                    return ""
                val_str = str(val).strip()
                if val_str.lower() in ["", "nan", "none"]:
                    return ""
                if val_str.endswith(".0"):
                    val_str = val_str[:-2]
                return val_str

            val_socio1 = _limpiar_cuit_db(client_data.get('cuit_socio1', ''))
            val_socio2 = _limpiar_cuit_db(client_data.get('cuit_socio2', ''))
            
            client_id = str(client_data.get('id', 'default'))
            col_s1.text_input("Giro Comercial", value=client_data.get('giro_comercial', ''), disabled=True, key=f"r_giro_{client_id}")
            col_s2.text_input("CUIT Socio 1", value=val_socio1, disabled=True, key=f"r_socio1_{client_id}")
            col_s3.text_input("CUIT Socio 2", value=val_socio2, disabled=True, key=f"r_socio2_{client_id}")
            
            cuit_s1_digits = "".join(filter(str.isdigit, str(val_socio1)))
            cuit_s2_digits = "".join(filter(str.isdigit, str(val_socio2)))
            
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
                        if c1.button("🔍 Análisis Nosis", key=f"r_btn_socio1_analisis_new_{client_id}", use_container_width=True):
                            mostrar_modal_socio(cuit_s1_digits, "Socio 1")
                            
                        pdf_key_s1 = f"pdf_path_socio_{cuit_s1_digits}"
                        import os
                        if pdf_key_s1 in st.session_state and os.path.exists(st.session_state[pdf_key_s1]):
                            with open(st.session_state[pdf_key_s1], "rb") as f:
                                c2.download_button(
                                    label="📥 descarga de resumen Cuit socio",
                                    data=f,
                                    file_name=f"Resumen_Socio_{cuit_s1_digits}.pdf",
                                    mime="application/pdf",
                                    key=f"r_dl_socio1_ready_new_{cuit_s1_digits}_{client_id}",
                                    use_container_width=True
                                )
                        else:
                            if c2.button("📥 descarga de resumen Cuit socio", key=f"r_dl_socio1_gen_new_{cuit_s1_digits}_{client_id}", use_container_width=True):
                                with st.spinner("Generando PDF..."):
                                    user_id = st.session_state.get('user_id', None)
                                    nosis_data = consultar_y_evaluar_nosis(cuit_s1_digits, user_id)
                                    if 'error' not in nosis_data:
                                        payload = nosis_data.get('payload_crudo', {})
                                        dictamen = nosis_data.get('dictamen', '')
                                        semaforos = nosis_data.get('semaforos', {})
                                        explicacion = nosis_data.get('explicacion', '')
                                        from modulos.reporte_pdf import generar_pdf_reporte_nosis
                                        path_pdf = generar_pdf_reporte_nosis(payload, cuit_s1_digits, dictamen, semaforos, explicacion)
                                        st.session_state[pdf_key_s1] = path_pdf
                                        st.rerun()
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
                        if c1_s2.button("🔍 Análisis Nosis", key=f"r_btn_socio2_analisis_new_{client_id}", use_container_width=True):
                            mostrar_modal_socio(cuit_s2_digits, "Socio 2")
                            
                        pdf_key_s2 = f"pdf_path_socio_{cuit_s2_digits}"
                        import os
                        if pdf_key_s2 in st.session_state and os.path.exists(st.session_state[pdf_key_s2]):
                            with open(st.session_state[pdf_key_s2], "rb") as f:
                                c2_s2.download_button(
                                    label="📥 descarga de resumen Cuit socio",
                                    data=f,
                                    file_name=f"Resumen_Socio_{cuit_s2_digits}.pdf",
                                    mime="application/pdf",
                                    key=f"r_dl_socio2_ready_new_{cuit_s2_digits}_{client_id}",
                                    use_container_width=True
                                )
                        else:
                            if c2_s2.button("📥 descarga de resumen Cuit socio", key=f"r_dl_socio2_gen_new_{cuit_s2_digits}_{client_id}", use_container_width=True):
                                with st.spinner("Generando PDF..."):
                                    user_id = st.session_state.get('user_id', None)
                                    nosis_data = consultar_y_evaluar_nosis(cuit_s2_digits, user_id)
                                    if 'error' not in nosis_data:
                                        payload = nosis_data.get('payload_crudo', {})
                                        dictamen = nosis_data.get('dictamen', '')
                                        semaforos = nosis_data.get('semaforos', {})
                                        explicacion = nosis_data.get('explicacion', '')
                                        from modulos.reporte_pdf import generar_pdf_reporte_nosis
                                        path_pdf = generar_pdf_reporte_nosis(payload, cuit_s2_digits, dictamen, semaforos, explicacion)
                                        st.session_state[pdf_key_s2] = path_pdf
                                        st.rerun()
                                    else:
                                        st.error(nosis_data['error'])
            
            st.markdown("##### Domicilio Fiscal (AFIP)")
            st.text_input("Domicilio Fiscal", value=client_data.get('domicilio_f', ''), disabled=True, key=f"r_dom_f_val_{client_id}")
            col_f1, col_f2, col_f3 = st.columns(3)
            col_f1.text_input("C.P. Fiscal", value=client_data.get('c_postal', ''), disabled=True, key=f"r_cp_f_val_{client_id}")
            col_f2.text_input("Localidad Fiscal", value=client_data.get('localidad', ''), disabled=True, key=f"r_loc_f_val_{client_id}")
            col_f3.text_input("Provincia Fiscal", value=client_data.get('provincia', ''), disabled=True, key=f"r_prov_f_val_{client_id}")

            st.markdown("##### Domicilio de Entrega")
            st.text_input("Domicilio Entrega", value=client_data.get('domicilio_e', ''), disabled=True, key=f"r_dom_e_val_{client_id}")
            col_e1, col_e2, col_e3 = st.columns(3)
            col_e1.text_input("C.P. Entrega", value=client_data.get('cp_ent', ''), disabled=True, key=f"r_cp_e_val_{client_id}")
            col_e2.text_input("Localidad Entrega", value=client_data.get('local_ent', ''), disabled=True, key=f"r_loc_e_val_{client_id}")
            col_e3.text_input("Provincia Entrega", value=client_data.get('prov_ent', ''), disabled=True, key=f"r_prov_e_val_{client_id}")
            
            st.markdown("##### Contacto")
            col_c1, col_c2 = st.columns(2)
            col_c1.text_input("Persona de Contacto", value=client_data.get('contacto', ''), disabled=True, key=f"r_contacto_val_{client_id}")
            col_c2.text_input("Teléfono", value=client_data.get('telefono', ''), disabled=True, key=f"r_telefono_val_{client_id}")
            
            st.divider()
            
            val_doc = client_data.get('documento', client_data.get('Documento', ''))
            if val_doc:
                st.markdown("#### Observaciones del Vendedor")
                st.text_area("Aclaraciones para Alta Temprana", value=str(val_doc), disabled=True, key=f"r_p_obs_val_{client_id}")
                st.divider()
            
            st.markdown("#### Acciones para Clientes Rechazados")
            if st.button("🔄 Recuperar y volver a evaluar", type="primary", use_container_width=True, key=f"btn_recover_{client_id}"):
                supabase.table('clientes_pendientes').update({'estado': 'Pendiente'}).eq('id', str(client_data['id'])).execute()
                st.success(f"El cliente {client_data.get('nombre', '')} ha sido recuperado y devuelto a la lista de pendientes.")
                st.rerun()
                
        else:
            st.info("Haz clic en una de las filas de arriba para inspeccionar los detalles de un cliente rechazado.")
            
    except Exception as e:
        st.error(f"Error al interactuar con la base de datos: {e}")
