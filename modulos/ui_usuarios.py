import streamlit as st
import pandas as pd
from modulos.db import supabase

def render_usuarios_dashboard():
    st.header("👥 Gestión de Usuarios y Permisos")
    st.write("Administra los accesos y permisos de cada usuario de la aplicación.")
    
    if supabase is None:
        st.error("No hay conexión a la base de datos configurada.")
        return

    try:
        # Cargar usuarios
        response = supabase.table('usuarios').select('*').execute()
        
        if not response.data:
            st.warning("No se encontraron usuarios en la base de datos.")
            return
            
        df = pd.DataFrame(response.data)
        
        # Ocultar campos sensibles (password) en la grilla visual
        display_df = df[['email', 'role', 'usuario', 'codigo_vendedor', 'permiso_alta', 'permiso_validacion', 'permiso_exportados', 'permiso_usuarios']].copy()
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.divider()
        st.markdown("### Modificar Permisos")
        
        # Seleccionar usuario a editar
        user_list = df['email'].tolist()
        selected_email = st.selectbox("Seleccione un usuario para modificar", user_list)
        
        if selected_email:
            user_data = df[df['email'] == selected_email].iloc[0]
            
            with st.form("form_permisos"):
                st.markdown(f"**Usuario:** {user_data['email']} ({user_data['role']})")
                
                col1, col2 = st.columns(2)
                p_alta = col1.checkbox("Alta de Clientes", value=bool(user_data.get('permiso_alta', False)))
                p_valid = col1.checkbox("Validar Clientes", value=bool(user_data.get('permiso_validacion', False)))
                
                p_exp = col2.checkbox("Ver Exportados", value=bool(user_data.get('permiso_exportados', False)))
                p_usr = col2.checkbox("Administrar Permisos", value=bool(user_data.get('permiso_usuarios', False)))
                
                cod_vendedor = st.number_input("Código de Vendedor (Presea)", value=int(user_data.get('codigo_vendedor', 0) or 0))
                
                submit = st.form_submit_button("Guardar Cambios", type="primary")
                
                if submit:
                    update_data = {
                        'permiso_alta': p_alta,
                        'permiso_validacion': p_valid,
                        'permiso_exportados': p_exp,
                        'permiso_usuarios': p_usr,
                        'codigo_vendedor': cod_vendedor
                    }
                    supabase.table('usuarios').update(update_data).eq('id', user_data['id']).execute()
                    st.success("Permisos actualizados correctamente.")
                    st.rerun()
                    
    except Exception as e:
        # Esto atrapará errores si las columnas nuevas no han sido creadas aún
        st.error(f"Error al cargar usuarios. Asegúrate de haber corrido los comandos SQL en Supabase para agregar las nuevas columnas. Detalles: {e}")
