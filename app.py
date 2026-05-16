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
            st.write(f"Rol base: **{st.session_state.get('role', '')}**")
            
            st.divider()
            
            # Construir el menú de navegación basado en permisos
            menu_options = []
            if st.session_state.get('permiso_alta', False):
                menu_options.append("Alta de Clientes")
            if st.session_state.get('permiso_validacion', False):
                menu_options.append("Validar Clientes")
                
            if not menu_options:
                st.warning("No tienes permisos asignados a ninguna sección.")
                seleccion = None
            else:
                seleccion = st.radio("Navegación", menu_options)
            
            st.divider()
            if st.button("Cerrar Sesión"):
                logout()
            
        # Renderizar la sección seleccionada
        if seleccion == "Alta de Clientes":
            render_vendedor_dashboard()
        elif seleccion == "Validar Clientes":
            render_validador_dashboard()

if __name__ == "__main__":
    main()
