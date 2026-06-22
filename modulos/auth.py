import streamlit as st
from modulos.db import supabase

def check_login():
    identificador = st.session_state.get('login_identificador')
    password = st.session_state.get('login_password')
    
    if not identificador or not password:
        st.session_state['login_error'] = "Por favor completa ambos campos."
        return

    if supabase is None:
        st.session_state['login_error'] = "No hay conexión a la base de datos configurada."
        return

    try:
        # Primero buscamos por email
        response = supabase.table('usuarios').select('*').eq('email', identificador).execute()
        
        # Si no hay resultados, buscamos por usuario
        if not response.data:
            response = supabase.table('usuarios').select('*').eq('usuario', identificador).execute()
            
        if response.data:
            user = response.data[0]
            if user['password'] == password:
                st.session_state['logged_in'] = True
                st.session_state['role'] = user['role']
                st.session_state['user_id'] = user['id']
                st.session_state['user_email'] = user['email']
                st.session_state['codigo_vendedor'] = user.get('codigo_vendedor')
                # Nuevos Permisos Dinámicos
                st.session_state['permiso_alta'] = user.get('permiso_alta', False)
                st.session_state['permiso_validacion'] = user.get('permiso_validacion', False)
                st.session_state['permiso_exportados'] = user.get('permiso_exportados', False)
                st.session_state['permiso_usuarios'] = user.get('permiso_usuarios', False)
                
                # permisos_sincro es de tipo text en Supabase (puede venir como string "TRUE"/"FALSE")
                val_sincro = user.get('permisos_sincro', False)
                if isinstance(val_sincro, str):
                    st.session_state['permisos_sincro'] = (val_sincro.strip().upper() == "TRUE")
                else:
                    st.session_state['permisos_sincro'] = bool(val_sincro)

                # permisos_av
                val_av = user.get('permisos_av', False)
                if isinstance(val_av, str):
                    st.session_state['permisos_av'] = (val_av.strip().upper() == "TRUE")
                else:
                    st.session_state['permisos_av'] = bool(val_av)
                
                st.session_state['login_error'] = None
            else:
                st.session_state['login_error'] = "Contraseña incorrecta"
        else:
            st.session_state['login_error'] = "Usuario no encontrado en la base de datos."
    except Exception as e:
        st.session_state['login_error'] = f"Error al conectar con la base de datos: {e}"

def login_form():
    st.subheader("Iniciar Sesión")
    
    with st.form("login_form"):
        st.text_input("Usuario o Correo electrónico", key="login_identificador")
        st.text_input("Contraseña", type="password", key="login_password")
        st.form_submit_button("Ingresar", on_click=check_login)
        
    if st.session_state.get('login_error'):
        st.error(st.session_state['login_error'])

def logout():
    keys_to_clear = ['logged_in', 'role', 'user_id', 'user_email', 'codigo_vendedor', 
                     'permiso_alta', 'permiso_validacion', 'permiso_exportados', 'permiso_usuarios', 'permisos_sincro', 'permisos_av']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()
