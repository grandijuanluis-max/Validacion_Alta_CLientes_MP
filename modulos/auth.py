import streamlit as st
from modulos.db import supabase

def login_form():
    st.subheader("Iniciar Sesión")
    
    with st.form("login_form"):
        identificador = st.text_input("Usuario o Correo electrónico")
        password = st.text_input("Contraseña", type="password")
        submit_btn = st.form_submit_button("Ingresar")
        
        if submit_btn:
            if not identificador or not password:
                st.warning("Por favor completa ambos campos.")
                return
                
            if supabase is None:
                st.error("No hay conexión a la base de datos configurada.")
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
                        st.success("¡Ingreso exitoso! Por favor, haz clic abajo para continuar al panel.")
                    else:
                        st.error("Contraseña incorrecta")
                else:
                    st.error("Usuario no encontrado en la base de datos.")
            except Exception as e:
                st.error(f"Error al conectar con la base de datos: {e}")
                
    if st.session_state.get('logged_in', False):
        if st.button("Continuar al Panel Principal"):
            st.rerun()

def logout():
    for key in ['logged_in', 'role', 'user_id', 'user_email', 'codigo_vendedor']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()
