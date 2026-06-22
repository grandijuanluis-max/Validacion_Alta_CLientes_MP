import streamlit as st
import os
import json
import datetime
from utils.ftp_sync import test_connection, upload_exports, download_and_import, METADATA_FILE, LOG_FILE

def read_sync_metadata():
    """Lee el archivo JSON de metadatos de sincronización."""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def read_last_log_lines(lines_count=30):
    """Lee las últimas N líneas del archivo de logs."""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return "".join(lines[-lines_count:])
        except Exception as e:
            return f"Error leyendo logs: {e}"
    return "No se ha generado ningún registro de log aún."

def render_sincronizacion_ftp_dashboard():
    if not st.session_state.get('permisos_sincro', False):
        st.error("Acceso denegado. No tienes permisos para acceder a esta sección.")
        return

    st.header("🔄 Sincronización FTP y Bases de Datos")
    st.caption("🟢 Integración y sincronización de datos con el ERP Presea")
    
    # 1. ESTADO DE LA CONEXIÓN FTP (Healthcheck en tiempo real)
    st.markdown("### 🔌 Estado de Conexión FTP")
    
    with st.spinner("Verificando conexión con el FTP..."):
        ftp_ok, ftp_msg = test_connection()
        
    if ftp_ok:
        st.success(f"**Conectado al Servidor FTP**\n\n{ftp_msg}")
    else:
        st.error(f"**Error de Conexión al Servidor FTP**\n\nDetalle: {ftp_msg}\n\n*Por favor, verifique que las credenciales en secrets.toml sean correctas y que el servidor no tenga bloqueos de red.*")

    st.divider()

    # 2. HISTORIAL DE SINCRONIZACIÓN Y MÉTRICAS
    metadata = read_sync_metadata()
    
    # Formatear fechas
    def format_iso_date(iso_str):
        if not iso_str:
            return "Nunca"
        try:
            dt = datetime.datetime.fromisoformat(iso_str)
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            return iso_str

    last_up_time = format_iso_date(metadata.get("last_upload_time"))
    last_up_status = metadata.get("last_upload_status", "N/A")
    last_up_error = metadata.get("last_upload_error", "")

    last_dl_time = format_iso_date(metadata.get("last_download_time"))
    last_dl_status = metadata.get("last_download_status", "N/A")
    last_dl_error = metadata.get("last_download_error", "")
    
    st.markdown("### 📊 Estado y Métricas de Sincronización")
    
    col_stat1, col_stat2 = st.columns(2)
    
    with col_stat1:
        st.markdown("#### 📤 Sincronización de Salida (DB -> FTP)")
        st.write(f"**Último Intento:** {last_up_time}")
        if last_up_status == "Success":
            st.markdown("🟢 **Estado:** Exitoso")
        elif last_up_status == "Error":
            st.markdown(f"🔴 **Estado:** Fallido")
            st.caption(f"Detalle del error: `{last_up_error}`")
        else:
            st.markdown("⚪ **Estado:** Sin ejecutar")
            
    with col_stat2:
        st.markdown("#### 📥 Sincronización de Entrada (FTP -> DB)")
        st.write(f"**Último Intento:** {last_dl_time}")
        if last_dl_status == "Success":
            st.markdown("🟢 **Estado:** Exitoso")
        elif last_dl_status == "Error":
            st.markdown(f"🔴 **Estado:** Fallido")
            st.caption(f"Detalle del error: `{last_dl_error}`")
        else:
            st.markdown("⚪ **Estado:** Sin ejecutar")

    st.divider()

    # 3. ACCIONES MANUALES DE SINCRONIZACIÓN
    st.markdown("### ⚙️ Acciones de Sincronización Manual")
    st.info("💡 *Nota: Estos procesos se ejecutan de manera automática en segundo plano cada 15 minutos en producción. Utilice estos botones si necesita sincronizar los datos de forma inmediata.*")
    
    col_act1, col_act2 = st.columns(2)
    
    with col_act1:
        st.markdown("##### Sincronización de Entrada (Descarga)")
        st.caption("Descarga `CLIENTESPA.DBI` y `CODIGOSMP.DBI` desde el FTP, actualiza la secuencia correlativa de códigos de clientes, verifica/crea cuentas de vendedores en Supabase y actualiza nuevos códigos postales.")
        
        btn_dl = st.button("📥 Ejecutar Descarga e Importación", use_container_width=True, key="btn_manual_download")
        if btn_dl:
            if not ftp_ok:
                st.error("No se puede iniciar el proceso porque el servidor FTP no está accesible.")
            else:
                with st.spinner("Procesando descarga e importación... Esto puede demorar unos segundos."):
                    success, msg = download_and_import()
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
                    
    with col_act2:
        st.markdown("##### Sincronización de Salida (Subida)")
        st.caption("Sube los archivos exportados `.dbi`, `.fpt` y `.txt` locales generados en el servidor (`Clientes_web.dbi`, `Clientes_web.fpt` y `domicilios_entrega.txt`) hacia el servidor FTP.")
        
        btn_up = st.button("📤 Ejecutar Subida de Exportaciones", use_container_width=True, key="btn_manual_upload", type="primary")
        if btn_up:
            if not ftp_ok:
                st.error("No se puede iniciar el proceso porque el servidor FTP no está accesible.")
            else:
                with st.spinner("Subiendo archivos exportados..."):
                    success, msg = upload_exports()
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    st.divider()

    # 4. REGISTRO DE LOGS EN VIVO
    st.markdown("### 📋 Registro de Logs Recientes (ftp_sync.log)")
    
    logs_content = read_last_log_lines(30)
    st.code(logs_content, language="text")
    
    col_log1, col_log2 = st.columns([2, 1])
    with col_log1:
        st.caption("Se muestran las últimas 30 líneas del log. Para auditoría completa, puede descargar el archivo.")
    with col_log2:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as lf:
                st.download_button(
                    label="📥 Descargar Log Completo",
                    data=lf.read(),
                    file_name="ftp_sync_completo.log",
                    mime="text/plain",
                    use_container_width=True
                )
