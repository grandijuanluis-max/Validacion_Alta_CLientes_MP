import streamlit as st

# Configuración inicial de la página
st.set_page_config(
    page_title="MP - Alta Rápida de Clientes",
    page_icon="💼",
    layout="wide"
)

from modulos.auth import login_form, logout
from modulos.ui_vendedor import render_vendedor_dashboard
from modulos.ui_validador import render_validador_dashboard

def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['role'] = None

    if not st.session_state['logged_in']:
        st.title("💼 MP - Alta Rápida de Clientes")
        st.caption("🟢 Versión 1.1 - Sistema de Login Habilitado")
        login_form()
    else:
        # Sidebar layout for logged-in users
        with st.sidebar:
            st.write(f"Conectado como: **{st.session_state.get('user_email', '')}**")
            st.write(f"Rol: **{st.session_state['role']}**")
            logout()
            
        if st.session_state['role'] == 'vendedor':
            render_vendedor_dashboard()
        elif st.session_state['role'] == 'admin':
            render_validador_dashboard()
        else:
            st.error("Rol no reconocido.")

if __name__ == "__main__":
    main()
