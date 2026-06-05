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
        
        # --- SECCIÓN DE ACCIONES ---
        if 'usuario_action_mode' not in st.session_state:
            st.session_state['usuario_action_mode'] = 'Alta'
            
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("➕ Alta de Usuario", use_container_width=True, type="primary" if st.session_state['usuario_action_mode'] == 'Alta' else "secondary"):
                st.session_state['usuario_action_mode'] = 'Alta'
                st.rerun()
        with col_btn2:
            if st.button("✏️ Modificar Usuario", use_container_width=True, type="primary" if st.session_state['usuario_action_mode'] == 'Modificar' else "secondary"):
                st.session_state['usuario_action_mode'] = 'Modificar'
                st.rerun()
                
        st.write("")
        
        if st.session_state['usuario_action_mode'] == 'Alta':
            with st.form("form_nuevo_usuario"):
                st.markdown("### ➕ Registrar Nuevo Usuario")
                st.write("Completa los datos para crear un nuevo acceso.")
                
                col_n1, col_n2 = st.columns(2)
                nuevo_email = col_n1.text_input("Correo Electrónico (Obligatorio)")
                nuevo_usuario = col_n2.text_input("Nombre de Usuario")
                
                col_n3, col_n4 = st.columns(2)
                nuevo_password = col_n3.text_input("Contraseña", type="password")
                nuevo_role = col_n4.selectbox("Rol", ["vendedor", "admin"])
                
                st.markdown("**Permisos Iniciales**")
                col_p1, col_p2 = st.columns(2)
                n_p_alta = col_p1.checkbox("Alta de Clientes (Vendedor)", value=True)
                n_p_valid = col_p1.checkbox("Validar Clientes", value=False)
                n_p_exp = col_p2.checkbox("Ver Exportados", value=False)
                n_p_usr = col_p2.checkbox("Administrar Permisos", value=False)
                
                n_cod_vendedor = st.number_input("Código de Vendedor (Presea) para este usuario", value=0)
                
                submit_nuevo = st.form_submit_button("Crear Usuario", type="primary", use_container_width=True)
                
                if submit_nuevo:
                    if not nuevo_email or not nuevo_password:
                        st.error("El email y la contraseña son obligatorios.")
                    else:
                        insert_data = {
                            "email": nuevo_email,
                            "usuario": nuevo_usuario,
                            "password": nuevo_password,
                            "role": nuevo_role,
                            "permiso_alta": n_p_alta,
                            "permiso_validacion": n_p_valid,
                            "permiso_exportados": n_p_exp,
                            "permiso_usuarios": n_p_usr,
                            "codigo_vendedor": n_cod_vendedor
                        }
                        try:
                            supabase.table('usuarios').insert(insert_data).execute()
                            st.success("¡Usuario creado exitosamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al crear el usuario. Es posible que el email ya exista. Detalle: {e}")
        
        else:
            st.markdown("### ✏️ Modificar Usuario Existente")
            user_list = ["-- Selecciona un usuario --"] + df['email'].tolist()
            selected_email = st.selectbox("Selecciona un usuario para modificar", user_list, index=0)
            
            if selected_email and selected_email != "-- Selecciona un usuario --":
                user_data = df[df['email'] == selected_email].iloc[0]
                
                with st.form("form_modificar_usuario"):
                    st.write(f"Editando perfil de: **{user_data['email']}**")
                    
                    col_m1, col_m2 = st.columns(2)
                    m_email = col_m1.text_input("Correo Electrónico (Obligatorio)", value=user_data['email'])
                    m_usuario = col_m2.text_input("Nombre de Usuario", value=user_data.get('usuario', '') or '')
                    
                    col_m3, col_m4 = st.columns(2)
                    m_password = col_m3.text_input("Contraseña", type="password", value=user_data.get('password', ''))
                    
                    role_options = ["vendedor", "admin"]
                    try:
                        role_index = role_options.index(user_data.get('role', 'vendedor'))
                    except ValueError:
                        role_index = 0
                    m_role = col_m4.selectbox("Rol", role_options, index=role_index)
                    
                    st.markdown("**Permisos**")
                    col_mp1, col_mp2 = st.columns(2)
                    p_alta = col_mp1.checkbox("Alta de Clientes (Vendedor)", value=bool(user_data.get('permiso_alta', False)))
                    p_valid = col_mp1.checkbox("Validar Clientes", value=bool(user_data.get('permiso_validacion', False)))
                    p_exp = col_mp2.checkbox("Ver Exportados", value=bool(user_data.get('permiso_exportados', False)))
                    p_usr = col_mp2.checkbox("Administrar Permisos", value=bool(user_data.get('permiso_usuarios', False)))
                    
                    cod_vendedor = st.number_input("Código de Vendedor (Presea)", value=int(user_data.get('codigo_vendedor', 0) or 0))
                    
                    submit_modificar = st.form_submit_button("Guardar Cambios", type="primary", use_container_width=True)
                    
                    if submit_modificar:
                        if not m_email or not m_password:
                            st.error("El email y la contraseña son obligatorios.")
                        else:
                            update_data = {
                                'email': m_email,
                                'usuario': m_usuario,
                                'password': m_password,
                                'role': m_role,
                                'permiso_alta': p_alta,
                                'permiso_validacion': p_valid,
                                'permiso_exportados': p_exp,
                                'permiso_usuarios': p_usr,
                                'codigo_vendedor': cod_vendedor
                            }
                            try:
                                supabase.table('usuarios').update(update_data).eq('id', user_data['id']).execute()
                                st.success("Datos del usuario y permisos actualizados correctamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar el usuario. Detalle: {e}")
                    
    except Exception as e:
        # Esto atrapará errores si las columnas nuevas no han sido creadas aún
        st.error(f"Error al cargar usuarios. Asegúrate de haber corrido los comandos SQL en Supabase para agregar las nuevas columnas. Detalles: {e}")
