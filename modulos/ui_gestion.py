import streamlit as st
import pandas as pd
import numpy as np
import datetime
from modulos.db import supabase

# Importar Gemini para el motor de análisis estratégico
import google.generativeai as genai

# Intentar configurar Gemini con la API KEY en secrets
api_key = None
try:
    api_key = st.secrets.get("GOOGLE_API_KEY", None)
except:
    pass

if api_key:
    genai.configure(api_key=api_key)

@st.cache_data(ttl=120)
def load_sales_data(vendedor_filter=None, limit=5000):
    """
    Carga los últimos registros de ventas de Supabase.
    Retorna un DataFrame limpio y tipado.
    """
    if supabase is None:
        return pd.DataFrame()
        
    try:
        # Seleccionamos columnas clave para optimizar ancho de banda y velocidad
        query = supabase.table("ventas").select(
            "fecha, empresa, formulario, numero, rubro, subrubro, localidad, provincia, unidades, ean, clien, cod_clien, producto, vendedo, impo"
        )
        
        if vendedor_filter and vendedor_filter != "Todos":
            query = query.eq("vendedo", vendedor_filter)
            
        res = query.order("fecha", desc=True).limit(limit).execute()
        
        if not res.data:
            return pd.DataFrame()
            
        df = pd.DataFrame(res.data)
        
        # Tipar columnas correctamente
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        df['impo'] = pd.to_numeric(df['impo'], errors='coerce').fillna(0.0)
        df['unidades'] = pd.to_numeric(df['unidades'], errors='coerce').fillna(0)
        df['cod_clien'] = pd.to_numeric(df['cod_clien'], errors='coerce').fillna(0).astype(int)
        
        return df
    except Exception as e:
        st.error(f"Error al cargar datos de ventas: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_vendedores_list():
    """Obtiene la lista única de vendedores con ventas registradas."""
    if supabase is None:
        return ["Todos"]
    try:
        res = supabase.table("ventas").select("vendedo").execute()
        if not res.data:
            return ["Todos"]
        df_v = pd.DataFrame(res.data)
        vendedores = df_v["vendedo"].dropna().unique().tolist()
        vendedores = [v for v in vendedores if v.strip()]
        return ["Todos"] + sorted(vendedores)
    except Exception as e:
        return ["Todos"]

def render_gestion_dashboard():
    # --- Estilos CSS Premium ---
    st.markdown("""
    <style>
    /* Estilos del Dashboard */
    .gestion-header {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }
    .kpi-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease, border-color 0.2s ease;
        margin-bottom: 15px;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        border-color: #3b82f6;
    }
    .kpi-title {
        color: #9ca3af;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 0;
    }
    .kpi-value {
        color: #f3f4f6;
        font-size: 1.85rem;
        font-weight: 700;
        margin-top: 8px;
        margin-bottom: 0;
    }
    .kpi-subtitle {
        color: #10b981;
        font-size: 0.75rem;
        margin-top: 5px;
        margin-bottom: 0;
    }
    /* Estilo del Panel de IA */
    .ia-panel {
        background: radial-gradient(circle at top left, #1e1b4b 0%, #0f172a 100%);
        border: 1px solid #312e81;
        border-radius: 16px;
        padding: 25px;
        margin-top: 25px;
        margin-bottom: 25px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<h1 class="gestion-header">📊 Análisis de Gestión</h1>', unsafe_allow_html=True)
    st.write("Panel inteligente de monitoreo de facturación, volumen y analítica estratégica de ventas.")
    
    if supabase is None:
        st.error("No hay conexión a la base de datos configurada.")
        return

    # --- FILTROS DE BÚSQUEDA ---
    st.sidebar.markdown("### 🔍 Filtros de Gestión")
    
    # Obtener lista de vendedores dinámicamente
    vendedores = get_vendedores_list()
    selected_vendedor = st.sidebar.selectbox("Vendedor", vendedores)
    
    # Rango de fechas
    today = datetime.date.today()
    start_default = today - datetime.timedelta(days=90)
    date_range = st.sidebar.date_input("Rango de Fechas", [start_default, today])
    
    limit_records = st.sidebar.slider("Límite de registros a consultar", 500, 10000, 5000, step=500)
    
    # Carga de Datos
    with st.spinner("Cargando datos de facturación..."):
        df_raw = load_sales_data(vendedor_filter=selected_vendedor, limit=limit_records)
        
    if df_raw.empty:
        st.warning("⚠️ No se encontraron registros de ventas que coincidan con los filtros seleccionados o la tabla está vacía.")
        st.info("Asegúrate de que el sincronizador local en Windows haya procesado y subido el archivo `ventas.csv` a Supabase.")
        return
        
    # Filtrar por rango de fechas en memoria
    df_filtered = df_raw.copy()
    if isinstance(date_range, list) or isinstance(date_range, tuple):
        if len(date_range) == 2:
            start_date, end_date = date_range
            df_filtered = df_filtered[
                (df_filtered['fecha'].dt.date >= start_date) & 
                (df_filtered['fecha'].dt.date <= end_date)
            ]
            
    if df_filtered.empty:
        st.info("No hay ventas en el rango de fechas seleccionado.")
        return

    # --- MÉTRICAS KPI ---
    total_facturado = df_filtered['impo'].sum()
    total_unidades = df_filtered['unidades'].sum()
    cant_transacciones = len(df_filtered)
    ticket_promedio = total_facturado / cant_transacciones if cant_transacciones > 0 else 0
    
    # Render layout with just the Uploader and Gemini Brain


    # --- PANEL DE SUBIDA HISTÓRICA ---
    with st.expander("📤 Carga Histórica de Ventas (ventas.dbi)"):
        st.write("Sube un archivo `ventas.dbi` histórico para procesarlo e importarlo incrementalmente en la base de datos de Supabase. El sistema evitará duplicados de forma inteligente utilizando las restricciones de base de datos.")
        uploaded_file = st.file_uploader("Selecciona el archivo ventas.dbi", type=["dbi"], key="uploader_ventas_history")
        
        if uploaded_file is not None:
            if st.button("🚀 Iniciar Procesamiento e Importación", use_container_width=True, key="btn_ventas_history_import"):
                import os
                temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, "temp_ventas_history.dbi")
                
                with open(temp_path, "wb") as f_temp:
                    f_temp.write(uploaded_file.getbuffer())
                
                try:
                    import dbf
                    
                    def parse_dbf_int(val):
                        if val is None: return 0
                        try: return int(val)
                        except: return 0
                        
                    def parse_dbf_float(val):
                        if val is None: return 0.0
                        try: return float(val)
                        except: return 0.0

                    def parse_dbf_str(val):
                        if val is None: return ""
                        try: return str(val).strip()
                        except: return ""
                        
                    def parse_dbf_date(val):
                        if not val: return None
                        if isinstance(val, (datetime.date, datetime.datetime)):
                            return val.strftime("%Y-%m-%d")
                        val_str = str(val).strip()
                        if len(val_str) >= 10 and val_str[4] == '-' and val_str[7] == '-':
                            return val_str[:10]
                        try:
                            parts = val_str.split('/')
                            if len(parts) == 3:
                                d, m, y = parts
                                return f"{y.zfill(4)}-{m.zfill(2)}-{d.zfill(2)}"
                        except: pass
                        return None
                    
                    # Crear archivos de memo ficticios si no existen para evitar que explote si no se subieron
                    def create_dummy_memo_files(dbf_path):
                        base, _ = os.path.splitext(dbf_path)
                        for ext in [".dbt", ".fpt", ".DBT", ".FPT"]:
                            p = base + ext
                            if not os.path.exists(p):
                                try:
                                    with open(p, "wb") as f:
                                        if ext.lower() == ".dbt":
                                            f.write(b'\x01\x00\x00\x00' + b'\x00' * 508)
                                        else:
                                            f.write(b'\x00\x00\x00\x01\x00\x00\x00\x40' + b'\x00' * 504)
                                except:
                                    pass

                    create_dummy_memo_files(temp_path)

                    # Leer cantidad total de registros
                    total_records = 0
                    with dbf.Table(temp_path, codepage='cp1252') as table:
                        table.open()
                        if table._meta.memo:
                            original_get_memo = table._meta.memo.get_memo
                            def safe_get_memo(block):
                                try:
                                    return original_get_memo(block)
                                except Exception:
                                    return b""
                            table._meta.memo.get_memo = safe_get_memo
                        total_records = len(table)
                    
                    st.info(f"Detectados {total_records} registros en el archivo dbi. Iniciando importación...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    batch_dict = {}
                    batch_size = 1000
                    total_procesados = 0
                    
                    with dbf.Table(temp_path, codepage='cp1252') as table:
                        table.open()
                        if table._meta.memo:
                            original_get_memo = table._meta.memo.get_memo
                            def safe_get_memo(block):
                                try:
                                    return original_get_memo(block)
                                except Exception:
                                    return b""
                            table._meta.memo.get_memo = safe_get_memo
                        for i, rec in enumerate(table):
                            fecha_iso = parse_dbf_date(rec.FECHA)
                            if not fecha_iso:
                                continue
                                
                            venta_item = {
                                "rubro": parse_dbf_str(rec.RUBRO),
                                "fecha": fecha_iso,
                                "empresa": parse_dbf_str(rec.EMPRESA),
                                "subrubro": parse_dbf_str(rec.SUBRUBRO),
                                "numero": parse_dbf_int(rec.NUMERO),
                                "localidad": parse_dbf_str(rec.LOCALIDAD),
                                "provincia": parse_dbf_str(rec.PROVINCIA),
                                "formulario": parse_dbf_str(rec.FORMULARIO),
                                "e_mail": parse_dbf_str(rec.E_MAIL),
                                "telefono": parse_dbf_str(rec.TELEFONO),
                                "pais": parse_dbf_str(rec.PAIS),
                                "codigo": parse_dbf_int(rec.CODIGO),
                                "cod_alfa": parse_dbf_str(rec.COD_ALFA),
                                "unidades": parse_dbf_float(rec.UNIDADES),
                                "codigocomp": parse_dbf_int(rec.CODIGOCOMP),
                                "tipo": parse_dbf_int(rec.TIPO),
                                "dto": parse_dbf_float(rec.DTO),
                                "dto1": parse_dbf_float(rec.DTO1),
                                "dto2": parse_dbf_float(rec.DTO2),
                                "alt_bonifi": parse_dbf_str(rec.ALT_BONIFI),
                                "grupo": parse_dbf_str(rec.GRUPO),
                                "sinonimo": parse_dbf_str(rec.SINONIMO),
                                "ean": parse_dbf_str(rec.EAN),
                                "clien": parse_dbf_str(rec.CLIEN),
                                "cod_clien": parse_dbf_int(rec.COD_CLIEN),
                                "producto": parse_dbf_str(rec.PRODUCTO),
                                "vendedo": parse_dbf_str(rec.VENDEDO),
                                "domicilio": parse_dbf_str(rec.DOMICILIO),
                                "deposito": parse_dbf_str(rec.DEPOSITO),
                                "bultos": parse_dbf_float(rec.BULTOS),
                                "impo": parse_dbf_float(rec.IMPO)
                            }
                            
                            # Usar clave única como clave de diccionario para deduplicar dentro del mismo lote
                            key = (
                                venta_item["fecha"],
                                venta_item["empresa"],
                                venta_item["formulario"],
                                venta_item["numero"],
                                venta_item["cod_clien"],
                                venta_item["cod_alfa"],
                                venta_item["bultos"]
                            )
                            batch_dict[key] = venta_item
                            
                            if len(batch_dict) >= batch_size:
                                supabase.table("ventas").upsert(list(batch_dict.values()), on_conflict="fecha,empresa,formulario,numero,cod_clien,cod_alfa,bultos").execute()
                                total_procesados += len(batch_dict)
                                status_text.text(f"Importados: {total_procesados} / {total_records} registros")
                                progress_bar.progress(min(1.0, total_procesados / total_records))
                                batch_dict = {}
                        
                        if batch_dict:
                            supabase.table("ventas").upsert(list(batch_dict.values()), on_conflict="fecha,empresa,formulario,numero,cod_clien,cod_alfa,bultos").execute()
                            total_procesados += len(batch_dict)
                            progress_bar.progress(1.0)
                            status_text.text(f"Importados: {total_procesados} / {total_records} registros (Completado)")
                            
                    st.success(f"🎉 ¡Sincronización exitosa! Se procesaron e importaron {total_procesados} registros de ventas.")
                    st.rerun()
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    st.error(f"Error procesando el archivo: {e}")
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    # Eliminar también archivos de memo ficticios
                    base, _ = os.path.splitext(temp_path)
                    for ext in [".dbt", ".fpt"]:
                        p = base + ext
                        if os.path.exists(p):
                            try: os.remove(p)
                            except: pass

    # --- SECCIÓN DE INTELIGENCIA ARTIFICIAL (MOTOR DE CONSULTORÍA) ---
    st.markdown('<div class="ia-panel">', unsafe_allow_html=True)
    st.markdown("<h2 style='color:#a5b4fc; margin-top:0;'>🧠 Consultor Estratégico IA (Gemini Brain)</h2>", unsafe_allow_html=True)
    st.write("El analista de inteligencia artificial evalúa el comportamiento general de las ventas e identifica riesgos u oportunidades.")

    if not api_key:
        st.info("🔑 Configura `GOOGLE_API_KEY` en tu archivo `secrets.toml` para habilitar el motor de consultoría estratégica por IA.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Generación de contexto agregado para no sobrecargar el límite de tokens
    # Agrupamos por mes, vendedor y rubro
    df_filtered['mes_año'] = df_filtered['fecha'].dt.strftime('%Y-%m')
    resumen_ia = df_filtered.groupby(['mes_año', 'vendedo', 'rubro']).agg(
        total_ventas=('impo', 'sum'),
        cant_operaciones=('impo', 'count'),
        clientes_distintos=('cod_clien', 'nunique')
    ).reset_index()
    
    # Quedarnos con el Top 30 combinaciones para mantener el contexto extremadamente limpio y veloz
    resumen_ia = resumen_ia.sort_values(by='total_ventas', ascending=False).head(40)
    context_str = resumen_ia.to_string(index=False)
    
    # Botones con prompts preestablecidos
    col_ia1, col_ia2, col_ia3 = st.columns(3)
    prompt_ia = None
    
    with col_ia1:
        if st.button("📊 Generar Informe Ejecutivo", use_container_width=True):
            prompt_ia = "Realiza un informe ejecutivo de alto nivel resumiendo el comportamiento comercial, los vendedores líderes, rubros principales y sugerencias estratégicas."
            
    with col_ia2:
        if st.button("🚨 Alerta de Desvíos o Concentración", use_container_width=True):
            prompt_ia = "Analiza los datos buscando alertas comerciales. ¿Hay excesiva dependencia en algún vendedor o rubro? ¿Hay clientes inactivos o baja capilaridad?"
            
    with col_ia3:
        if st.button("💡 Propuesta de Plan Comercial", use_container_width=True):
            prompt_ia = "Propone 3 iniciativas comerciales concretas para expandir la facturación y la capilaridad basándote en la distribución actual de ventas."
            
    pregunta_libre = st.text_input("Hazle una pregunta personalizada al Consultor de Ventas:", placeholder="Ej: ¿Qué vendedor tiene mejor relación importe/operaciones?")
    
    prompt_final = prompt_ia if prompt_ia else pregunta_libre
    
    if prompt_final:
        # Prompt final enriquecido con el contexto autónomo de toda la historia cargada
        prompt_completo = f"""
        ERES EL CONSULTOR ESTRATÉGICO DE NEGOCIOS DE LA EMPRESA "MP" (MESSINA & PASINA).
        TU TAREA ES ANALIZAR LA SIGUIENTE TABLA DE RESUMEN DE VENTAS HISTÓRICAS AGREGADAS Y CONTESTAR LA PREGUNTA DEL USUARIO CON PROPUESTAS PRÁCTICAS, NÚMEROS CLAVE Y TONALIDAD CORPORATIVA.

        TABLA DE RESUMEN DE VENTAS (Campos: Mes/Año, Vendedor, Rubro, Total Ventas $, Cant. Operaciones, Clientes Distintos):
        {context_str}

        INFORMACIÓN GENERAL DEL PERÍODO SELECCIONADO:
        - Facturación Total: $ {total_facturado:,.2f}
        - Unidades Totales Despachadas: {total_unidades:,.0f}
        - Cantidad de Transacciones: {cant_transacciones:,}
        - Clientes Únicos Atendidos: {df_filtered['cod_clien'].nunique()}

        SOLICITUD DEL USUARIO: "{prompt_final}"

        Escribe tu respuesta con formato markdown enriquecido (negritas, listas, subtítulos). Sé directo, profesional y aporta valor ejecutivo real.
        """
        
        with st.spinner("🧠 Gemini está analizando las tendencias de ventas..."):
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt_completo)
                
                st.markdown("---")
                st.markdown("### 📋 Análisis e Insights del Consultor:")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error al procesar la consulta con IA: {e}")
                
    st.markdown('</div>', unsafe_allow_html=True)
