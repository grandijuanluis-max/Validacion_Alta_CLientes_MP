import streamlit as st
import pandas as pd
from modulos.generador_dbi import generar_archivo_dbi
from modulos.db import supabase
MAP_TIPO_RESP = {
    "1.0": "Resp. Inscripto",
    "3.0": "Monotributista",
    "4.0": "IVA Exento",
    "5.0": "Consumidor Final"
}

def render_validador_dashboard():
    st.header("✅ Validación de Clientes")
    
    st.write("A continuación se listan los clientes cargados por los vendedores que esperan validación.")
    
    if supabase is None:
        st.error("No hay conexión a la base de datos configurada.")
        return

    try:
        # Traer todos los clientes (podría ser filtrado por Pendiente, pero el cliente quiere ver la tabla para analizar)
        response = supabase.table('clientes_pendientes').select('*, usuarios(codigo_vendedor)').eq('estado', 'Pendiente').execute()
        
        if not response.data:
            st.info("No hay clientes pendientes de validación.")
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
            
            # Formulario de lectura
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
            col_s1.text_input("Giro Comercial", value=client_data.get('giro_comercial', ''), disabled=True)
            col_s2.text_input("CUIT Socio 1", value=client_data.get('cuit_socio1', ''), disabled=True)
            col_s3.text_input("CUIT Socio 2", value=client_data.get('cuit_socio2', ''), disabled=True)
            
            st.markdown("##### Domicilio Fiscal")
            st.text_input("Domicilio Fiscal", value=client_data.get('domicilio_f', ''), disabled=True)
            col_f1, col_f2, col_f3 = st.columns(3)
            col_f1.text_input("C.P. Fiscal", value=client_data.get('c_postal', ''), disabled=True)
            col_f2.text_input("Localidad Fiscal", value=client_data.get('localidad', ''), disabled=True)
            col_f3.text_input("Provincia Fiscal", value=client_data.get('provincia', ''), disabled=True)

            st.markdown("##### Domicilio de Entrega")
            st.text_input("Domicilio Entrega", value=client_data.get('domicilio_e', ''), disabled=True)
            col_e1, col_e2, col_e3 = st.columns(3)
            col_e1.text_input("C.P. Entrega", value=client_data.get('cp_ent', ''), disabled=True)
            col_e2.text_input("Localidad Entrega", value=client_data.get('local_ent', ''), disabled=True)
            col_e3.text_input("Provincia Entrega", value=client_data.get('prov_ent', ''), disabled=True)
            
            st.markdown("##### Contacto")
            col_c1, col_c2 = st.columns(2)
            col_c1.text_input("Persona de Contacto", value=client_data.get('contacto', ''), disabled=True)
            col_c2.text_input("Teléfono", value=client_data.get('telefono', ''), disabled=True)
            
            st.divider()
            st.markdown("#### Ingreso de Datos del Validador")
            
            # Traer el valor que ya tenga si existe (probando ambas capitalizaciones comunes)
            val_doc = client_data.get('documento', client_data.get('Documento', ''))
            dato_adicional = st.text_input("Documento (Dato Adicional)", value=str(val_doc) if val_doc else "")
            
            col_btn1, col_btn2 = st.columns(2)
            if col_btn1.button("Guardar Documento", use_container_width=True):
                # Convertimos a minusculas el nombre de la columna para evitar el mismo error de cache de antes
                supabase.table('clientes_pendientes').update({'documento': dato_adicional}).eq('id', int(client_data['id'])).execute()
                st.success(f"El campo Documento ha sido guardado para {client_data.get('nombre', '')}.")
                
            if col_btn2.button("Aprobar Cliente (Marcar Exportado)", type="primary", use_container_width=True):
                # Guardamos el estado y el documento al mismo tiempo
                supabase.table('clientes_pendientes').update({
                    'estado': 'Exportado',
                    'documento': dato_adicional
                }).eq('id', int(client_data['id'])).execute()
                st.success(f"Cliente {client_data.get('nombre', '')} aprobado exitosamente.")
                st.rerun()
                
        else:
            st.info("Haz clic en una de las filas de arriba para analizar el cliente en detalle.")
            
        st.divider()
        # Mantenemos el botón de exportación masiva
        if st.button("Exportar TODOS los Pendientes a Presea (.DBI)"):
            secuencia_resp = supabase.table('secuencia_codigo').select('ultimo_valor').eq('id', 1).execute()
            ultimo_valor = 0 if not secuencia_resp.data else secuencia_resp.data[0]['ultimo_valor']
            numero_inicio = int(ultimo_valor) + 1
            
            ruta_salida, nuevo_codigo_actual = generar_archivo_dbi(df, numero_inicio_codigo=numero_inicio)
            ultimo_asignado = nuevo_codigo_actual - 1
            
            for index, row in df.iterrows():
                supabase.table('clientes_pendientes').update({'estado': 'Exportado'}).eq('id', row['id']).execute()
                
            if secuencia_resp.data:
                supabase.table('secuencia_codigo').update({'ultimo_valor': ultimo_asignado}).eq('id', 1).execute()
            else:
                supabase.table('secuencia_codigo').insert({'id': 1, 'ultimo_valor': ultimo_asignado}).execute()
                
            st.success(f"¡Archivo generado con éxito! Clientes exportados correctamente.")
            st.info(f"Se generaron códigos correlativos desde el {numero_inicio} hasta el {ultimo_asignado}.")
            st.rerun()
            
    except Exception as e:
        st.error(f"Error al interactuar con la base de datos: {e}")
