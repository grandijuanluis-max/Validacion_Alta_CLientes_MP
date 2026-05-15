import streamlit as st
import pandas as pd
from modulos.generador_dbi import generar_archivo_dbi
from modulos.db import supabase

def render_validador_dashboard():
    st.header("✅ Validación de Clientes")
    
    st.write("A continuación se listan los clientes cargados por los vendedores que esperan validación.")
    
    if supabase is None:
        st.error("No hay conexión a la base de datos configurada.")
        return

    try:
        response = supabase.table('clientes_pendientes').select('*').eq('estado', 'Pendiente').execute()
        
        if not response.data:
            st.info("No hay clientes pendientes de validación.")
            return
            
        df = pd.DataFrame(response.data)
        
        # Mapeo para visualización (se muestran solo algunas columnas para no saturar)
        display_df = df[['cuit', 'nombre', 'localidad', 'estado']].copy()
        display_df.rename(columns={'cuit': 'CUIT', 'nombre': 'Nombre', 'localidad': 'Localidad', 'estado': 'Estado'}, inplace=True)
        
        st.dataframe(display_df, use_container_width=True)
        
        st.divider()
        
        if st.button("Exportar Pendientes a Presea (.DBI)", type="primary"):
            # Generar DBI (se pasa el df completo porque el generador_dbi necesita todos los datos)
            generar_archivo_dbi(df)
            
            # Actualizar estado en Supabase
            for index, row in df.iterrows():
                supabase.table('clientes_pendientes').update({'estado': 'Exportado'}).eq('id', row['id']).execute()
                
            st.success("¡Archivo generado con éxito y clientes marcados como Exportados! El autómata lo procesará en breve.")
            st.rerun()
            
    except Exception as e:
        st.error(f"Error al interactuar con la base de datos: {e}")
