from __future__ import annotations

import os
import tempfile
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos


def clean_str(s) -> str:
    if s is None:
        return ""
    text = str(s)
    # fpdf2 core fonts: Latin-1; reemplazar caracteres no representables
    return text.encode("latin-1", "replace").decode("latin-1")


def _as_number(val, default=0):
    if val is None or val == "":
        return default
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, (int, float)):
        return val
    text = str(val).strip().replace(",", ".")
    if not text or text.lower() in {"none", "nan", "-"}:
        return default
    try:
        num = float(text)
        return int(num) if num.is_integer() else num
    except (ValueError, TypeError):
        return default


def normalizar_payload_nosis(payload: dict | None) -> dict:
    """Normaliza tipos del payload Nosis (API, caché o simulador)."""
    if not payload:
        return {}
    data = dict(payload)
    numeric_keys = (
        "score_riesgo",
        "calificacion_bcra",
        "cheques_rechazados",
        "juicios_concursos",
        "baches_afip_meses",
        "deuda_total",
        "compromiso_mensual",
        "cant_bancos",
        "consultas_12m",
        "antiguedad_laboral",
    )
    text_keys = (
        "razon_social",
        "nse",
        "es_empleado",
        "empleador",
        "facturas_apocrifas",
        "deudas_fiscales",
        "es_moroso",
    )
    for key in numeric_keys:
        data[key] = _as_number(data.get(key), 0)
    for key in text_keys:
        val = data.get(key)
        data[key] = str(val).strip() if val is not None else ""
    if not data.get("razon_social"):
        data["razon_social"] = "DESCONOCIDO"
    return data


def _fmt_money(val) -> str:
    num = _as_number(val, 0)
    return f"$ {num:,.2f}"


class NosisPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(26, 82, 118)
        self.cell(
            0,
            10,
            clean_str("SARC - SISTEMA DE ALTA RAPIDA DE CLIENTES"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="C",
        )
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(127, 140, 141)
        self.cell(
            0,
            5,
            clean_str("Resumen de Inteligencia Crediticia & Riesgo Nosis"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="C",
        )
        self.ln(5)
        self.set_draw_color(26, 82, 118)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(127, 140, 141)
        self.cell(
            0,
            10,
            clean_str(f"Pagina {self.page_no()}/{{nb}} - Resumen Confidencial Autorizado"),
            align="C",
        )


def generar_pdf_reporte_nosis(
    payload: dict,
    cuit: str,
    dictamen: str,
    semaforos: dict,
    explicacion: str = "",
) -> str:
    payload = normalizar_payload_nosis(payload)
    semaforos = semaforos or {}
    dictamen = clean_str(dictamen or "SIN DICTAMEN")
    explicacion = clean_str(explicacion or "")
    cuit = clean_str(cuit or "")

    pdf = NosisPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # 1. Encabezado cliente
    pdf.set_fill_color(242, 244, 244)
    y_box = pdf.get_y()
    pdf.rect(10, y_box, 190, 25, style="F")

    pdf.set_y(y_box + 2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(5)
    pdf.cell(40, 6, clean_str("RAZON SOCIAL:"))
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(
        140,
        6,
        clean_str(payload.get("razon_social", "DESCONOCIDO").upper()),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(5)
    pdf.cell(40, 6, clean_str("CUIT / CUIL:"))
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(140, 6, cuit, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(5)
    pdf.cell(40, 6, clean_str("FECHA EMISION:"))
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(
        140,
        6,
        clean_str(datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.ln(10)

    # 2. Dictamen
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(
        0,
        8,
        clean_str("EVALUACION DEL MOTOR DE DECISION"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    if dictamen == "RECHAZO AUTOMÁTICO" or "RECHAZO" in dictamen.upper():
        pdf.set_fill_color(245, 183, 177)
        pdf.set_text_color(120, 40, 31)
    elif dictamen == "REVISIÓN GERENCIAL" or "REVISI" in dictamen.upper():
        pdf.set_fill_color(252, 244, 197)
        pdf.set_text_color(125, 96, 5)
    else:
        pdf.set_fill_color(212, 239, 223)
        pdf.set_text_color(20, 90, 50)

    pdf.rect(10, pdf.get_y(), 190, 10, style="F")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(
        0,
        10,
        clean_str(f"   DICTAMEN FINAL: {dictamen}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 9.5)
    pdf.set_text_color(84, 110, 122)
    pdf.multi_cell(190, 4.5, clean_str(f"Analisis del Motor: {explicacion}"))
    pdf.ln(5)
    pdf.set_text_color(44, 62, 80)

    # 3. Semáforos
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(
        0,
        8,
        clean_str("INDICADORES PRINCIPALES DE MOTOR"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(26, 82, 118)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(40, 7, clean_str("Metrica"), border=1, align="C", fill=True)
    pdf.cell(30, 7, clean_str("Valor"), border=1, align="C", fill=True)
    pdf.cell(30, 7, clean_str("Semaforo"), border=1, align="C", fill=True)
    pdf.cell(
        90,
        7,
        clean_str("Detalle Tecnico de Evaluacion"),
        border=1,
        align="C",
        fill=True,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_text_color(44, 62, 80)
    pdf.set_font("Helvetica", "", 9)

    metrics = [
        (
            "Score de Riesgo",
            payload.get("score_riesgo", 850),
            semaforos.get("score", "VERDE"),
            "Puntaje crediticio (Riesgo Alto < 450, Optimo > 700)",
        ),
        (
            "Calificacion BCRA",
            payload.get("calificacion_bcra", 1),
            semaforos.get("bcra", "VERDE"),
            "Situacion BCRA (1=Normal, 2=Seguimiento, 3+=Alerta)",
        ),
        (
            "Cheques Rechazados",
            payload.get("cheques_rechazados", 0),
            semaforos.get("cheques", "VERDE"),
            "Cantidad de cheques rechazados en ultimos 24 meses",
        ),
        (
            "Juicios y Concursos",
            payload.get("juicios_concursos", 0),
            semaforos.get("juicios", "VERDE"),
            "Presencia de juicios activos, concursos o quiebras",
        ),
        (
            "Deuda Cargas AFIP",
            payload.get("baches_afip_meses", 0),
            semaforos.get("afip", "VERDE"),
            "Meses de atraso impagos en aportes de cargas sociales",
        ),
    ]

    for label, valor, color, desc in metrics:
        pdf.cell(40, 7, clean_str(label), border=1)
        pdf.cell(30, 7, clean_str(valor), border=1, align="C")
        if color == "VERDE":
            pdf.set_text_color(39, 174, 96)
        elif color == "AMARILLO":
            pdf.set_text_color(212, 172, 13)
        else:
            pdf.set_text_color(192, 57, 43)
        pdf.cell(30, 7, clean_str(color), border=1, align="C")
        pdf.set_text_color(44, 62, 80)
        pdf.cell(
            90,
            7,
            clean_str(desc),
            border=1,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    pdf.ln(8)

    # 4. Variables adicionales
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(
        0,
        8,
        clean_str("DATOS ADICIONALES DE RIESGO Y COMPORTAMIENTO (NOSIS)"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    y_start = pdf.get_y()
    empleador = payload.get("empleador", "No registrado") or "No registrado"

    pdf.set_fill_color(248, 249, 249)
    pdf.rect(10, y_start, 92, 32, style="F")
    pdf.set_xy(12, y_start + 2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(88, 5, clean_str("Perfil de Estabilidad Laboral"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(88, 4.5, clean_str(f'Nivel Socioeconomico: {payload.get("nse")}'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(12)
    pdf.cell(88, 4.5, clean_str(f'Es Empleado Rel. Dep.: {payload.get("es_empleado")}'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(12)
    pdf.cell(88, 4.5, clean_str(f"Empleador: {empleador[:32]}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(12)
    pdf.cell(
        88,
        4.5,
        clean_str(f'Antiguedad Laboral: {payload.get("antiguedad_laboral")} meses'),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_fill_color(248, 249, 249)
    pdf.rect(105, y_start, 95, 32, style="F")
    pdf.set_xy(107, y_start + 2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(91, 5, clean_str("Riesgo de Deuda y Comportamiento"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(107)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(91, 4.5, clean_str(f'Deuda Financiera Total: {_fmt_money(payload.get("deuda_total"))}'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(107)
    pdf.cell(91, 4.5, clean_str(f'Compromiso Mensual: {_fmt_money(payload.get("compromiso_mensual"))}'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(107)
    pdf.cell(91, 4.5, clean_str(f'Bancos Consultantes: {payload.get("cant_bancos")}'), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(107)
    pdf.cell(
        91,
        4.5,
        clean_str(f'Consultas a CUIT (ultimos 12 meses): {payload.get("consultas_12m")}'),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_y(y_start + 36)
    riesgo = (
        str(payload.get("facturas_apocrifas", "")).strip().lower() == "si"
        or str(payload.get("deudas_fiscales", "")).strip().lower() == "si"
        or str(payload.get("es_moroso", "")).strip().lower() == "si"
    )
    if riesgo:
        pdf.set_fill_color(253, 235, 230)
    else:
        pdf.set_fill_color(242, 243, 244)

    pdf.rect(10, pdf.get_y(), 190, 18, style="F")
    pdf.set_xy(12, pdf.get_y() + 2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(
        186,
        4,
        clean_str("ALERTAS DE INTEGRIDAD Y MOROSIDAD AFIP/COMERCIAL"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_x(12)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(
        186,
        5,
        clean_str(
            f'Facturas Apocrifas: {payload.get("facturas_apocrifas")}   |   '
            f'Deudas Fiscales (AFIP): {payload.get("deudas_fiscales")}   |   '
            f'Es Moroso Comercial: {payload.get("es_moroso")}'
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(149, 165, 166)
    pdf.multi_cell(
        190,
        4,
        clean_str(
            "Este reporte es estrictamente confidencial y ha sido generado por el Sistema de Alta "
            "Rapida de Clientes (SARC). La informacion contenida en este dossier es propiedad "
            "exclusiva del receptor autorizado y esta basada en datos provistos por la API de Nosis."
        ),
    )

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    pdf.output(tmp.name)
    return tmp.name


def build_nosis_pdf_bytes(
    payload: dict,
    cuit: str,
    dictamen: str,
    semaforos: dict,
    explicacion: str = "",
) -> bytes:
    path = generar_pdf_reporte_nosis(payload, cuit, dictamen, semaforos, explicacion)
    try:
        with open(path, "rb") as pdf_file:
            return pdf_file.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def render_nosis_pdf_download(
    payload: dict,
    cuit: str,
    dictamen: str,
    semaforos: dict,
    explicacion: str = "",
    *,
    label: str = "Generar y descargar Resumen PDF",
    file_name: str | None = None,
    key: str,
    use_container_width: bool = True,
) -> None:
    """Genera el PDF solo al solicitarlo (evita errores al abrir la ficha)."""
    import streamlit as st

    cuit_clean = "".join(filter(str.isdigit, str(cuit))) or str(cuit).strip()
    file_name = file_name or f"Resumen_Riesgo_{cuit_clean}.pdf"
    bytes_key = f"nosis_pdf_bytes::{key}"
    err_key = f"nosis_pdf_err::{key}"

    if st.button(label, key=f"{key}::generate", use_container_width=use_container_width):
        with st.spinner("Generando PDF..."):
            try:
                st.session_state[bytes_key] = build_nosis_pdf_bytes(
                    payload, cuit_clean, dictamen, semaforos, explicacion
                )
                st.session_state.pop(err_key, None)
            except Exception as exc:
                st.session_state[err_key] = str(exc)
                st.session_state.pop(bytes_key, None)
        st.rerun()

    if err_key in st.session_state:
        st.error(f"No se pudo generar el PDF: {st.session_state[err_key]}")

    if st.session_state.get(bytes_key):
        st.download_button(
            label="Descargar PDF generado",
            data=st.session_state[bytes_key],
            file_name=file_name,
            mime="application/pdf",
            key=f"{key}::download",
            use_container_width=use_container_width,
            type="primary",
        )
