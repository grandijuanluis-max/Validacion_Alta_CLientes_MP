import streamlit as st
import pandas as pd
from modulos.db import supabase
from modulos.ui_validador import MAP_TIPO_RESP

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
            # Usar filtered_df en lugar de df para que el índice coincida con la selección
            client_data = filtered_df.iloc[selected_index]
            
            # Obtener el registro completo original desde el dataframe sin filtrar columnas
            cuit_seleccionado = client_data.get('CUIT', '')
            original_client_data = df[df['cuit'] == cuit_seleccionado].iloc[0]
            
            st.markdown(f"### 📋 Detalle Histórico: {original_client_data.get('nombre', '')}")
            
            # --- SECCIÓN NOSIS (Histórico) ---
            st.markdown("#### 🛡️ Análisis de Riesgo Crediticio (Histórico Nosis)")
            
            # Buscar en log de auditoría el último análisis de este CUIT
            log_resp = supabase.table('log_auditoria_riesgo').select('*').eq('cuit_consultado', cuit_seleccionado).order('fecha_hora', desc=True).limit(1).execute()
            
            if log_resp.data:
                log_data = log_resp.data[0]
                dictamen = log_data.get('dictamen_motor', '')
                payload = log_data.get('payload_crudo', {})
                fecha_log = log_data.get('fecha_hora', '').split('T')[0]
                
                st.caption(f"Evaluado el: {fecha_log} (Datos recuperados de Auditoría)")
                
                if dictamen == "RECHAZO AUTOMÁTICO":
                    st.error(f"### 🛑 DICTAMEN HISTÓRICO: {dictamen}")
                elif dictamen == "REVISIÓN GERENCIAL":
                    st.warning(f"### ⚠️ DICTAMEN HISTÓRICO: {dictamen}")
                else:
                    st.success(f"### ✅ DICTAMEN HISTÓRICO: {dictamen}")
                
                # Reconstruir semáforos (simplificado solo visual)
                def pinta_semaforo_val(val, variable):
                    if variable == 'score':
                        if val > 700: return "🟢"
                        elif 450 <= val <= 699: return "🟡"
                        return "🔴"
                    elif variable == 'bcra':
                        if val == 1: return "🟢"
                        elif val == 2: return "🟡"
                        return "🔴"
                    elif variable == 'cheques':
                        if val == 0: return "🟢"
                        elif 1 <= val <= 3: return "🟡"
                        return "🔴"
                    elif variable == 'juicios':
                        if val == 0: return "🟢"
                        return "🔴"
                    elif variable == 'afip':
                        if val == 0: return "🟢"
                        elif val < 3: return "🟡"
                        return "🔴"
                    return "⚪"
                
                s_score = payload.get('score_riesgo', 0)
                s_bcra = payload.get('calificacion_bcra', 1)
                s_cheques = payload.get('cheques_rechazados', 0)
                s_juicios = payload.get('juicios_concursos', 0)
                s_afip = payload.get('baches_afip_meses', 0)
                
                col_n1, col_n2, col_n3, col_n4, col_n5 = st.columns(5)
                col_n1.metric(f"{pinta_semaforo_val(s_score, 'score')} Score", s_score)
                col_n2.metric(f"{pinta_semaforo_val(s_bcra, 'bcra')} BCRA", s_bcra)
                col_n3.metric(f"{pinta_semaforo_val(s_cheques, 'cheques')} Cheques", s_cheques)
                col_n4.metric(f"{pinta_semaforo_val(s_juicios, 'juicios')} Juicios", s_juicios)
                col_n5.metric(f"{pinta_semaforo_val(s_afip, 'afip')} Deuda AFIP", s_afip)
                
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
            else:
                st.info("No se encontró registro histórico de Nosis para este cliente.")
                
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
            col_s1.text_input("Giro Comercial", value=original_client_data.get('giro_comercial', ''), disabled=True)
            col_s2.text_input("CUIT Socio 1", value=original_client_data.get('cuit_socio1', ''), disabled=True)
            col_s3.text_input("CUIT Socio 2", value=original_client_data.get('cuit_socio2', ''), disabled=True)
            
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
        else:
            st.info("👆 Selecciona un cliente de la tabla para ver todos los detalles históricos de su exportación.")
            
    except Exception as e:
        st.error(f"Error al cargar clientes exportados: {e}")
