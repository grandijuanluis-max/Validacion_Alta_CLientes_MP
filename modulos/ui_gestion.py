import streamlit as st
import pandas as pd
import numpy as np
import datetime
from modulos.db import supabase

# ── Gemini ───────────────────────────────────────────────────────────────────
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

# Mapa campo_db → etiqueta visual
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

DEFAULT_ROW_DIMS  = ["rubro", "subrubro", "vendedo", "clien", "producto"]
DEFAULT_COL_DIMS  = ["_año", "_mes"]   # dimensiones de banda columna
METRICAS          = {"impo": "IMPO NETO", "bultos": "BULTOS"}

# ══════════════════════════════════════════════════════════════════════════════
#  CARGA DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def load_sales_full() -> pd.DataFrame:
    """Carga TODOS los registros de ventas de Supabase con paginación."""
    if supabase is None:
        return pd.DataFrame()
    try:
        PAGE = 10_000
        offset = 0
        frames = []
        cols = (
            "fecha, empresa, formulario, numero, rubro, subrubro, grupo, "
            "localidad, provincia, unidades, ean, clien, cod_clien, producto, "
            "sinonimo, vendedo, domicilio, deposito, bultos, impo"
        )
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
        df["fecha"]     = pd.to_datetime(df["fecha"], errors="coerce")
        df["impo"]      = pd.to_numeric(df["impo"],      errors="coerce").fillna(0.0)
        df["bultos"]    = pd.to_numeric(df["bultos"],    errors="coerce").fillna(0.0)
        df["unidades"]  = pd.to_numeric(df["unidades"],  errors="coerce").fillna(0.0)
        df["cod_clien"] = pd.to_numeric(df["cod_clien"], errors="coerce").fillna(0).astype(int)

        # Columnas derivadas de fecha
        df["_año"] = df["fecha"].dt.year.astype("Int64").astype(str)
        df["_mes"] = df["fecha"].dt.month.astype("Int64").astype(str).str.zfill(2)

        # Limpiar strings vacíos → "(Vacío)"
        str_cols = ["empresa", "rubro", "subrubro", "grupo", "vendedo",
                    "formulario", "deposito", "provincia", "localidad",
                    "clien", "producto", "sinonimo", "ean"]
        for c in str_cols:
            if c in df.columns:
                df[c] = df[c].fillna("").str.strip()
                df[c] = df[c].replace("", "(Vacío)")

        return df

    except Exception as e:
        st.error(f"Error cargando ventas: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def get_unique_values(col: str) -> list:
    """Obtiene valores únicos de una columna para los filtros."""
    if supabase is None:
        return []
    try:
        res = supabase.table("ventas").select(col).execute()
        vals = pd.DataFrame(res.data)[col].dropna().unique().tolist()
        vals = sorted([str(v).strip() for v in vals if str(v).strip()])
        return vals
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES DE FECHA
# ══════════════════════════════════════════════════════════════════════════════

def date_range_for_shortcut(shortcut: str):
    """Devuelve (desde, hasta) para cada atajo de fecha."""
    hoy = datetime.date.today()
    if shortcut == "Hoy":
        return hoy, hoy
    elif shortcut == "Ayer":
        ayer = hoy - datetime.timedelta(days=1)
        return ayer, ayer
    elif shortcut == "Semana Actual":
        lunes = hoy - datetime.timedelta(days=hoy.weekday())
        return lunes, hoy
    elif shortcut == "Semana Anterior":
        lunes_ant = hoy - datetime.timedelta(days=hoy.weekday() + 7)
        domingo_ant = lunes_ant + datetime.timedelta(days=6)
        return lunes_ant, domingo_ant
    elif shortcut == "Mes Actual":
        inicio = hoy.replace(day=1)
        return inicio, hoy
    elif shortcut == "Mes Anterior":
        fin_mes_ant = hoy.replace(day=1) - datetime.timedelta(days=1)
        inicio_mes_ant = fin_mes_ant.replace(day=1)
        return inicio_mes_ant, fin_mes_ant
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


def fmt_date_ar(d: datetime.date) -> str:
    """Formatea fecha como dd/mm/aaaa."""
    if d is None:
        return ""
    return d.strftime("%d/%m/%Y")


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTRUCCIÓN DEL CUADRO DINÁMICO
# ══════════════════════════════════════════════════════════════════════════════

def fmt_num_ar(val, decimals=2) -> str:
    """Formato numérico argentino: punto de miles, coma decimal."""
    if pd.isna(val) or val == 0:
        return "-"
    try:
        s = f"{val:,.{decimals}f}"
        # Reemplazar separadores: , → _ temporal → .  y  . → ,
        s = s.replace(",", "MILLES").replace(".", ",").replace("MILLES", ".")
        return s
    except Exception:
        return str(val)


def build_hierarchical_table(
    df: pd.DataFrame,
    row_dims: list[str],
    col_dims: list[str],
    metrics: list[str],
) -> pd.DataFrame:
    """
    Construye la tabla dinámica agrupada con subtotales jerárquicos.
    
    - row_dims: campos de agrupación de filas (izq → der)
    - col_dims: campos de banda de columna (ej: ['_año', '_mes'])
    - metrics:  lista de campos a sumar (ej: ['impo', 'bultos'])
    
    Retorna un DataFrame formateado listo para mostrar.
    """
    if df.empty or not row_dims:
        return pd.DataFrame()

    # Si hay dimensiones de columna, hacemos pivot
    if col_dims:
        all_group = row_dims + col_dims
        # Asegurarnos que todas las columnas existen
        valid_group = [c for c in all_group if c in df.columns]
        valid_metrics = [m for m in metrics if m in df.columns]
        if not valid_metrics:
            return pd.DataFrame()

        agg = df.groupby(valid_group, observed=True)[valid_metrics].sum().reset_index()

        # Construir tabla con subtotales por jerarquía de filas
        result_frames = []
        result_frames.append(_build_level_subtotals(agg, row_dims, col_dims, valid_metrics))
        if result_frames:
            final = result_frames[0]
        else:
            final = pd.DataFrame()
        return final

    else:
        # Sin bandas de columna: tabla plana agrupada
        valid_group = [c for c in row_dims if c in df.columns]
        valid_metrics = [m for m in metrics if m in df.columns]
        if not valid_metrics:
            return pd.DataFrame()

        agg = df.groupby(valid_group, observed=True)[valid_metrics].sum().reset_index()
        return _add_row_subtotals_flat(agg, row_dims, valid_metrics)


def _build_level_subtotals(
    agg: pd.DataFrame,
    row_dims: list[str],
    col_dims: list[str],
    metrics: list[str],
) -> pd.DataFrame:
    """
    Genera tabla jerárquica con subtotales, pivotada por col_dims.
    Retorna un DataFrame con MultiIndex de columnas aplanado.
    """
    all_col_vals = {}
    for cd in col_dims:
        if cd in agg.columns:
            all_col_vals[cd] = sorted(agg[cd].dropna().unique().tolist())

    def pivot_slice(df_slice: pd.DataFrame, group_keys: dict) -> pd.Series:
        """Pivota un slice del df y retorna una Serie con columnas (col_val, metric)."""
        data = {}
        # Total general
        for m in metrics:
            data[("Totales", METRICAS.get(m, m))] = df_slice[m].sum()
        # Por cada combinación de col_dims
        if col_dims and col_dims[0] in df_slice.columns:
            grp_cols = [c for c in col_dims if c in df_slice.columns]
            for _, sub in df_slice.groupby(grp_cols, observed=True):
                if isinstance(sub, pd.DataFrame):
                    col_key = tuple(sub[c].iloc[0] for c in grp_cols) if len(grp_cols) > 1 else sub[grp_cols[0]].iloc[0]
                else:
                    col_key = sub[grp_cols[0]].iloc[0]
                col_key_str = str(col_key)
                for m in metrics:
                    data[(col_key_str, METRICAS.get(m, m))] = sub[m].sum()
        return pd.Series(data)

    rows = []

    def recurse(df_sub: pd.DataFrame, level: int, prefix_vals: list):
        if level >= len(row_dims):
            return

        dim = row_dims[level]
        if dim not in df_sub.columns:
            return

        for val, grp in df_sub.groupby(dim, sort=True, observed=True):
            row_info = {rd: "" for rd in row_dims}
            for i, pv in enumerate(prefix_vals):
                row_info[row_dims[i]] = pv
            row_info[dim] = str(val)

            if level == len(row_dims) - 1:
                # Hoja
                pivot_data = pivot_slice(grp, row_info)
                row_info.update(pivot_data.to_dict())
                rows.append(row_info)
            else:
                # Recursión
                recurse(grp, level + 1, prefix_vals + [str(val)])
                # Subtotal de este nivel
                subtotal_info = {rd: "" for rd in row_dims}
                for i, pv in enumerate(prefix_vals):
                    subtotal_info[row_dims[i]] = pv
                subtotal_info[dim] = f"  ∑ Totales {str(val)}"
                pivot_data = pivot_slice(grp, subtotal_info)
                subtotal_info.update(pivot_data.to_dict())
                subtotal_info["_is_subtotal"] = True
                rows.append(subtotal_info)

        # Total general de este nivel
        total_info = {rd: "" for rd in row_dims}
        for i, pv in enumerate(prefix_vals):
            total_info[row_dims[i]] = pv
        if prefix_vals:
            total_info[row_dims[level - 1]] = f"  ► TOTAL GENERAL"
        else:
            total_info[row_dims[0]] = "▌ TOTAL GENERAL"
        pivot_data = pivot_slice(df_sub, total_info)
        total_info.update(pivot_data.to_dict())
        total_info["_is_total"] = True
        rows.append(total_info)

    recurse(agg, 0, [])

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result = result.drop(columns=[c for c in ["_is_subtotal", "_is_total"] if c in result.columns], errors="ignore")
    return result


def _add_row_subtotals_flat(
    agg: pd.DataFrame,
    row_dims: list[str],
    metrics: list[str],
) -> pd.DataFrame:
    """Para el caso sin bandas de columna: agrega filas de subtotal."""
    rows = []

    def recurse(df_sub: pd.DataFrame, level: int, prefix_vals: list):
        if level >= len(row_dims):
            return
        dim = row_dims[level]
        if dim not in df_sub.columns:
            return

        for val, grp in df_sub.groupby(dim, sort=True, observed=True):
            row_info = {rd: "" for rd in row_dims}
            for i, pv in enumerate(prefix_vals):
                row_info[row_dims[i]] = pv
            row_info[dim] = str(val)

            if level == len(row_dims) - 1:
                for m in metrics:
                    row_info[METRICAS.get(m, m)] = grp[m].sum()
                rows.append(row_info)
            else:
                recurse(grp, level + 1, prefix_vals + [str(val)])
                subtotal_info = {rd: "" for rd in row_dims}
                for i, pv in enumerate(prefix_vals):
                    subtotal_info[row_dims[i]] = pv
                subtotal_info[dim] = f"  ∑ Totales {str(val)}"
                for m in metrics:
                    subtotal_info[METRICAS.get(m, m)] = grp[m].sum()
                rows.append(subtotal_info)

        total_info = {rd: "" for rd in row_dims}
        if prefix_vals:
            total_info[row_dims[level - 1]] = "  ► TOTAL GENERAL"
        else:
            total_info[row_dims[0]] = "▌ TOTAL GENERAL"
        for m in metrics:
            total_info[METRICAS.get(m, m)] = df_sub[m].sum()
        rows.append(total_info)

    recurse(agg, 0, [])
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ══════════════════════════════════════════════════════════════════════════════
#  RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def render_gestion_dashboard():
    # ── CSS Premium ──────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    .gestion-header {
        font-family: 'Inter', sans-serif;
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 60%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
    }
    .gestion-sub {
        color: #94a3b8;
        font-size: 0.92rem;
        margin-bottom: 20px;
    }
    .kpi-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 14px;
        padding: 18px 22px;
        margin-bottom: 14px;
        transition: transform 0.2s, border-color 0.2s;
    }
    .kpi-card:hover { transform: translateY(-3px); border-color: #38bdf8; }
    .kpi-title { color: #94a3b8; font-size: 0.78rem; font-weight: 600;
                 text-transform: uppercase; letter-spacing: 0.06em; margin: 0; }
    .kpi-value { color: #f1f5f9; font-size: 1.75rem; font-weight: 700;
                 margin: 6px 0 2px 0; }
    .kpi-sub   { color: #10b981; font-size: 0.76rem; margin: 0; }

    .section-title {
        font-family: 'Inter', sans-serif;
        font-size: 1.1rem; font-weight: 700;
        color: #e2e8f0; margin: 22px 0 10px 0;
        border-left: 4px solid #38bdf8; padding-left: 10px;
    }

    /* Atajos de fecha */
    .fecha-atajos-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }

    /* Panel IA */
    .ia-panel {
        background: radial-gradient(circle at top left, #1e1b4b 0%, #0f172a 100%);
        border: 1px solid #3730a3;
        border-radius: 18px;
        padding: 28px;
        margin-top: 28px;
        box-shadow: 0 12px 40px rgba(79,70,229,0.15);
    }

    /* Tabla dinámica */
    .pivot-container {
        border: 1px solid #1e293b;
        border-radius: 12px;
        overflow: hidden;
        margin-top: 10px;
    }
    /* Filas de subtotal y total */
    [data-testid="stDataFrame"] tr td:first-child { font-weight: 600; }

    /* Ajuste sidebar */
    section[data-testid="stSidebar"] { background: #0b1120 !important; }
    section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    </style>
    """, unsafe_allow_html=True)

    # ── Encabezado ───────────────────────────────────────────────────────────
    st.markdown('<h1 class="gestion-header">📊 Análisis de Gestión</h1>', unsafe_allow_html=True)
    st.markdown('<p class="gestion-sub">Cuadro dinámico de ventas · Motor IA · Filtros ágiles</p>', unsafe_allow_html=True)

    if supabase is None:
        st.error("⚠️ Sin conexión a la base de datos.")
        return

    # ── Carga de datos completa ───────────────────────────────────────────────
    with st.spinner("⏳ Cargando tabla de ventas completa..."):
        df_all = load_sales_full()

    if df_all.empty:
        st.warning("No se encontraron registros en la tabla de ventas.")
        st.info("Asegurate de que el sincronizador local haya subido los datos a Supabase.")
        _render_uploader()
        return

    total_registros = len(df_all)

    # ══════════════════════════════════════════════════════════════════════════
    #  SIDEBAR — FILTROS
    # ══════════════════════════════════════════════════════════════════════════
    with st.sidebar:
        st.markdown("### 🔍 Filtros de Gestión")
        st.caption(f"Base completa: {total_registros:,} registros")

        st.markdown("---")

        # ── Atajos de Fecha ──────────────────────────────────────────────────
        st.markdown("**📅 Período**")

        ATAJOS = [
            "Hoy", "Ayer", "Semana Actual", "Semana Anterior",
            "Mes Actual", "Mes Anterior", "Este Año",
            "Últimos 3 Años", "Últimos 5 Años", "Todo"
        ]

        if "fecha_atajo" not in st.session_state:
            st.session_state["fecha_atajo"] = "Este Año"
        if "fecha_desde" not in st.session_state or "fecha_hasta" not in st.session_state:
            d0, d1 = date_range_for_shortcut("Este Año")
            st.session_state["fecha_desde"] = d0
            st.session_state["fecha_hasta"] = d1

        # Grilla de botones de atajos (2 columnas)
        cols_atajos = st.columns(2)
        for i, atajo in enumerate(ATAJOS):
            col = cols_atajos[i % 2]
            is_active = st.session_state.get("fecha_atajo") == atajo
            label = f"✅ {atajo}" if is_active else atajo
            if col.button(label, key=f"atajo_{i}", use_container_width=True):
                st.session_state["fecha_atajo"] = atajo
                d0, d1 = date_range_for_shortcut(atajo)
                st.session_state["fecha_desde"] = d0
                st.session_state["fecha_hasta"] = d1

        st.markdown("**Desde / Hasta** *(dd/mm/aaaa)*")

        # Inputs manuales (formato dd/mm/aaaa visual)
        col_d, col_h = st.columns(2)
        with col_d:
            txt_desde = st.text_input(
                "Desde",
                value=fmt_date_ar(st.session_state.get("fecha_desde", datetime.date.today())),
                key="txt_fecha_desde",
                label_visibility="collapsed",
                placeholder="dd/mm/aaaa",
            )
        with col_h:
            txt_hasta = st.text_input(
                "Hasta",
                value=fmt_date_ar(st.session_state.get("fecha_hasta", datetime.date.today())),
                key="txt_fecha_hasta",
                label_visibility="collapsed",
                placeholder="dd/mm/aaaa",
            )

        # Parsear inputs manuales
        def parse_date_ar(s: str) -> datetime.date | None:
            s = s.strip()
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                try:
                    return datetime.datetime.strptime(s, fmt).date()
                except ValueError:
                    pass
            return None

        fecha_desde = parse_date_ar(txt_desde) or st.session_state.get("fecha_desde", datetime.date.today())
        fecha_hasta = parse_date_ar(txt_hasta) or st.session_state.get("fecha_hasta", datetime.date.today())
        st.session_state["fecha_desde"] = fecha_desde
        st.session_state["fecha_hasta"] = fecha_hasta

        st.caption(f"📆 {fmt_date_ar(fecha_desde)} → {fmt_date_ar(fecha_hasta)}")

        st.markdown("---")

        # ── Filtros Adicionales ───────────────────────────────────────────────
        st.markdown("**🏢 Empresa**")
        empresas_lista = sorted(df_all["empresa"].dropna().unique().tolist())
        sel_empresa = st.multiselect("Empresa", empresas_lista, default=[], key="fil_empresa",
                                     label_visibility="collapsed")

        st.markdown("**👤 Vendedor**")
        vendedores_lista = sorted(df_all["vendedo"].dropna().unique().tolist())
        sel_vendedor = st.multiselect("Vendedor", vendedores_lista, default=[], key="fil_vendedor",
                                      label_visibility="collapsed")

        st.markdown("**📦 Rubro**")
        rubros_lista = sorted(df_all["rubro"].dropna().unique().tolist())
        sel_rubro = st.multiselect("Rubro", rubros_lista, default=[], key="fil_rubro",
                                   label_visibility="collapsed")

        st.markdown("**📄 Formulario**")
        forms_lista = sorted(df_all["formulario"].dropna().unique().tolist())
        sel_form = st.multiselect("Formulario", forms_lista, default=[], key="fil_form",
                                  label_visibility="collapsed")

        st.markdown("**🗺️ Provincia**")
        prov_lista = sorted(df_all["provincia"].dropna().unique().tolist())
        sel_prov = st.multiselect("Provincia", prov_lista, default=[], key="fil_prov",
                                  label_visibility="collapsed")

    # ══════════════════════════════════════════════════════════════════════════
    #  APLICAR FILTROS
    # ══════════════════════════════════════════════════════════════════════════
    df = df_all.copy()

    # Filtro de fechas
    df = df[
        (df["fecha"].dt.date >= fecha_desde) &
        (df["fecha"].dt.date <= fecha_hasta)
    ]

    if sel_empresa:
        df = df[df["empresa"].isin(sel_empresa)]
    if sel_vendedor:
        df = df[df["vendedo"].isin(sel_vendedor)]
    if sel_rubro:
        df = df[df["rubro"].isin(sel_rubro)]
    if sel_form:
        df = df[df["formulario"].isin(sel_form)]
    if sel_prov:
        df = df[df["provincia"].isin(sel_prov)]

    if df.empty:
        st.info("📭 No hay ventas que coincidan con los filtros seleccionados.")
        _render_uploader()
        return

    # ══════════════════════════════════════════════════════════════════════════
    #  KPIs
    # ══════════════════════════════════════════════════════════════════════════
    total_impo     = df["impo"].sum()
    total_bultos   = df["bultos"].sum()
    total_unidades = df["unidades"].sum()
    cant_clientes  = df["cod_clien"].nunique()
    cant_registros = len(df)

    k1, k2, k3, k4, k5 = st.columns(5)
    def _kpi(col, title, value, sub=""):
        col.markdown(f"""
        <div class="kpi-card">
            <p class="kpi-title">{title}</p>
            <p class="kpi-value">{value}</p>
            <p class="kpi-sub">{sub}</p>
        </div>""", unsafe_allow_html=True)

    _kpi(k1, "💰 Impo Neto",      f"$ {fmt_num_ar(total_impo, 2)}",   f"Período: {fmt_date_ar(fecha_desde)} → {fmt_date_ar(fecha_hasta)}")
    _kpi(k2, "📦 Bultos",         fmt_num_ar(total_bultos, 2),          f"{cant_registros:,} ítems procesados")
    _kpi(k3, "🔢 Unidades",       fmt_num_ar(total_unidades, 0),        "Unidades despachadas")
    _kpi(k4, "🤝 Clientes",       f"{cant_clientes:,}",                 "Clientes únicos")
    _kpi(k5, "📋 Comprobantes",   f"{df['numero'].nunique():,}",        "Números únicos")

    # ══════════════════════════════════════════════════════════════════════════
    #  CONFIGURACIÓN DEL CUADRO DINÁMICO
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="section-title">⚙️ Configuración del Cuadro Dinámico</p>', unsafe_allow_html=True)

    dim_labels = {v: k for k, v in DIMENSIONES_DISPONIBLES.items()}  # label→campo
    label_list = list(DIMENSIONES_DISPONIBLES.values())

    col_cfg1, col_cfg2, col_cfg3 = st.columns([3, 2, 2])

    with col_cfg1:
        st.markdown("**Filas — Agrupación (izq → der)**")
        default_row_labels = [DIMENSIONES_DISPONIBLES[d] for d in DEFAULT_ROW_DIMS if d in DIMENSIONES_DISPONIBLES]
        sel_row_labels = st.multiselect(
            "Dimensiones de fila",
            options=label_list,
            default=default_row_labels,
            key="pivot_row_dims",
            label_visibility="collapsed",
        )

    with col_cfg2:
        st.markdown("**Bandas de Columna (opcional)**")
        default_col_labels = [DIMENSIONES_DISPONIBLES[d] for d in DEFAULT_COL_DIMS if d in DIMENSIONES_DISPONIBLES]
        sel_col_labels = st.multiselect(
            "Dimensiones de columna",
            options=["Año", "Mes"],
            default=default_col_labels,
            key="pivot_col_dims",
            label_visibility="collapsed",
        )

    with col_cfg3:
        st.markdown("**Métricas a mostrar**")
        sel_metrics_labels = st.multiselect(
            "Métricas",
            options=list(METRICAS.values()),
            default=list(METRICAS.values()),
            key="pivot_metrics",
            label_visibility="collapsed",
        )

    # Reorden de dimensiones de fila
    if sel_row_labels:
        st.markdown("**🔀 Reordenar dimensiones de fila:**")
        rc = st.columns(len(sel_row_labels) + 1)
        current = list(sel_row_labels)
        if "pivot_row_order" not in st.session_state or set(st.session_state["pivot_row_order"]) != set(current):
            st.session_state["pivot_row_order"] = current
        ordered = st.session_state["pivot_row_order"]

        for i, lbl in enumerate(ordered):
            with rc[i]:
                col_btns = st.columns([1, 1])
                if i > 0:
                    if col_btns[0].button("←", key=f"move_left_{i}", help=f"Mover '{lbl}' a la izquierda"):
                        ordered[i - 1], ordered[i] = ordered[i], ordered[i - 1]
                        st.session_state["pivot_row_order"] = ordered
                        st.rerun()
                if i < len(ordered) - 1:
                    if col_btns[1].button("→", key=f"move_right_{i}", help=f"Mover '{lbl}' a la derecha"):
                        ordered[i + 1], ordered[i] = ordered[i], ordered[i + 1]
                        st.session_state["pivot_row_order"] = ordered
                        st.rerun()
                st.caption(f"`{i+1}. {lbl}`")

        sel_row_labels = st.session_state["pivot_row_order"]

    # Convertir labels → campos
    map_label_to_field = {v: k for k, v in DIMENSIONES_DISPONIBLES.items()}
    row_dims_fields = [map_label_to_field[l] for l in sel_row_labels if l in map_label_to_field]
    col_dims_fields = [map_label_to_field[l] for l in sel_col_labels if l in map_label_to_field]
    metrics_inv = {v: k for k, v in METRICAS.items()}
    metrics_fields = [metrics_inv[l] for l in sel_metrics_labels if l in metrics_inv]

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
            if col_dims_fields:
                # Con bandas de columna — usamos pivot_table de pandas
                valid_row = [r for r in row_dims_fields if r in df.columns]
                valid_col = [c for c in col_dims_fields if c in df.columns]
                valid_met = [m for m in metrics_fields if m in df.columns]

                if valid_row and valid_met:
                    try:
                        # Tabla pivot por pandas
                        pt = pd.pivot_table(
                            df,
                            index=valid_row,
                            columns=valid_col if valid_col else None,
                            values=valid_met,
                            aggfunc="sum",
                            margins=True,
                            margins_name="▌ TOTAL",
                            observed=True,
                            fill_value=0,
                        )

                        # Renombrar columnas de métricas
                        if isinstance(pt.columns, pd.MultiIndex):
                            new_cols = []
                            for col_tuple in pt.columns:
                                metric_label = METRICAS.get(col_tuple[0], col_tuple[0])
                                rest = " | ".join(str(x) for x in col_tuple[1:])
                                new_cols.append(f"{rest} | {metric_label}" if rest else metric_label)
                            pt.columns = new_cols
                        else:
                            pt.columns = [METRICAS.get(c, c) for c in pt.columns]

                        # Formatear índice
                        pt.index.names = [DIMENSIONES_DISPONIBLES.get(n, n) for n in pt.index.names]

                        # Formatear números como string argentino
                        pt_display = pt.copy()
                        for c in pt_display.columns:
                            pt_display[c] = pt_display[c].apply(lambda x: fmt_num_ar(x, 2))

                        st.markdown('<div class="pivot-container">', unsafe_allow_html=True)
                        st.dataframe(
                            pt_display,
                            use_container_width=True,
                            height=600,
                        )
                        st.markdown('</div>', unsafe_allow_html=True)

                        # Info de conteo
                        st.caption(f"📊 {len(df):,} registros · {df['cod_clien'].nunique():,} clientes · {df['numero'].nunique():,} comprobantes")

                    except Exception as e:
                        st.error(f"Error generando pivot: {e}")
                        import traceback
                        st.code(traceback.format_exc())
                else:
                    st.warning("Algunas dimensiones seleccionadas no están disponibles en los datos.")

            else:
                # Sin bandas de columna — tabla plana con subtotales
                tbl = _add_row_subtotals_flat(
                    df.groupby([r for r in row_dims_fields if r in df.columns], observed=True)
                    [[m for m in metrics_fields if m in df.columns]].sum().reset_index(),
                    row_dims_fields,
                    metrics_fields,
                )
                if not tbl.empty:
                    # Renombrar columnas de dimensión
                    rename_map = {k: v for k, v in DIMENSIONES_DISPONIBLES.items() if k in tbl.columns}
                    tbl = tbl.rename(columns=rename_map)
                    # Formatear métricas
                    for m_label in list(METRICAS.values()):
                        if m_label in tbl.columns:
                            tbl[m_label] = tbl[m_label].apply(lambda x: fmt_num_ar(x, 2))
                    st.markdown('<div class="pivot-container">', unsafe_allow_html=True)
                    st.dataframe(tbl, use_container_width=True, height=600, hide_index=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.caption(f"📊 {len(df):,} registros · {df['cod_clien'].nunique():,} clientes")

    # ══════════════════════════════════════════════════════════════════════════
    #  CARGA HISTÓRICA
    # ══════════════════════════════════════════════════════════════════════════
    _render_uploader()

    # ══════════════════════════════════════════════════════════════════════════
    #  MOTOR IA — GEMINI BRAIN
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="ia-panel">', unsafe_allow_html=True)
    st.markdown(
        "<h2 style='color:#a5b4fc; margin-top:0; font-family:Inter,sans-serif;'>"
        "🧠 Gemini Brain — Consultor Estratégico de Ventas</h2>",
        unsafe_allow_html=True,
    )
    st.write(
        "El motor de IA analiza **toda la tabla de ventas** (independientemente de los filtros "
        "activos) y responde consultas estratégicas con datos reales."
    )

    if not api_key:
        st.info("🔑 Configurá `GOOGLE_API_KEY` en `secrets.toml` para habilitar el Gemini Brain.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Contexto agregado de TODA la tabla (df_all — sin filtros UI)
    @st.cache_data(ttl=600, show_spinner=False)
    def build_ia_context(total_rows: int) -> str:
        ctx_df = df_all.groupby(
            ["_año", "_mes", "vendedo", "rubro", "provincia", "formulario"],
            observed=True,
        ).agg(
            impo_neto=("impo", "sum"),
            bultos=("bultos", "sum"),
            cant_items=("impo", "count"),
            clientes=("cod_clien", "nunique"),
        ).reset_index()
        ctx_df = ctx_df.sort_values("impo_neto", ascending=False).head(200)
        return ctx_df.to_string(index=False)

    context_str = build_ia_context(total_registros)

    # KPIs globales (toda la tabla)
    kpi_global = {
        "impo_total":   df_all["impo"].sum(),
        "bultos_total": df_all["bultos"].sum(),
        "clientes":     df_all["cod_clien"].nunique(),
        "registros":    len(df_all),
        "fecha_min":    df_all["fecha"].min().strftime("%d/%m/%Y"),
        "fecha_max":    df_all["fecha"].max().strftime("%d/%m/%Y"),
    }

    col_ia1, col_ia2, col_ia3, col_ia4 = st.columns(4)
    prompt_ia = None
    with col_ia1:
        if st.button("📊 Informe Ejecutivo", use_container_width=True, key="ia_btn1"):
            prompt_ia = "Generá un informe ejecutivo de alto nivel resumiendo el comportamiento comercial histórico: vendedores líderes, rubros principales, evolución por año y sugerencias estratégicas."
    with col_ia2:
        if st.button("🚨 Alertas de Desvíos", use_container_width=True, key="ia_btn2"):
            prompt_ia = "Detectá alertas comerciales: ¿hay excesiva dependencia en algún vendedor, rubro o provincia? ¿Hay períodos de caída marcada? ¿Concentración de clientes?"
    with col_ia3:
        if st.button("💡 Plan Comercial", use_container_width=True, key="ia_btn3"):
            prompt_ia = "Proponé 3 iniciativas comerciales concretas para expandir la facturación basándote en la distribución actual de ventas por región, rubro y vendedor."
    with col_ia4:
        if st.button("📈 Tendencias", use_container_width=True, key="ia_btn4"):
            prompt_ia = "Analizá las tendencias de crecimiento o decrecimiento mensual/anual. ¿Qué meses son los pico? ¿Hay estacionalidad marcada? ¿Qué año fue el mejor?"

    pregunta_libre = st.text_input(
        "💬 Hacé una consulta personalizada sobre las ventas:",
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
- Facturación Total Histórica: $ {kpi_global['impo_total']:,.2f}
- Bultos Totales: {kpi_global['bultos_total']:,.0f}
- Clientes Únicos Históricos: {kpi_global['clientes']:,}
- Total de Registros: {kpi_global['registros']:,}
- Período: {kpi_global['fecha_min']} → {kpi_global['fecha_max']}

NOTA: Los registros con importe negativo son devoluciones (DEVOLUCION B). El impo_neto ya refleja el neto (ventas - devoluciones).

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
#  CARGA HISTÓRICA (extraída como función auxiliar)
# ══════════════════════════════════════════════════════════════════════════════

def _render_uploader():
    with st.expander("📤 Carga Histórica de Ventas (ventas.dbi)"):
        st.write(
            "Subí un archivo `ventas.dbi` histórico para importarlo de forma incremental en Supabase. "
            "El sistema evitará duplicados usando restricciones de base de datos."
        )
        uploaded_file = st.file_uploader(
            "Seleccioná el archivo ventas.dbi",
            type=["dbi"],
            key="uploader_ventas_history_v2",
        )

        if uploaded_file is not None:
            if st.button("🚀 Iniciar Procesamiento e Importación", use_container_width=True, key="btn_ventas_import_v2"):
                import os
                temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, "temp_ventas_history.dbi")

                with open(temp_path, "wb") as f_temp:
                    f_temp.write(uploaded_file.getbuffer())

                try:
                    import dbf

                    def _str(v):
                        return str(v).strip() if v else ""
                    def _int(v):
                        try: return int(v)
                        except: return 0
                    def _float(v):
                        try: return float(v)
                        except: return 0.0
                    def _date(v):
                        if not v: return None
                        if isinstance(v, (datetime.date, datetime.datetime)):
                            return v.strftime("%Y-%m-%d")
                        s = str(v).strip()
                        if len(s) >= 10 and s[4] == "-":
                            return s[:10]
                        try:
                            parts = s.split("/")
                            if len(parts) == 3:
                                d, m, y = parts
                                return f"{y.zfill(4)}-{m.zfill(2)}-{d.zfill(2)}"
                        except: pass
                        return None

                    def _dummy_memo(path):
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

                    _dummy_memo(temp_path)

                    total_records = 0
                    with dbf.Table(temp_path, codepage="cp1252") as table:
                        table.open()
                        if table._meta.memo:
                            _orig = table._meta.memo.get_memo
                            def _safe(b):
                                try: return _orig(b)
                                except: return b""
                            table._meta.memo.get_memo = _safe
                        total_records = len(table)

                    st.info(f"Detectados {total_records:,} registros. Iniciando importación...")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    batch_dict = {}
                    batch_size = 1000
                    total_proc = 0

                    with dbf.Table(temp_path, codepage="cp1252") as table:
                        table.open()
                        if table._meta.memo:
                            _orig = table._meta.memo.get_memo
                            def _safe(b):
                                try: return _orig(b)
                                except: return b""
                            table._meta.memo.get_memo = _safe

                        for rec in table:
                            fecha_iso = _date(rec.FECHA)
                            if not fecha_iso:
                                continue
                            item = {
                                "rubro": _str(rec.RUBRO), "fecha": fecha_iso,
                                "empresa": _str(rec.EMPRESA), "subrubro": _str(rec.SUBRUBRO),
                                "numero": _int(rec.NUMERO), "localidad": _str(rec.LOCALIDAD),
                                "provincia": _str(rec.PROVINCIA), "formulario": _str(rec.FORMULARIO),
                                "e_mail": _str(rec.E_MAIL), "telefono": _str(rec.TELEFONO),
                                "pais": _str(rec.PAIS), "codigo": _int(rec.CODIGO),
                                "cod_alfa": _str(rec.COD_ALFA), "unidades": _float(rec.UNIDADES),
                                "codigocomp": _int(rec.CODIGOCOMP), "tipo": _int(rec.TIPO),
                                "dto": _float(rec.DTO), "dto1": _float(rec.DTO1),
                                "dto2": _float(rec.DTO2), "alt_bonifi": _str(rec.ALT_BONIFI),
                                "grupo": _str(rec.GRUPO), "sinonimo": _str(rec.SINONIMO),
                                "ean": _str(rec.EAN), "clien": _str(rec.CLIEN),
                                "cod_clien": _int(rec.COD_CLIEN), "producto": _str(rec.PRODUCTO),
                                "vendedo": _str(rec.VENDEDO), "domicilio": _str(rec.DOMICILIO),
                                "deposito": _str(rec.DEPOSITO), "bultos": _float(rec.BULTOS),
                                "impo": _float(rec.IMPO),
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
                                status_text.text(f"Importados: {total_proc:,} / {total_records:,}")
                                progress_bar.progress(min(1.0, total_proc / total_records))
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
                    load_sales_full.clear()
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
