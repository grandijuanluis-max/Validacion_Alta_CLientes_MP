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

## Esquema de campos (CLIENTESPA.DBI — export real Presea)

| Campo | Tipo dBASE | Mapeo Supabase |
|-------|------------|----------------|
| CODIGO | N(15,0) | `codigo` (< 40000) |
| NOMBRE | C(30) | `nombre` |
| N_FANTASIA | C(30) | `n_fantasia` |
| CUIT | N(15,0) | `cuit` |
| DOMICILIO | C(50) | `domicilio_f` |
| LOCALIDAD | C(35) | `localidad` |
| C_POSTAL | C(5) | `c_postal` |
| PROVINCIA | C(25) | `provincia` |
| PAIS | C(20) | `pais` |
| CONTACTO | C(30) | `contacto` |
| TELEFONO | C(40) | `telefono` |
| RUBRO | C(30) | `giro_comercial` |
| TIPO_RESP | N(5,1) | `tipo_resp` |
| TIPO_DOC | N(2,0) | `tipo_doc` |
| TRANSPORTE | N(15,0) | (no se importa) |
| CATEGORIA | C(10) | (no se importa) |
| VENDEDOR | N(15,0) | `vendedor` |
| MEMO | M (memo) | `documento` — requiere `.FPT` |

**Importante:** el export Presea **no incluye** CUIT_S1, CUIT_S2, CONDICION ni LISTAPRE (sí existen en `Clientes_web.dbi` de la app).

**Archivo memo:** descargar también `CLIENTESPA.FPT` desde FTP, o el importador crea un sidecar vacío automáticamente.

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
