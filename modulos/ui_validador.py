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
        # Hacemos un JOIN con la tabla usuarios para traernos el codigo_vendedor
        response = supabase.table('clientes_pendientes').select('*, usuarios(codigo_vendedor)').eq('estado', 'Pendiente').execute()
        
        if not response.data:
            st.info("No hay clientes pendientes de validación.")
            return
            
        df = pd.DataFrame(response.data)
        
        # Extraer el codigo_vendedor del JSON anidado
        if 'usuarios' in df.columns:
            df['codigo_vendedor'] = df['usuarios'].apply(lambda x: x.get('codigo_vendedor', 0) if isinstance(x, dict) else 0)
        else:
            df['codigo_vendedor'] = 0
            
        # Mapeo para visualización (se muestran solo algunas columnas para no saturar)
        display_df = df[['cuit', 'nombre', 'localidad', 'estado']].copy()
        display_df.rename(columns={'cuit': 'CUIT', 'nombre': 'Nombre', 'localidad': 'Localidad', 'estado': 'Estado'}, inplace=True)
        
        st.dataframe(display_df, use_container_width=True)
        
        st.divider()
        
        if st.button("Exportar Pendientes a Presea (.DBI)", type="primary"):
            # Consultar la secuencia actual
            secuencia_resp = supabase.table('secuencia_codigo').select('ultimo_valor').eq('id', 1).execute()
            if not secuencia_resp.data:
                ultimo_valor = 0
            else:
                ultimo_valor = secuencia_resp.data[0]['ultimo_valor']
                
            numero_inicio = int(ultimo_valor) + 1
            
            # Generar DBI
            ruta_salida, nuevo_codigo_actual = generar_archivo_dbi(df, numero_inicio_codigo=numero_inicio)
            
            # El generador suma 1 al final del loop, por ende el último asignado es nuevo_codigo_actual - 1
            ultimo_asignado = nuevo_codigo_actual - 1
            
            # Actualizar estado en Supabase
            for index, row in df.iterrows():
                supabase.table('clientes_pendientes').update({'estado': 'Exportado'}).eq('id', row['id']).execute()
                
            # Actualizar la secuencia con el nuevo tope
            if secuencia_resp.data:
                supabase.table('secuencia_codigo').update({'ultimo_valor': ultimo_asignado}).eq('id', 1).execute()
            else:
                supabase.table('secuencia_codigo').insert({'id': 1, 'ultimo_valor': ultimo_asignado}).execute()
                
            st.success(f"¡Archivo generado con éxito! Clientes exportados correctamente.")
            st.info(f"Se generaron códigos correlativos desde el {numero_inicio} hasta el {ultimo_asignado}.")
            st.rerun()
            
    except Exception as e:
        st.error(f"Error al interactuar con la base de datos: {e}")
