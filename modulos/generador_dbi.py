import os
import datetime
import dbf

def generar_archivo_dbi(dataframe_clientes, numero_inicio_codigo=1):
    """
    Genera un archivo .dbi nativo de dBASE utilizando la librería dbf.
    El DataFrame debe contener clientes validados listos para exportar.
    """
    # Esquema exacto de Presea + Nuevo campo DOMICILIOE
    # N(15,0) = Numérico de 15, C(30) = Texto de 30.
    schema_str = (
        "CODIGO N(15,0); CUIT N(15,0); NOMBRE C(30); N_FANTASIA C(30); "
        "DOMICILIO C(50); DOMICILIOE C(50); LOCALIDAD C(35); C_POSTAL C(5); "
        "PAIS C(15); CONTACTO C(30); TELEFONO C(40); RUBRO C(30); VENDEDOR N(15,0)"
    )
    
    os.makedirs("data", exist_ok=True)
    ruta_salida = os.path.join("data", f"clientes_exportar_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.dbi")
    
    table = dbf.Table(ruta_salida, schema_str, dbf_type='db3', codepage='cp1252')
    table.open(mode=dbf.READ_WRITE)
    
    codigo_actual = numero_inicio_codigo
    
    for index, row in dataframe_clientes.iterrows():
        # Limpieza de CUIT a numérico
        cuit_num = str(row.get('CUIT', '0')).replace('-', '').replace(' ', '')
        if not cuit_num.isdigit(): cuit_num = 0
        else: cuit_num = int(cuit_num)
            
        codigo_vendedor = 0
        try: codigo_vendedor = int(row.get('VENDEDOR', 0))
        except: pass
        
        # Armamos la tupla respetando el orden del schema
        registro = (
            codigo_actual,                      # CODIGO
            cuit_num,                           # CUIT
            str(row.get('NOMBRE', ''))[:30],      # NOMBRE
            str(row.get('N_FANTASIA', ''))[:30],  # N_FANTASIA
            str(row.get('DOMICILIO', ''))[:50],   # DOMICILIO (Fiscal)
            str(row.get('DOMICILIOE', ''))[:50],  # DOMICILIOE (Entrega)
            str(row.get('LOCALIDAD', ''))[:35],   # LOCALIDAD
            str(row.get('C_POSTAL', ''))[:5],     # C_POSTAL
            str(row.get('PAIS', ''))[:15],        # PAIS
            str(row.get('CONTACTO', ''))[:30],    # CONTACTO
            str(row.get('TELEFONO', ''))[:40],    # TELEFONO
            str(row.get('RUBRO', ''))[:30],       # RUBRO (Giro Comercial)
            codigo_vendedor                     # VENDEDOR
        )
        table.append(registro)
        codigo_actual += 1
        
    table.close()
    
    return ruta_salida, codigo_actual
