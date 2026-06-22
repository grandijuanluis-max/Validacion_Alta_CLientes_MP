import os
import sys
import pandas as pd
from supabase import create_client

# Configurar ruta absoluta para poder importar la conexión a Supabase de la app
sys.path.append('/Users/juanluisgrandi/AI/MP')
from modulos.db import supabase

def actualizar_codigos_postales():
    if supabase is None:
        print("❌ Error: No hay conexión a Supabase configurada en modulos.db.")
        return

    excel_file = '/Users/juanluisgrandi/AI/MP/cpostal_toto.xlsx'
    if not os.path.exists(excel_file):
        print(f"❌ Error: El archivo Excel '{excel_file}' no existe.")
        return

    print("📖 Leyendo archivo Excel cpostal_toto.xlsx...")
    df = pd.read_excel(excel_file)
    print(f"--> Se encontraron {len(df)} filas en el archivo Excel.")

    # Sanitizar columnas del excel
    df['c_postal'] = df['c_postal'].astype(str).str.strip().str.replace('.0', '', regex=False)
    df['localidad'] = df['localidad'].astype(str).str.strip()

    total_procesados = 0
    total_actualizados_db = 0
    no_encontrados = []

    print("\n🚀 Iniciando actualización en Supabase...")
    for index, row in df.iterrows():
        cp_val = row['c_postal']
        loc_val = row['localidad']
        zona_val = int(row['zona']) if not pd.isna(row['zona']) else None
        dep_val = int(row['deposito']) if not pd.isna(row['deposito']) else None
        grupo_val = str(row['grupo1_dep']).strip() if not pd.isna(row['grupo1_dep']) else None

        # Realizar update en base a CP y Localidad (ilike para ignorar mayúsculas/minúsculas)
        try:
            # Primero buscamos para ver si existe y cuántos registros hay
            res = supabase.table('codigos_postales').select('id, localidad, cp').eq('cp', cp_val).ilike('localidad', loc_val).execute()
            
            if res.data:
                # Si existe, actualizamos todos los que coincidan con ese CP y Localidad
                update_res = supabase.table('codigos_postales').update({
                    'zona': zona_val,
                    'deposito': dep_val,
                    'grupo1_dep': grupo_val
                }).eq('cp', cp_val).ilike('localidad', loc_val).execute()
                
                cant_filas = len(update_res.data) if update_res.data else 0
                total_actualizados_db += cant_filas
                print(f"✅ [{index + 1}/{len(df)}] CP {cp_val} - {loc_val}: Actualizado(s) {cant_filas} registro(s) en la base de datos (Zona: {zona_val}, Deposito: {dep_val}, Grupo: {grupo_val}).")
            else:
                print(f"⚠️ [{index + 1}/{len(df)}] CP {cp_val} - {loc_val}: No encontrado en la base de datos.")
                no_encontrados.append((cp_val, loc_val))
                
        except Exception as e:
            print(f"❌ Error al procesar CP {cp_val} - {loc_val}: {e}")

        total_procesados += 1

    print("\n=======================================================")
    print("🎉 ¡Proceso de actualización finalizado!")
    print(f"--> Filas procesadas del Excel: {total_procesados}")
    print(f"--> Registros totales actualizados en Supabase: {total_actualizados_db}")
    if no_encontrados:
        print(f"--> Filas del Excel no encontradas en Supabase: {len(no_encontrados)}")
        print("Detalle de no encontrados (primeros 10):")
        for i, item in enumerate(no_encontrados[:10]):
            print(f"   - CP: {item[0]} | Localidad: {item[1]}")
    print("=======================================================")

if __name__ == '__main__':
    actualizar_codigos_postales()
