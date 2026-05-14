import streamlit as st

# Configuración inicial de la página
st.set_page_config(
    page_title="MP - Alta Rápida de Clientes",
    page_icon="💼",
    layout="wide"
)

def main():
    st.title("💼 MP - Alta Rápida de Clientes")
    st.write("Bienvenido al sistema de carga de clientes.")
    st.info("Módulo en construcción. Pronto agregaremos login y roles.")

if __name__ == "__main__":
    main()
