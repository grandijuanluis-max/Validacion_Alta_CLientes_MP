from fpdf import FPDF
import tempfile
import os
from datetime import datetime

def clean_str(s) -> str:
    if s is None:
        return ""
    # FPDF1.7 default fonts only support Latin-1 characters
    return str(s).encode('latin1', 'replace').decode('latin1')

class NosisPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.set_text_color(26, 82, 118) # Azul marino profundo
        self.cell(0, 10, clean_str('SARC - SISTEMA DE ALTA RÁPIDA DE CLIENTES'), 0, 1, 'C')
        self.set_font('Arial', 'I', 9)
        self.set_text_color(127, 140, 141) # Gris elegante
        self.cell(0, 5, clean_str('Resumen de Inteligencia Crediticia & Riesgo Nosis'), 0, 1, 'C')
        self.ln(5)
        self.set_draw_color(26, 82, 118)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(127, 140, 141)
        self.cell(0, 10, clean_str(f'Página {self.page_no()}/{{nb}} - Resumen Confidencial Autorizado'), 0, 0, 'C')

def generar_pdf_reporte_nosis(payload: dict, cuit: str, dictamen: str, semaforos: dict, explicacion: str = "") -> str:
    pdf = NosisPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # 1. ENCABEZADO CLIENTE (Formulario Header)
    pdf.set_fill_color(242, 244, 244) # Fondo gris claro
    pdf.rect(10, pdf.get_y(), 190, 25, 'F')
    
    pdf.set_y(pdf.get_y() + 2)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(5)
    pdf.cell(40, 6, clean_str('RAZÓN SOCIAL:'), 0, 0)
    pdf.set_font('Arial', '', 11)
    pdf.cell(140, 6, clean_str(payload.get('razon_social', 'DESCONOCIDO').upper()), 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(5)
    pdf.cell(40, 6, clean_str('CUIT / CUIL:'), 0, 0)
    pdf.set_font('Arial', '', 11)
    pdf.cell(140, 6, clean_str(cuit), 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(5)
    pdf.cell(40, 6, clean_str('FECHA EMISIÓN:'), 0, 0)
    pdf.set_font('Arial', '', 11)
    pdf.cell(140, 6, clean_str(datetime.now().strftime('%d/%m/%Y %H:%M:%S')), 0, 1)
    
    pdf.ln(10)
    
    # 2. DICTAMEN DE RIESGO CORPORATIVO
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, clean_str('EVALUACIÓN DEL MOTOR DE DECISIÓN'), 0, 1, 'L')
    
    # Pintar dictamen con fondo de color del semáforo
    if dictamen == "RECHAZO AUTOMÁTICO":
        pdf.set_fill_color(245, 183, 177) # Rojo suave
        pdf.set_text_color(120, 40, 31)
    elif dictamen == "REVISIÓN GERENCIAL":
        pdf.set_fill_color(252, 244, 197) # Amarillo suave
        pdf.set_text_color(125, 96, 5)
    else:
        pdf.set_fill_color(212, 239, 223) # Verde suave
        pdf.set_text_color(20, 90, 50)
        
    pdf.rect(10, pdf.get_y(), 190, 10, 'F')
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, clean_str(f'   DICTAMEN FINAL: {dictamen}'), 0, 1, 'L', fill=False)
    
    pdf.ln(2)
    pdf.set_font('Arial', 'I', 9.5)
    pdf.set_text_color(84, 110, 122) # Gris azulado refinado
    pdf.multi_cell(190, 4.5, clean_str(f"Análisis del Motor: {explicacion}"))
    pdf.ln(5)
    pdf.set_text_color(44, 62, 80)
    
    # 3. TABLA DE LOS 5 SEMÁFOROS PRINCIPALES
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 8, clean_str('INDICADORES PRINCIPALES DE MOTOR'), 0, 1, 'L')
    
    # Table Header
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(26, 82, 118)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(40, 7, clean_str('Métrica'), 1, 0, 'C', True)
    pdf.cell(30, 7, clean_str('Valor'), 1, 0, 'C', True)
    pdf.cell(30, 7, clean_str('Semáforo'), 1, 0, 'C', True)
    pdf.cell(90, 7, clean_str('Detalle Técnico de Evaluación'), 1, 1, 'C', True)
    
    pdf.set_text_color(44, 62, 80)
    pdf.set_font('Arial', '', 9)
    
    # Fila de datos
    metris = [
        ('Score de Riesgo', payload.get('score_riesgo', 850), semaforos.get('score', 'VERDE'), 'Puntaje crediticio (Riesgo Alto < 450, Óptimo > 700)'),
        ('Calificación BCRA', payload.get('calificacion_bcra', 1), semaforos.get('bcra', 'VERDE'), 'Situación BCRA (1=Normal, 2=Seguimiento, 3+=Alerta)'),
        ('Cheques Rechazados', payload.get('cheques_rechazados', 0), semaforos.get('cheques', 'VERDE'), 'Cantidad de cheques rechazados en últimos 24 meses'),
        ('Juicios y Concursos', payload.get('juicios_concursos', 0), semaforos.get('juicios', 'VERDE'), 'Presencia de juicios activos, concursos o quiebras'),
        ('Deuda Cargas AFIP', payload.get('baches_afip_meses', 0), semaforos.get('afip', 'VERDE'), 'Meses de atraso impagos en aportes de cargas sociales')
    ]
    
    for label, valor, color, desc in metris:
        pdf.cell(40, 7, clean_str(label), 1, 0, 'L')
        pdf.cell(30, 7, clean_str(valor), 1, 0, 'C')
        # Celdas con texto coloreado para semáforo
        if color == "VERDE": 
            pdf.set_text_color(39, 174, 96)
        elif color == "AMARILLO": 
            pdf.set_text_color(212, 172, 13)
        else: 
            pdf.set_text_color(192, 57, 43)
        pdf.cell(30, 7, clean_str(color), 1, 0, 'C')
        pdf.set_text_color(44, 62, 80)
        pdf.cell(90, 7, clean_str(desc), 1, 1, 'L')
        
    pdf.ln(8)
    
    # 4. VARIABLES ADICIONALES DE INTELIGENCIA
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 8, clean_str('DATOS ADICIONALES DE RIESGO Y COMPORTAMIENTO (NOSIS)'), 0, 1, 'L')
    
    # Formato de dos columnas de datos recopilados
    pdf.set_font('Arial', '', 9)
    y_start = pdf.get_y()
    
    # Columna 1
    pdf.set_fill_color(248, 249, 249)
    pdf.rect(10, y_start, 92, 32, 'F')
    pdf.set_xy(12, y_start + 2)
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(88, 5, clean_str('Perfil de Estabilidad Laboral'), 0, 2, 'L')
    pdf.set_font('Arial', '', 9)
    pdf.cell(88, 4.5, clean_str(f'Nivel Socioeconómico: {payload.get("nse")}'), 0, 2, 'L')
    pdf.cell(88, 4.5, clean_str(f'Es Empleado Rel. Dep.: {payload.get("es_empleado")}'), 0, 2, 'L')
    pdf.cell(88, 4.5, clean_str(f'Empleador: {payload.get("empleador", "No registrado")[:32]}'), 0, 2, 'L')
    pdf.cell(88, 4.5, clean_str(f'Antigüedad Laboral: {payload.get("antiguedad_laboral")} meses'), 0, 2, 'L')
    
    # Columna 2
    pdf.set_fill_color(248, 249, 249)
    pdf.rect(105, y_start, 95, 32, 'F')
    pdf.set_xy(107, y_start + 2)
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(91, 5, clean_str('Riesgo de Deuda y Comportamiento'), 0, 2, 'L')
    pdf.set_font('Arial', '', 9)
    
    deuda = payload.get("deuda_total", 0)
    comp = payload.get("compromiso_mensual", 0)
    pdf.cell(91, 4.5, clean_str(f'Deuda Financiera Total: $ {deuda:,.2f}'), 0, 2, 'L')
    pdf.cell(91, 4.5, clean_str(f'Compromiso Mensual: $ {comp:,.2f}'), 0, 2, 'L')
    pdf.cell(91, 4.5, clean_str(f'Bancos Consultantes: {payload.get("cant_bancos")}'), 0, 2, 'L')
    pdf.cell(91, 4.5, clean_str(f'Consultas a CUIT (últimos 12 meses): {payload.get("consultas_12m")}'), 0, 2, 'L')
    
    pdf.ln(8)
    
    # Columna Alertas Impositivas
    pdf.set_y(y_start + 36)
    
    # Condicionar color de alerta si tiene factores de riesgo
    riesgo = (payload.get("facturas_apocrifas") == "Si" or payload.get("deudas_fiscales") == "Si" or payload.get("es_moroso") == "Si")
    if riesgo:
        pdf.set_fill_color(253, 235, 230) # Rojo claro si hay alerta impositiva
    else:
        pdf.set_fill_color(242, 243, 244) # Gris claro normal
        
    pdf.rect(10, pdf.get_y(), 190, 18, 'F')
    pdf.set_xy(12, pdf.get_y() + 2)
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(186, 4, clean_str('ALERTAS DE INTEGRIDAD Y MOROSIDAD AFIP/COMERCIAL'), 0, 1, 'L')
    pdf.set_font('Arial', '', 9)
    pdf.cell(186, 5, clean_str(f'Facturas Apócrifas: {payload.get("facturas_apocrifas")}   |   Deudas Fiscales (AFIP): {payload.get("deudas_fiscales")}   |   Es Moroso Comercial: {payload.get("es_moroso")}'), 0, 1, 'L')
    
    # Leyenda legal
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 7.5)
    pdf.set_text_color(149, 165, 166)
    pdf.multi_cell(190, 4, clean_str('Este reporte es estrictamente confidencial y ha sido generado por el Sistema de Alta Rápida de Clientes (SARC). La información contenida en este dossier es propiedad exclusiva del receptor autorizado y está basada en datos provistos por la API de Nosis. La interpretación de estos resultados debe hacerse bajo los lineamientos y políticas internas de riesgo comercial de la compañía.'))
    
    # Guardar a archivo temporal
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf.output(tmp.name, 'F')
    tmp.close()
    return tmp.name
