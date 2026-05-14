import streamlit as st
import pandas as pd
from modulos.generador_dbi import generar_archivo_dbi

def render_validador_dashboard():
    st.header("✅ Validación de Clientes")
    
    st.write("A continuación se listan los clientes cargados por los vendedores que esperan validación.")
    
    # TODO: Cargar esto desde Supabase
    data = {
        "CUIT": ["30-12345678-9", "20-87654321-1"],
        "Nombre": ["Empresa Falsa SRL", "Juan Perez"],
        "Localidad": ["Rosario", "Santa Fe"],
        "Estado": ["Pendiente", "Pendiente"]
    }
    
    df = pd.DataFrame(data)
    
    st.dataframe(df, use_container_width=True)
    
    st.divider()
    
    if st.button("Exportar Pendientes a Presea (.DBI)", type="primary"):
        generar_archivo_dbi(df)
        st.success("¡Archivo generado con éxito! El autómata lo procesará en breve.")
