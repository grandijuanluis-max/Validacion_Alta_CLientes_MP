import dbf
import csv
import os

# Rutas de archivos
ruta_dbi = os.path.join(os.path.dirname(__file__), "CODIGOSMP.DBI")
ruta_csv = os.path.join(os.path.dirname(__file__), "codigos_postales.csv")

def convertir():
    if not os.path.exists(ruta_dbi):
        print("ERROR: No se encontró el archivo CODIGOSMP.DBI")
        return
        
    print("Abriendo CODIGOSMP.DBI...")
    table = dbf.Table(ruta_dbi, codepage='cp1252')
    table.open()
    
    print(f"Total de registros a procesar: {len(table)}")
    
    with open(ruta_csv, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, delimiter=';')
        # Cabecera exacta para Supabase
        writer.writerow(['localidad', 'provincia', 'cp'])
        
        for row in table:
            # Limpiamos espacios en blanco extra que deja dBASE
            localidad = str(row['LOCALIDAD']).strip()
            provincia = str(row['PROVINCIA']).strip()
            cp = str(row['C_POSTAL']).strip()
            
            # Solo guardamos si tienen datos
            if localidad and provincia and cp:
                writer.writerow([localidad, provincia, cp])
                
    table.close()
    print("¡ÉXITO! Archivo codigos_postales.csv generado a la perfección.")

if __name__ == "__main__":
    convertir()
