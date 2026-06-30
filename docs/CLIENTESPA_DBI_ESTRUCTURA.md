# Estructura del archivo CLIENTESPA.DBI (Presea ERP)

Archivo dBASE exportado por Presea desde:
```
F:\Clientes\Pasina\EXPORTACIONES\Validador\Exporta\CLIENTESPA.DBI
```

Procesado diariamente por `windows_sync.exe` → FTP → Supabase (`clientes_pendientes`, origen=`presea`).

---

## Regla de códigos

| Origen | Rango CODIGO | Descripción |
|--------|--------------|-------------|
| Presea ERP | **1 – 39.999** | Altas excepcionales directas en el ERP |
| Aplicación web | **40.000+** | Altas normales desde Streamlit |

---

## Esquema de campos (CLIENTESPA.DBI / Clientes_web.dbi)

| Campo | Tipo dBASE | Longitud | Obligatorio | Mapeo Supabase |
|-------|------------|----------|-------------|----------------|
| CODIGO | N | 6,0 | Sí | `codigo` |
| NOMBRE | C | 30 | Sí | `nombre` |
| N_FANTASIA | C | 30 | No | `n_fantasia` |
| CUIT | N | 12,0 | Sí | `cuit` (formato XX-XXXXXXXX-X) |
| DOMICILIO | C | 50 | Sí | `domicilio_f` |
| LOCALIDAD | C | 35 | Sí | `localidad` |
| C_POSTAL | C | 50 | Sí | `c_postal` |
| PROVINCIA | C | 25 | Sí | `provincia` |
| PAIS | C | 20 | No | `pais` (default ARGENTINA) |
| CONTACTO | C | 30 | No | `contacto` |
| TELEFONO | C | 40 | No | `telefono` |
| RUBRO | C | 30 | No | `giro_comercial` |
| TIPO_RESP | N | 5,1 | Sí | `tipo_resp` (1.0=RI, 3.0=Mono, etc.) |
| TIPO_DOC | N | 2,0 | Sí | `tipo_doc` (default 80) |
| CUIT_S1 | N | 12,0 | No | `cuit_socio1` |
| CUIT_S2 | N | 12,0 | No | `cuit_socio2` |
| TRANSPORTE | N | 2,0 | Sí | Fijo: 1 |
| CONDICION | N | 2,0 | Sí | Fijo: 1 |
| CATEGORIA | C | 10 | Sí | Fijo: CLI_GRAL |
| LISTAPRE | C | 10 | Sí | Fijo: LISTA_UNIC |
| VENDEDOR | N | 6,0 | Sí | `vendedor` |
| MEMO | M | memo | No | `documento` (observaciones) |

**Formato técnico:** dBASE III/IV (`dbf_type='fp'`), codepage `cp1252`.  
**Archivo memo:** `CLIENTESPA.FPT` (campo MEMO).

---

## Flujo de importación

```
Presea exporta CLIENTESPA.DBI
        ↓
F:\...\Validador\Exporta\
        ↓  (Task Scheduler ~15 min)
windows_sync.exe
        ├─ Sube copia al FTP
        ├─ Importa clientes CODIGO < 40000 → Supabase
        ├─ Actualiza secuencia_codigo (max codigo)
        └─ Mueve DBI a Exporta\Subidos\
        ↓
Streamlit → solapa "Clientes Altas desde Presea"
```

---

## Exportación de cambios hacia Presea

Cuando el validador confirma cambios y marca **"Enviar a Presea"**:

1. Se genera `Clientes_web.dbi` con el **mismo CODIGO** del cliente Presea
2. Se genera `domicilios_entrega.txt`
3. Se sube al FTP
4. `windows_sync.exe` descarga a carpeta **Importa** de Presea

---

## Ejemplo de registro válido

```
CODIGO=1234, NOMBRE="DISTRIBUIDORA EJEMPLO SA", CUIT=30123456789,
DOMICILIO="AV. CORRIENTES 1234", LOCALIDAD="CABA", C_POSTAL="1043",
PROVINCIA="CAPITAL FEDERAL", TIPO_RESP=1.0, TIPO_DOC=80, VENDEDOR=5
```

---

## Migración Supabase requerida

Ejecutar `supabase_migration_presea_clientes.sql` antes del primer import.
