import os
import sys
import dbf
import streamlit as st

# Append MP to path so it can import modulos.db
sys.path.append('/Users/juanluisgrandi/AI/MP')
from modulos.db import supabase

def importar():
    if supabase is None:
        print("No hay conexión a Supabase configurada.")
        return

    print("Leyendo CLIENTESPA.DBI para extraer Código Máximo y Vendedores...")
    max_codigo = 0
    vendedores = set()
    
    ruta_dbf = '/Users/juanluisgrandi/AI/MP/CLIENTESPA.DBI'
    with dbf.Table(ruta_dbf) as table:
        for rec in table:
            try:
                codigo = int(rec.CODIGO)
                if codigo > max_codigo: max_codigo = codigo
            except: pass
            
            try:
                vend = int(rec.VENDEDOR)
                if vend > 0: vendedores.add(vend)
            except: pass

    print(f"--> Máximo Código encontrado en DBF: {max_codigo}")
    print(f"--> Cantidad de Vendedores a importar: {len(vendedores)}")
    
    # 1. Actualizar secuencia_codigo
    print("\nActualizando secuencia_codigo en Supabase...")
    res_seq = supabase.table('secuencia_codigo').select('id').execute()
    if res_seq.data:
        id_seq = res_seq.data[0]['id']
        supabase.table('secuencia_codigo').update({'ultimo_valor': max(39999, max_codigo)}).eq('id', id_seq).execute()
        proximo = max(40000, max_codigo + 1)
        print(f"Secuencia actualizada con éxito. Próximo cliente será el {proximo}.")
    else:
        # Si por alguna razón no existía la fila, la creamos
        supabase.table('secuencia_codigo').insert({'id': 1, 'ultimo_valor': max(39999, max_codigo)}).execute()
        proximo = max(40000, max_codigo + 1)
        print(f"Secuencia creada con éxito. Próximo cliente será el {proximo}.")
    
    # 2. Insertar Vendedores
    print("\nCreando usuarios para los Vendedores...")
    for vend in sorted(list(vendedores)):
        email = f"vendedor{vend}@presea.com"
        password = f"clave{vend}"
        
        res = supabase.table('usuarios').select('id').eq('email', email).execute()
        if not res.data:
            data = {
                "email": email,
                "password": password,
                "role": "vendedor",
                "nombre_vendedor": f"Vendedor {vend}",
                "codigo_vendedor": vend
            }
            supabase.table('usuarios').insert(data).execute()
            print(f"  [CREADO] Email: {email} | Clave: {password}")
        else:
            print(f"  [OMITIDO] El usuario {email} ya existe.")
            
    print("\n✅ ¡Importación completada con éxito!")

if __name__ == '__main__':
    importar()
