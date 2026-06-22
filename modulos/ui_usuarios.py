import streamlit as st
import pandas as pd
from modulos.db import supabase

def render_usuarios_dashboard():
    st.header("👥 Gestión de Usuarios y Permisos")
    st.write("Administra los accesos y permisos de cada usuario de la aplicación.")
    
    if supabase is None:
        st.error("No hay conexión a la base de datos configurada.")
        return

    # Mostrar mensajes de éxito persistentes entre recargas de Streamlit
    if 'usuario_success_msg' in st.session_state and st.session_state['usuario_success_msg']:
        st.success(st.session_state['usuario_success_msg'])
        del st.session_state['usuario_success_msg']

    # --- SECCIÓN DE ACCIONES ---
    if 'usuario_action_mode' not in st.session_state:
        st.session_state['usuario_action_mode'] = None
        
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Alta de Usuario", use_container_width=True, type="primary" if st.session_state['usuario_action_mode'] == 'Alta' else "secondary"):
            if st.session_state['usuario_action_mode'] == 'Alta':
                st.session_state['usuario_action_mode'] = None
            else:
                st.session_state['usuario_action_mode'] = 'Alta'
            if "modificar_usuario_select" in st.session_state:
                del st.session_state["modificar_usuario_select"]
            st.rerun()
            
    with col_btn2:
        if st.button("✏️ Modificar Usuario", use_container_width=True, type="primary" if st.session_state['usuario_action_mode'] == 'Modificar' else "secondary"):
            if st.session_state['usuario_action_mode'] == 'Modificar':
                st.session_state['usuario_action_mode'] = None
            else:
                st.session_state['usuario_action_mode'] = 'Modificar'
            if "modificar_usuario_select" in st.session_state:
                del st.session_state["modificar_usuario_select"]
            st.rerun()
            
    st.write("")
    
    if st.session_state['usuario_action_mode'] is None:
        # No se muestra ningún formulario ni datos si no hay un modo de acción seleccionado
        return
        
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
            n_p_sincro = col_p1.checkbox("Sincronización FTP", value=False)
            n_p_av = col_p2.checkbox("Análisis de Gestión", value=False)
            
            n_cod_vendedor = st.number_input("Código de Vendedor (Presea) para este usuario", value=0)
            
            col_sub1, col_sub2 = st.columns(2)
            with col_sub1:
                submit_nuevo = st.form_submit_button("Crear Usuario", type="primary", use_container_width=True)
            with col_sub2:
                cancelar_nuevo = st.form_submit_button("Cancelar", use_container_width=True)
                
            if cancelar_nuevo:
                st.session_state['usuario_action_mode'] = None
                st.rerun()
                
            if submit_nuevo:
                if not nuevo_email or not nuevo_password:
                    st.error("El email y la contraseña son obligatorios.")
                elif nuevo_email.strip().lower() == 'grandijuanluis@gmail.com' or (nuevo_usuario and nuevo_usuario.strip().lower() == 'juanluis'):
                    st.error("No se puede registrar un usuario con el correo o nombre de usuario de JuanLuis.")
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
                        "permisos_sincro": n_p_sincro,
                        "permisos_av": n_p_av,
                        "codigo_vendedor": n_cod_vendedor
                    }
                    try:
                        supabase.table('usuarios').insert(insert_data).execute()
                        st.session_state['usuario_success_msg'] = "¡Usuario creado exitosamente!"
                        st.session_state['usuario_action_mode'] = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear el usuario. Es posible que el email ya exista. Detalle: {e}")
                        
    elif st.session_state['usuario_action_mode'] == 'Modificar':
        try:
            # Cargar usuarios
            response = supabase.table('usuarios').select('*').execute()
            
            if not response.data:
                st.warning("No se encontraron usuarios en la base de datos.")
                return
                
            df = pd.DataFrame(response.data)
            if 'permisos_sincro' in df.columns:
                df['permisos_sincro'] = df['permisos_sincro'].apply(
                    lambda x: (x.strip().upper() == "TRUE") if isinstance(x, str) else bool(x)
                )
            if 'permisos_av' in df.columns:
                df['permisos_av'] = df['permisos_av'].apply(
                    lambda x: (x.strip().upper() == "TRUE") if isinstance(x, str) else bool(x)
                )
            
            st.markdown("### ✏️ Modificar Usuario Existente")
            
            # Mostramos la grilla de usuarios únicamente aquí en el modo modificación
            display_df = df[['email', 'role', 'usuario', 'codigo_vendedor', 'permiso_alta', 'permiso_validacion', 'permiso_exportados', 'permiso_usuarios', 'permisos_sincro', 'permisos_av']].copy()
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            st.write("")
            
            user_list = df['email'].tolist()
            selected_email = st.selectbox(
                "Selecciona un usuario para modificar",
                user_list,
                index=None,
                placeholder="-- Selecciona un usuario --",
                key="modificar_usuario_select"
            )
            
            if selected_email:
                user_data = df[df['email'] == selected_email].iloc[0]
                
                # Validación de seguridad: Solo JuanLuis puede modificar a JuanLuis
                is_target_juanluis = (user_data['email'] == 'grandijuanluis@gmail.com' or user_data.get('usuario') == 'JuanLuis')
                is_current_juanluis = (st.session_state.get('user_email') == 'grandijuanluis@gmail.com')
                
                if is_target_juanluis and not is_current_juanluis:
                    st.warning("⚠️ El perfil y permisos del usuario **JuanLuis** sólo pueden ser modificados por él mismo.")
                    if st.button("❌ Cancelar y Volver", use_container_width=True):
                        if "modificar_usuario_select" in st.session_state:
                            del st.session_state["modificar_usuario_select"]
                        st.session_state['usuario_action_mode'] = None
                        st.rerun()
                    return
                
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
                    p_sincro = col_mp1.checkbox("Sincronización FTP", value=bool(user_data.get('permisos_sincro', False)))
                    p_av = col_mp2.checkbox("Análisis de Gestión", value=bool(user_data.get('permisos_av', False)))
                    
                    cod_vendedor = st.number_input("Código de Vendedor (Presea)", value=int(user_data.get('codigo_vendedor', 0) or 0))
                    
                    col_subm1, col_subm2 = st.columns(2)
                    with col_subm1:
                        submit_modificar = st.form_submit_button("Guardar Cambios", type="primary", use_container_width=True)
                    with col_subm2:
                        cancelar_modificar = st.form_submit_button("Cancelar", use_container_width=True)
                        
                    if cancelar_modificar:
                        if "modificar_usuario_select" in st.session_state:
                            del st.session_state["modificar_usuario_select"]
                        st.session_state['usuario_action_mode'] = None
                        st.rerun()
                        
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
                                'permisos_sincro': p_sincro,
                                'permisos_av': p_av,
                                'codigo_vendedor': cod_vendedor
                            }
                            try:
                                supabase.table('usuarios').update(update_data).eq('id', user_data['id']).execute()
                                st.session_state['usuario_success_msg'] = "Datos del usuario y permisos actualizados correctamente."
                                st.session_state['usuario_action_mode'] = None
                                if "modificar_usuario_select" in st.session_state:
                                    del st.session_state["modificar_usuario_select"]
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar el usuario. Detalle: {e}")
            else:
                if st.button("❌ Cancelar y Volver", use_container_width=True):
                    st.session_state['usuario_action_mode'] = None
                    st.rerun()
                    
        except Exception as e:
            st.error(f"Error al cargar usuarios. Asegúrate de haber corrido los comandos SQL en Supabase para agregar las nuevas columnas. Detalles: {e}")
