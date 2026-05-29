import os
import datetime
import dbf

def generar_archivo_dbi(dataframe_clientes, numero_inicio_codigo=1):
    """
    Genera un archivo .dbi nativo de dBASE utilizando la librería dbf con el layout de Presea.
    """
    schema_str = (
        "CODIGO N(6,0); NOMBRE C(30); N_FANTASIA C(30); CUIT N(12,0); "
        "DOMICILIO C(50); LOCALIDAD C(35); C_POSTAL C(50); PROVINCIA C(25); "
        "PAIS C(20); CONTACTO C(30); TELEFONO C(40); RUBRO C(30); "
        "TIPO_RESP N(5,1); TIPO_DOC N(2,0); CUIT_S1 N(12,0); CUIT_S2 N(12,0); "
        "TRANSPORTE N(2,0); CONDICION N(2,0); CATEGORIA C(10); LISTAPRE C(10); "
        "MEMO C(210)"
    )
    
    os.makedirs("data", exist_ok=True)
    ruta_salida = os.path.join("data", "Clientes_web.dbi")
    
    # Si el archivo existe, lo pisamos o lo re-creamos para limpiar datos anteriores
    if os.path.exists(ruta_salida):
        os.remove(ruta_salida)
    
    table = dbf.Table(ruta_salida, schema_str, dbf_type='db3', codepage='cp1252')
    table.open(mode=dbf.READ_WRITE)
    
    codigo_actual = numero_inicio_codigo
    
    for index, row in dataframe_clientes.iterrows():
        # Limpieza de numéricos (CUITs)
        cuit_num = str(row.get('cuit', '0')).replace('-', '').replace(' ', '')
        if not cuit_num.isdigit(): cuit_num = 0
        else: cuit_num = int(cuit_num)
        
        cuit_s1_num = str(row.get('cuit_socio1', '0')).replace('-', '').replace(' ', '')
        if not cuit_s1_num.isdigit() or cuit_s1_num == '': cuit_s1_num = 0
        else: cuit_s1_num = int(cuit_s1_num)
        
        cuit_s2_num = str(row.get('cuit_socio2', '0')).replace('-', '').replace(' ', '')
        if not cuit_s2_num.isdigit() or cuit_s2_num == '': cuit_s2_num = 0
        else: cuit_s2_num = int(cuit_s2_num)
        
        # Limpieza TIPO_RESP y TIPO_DOC
        try: tipo_resp = float(row.get('tipo_resp', 0.0))
        except: tipo_resp = 0.0
            
        try: tipo_doc = int(row.get('tipo_doc', 80))
        except: tipo_doc = 80
        
        registro = (
            codigo_actual,                            # CODIGO N(6,0)
            str(row.get('nombre', ''))[:30],            # NOMBRE C(30)
            str(row.get('n_fantasia', ''))[:30],        # N_FANTASIA C(30)
            cuit_num,                                 # CUIT N(12,0)
            str(row.get('domicilio_f', ''))[:50],         # DOMICILIO C(50)
            str(row.get('localidad', ''))[:35],         # LOCALIDAD C(35)
            str(row.get('c_postal', ''))[:50],          # C_POSTAL C(50)
            str(row.get('provincia', ''))[:25],         # PROVINCIA C(25)
            str(row.get('pais', ''))[:20],              # PAIS C(20)
            str(row.get('contacto', ''))[:30],          # CONTACTO C(30)
            str(row.get('telefono', ''))[:40],          # TELEFONO C(40)
            str(row.get('giro_comercial', ''))[:30],    # RUBRO C(30)
            tipo_resp,                                # TIPO_RESP N(5,1)
            tipo_doc,                                 # TIPO_DOC N(2,0)
            cuit_s1_num,                              # CUIT_S1 N(12,0)
            cuit_s2_num,                              # CUIT_S2 N(12,0)
            1,                                        # TRANSPORTE N(2,0)
            1,                                        # CONDICION N(2,0)
            "CLI_GRAL",                               # CATEGORIA C(10)
            "LISTA_UNIC",                             # LISTAPRE C(10)
            str(row.get('documento', ''))[:210]         # MEMO C(210)
        )
        table.append(registro)
        codigo_actual += 1
        
    table.close()
    
    # Generar 4 copias idénticas solicitadas en la carpeta data
    import shutil
    copias = [
        "clientes_web0.dbi",
        "clientes_web1.dbi",
        "clientes_web10.dbi",
        "clientes_we11.dbi"
    ]
    dir_salida = os.path.dirname(ruta_salida)
    for c in copias:
        ruta_c = os.path.join(dir_salida, c)
        if os.path.exists(ruta_c):
            os.remove(ruta_c)
        shutil.copy2(ruta_salida, ruta_c)
        
    return ruta_salida, codigo_actual
