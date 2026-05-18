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
            
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Error al cargar clientes exportados: {e}")
