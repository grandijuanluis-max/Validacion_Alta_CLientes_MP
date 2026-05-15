import streamlit as st
from modulos.db import supabase

def login_form():
    st.subheader("Iniciar Sesión")
    identificador = st.text_input("Usuario o Correo electrónico")
    password = st.text_input("Contraseña", type="password")
    
    if st.button("Ingresar"):
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
                # Para MVP comparamos texto plano (o el hash que hayas guardado)
                if user['password'] == password:
                    st.session_state['logged_in'] = True
                    st.session_state['role'] = user['role']
                    st.session_state['user_id'] = user['id']
                    st.session_state['user_email'] = user['email']
                    st.session_state['codigo_vendedor'] = user.get('codigo_vendedor')
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
            else:
                st.error("Usuario no encontrado")
        except Exception as e:
            st.error(f"Error al conectar con la base de datos: {e}")

def logout():
    for key in ['logged_in', 'role', 'user_id', 'user_email', 'codigo_vendedor']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()
