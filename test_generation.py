import pandas as pd
from modulos.generador_dbi import generar_archivo_dbi
import os

data = {
    'codigo': [40001],
    'nombre': ['CLIENTE TEST SRL'],
    'n_fantasia': ['FANTASIA TEST'],
    'cuit': ['30123456789'],
    'domicilio_f': ['Calle Falsa 123'],
    'localidad': ['Rosario'],
    'c_postal': ['2000'],
    'provincia': ['Santa Fe'],
    'pais': ['Argentina'],
    'contacto': ['Juan Perez'],
    'telefono': ['3415555555'],
    'giro_comercial': ['Kiosco'],
    'tipo_resp': [1.0],
    'tipo_doc': [80],
    'cuit_socio1': ['0'],
    'cuit_socio2': ['0'],
    'vendedor': [1],
    'documento': ['Documento de prueba largo memo para verificar la creacion del archivo .fpt correspondiente y ver si el formato es correcto.'],
    'domicilio_e': ['Calle Entrega 456'],
    'cp_ent': ['2000'],
    'local_ent': ['Rosario'],
    'prov_ent': ['Santa Fe']
}
df = pd.DataFrame(data)

# Remove old files first to make sure we inspect the fresh ones
for f in ["Clientes_web.dbi", "Clientes_web.fpt", "domicilios_entrega.txt"]:
    p = os.path.join("data", f)
    if os.path.exists(p):
        os.remove(p)

ruta, nuevo_cod = generar_archivo_dbi(df, 40001)
print(f"Generated successfully. Files in data/:")
for f in os.listdir("data"):
    if f.endswith(".dbi") or f.endswith(".fpt") or f.endswith(".txt"):
        p = os.path.join("data", f)
        print(f"  {f}: size={os.path.getsize(p)} bytes")
