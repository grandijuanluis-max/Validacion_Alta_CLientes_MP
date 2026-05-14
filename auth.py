import streamlit as st

def login_form():
    st.subheader("Iniciar Sesión")
    email = st.text_input("Correo electrónico")
    password = st.text_input("Contraseña", type="password")
    
    if st.button("Ingresar"):
        # TODO: Conectar con Supabase Auth
        if email == "admin" and password == "123":
            st.session_state['logged_in'] = True
            st.session_state['role'] = 'validador'
            st.rerun()
        elif email == "vendedor" and password == "123":
            st.session_state['logged_in'] = True
            st.session_state['role'] = 'vendedor'
            st.rerun()
        else:
            st.error("Credenciales inválidas")

def logout():
    st.session_state['logged_in'] = False
    st.session_state['role'] = None
    st.rerun()
