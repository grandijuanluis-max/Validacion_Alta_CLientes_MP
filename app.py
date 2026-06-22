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
from modulos.ui_exportados import render_exportados_dashboard
from modulos.ui_usuarios import render_usuarios_dashboard
from modulos.ui_sincronizacion import render_sincronizacion_ftp_dashboard


def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['role'] = None

    if not st.session_state['logged_in']:
        st.title("💼 MP - Alta Rápida de Clientes")
        st.caption("🟢 Versión 1.2 - Sistema de Permisos y Workflow Avanzado")
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
            if st.session_state.get('permiso_exportados', False):
                menu_options.append("Clientes Exportados")
            if st.session_state.get('permiso_usuarios', False):
                menu_options.append("Permisos de Usuarios")
            if st.session_state.get('permisos_sincro', False):
                menu_options.append("Sincronización FTP")
            if st.session_state.get('permisos_av', False):
                menu_options.append("Análisis de Gestión")
                
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
        elif seleccion == "Clientes Exportados":
            render_exportados_dashboard()
        elif seleccion == "Permisos de Usuarios":
            render_usuarios_dashboard()
        elif seleccion == "Sincronización FTP":
            if st.session_state.get('permisos_sincro', False):
                render_sincronizacion_ftp_dashboard()
            else:
                st.error("Acceso denegado. No tienes permisos para acceder a esta sección.")
        elif seleccion == "Análisis de Gestión":
            if st.session_state.get('permisos_av', False):
                from modulos.ui_gestion import render_gestion_dashboard
                render_gestion_dashboard()
            else:
                st.error("Acceso denegado. No tienes permisos para acceder a esta sección.")


if __name__ == "__main__":
    main()
