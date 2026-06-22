import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def init_connection() -> Client:
    """
    Inicializa y retorna el cliente de Supabase usando los secretos de Streamlit.
    Utiliza st.cache_resource para evitar crear una conexión nueva en cada recarga.
    """
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error de conexión a Supabase: Verifica que '.streamlit/secrets.toml' esté configurado correctamente. Error: {e}")
        return None

# Instancia global (opcional) o simplemente usar la función
supabase = init_connection()
