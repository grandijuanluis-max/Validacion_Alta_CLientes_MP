import streamlit as st
import pandas as pd
import numpy as np
import datetime
from modulos.db import supabase

# ── Gemini ────────────────────────────────────────────────────────────────────
import google.generativeai as genai
api_key = None
try:
    api_key = st.secrets.get("GOOGLE_API_KEY", None)
except Exception:
    pass
if api_key:
    genai.configure(api_key=api_key)

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTES
# ══════════════════════════════════════════════════════════════════════════════

DIMENSIONES_DISPONIBLES = {
    "empresa":    "Empresa",
    "rubro":      "Rubro",
    "subrubro":   "Sub Rubro",
    "grupo":      "Grupo",
    "vendedo":    "Vendedor",
    "formulario": "Formulario",
    "deposito":   "Depósito",
    "provincia":  "Provincia",
    "localidad":  "Localidad",
    "clien":      "Cliente",
    "cod_clien":  "Cód. Cliente",
    "producto":   "Producto",
    "sinonimo":   "Sinónimo",
    "ean":        "EAN",
    "_año":       "Año",
    "_mes":       "Mes",
}

DEFAULT_ROW_DIMS = ["rubro", "subrubro", "vendedo", "clien", "producto"]
DEFAULT_COL_DIMS = ["_año", "_mes"]
METRICAS         = {"impo": "IMPO NETO", "bultos": "BULTOS"}

ATAJOS = [
    "Mes Actual",
    "Hoy",
    "Ayer",
    "Semana Actual",
    "Semana Anterior",
    "Mes Anterior",
    "Este Año",
    "Últimos 3 Años",
    "Últimos 5 Años",
    "Todo",
    "Ingresar fecha manualmente",
]

# ══════════════════════════════════════════════════════════════════════════════
#  CARGA DE DATOS — Paginación completa sin límite artificial
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def load_sales_range(fecha_desde_iso: str, fecha_hasta_iso: str) -> pd.DataFrame:
    """
    Carga TODOS los registros de ventas en el rango dado, usando paginación.
    Retorna un DataFrame limpio y tipado.
    """
    if supabase is None:
        return pd.DataFrame()
    try:
        PAGE = 10_000
        offset = 0
        frames = []
        cols = (
            "fecha, empresa, formulario, numero, rubro, subrubro, grupo, "
            "localidad, provincia, unidades, ean, clien, cod_clien, producto, "
            "sinonimo, vendedo, deposito, bultos, impo"
        )
        while True:
            res = (
                supabase.table("ventas")
                .select(cols)
                .gte("fecha", fecha_desde_iso)
                .lte("fecha", fecha_hasta_iso)
                .range(offset, offset + PAGE - 1)
                .execute()
            )
            if not res.data:
                break
            frames.append(pd.DataFrame(res.data))
            if len(res.data) < PAGE:
                break
            offset += PAGE

        if not frames:
            return pd.DataFrame()

        df = pd.concat(frames, ignore_index=True)
        _typecast(df)
        return df

    except Exception as e:
        st.error(f"Error cargando ventas: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def load_sales_full_for_ia() -> pd.DataFrame:
    """Carga TODA la tabla ventas para el contexto del Gemini Brain (sin filtros de UI)."""
    if supabase is None:
        return pd.DataFrame()
    try:
        PAGE = 10_000
        offset = 0
        frames = []
        cols = "fecha, rubro, vendedo, provincia, formulario, bultos, impo, cod_clien"
        while True:
            res = (
                supabase.table("ventas")
                .select(cols)
                .range(offset, offset + PAGE - 1)
                .execute()
            )
            if not res.data:
                break
            frames.append(pd.DataFrame(res.data))
            if len(res.data) < PAGE:
                break
            offset += PAGE

        if not frames:
            return pd.DataFrame()

        df = pd.concat(frames, ignore_index=True)
        df["fecha"]  = pd.to_datetime(df["fecha"], errors="coerce")
        df["impo"]   = pd.to_numeric(df["impo"],   errors="coerce").fillna(0.0)
        df["bultos"] = pd.to_numeric(df["bultos"], errors="coerce").fillna(0.0)
        df["cod_clien"] = pd.to_numeric(df["cod_clien"], errors="coerce").fillna(0).astype(int)
        df["_año"] = df["fecha"].dt.year.astype("Int64").astype(str)
        df["_mes"] = df["fecha"].dt.month.astype("Int64").astype(str).str.zfill(2)
        return df
    except Exception as e:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def get_total_count() -> int:
    """Cuenta el total de registros en la tabla ventas."""
    if supabase is None:
        return 0
    try:
        res = supabase.table("ventas").select("id", count="exact").execute()
        return res.count or 0
    except Exception:
        return 0


def _typecast(df: pd.DataFrame):
    """Convierte tipos en el DataFrame in-place."""
    df["fecha"]     = pd.to_datetime(df["fecha"],    errors="coerce")
    df["impo"]      = pd.to_numeric(df["impo"],      errors="coerce").fillna(0.0)
    df["bultos"]    = pd.to_numeric(df["bultos"],    errors="coerce").fillna(0.0)
    df["unidades"]  = pd.to_numeric(df["unidades"],  errors="coerce").fillna(0.0)
    df["cod_clien"] = pd.to_numeric(df["cod_clien"], errors="coerce").fillna(0).astype(int)
    df["_año"] = df["fecha"].dt.year.astype("Int64").astype(str)
    df["_mes"] = df["fecha"].dt.month.astype("Int64").astype(str).str.zfill(2)
    str_cols = ["empresa", "rubro", "subrubro", "grupo", "vendedo", "formulario",
                "deposito", "provincia", "localidad", "clien", "producto", "sinonimo", "ean"]
    for c in str_cols:
        if c in df.columns:
            df[c] = df[c].fillna("").str.strip().replace("", "(Vacío)")


# ══════════════════════════════════════════════════════════════════════════════
#  FECHAS
# ══════════════════════════════════════════════════════════════════════════════

def date_range_for_shortcut(shortcut: str):
    hoy = datetime.date.today()
    if shortcut == "Hoy":
        return hoy, hoy
    elif shortcut == "Ayer":
        a = hoy - datetime.timedelta(days=1)
        return a, a
    elif shortcut == "Semana Actual":
        return hoy - datetime.timedelta(days=hoy.weekday()), hoy
    elif shortcut == "Semana Anterior":
        la = hoy - datetime.timedelta(days=hoy.weekday() + 7)
        return la, la + datetime.timedelta(days=6)
    elif shortcut == "Mes Actual":
        return hoy.replace(day=1), hoy
    elif shortcut == "Mes Anterior":
        fin = hoy.replace(day=1) - datetime.timedelta(days=1)
        return fin.replace(day=1), fin
    elif shortcut == "Este Año":
        return hoy.replace(month=1, day=1), hoy
    elif shortcut == "Últimos 3 Años":
        return hoy.replace(year=hoy.year - 3, month=1, day=1), hoy
    elif shortcut == "Últimos 5 Años":
        return hoy.replace(year=hoy.year - 5, month=1, day=1), hoy
    elif shortcut == "Todo":
        return datetime.date(2000, 1, 1), hoy
    else:
        return hoy.replace(month=1, day=1), hoy


def fmt_ar(d) -> str:
    if d is None:
        return ""
    return d.strftime("%d/%m/%Y")


def fmt_num_ar(val, decimals=2) -> str:
    if pd.isna(val) or val == 0:
        return "-"
    try:
        s = f"{val:,.{decimals}f}"
        return s.replace(",", "MILLES").replace(".", ",").replace("MILLES", ".")
    except Exception:
        return str(val)


# ══════════════════════════════════════════════════════════════════════════════
#  RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_gestion_dashboard():

    # ── CSS Premium — NO pisa el sidebar de Streamlit ─────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* Encabezado */
    .gestion-header {
        font-family: 'Inter', sans-serif;
        font-size: 2.2rem; font-weight: 800;
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 55%, #c084fc 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 2px; line-height: 1.2;
    }
    .gestion-sub { color: #64748b; font-size: 0.9rem; margin-bottom: 18px; }

    /* KPIs */
    .kpi-card {
        background: linear-gradient(145deg, #0f172a, #1e293b);
        border: 1px solid #1e3a5f; border-radius: 16px;
        padding: 20px 24px; margin-bottom: 14px;
        transition: transform 0.2s ease, border-color 0.25s ease, box-shadow 0.2s ease;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    }
    .kpi-card:hover { transform: translateY(-4px); border-color: #38bdf8;
                      box-shadow: 0 8px 24px rgba(56,189,248,0.15); }
    .kpi-icon  { font-size: 1.4rem; margin-bottom: 4px; }
    .kpi-title { color: #64748b; font-size: 0.72rem; font-weight: 700;
                 text-transform: uppercase; letter-spacing: 0.08em; margin: 0; }
    .kpi-value { color: #f1f5f9; font-size: 1.65rem; font-weight: 700; margin: 4px 0 2px 0;
                 letter-spacing: -0.02em; }
    .kpi-sub   { color: #10b981; font-size: 0.72rem; margin: 0; font-weight: 500; }

    /* Títulos de sección */
    .section-title {
        font-family: 'Inter', sans-serif; font-size: 1rem; font-weight: 700;
        color: #e2e8f0; margin: 24px 0 12px 0;
        border-left: 3px solid #38bdf8; padding-left: 12px;
        letter-spacing: 0.01em;
    }

    /* Panel config cuadro dinámico */
    .config-panel {
        background: linear-gradient(135deg, #0f172a 0%, #131f35 100%);
        border: 1px solid #1e3a5f; border-radius: 14px;
        padding: 20px 24px; margin-bottom: 16px;
    }
    .dim-chip {
        display: inline-flex; align-items: center; gap: 6px;
        background: linear-gradient(135deg, #1d4ed8, #4f46e5);
        color: #e0f2fe; font-size: 0.8rem; font-weight: 600;
        padding: 4px 12px; border-radius: 20px; margin: 3px 4px 3px 0;
        box-shadow: 0 2px 8px rgba(79,70,229,0.3);
    }
    .dim-badge {
        background: rgba(255,255,255,0.15); color: white;
        border-radius: 50%; width: 18px; height: 18px;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 0.7rem; font-weight: 800;
    }

    /* Panel IA */
    .ia-panel {
        background: radial-gradient(circle at top left, #1e1b4b 0%, #0f172a 100%);
        border: 1px solid #3730a3; border-radius: 18px;
        padding: 28px; margin-top: 28px;
        box-shadow: 0 12px 40px rgba(79,70,229,0.15);
    }

    /* Tabla dinámica */
    .pivot-container {
        border: 1px solid #1e3a5f; border-radius: 12px;
        overflow: hidden; margin-top: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Encabezado ─────────────────────────────────────────────────────────────
    st.markdown('<h1 class="gestion-header">📊 Análisis de Gestión</h1>', unsafe_allow_html=True)
    st.markdown('<p class="gestion-sub">Cuadro dinámico de ventas · Motor IA · Filtros ágiles</p>', unsafe_allow_html=True)

    if supabase is None:
        st.error("⚠️ Sin conexión a la base de datos.")
        return

    total_bd = get_total_count()

    # ══════════════════════════════════════════════════════════════════════════
    #  SIDEBAR — FILTROS
    # ══════════════════════════════════════════════════════════════════════════
    with st.sidebar:
        st.markdown("### 🔍 Filtros de Gestión")
        st.caption(f"Base total: {total_bd:,} registros")
        st.markdown("---")

        # ── Selector de período (combo único) ────────────────────────────────
        st.markdown("**📅 Período**")

        # Inicializar estado
        if "fecha_atajo" not in st.session_state:
            st.session_state["fecha_atajo"] = "Mes Actual"
        if "fecha_desde" not in st.session_state or "fecha_hasta" not in st.session_state:
            d0, d1 = date_range_for_shortcut("Mes Actual")
            st.session_state["fecha_desde"] = d0
            st.session_state["fecha_hasta"] = d1

        # Índice actual en la lista
        try:
            idx_actual = ATAJOS.index(st.session_state["fecha_atajo"])
        except ValueError:
            idx_actual = 0

        sel_atajo = st.selectbox(
            "Período",
            options=ATAJOS,
            index=idx_actual,
            key="sel_atajo_periodo",
            label_visibility="collapsed",
        )

        # Actualizar fechas si cambia el atajo (y no es manual)
        if sel_atajo != "Ingresar fecha manualmente":
            if sel_atajo != st.session_state.get("fecha_atajo"):
                d0, d1 = date_range_for_shortcut(sel_atajo)
                st.session_state["fecha_desde"] = d0
                st.session_state["fecha_hasta"] = d1
            st.session_state["fecha_atajo"] = sel_atajo
            fecha_desde = st.session_state["fecha_desde"]
            fecha_hasta = st.session_state["fecha_hasta"]
            st.caption(f"📆 {fmt_ar(fecha_desde)} → {fmt_ar(fecha_hasta)}")
        else:
            # Modo manual: mostrar calendarios
            st.session_state["fecha_atajo"] = "Ingresar fecha manualmente"
            st.markdown("*Seleccioná las fechas:*")
            fecha_desde = st.date_input(
                "Desde",
                value=st.session_state.get("fecha_desde", datetime.date.today().replace(day=1)),
                key="cal_fecha_desde",
                format="DD/MM/YYYY",
            )
            fecha_hasta = st.date_input(
                "Hasta",
                value=st.session_state.get("fecha_hasta", datetime.date.today()),
                key="cal_fecha_hasta",
                format="DD/MM/YYYY",
            )
            st.session_state["fecha_desde"] = fecha_desde
            st.session_state["fecha_hasta"] = fecha_hasta
            if fecha_desde > fecha_hasta:
                st.warning("⚠️ La fecha desde es posterior a la fecha hasta.")

        st.markdown("---")

        # ── Filtros Adicionales ───────────────────────────────────────────────
        # Los obtenemos de los datos ya cargados (se cargan después)
        # Los guardamos como placeholders por ahora
        st.markdown("**Otros filtros** *(se aplican sobre los datos del período)*")

        sel_empresa  = st.multiselect("🏢 Empresa",    [], key="fil_empresa",  placeholder="Todas las empresas")
        sel_vendedor = st.multiselect("👤 Vendedor",   [], key="fil_vendedor", placeholder="Todos los vendedores")
        sel_rubro    = st.multiselect("📦 Rubro",      [], key="fil_rubro",    placeholder="Todos los rubros")
        sel_form     = st.multiselect("📄 Formulario", [], key="fil_form",     placeholder="Todos los formularios")
        sel_prov     = st.multiselect("🗺️ Provincia",  [], key="fil_prov",     placeholder="Todas las provincias")

    # ══════════════════════════════════════════════════════════════════════════
    #  CARGA DE DATOS SEGÚN PERÍODO SELECCIONADO
    # ══════════════════════════════════════════════════════════════════════════
    fecha_desde_iso = fecha_desde.strftime("%Y-%m-%d")
    fecha_hasta_iso = fecha_hasta.strftime("%Y-%m-%d")

    with st.spinner(f"⏳ Cargando ventas {fmt_ar(fecha_desde)} → {fmt_ar(fecha_hasta)}..."):
        df = load_sales_range(fecha_desde_iso, fecha_hasta_iso)

    if df.empty:
        st.warning("📭 No hay ventas en el período seleccionado.")
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.info(f"**Período:** {fmt_ar(fecha_desde)} → {fmt_ar(fecha_hasta)}")
        with col_info2:
            st.info(f"**Total en base de datos:** {total_bd:,} registros")
        _render_uploader()
        return

    # ── Actualizar filtros del sidebar con valores reales del período ─────────
    # (Streamlit no permite modificar widgets ya renderizados, pero podemos mostrar
    #  la info de opciones disponibles como texto complementario)

    # Aplicar filtros adicionales si el usuario seleccionó algo
    df_filtrado = df.copy()
    if sel_empresa:
        df_filtrado = df_filtrado[df_filtrado["empresa"].isin(sel_empresa)]
    if sel_vendedor:
        df_filtrado = df_filtrado[df_filtrado["vendedo"].isin(sel_vendedor)]
    if sel_rubro:
        df_filtrado = df_filtrado[df_filtrado["rubro"].isin(sel_rubro)]
    if sel_form:
        df_filtrado = df_filtrado[df_filtrado["formulario"].isin(sel_form)]
    if sel_prov:
        df_filtrado = df_filtrado[df_filtrado["provincia"].isin(sel_prov)]

    if df_filtrado.empty:
        st.info("📭 Los filtros adicionales no devuelven resultados. Revisá las selecciones.")
        return

    # ══════════════════════════════════════════════════════════════════════════
    #  KPIs
    # ══════════════════════════════════════════════════════════════════════════
    total_impo     = df_filtrado["impo"].sum()
    total_bultos   = df_filtrado["bultos"].sum()
    total_unidades = df_filtrado["unidades"].sum() if "unidades" in df_filtrado.columns else 0
    cant_clientes  = df_filtrado["cod_clien"].nunique()
    cant_registros = len(df_filtrado)

    k1, k2, k3, k4, k5 = st.columns(5)

    def _kpi(col, title, value, sub=""):
        col.markdown(f"""
        <div class="kpi-card">
            <p class="kpi-title">{title}</p>
            <p class="kpi-value">{value}</p>
            <p class="kpi-sub">{sub}</p>
        </div>""", unsafe_allow_html=True)

    _kpi(k1, "💰 Impo Neto",    f"$ {fmt_num_ar(total_impo, 2)}",  f"{fmt_ar(fecha_desde)} → {fmt_ar(fecha_hasta)}")
    _kpi(k2, "📦 Bultos",       fmt_num_ar(total_bultos, 2),        f"{cant_registros:,} ítems")
    _kpi(k3, "🔢 Unidades",     fmt_num_ar(total_unidades, 0),      "Unidades despachadas")
    _kpi(k4, "🤝 Clientes",     f"{cant_clientes:,}",               "Clientes únicos")
    _kpi(k5, "📋 Comprobantes", f"{df_filtrado['numero'].nunique():,}", "Números únicos")

    # Info de disponibilidad de filtros adicionales
    with st.expander("ℹ️ Valores disponibles para filtros adicionales en este período"):
        fc1, fc2, fc3, fc4, fc5 = st.columns(5)
        def _list_vals(col, label, series):
            vals = sorted(series.dropna().unique().tolist())
            col.markdown(f"**{label}** ({len(vals)})")
            col.caption(" · ".join(str(v) for v in vals[:20]) + ("..." if len(vals) > 20 else ""))
        _list_vals(fc1, "Empresas",    df_filtrado["empresa"])
        _list_vals(fc2, "Vendedores",  df_filtrado["vendedo"])
        _list_vals(fc3, "Rubros",      df_filtrado["rubro"])
        _list_vals(fc4, "Formularios", df_filtrado["formulario"])
        _list_vals(fc5, "Provincias",  df_filtrado["provincia"])

    # ══════════════════════════════════════════════════════════════════════════
    #  CONFIGURACIÓN DEL CUADRO DINÁMICO
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-title">⚙️ Configuración del Cuadro Dinámico</p>', unsafe_allow_html=True)
    st.markdown('<div class="config-panel">', unsafe_allow_html=True)

    label_list = list(DIMENSIONES_DISPONIBLES.values())
    map_label_to_field = {v: k for k, v in DIMENSIONES_DISPONIBLES.items()}

    col_cfg1, col_cfg2, col_cfg3 = st.columns([4, 2, 2])

    with col_cfg1:
        st.markdown("##### 📂 Agrupación de Filas *(izq → der)*")
        default_row_labels = [DIMENSIONES_DISPONIBLES[d] for d in DEFAULT_ROW_DIMS if d in DIMENSIONES_DISPONIBLES]
        sel_row_labels = st.multiselect(
            "Dimensiones de fila",
            options=label_list,
            default=default_row_labels,
            key="pivot_row_dims",
            label_visibility="collapsed",
            help="Elegí los campos para agrupar las filas. Se aplican de izquierda a derecha.",
        )

    with col_cfg2:
        st.markdown("##### 📊 Bandas de Columna")
        default_col_labels = [DIMENSIONES_DISPONIBLES[d] for d in DEFAULT_COL_DIMS if d in DIMENSIONES_DISPONIBLES]
        sel_col_labels = st.multiselect(
            "Bandas de columna",
            options=["Año", "Mes"],
            default=default_col_labels,
            key="pivot_col_dims",
            label_visibility="collapsed",
            help="Activá Año y/o Mes para crear columnas dinámicas de período.",
        )

    with col_cfg3:
        st.markdown("##### 💹 Métricas")
        sel_metrics_labels = st.multiselect(
            "Métricas",
            options=list(METRICAS.values()),
            default=list(METRICAS.values()),
            key="pivot_metrics",
            label_visibility="collapsed",
        )

    # ── Reorden visual de dimensiones de fila ─────────────────────────────────
    if sel_row_labels:
        current_set = set(sel_row_labels)
        if "pivot_row_order" not in st.session_state or set(st.session_state["pivot_row_order"]) != current_set:
            st.session_state["pivot_row_order"] = list(sel_row_labels)
        ordered = st.session_state["pivot_row_order"]
        ordered = [x for x in ordered if x in current_set]
        for x in sel_row_labels:
            if x not in ordered:
                ordered.append(x)
        st.session_state["pivot_row_order"] = ordered

        st.markdown("---")
        st.markdown("**🔀 Orden de agrupación** — Usá los botones para reordenar:")

        # Mostrar chips con número de orden + botones compactos
        chips_html = "".join(
            f'<span class="dim-chip"><span class="dim-badge">{i+1}</span> {lbl}</span>'
            for i, lbl in enumerate(ordered)
        )
        st.markdown(chips_html, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # Botones de reorden en una sola fila compacta
        n = len(ordered)
        btn_cols = st.columns(n * 3 + 1)
        moved = False
        for i in range(n):
            base = i * 3
            btn_cols[base].markdown(f"<small style='color:#94a3b8'>{ordered[i][:8]}</small>", unsafe_allow_html=True)
            if i > 0:
                if btn_cols[base + 1].button("⬅", key=f"ml_{i}", help=f"Mover '{ordered[i]}' a la izquierda"):
                    ordered[i - 1], ordered[i] = ordered[i], ordered[i - 1]
                    moved = True
            if i < n - 1:
                if btn_cols[base + 2].button("➡", key=f"mr_{i}", help=f"Mover '{ordered[i]}' a la derecha"):
                    ordered[i + 1], ordered[i] = ordered[i], ordered[i + 1]
                    moved = True
        if moved:
            st.session_state["pivot_row_order"] = ordered
            st.rerun()

        sel_row_labels = st.session_state["pivot_row_order"]

    st.markdown('</div>', unsafe_allow_html=True)

    row_dims_fields = [map_label_to_field[l] for l in sel_row_labels if l in map_label_to_field]
    col_dims_fields = [map_label_to_field[l] for l in sel_col_labels if l in map_label_to_field]
    metrics_inv     = {v: k for k, v in METRICAS.items()}
    metrics_fields  = [metrics_inv[l] for l in sel_metrics_labels if l in metrics_inv]

    # ══════════════════════════════════════════════════════════════════════════
    #  CUADRO DINÁMICO
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-title">📋 Cuadro Dinámico de Ventas</p>', unsafe_allow_html=True)

    if not row_dims_fields:
        st.info("Seleccioná al menos una dimensión de fila para generar el cuadro.")
    elif not metrics_fields:
        st.info("Seleccioná al menos una métrica.")
    else:
        with st.spinner("Construyendo cuadro dinámico..."):
            valid_row = [r for r in row_dims_fields if r in df_filtrado.columns]
            valid_col = [c for c in col_dims_fields if c in df_filtrado.columns]
            valid_met = [m for m in metrics_fields if m in df_filtrado.columns]

            if not valid_row or not valid_met:
                st.warning("Alguna dimensión o métrica seleccionada no está disponible en los datos del período.")
            else:
                try:
                    pt = pd.pivot_table(
                        df_filtrado,
                        index=valid_row,
                        columns=valid_col if valid_col else None,
                        values=valid_met,
                        aggfunc="sum",
                        margins=True,
                        margins_name="▌ TOTAL",
                        observed=True,
                        fill_value=0,
                    )

                    # Renombrar columnas — compatible pandas 1.x y 2.x
                    if isinstance(pt.columns, pd.MultiIndex):
                        new_cols = []
                        for col_tuple in pt.columns:
                            m_label = METRICAS.get(col_tuple[0], col_tuple[0])
                            rest = " | ".join(str(x) for x in col_tuple[1:])
                            new_cols.append(f"{rest} | {m_label}" if rest else m_label)
                        pt.columns = new_cols
                    else:
                        pt.columns = [METRICAS.get(c, c) for c in pt.columns]

                    # Renombrar índices
                    pt.index.names = [DIMENSIONES_DISPONIBLES.get(str(n), str(n)) for n in pt.index.names]

                    # Formatear números argentinos — compatible pandas 2.x (map en lugar de applymap)
                    def _fmt_cell(x):
                        if isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool):
                            return fmt_num_ar(x, 2)
                        return x

                    try:
                        # pandas >= 2.1
                        pt_display = pt.map(_fmt_cell)
                    except AttributeError:
                        # pandas < 2.1 fallback
                        pt_display = pt.applymap(_fmt_cell)

                    st.markdown('<div class="pivot-container">', unsafe_allow_html=True)
                    st.dataframe(
                        pt_display,
                        use_container_width=True,
                        height=min(600, max(200, len(pt_display) * 35 + 60)),
                    )
                    st.markdown('</div>', unsafe_allow_html=True)

                    # Barra de info
                    ic1, ic2, ic3, ic4 = st.columns(4)
                    ic1.metric("Registros",    f"{cant_registros:,}")
                    ic2.metric("Clientes",     f"{cant_clientes:,}")
                    ic3.metric("Comprobantes", f"{df_filtrado['numero'].nunique():,}")
                    ic4.metric("Filas tabla",  f"{len(pt_display) - 1:,}")

                except Exception as e:
                    st.error(f"Error generando el cuadro dinámico: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    # ══════════════════════════════════════════════════════════════════════════
    #  CARGA HISTÓRICA
    # ══════════════════════════════════════════════════════════════════════════
    _render_uploader()

    # ══════════════════════════════════════════════════════════════════════════
    #  GEMINI BRAIN
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="ia-panel">', unsafe_allow_html=True)
    st.markdown(
        "<h2 style='color:#a5b4fc; margin-top:0; font-family:Inter,sans-serif;'>"
        "🧠 Gemini Brain — Consultor Estratégico de Ventas</h2>",
        unsafe_allow_html=True,
    )
    st.write(
        "El motor de IA analiza **toda la tabla de ventas** (independientemente de los filtros activos) "
        "y responde consultas estratégicas con datos reales."
    )

    if not api_key:
        st.info("🔑 Configurá `GOOGLE_API_KEY` en `secrets.toml` para habilitar el Gemini Brain.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Contexto de TODA la tabla (independiente de filtros UI)
    with st.spinner("Preparando contexto histórico completo para el Brain..."):
        df_ia = load_sales_full_for_ia()

    if df_ia.empty:
        st.warning("No se pudo cargar el contexto histórico.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    @st.cache_data(ttl=1800, show_spinner=False)
    def _build_ctx(n_rows: int) -> str:
        ctx = df_ia.groupby(
            ["_año", "_mes", "vendedo", "rubro", "provincia", "formulario"],
            observed=True,
        ).agg(
            impo_neto=("impo", "sum"),
            bultos=("bultos", "sum"),
            cant_items=("impo", "count"),
            clientes=("cod_clien", "nunique"),
        ).reset_index().sort_values("impo_neto", ascending=False).head(200)
        return ctx.to_string(index=False)

    context_str = _build_ctx(len(df_ia))

    kpi_g = {
        "impo_total":   df_ia["impo"].sum(),
        "bultos_total": df_ia["bultos"].sum(),
        "clientes":     df_ia["cod_clien"].nunique(),
        "registros":    len(df_ia),
        "fecha_min":    df_ia["fecha"].min().strftime("%d/%m/%Y") if not df_ia.empty else "N/A",
        "fecha_max":    df_ia["fecha"].max().strftime("%d/%m/%Y") if not df_ia.empty else "N/A",
    }

    ia1, ia2, ia3, ia4 = st.columns(4)
    prompt_ia = None
    if ia1.button("📊 Informe Ejecutivo",      use_container_width=True, key="ia_btn1"):
        prompt_ia = "Generá un informe ejecutivo de alto nivel resumiendo el comportamiento comercial histórico: vendedores líderes, rubros principales, evolución por año y sugerencias estratégicas."
    if ia2.button("🚨 Alertas de Desvíos",     use_container_width=True, key="ia_btn2"):
        prompt_ia = "Detectá alertas comerciales: ¿hay excesiva dependencia en algún vendedor, rubro o provincia? ¿Hay períodos de caída marcada? ¿Concentración de clientes?"
    if ia3.button("💡 Plan Comercial",         use_container_width=True, key="ia_btn3"):
        prompt_ia = "Proponé 3 iniciativas comerciales concretas para expandir la facturación basándote en la distribución actual de ventas por región, rubro y vendedor."
    if ia4.button("📈 Tendencias y Estación.", use_container_width=True, key="ia_btn4"):
        prompt_ia = "Analizá las tendencias de crecimiento o decrecimiento mensual/anual. ¿Qué meses son los pico? ¿Hay estacionalidad marcada? ¿Qué año fue el mejor?"

    pregunta_libre = st.text_input(
        "💬 Hacé una consulta personalizada sobre toda la base de ventas:",
        placeholder="Ej: ¿Qué vendedor tuvo mejor performance en 2025? ¿Cuál fue el mes con más bultos?",
        key="ia_pregunta_libre",
    )
    prompt_final = prompt_ia if prompt_ia else pregunta_libre

    if prompt_final:
        prompt_completo = f"""
ERES EL CONSULTOR ESTRATÉGICO DE VENTAS DE LA EMPRESA "MP" (MESSINA & PASINA).
ANALIZAS LA SIGUIENTE TABLA DE RESUMEN HISTÓRICO AGREGADO Y RESPONDÉS CON PROPUESTAS PRÁCTICAS, NÚMEROS CLAVE Y TONALIDAD CORPORATIVA PROFESIONAL.

TABLA DE VENTAS HISTÓRICAS (Top 200 combinaciones por importe, campos: Año | Mes | Vendedor | Rubro | Provincia | Formulario | Impo Neto | Bultos | Cant. Ítems | Clientes Únicos):
{context_str}

KPIs GLOBALES DE TODA LA BASE (sin filtros):
- Facturación Total Histórica: $ {kpi_g['impo_total']:,.2f}
- Bultos Totales: {kpi_g['bultos_total']:,.0f}
- Clientes Únicos Históricos: {kpi_g['clientes']:,}
- Total de Registros: {kpi_g['registros']:,}
- Período: {kpi_g['fecha_min']} → {kpi_g['fecha_max']}

NOTA: Los registros con importe negativo son devoluciones (DEVOLUCION B). El impo_neto ya refleja el neto.

CONSULTA DEL USUARIO: "{prompt_final}"

Respondé con formato markdown enriquecido (negritas, listas, subtítulos con ##, tablas si aplica).
Sé directo, ejecutivo y aportá valor real con números concretos extraídos de los datos.
        """
        with st.spinner("🧠 Gemini está analizando toda la base de ventas..."):
            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt_completo)
                st.markdown("---")
                st.markdown("### 📋 Respuesta del Consultor Estratégico:")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error al procesar con IA: {e}")

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  CARGA HISTÓRICA (auxiliar)
# ══════════════════════════════════════════════════════════════════════════════

def _render_uploader():
    with st.expander("📤 Carga Histórica de Ventas (ventas.dbi)"):
        st.write(
            "Subí un archivo `ventas.dbi` histórico para importarlo de forma incremental en Supabase. "
            "El sistema evita duplicados usando la restricción única de la base de datos."
        )
        uploaded_file = st.file_uploader(
            "Seleccioná el archivo ventas.dbi",
            type=["dbi"],
            key="uploader_ventas_v3",
        )
        if uploaded_file is not None:
            if st.button("🚀 Iniciar Procesamiento e Importación", use_container_width=True, key="btn_import_v3"):
                import os
                temp_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
                )
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, "temp_ventas_hist.dbi")

                with open(temp_path, "wb") as f_t:
                    f_t.write(uploaded_file.getbuffer())

                try:
                    import dbf

                    def _s(v):  return str(v).strip() if v else ""
                    def _i(v):
                        try: return int(v)
                        except: return 0
                    def _f(v):
                        try: return float(v)
                        except: return 0.0
                    def _d(v):
                        if not v: return None
                        if isinstance(v, (datetime.date, datetime.datetime)):
                            return v.strftime("%Y-%m-%d")
                        s = str(v).strip()
                        if len(s) >= 10 and s[4] == "-": return s[:10]
                        try:
                            p = s.split("/")
                            if len(p) == 3: return f"{p[2].zfill(4)}-{p[1].zfill(2)}-{p[0].zfill(2)}"
                        except: pass
                        return None

                    def _memo(path):
                        base = os.path.splitext(path)[0]
                        for ext in [".dbt", ".fpt", ".DBT", ".FPT"]:
                            p = base + ext
                            if not os.path.exists(p):
                                try:
                                    with open(p, "wb") as f:
                                        if ext.lower() == ".dbt":
                                            f.write(b"\x01\x00\x00\x00" + b"\x00" * 508)
                                        else:
                                            f.write(b"\x00\x00\x00\x01\x00\x00\x00\x40" + b"\x00" * 504)
                                except: pass

                    _memo(temp_path)

                    total_rec = 0
                    with dbf.Table(temp_path, codepage="cp1252") as t:
                        t.open()
                        if t._meta.memo:
                            _o = t._meta.memo.get_memo
                            def _sg(b):
                                try: return _o(b)
                                except: return b""
                            t._meta.memo.get_memo = _sg
                        total_rec = len(t)

                    st.info(f"Detectados {total_rec:,} registros. Iniciando importación...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    batch_dict = {}
                    batch_size = 1000
                    total_proc = 0

                    with dbf.Table(temp_path, codepage="cp1252") as t:
                        t.open()
                        if t._meta.memo:
                            _o = t._meta.memo.get_memo
                            def _sg(b):
                                try: return _o(b)
                                except: return b""
                            t._meta.memo.get_memo = _sg

                        for rec in t:
                            fd = _d(rec.FECHA)
                            if not fd: continue
                            item = {
                                "rubro": _s(rec.RUBRO), "fecha": fd,
                                "empresa": _s(rec.EMPRESA), "subrubro": _s(rec.SUBRUBRO),
                                "numero": _i(rec.NUMERO), "localidad": _s(rec.LOCALIDAD),
                                "provincia": _s(rec.PROVINCIA), "formulario": _s(rec.FORMULARIO),
                                "e_mail": _s(rec.E_MAIL), "telefono": _s(rec.TELEFONO),
                                "pais": _s(rec.PAIS), "codigo": _i(rec.CODIGO),
                                "cod_alfa": _s(rec.COD_ALFA), "unidades": _f(rec.UNIDADES),
                                "codigocomp": _i(rec.CODIGOCOMP), "tipo": _i(rec.TIPO),
                                "dto": _f(rec.DTO), "dto1": _f(rec.DTO1), "dto2": _f(rec.DTO2),
                                "alt_bonifi": _s(rec.ALT_BONIFI), "grupo": _s(rec.GRUPO),
                                "sinonimo": _s(rec.SINONIMO), "ean": _s(rec.EAN),
                                "clien": _s(rec.CLIEN), "cod_clien": _i(rec.COD_CLIEN),
                                "producto": _s(rec.PRODUCTO), "vendedo": _s(rec.VENDEDO),
                                "domicilio": _s(rec.DOMICILIO), "deposito": _s(rec.DEPOSITO),
                                "bultos": _f(rec.BULTOS), "impo": _f(rec.IMPO),
                            }
                            key = (item["fecha"], item["empresa"], item["formulario"],
                                   item["numero"], item["cod_clien"], item["cod_alfa"], item["bultos"])
                            batch_dict[key] = item

                            if len(batch_dict) >= batch_size:
                                supabase.table("ventas").upsert(
                                    list(batch_dict.values()),
                                    on_conflict="fecha,empresa,formulario,numero,cod_clien,cod_alfa,bultos"
                                ).execute()
                                total_proc += len(batch_dict)
                                status_text.text(f"Importados: {total_proc:,} / {total_rec:,}")
                                progress_bar.progress(min(1.0, total_proc / total_rec))
                                batch_dict = {}

                        if batch_dict:
                            supabase.table("ventas").upsert(
                                list(batch_dict.values()),
                                on_conflict="fecha,empresa,formulario,numero,cod_clien,cod_alfa,bultos"
                            ).execute()
                            total_proc += len(batch_dict)
                            progress_bar.progress(1.0)
                            status_text.text(f"Completado: {total_proc:,} registros importados.")

                    st.success(f"🎉 ¡Importación exitosa! {total_proc:,} registros procesados.")
                    load_sales_range.clear()
                    load_sales_full_for_ia.clear()
                    st.rerun()

                except Exception as e:
                    import traceback
                    st.error(f"Error procesando el archivo: {e}")
                    st.code(traceback.format_exc())
                finally:
                    if os.path.exists(temp_path):
                        try: os.remove(temp_path)
                        except: pass
                    base = os.path.splitext(temp_path)[0]
                    for ext in [".dbt", ".fpt"]:
                        p = base + ext
                        if os.path.exists(p):
                            try: os.remove(p)
                            except: pass
