# Sincronizador Windows — guía definitiva (CLIENTESPA → Supabase)

## Qué hace (ERP → Supabase)

1. Presea deja **`CLIENTESPA.DBI`** en `EXPORTA_DIR` (por defecto `F:\...\Validador\Exporta\`).
2. `windows_sync.exe` lee ese archivo **en disco** (no lo baja del FTP).
3. Inserta en Supabase solo clientes con **código &lt; 40000** que **aún no existen** en `clientes_pendientes`.
4. Sube copia al FTP (raíz del usuario) como respaldo.
5. Si el import OK, mueve el DBI a `Exporta\Subidos\`.

---

## Paso 1 — Compilar (PC Windows)

Llevá **solo la carpeta del repo** (clone o ZIP de GitHub). Mínimo:

```text
MP\
├── modulos\          (presea_db, ramos_utils, __init__.py)
└── utils\
    ├── windows_sync.py
    ├── windows_sync.spec
    ├── compilar_sincronizador.bat
    ├── dbi_clientes.py
    ├── ventas_importer.py
    ├── *_loader.py
    └── windows_sync_config.json.example
```

En **cmd**:

```text
cd ruta\al\repo\MP\utils
compilar_sincronizador.bat
```

Resultado: **`utils\windows_sync.exe`** (incluye importadores; no hace falta copiar `.py` al servidor).

---

## Paso 2 — Instalar en servidor Presea

Copiá a **una carpeta fija** (ej. donde ya corre el Task Scheduler):

- `windows_sync.exe`

La **primera ejecución** crea `windows_sync_config.json` desde el `.example` embebido si no existe.

Editá **`windows_sync_config.json`** (una sola vez):

- `FTP_USER` / `FTP_PASS`
- `SUPABASE_URL` / `SUPABASE_KEY` (ideal: **service role**)
- `IMPORTA_DIR`, `EXPORTA_DIR`, `VENTAS_DIR`

---

## Paso 3 — Presea

Confirmá que el ERP exporta:

```text
EXPORTA_DIR\CLIENTESPA.DBI
```

(opcional memo: `CLIENTESPA.FPT`)

---

## Paso 4 — Programar tareas

Lun–vie 09:00, 13:00, 17:00 → ejecutar `windows_sync.exe`.

---

## Paso 5 — Verificar

Tras una corrida con DBI en Exporta, en **`windows_sync.log`**:

```text
CLIENTESPA detectado: ...
CLIENTESPA → Supabase: nuevos=X omitidos_existentes=Y errores=0
```

En Supabase:

```sql
SELECT codigo, nombre, origen, created_at
FROM clientes_pendientes
WHERE origen = 'presea'
ORDER BY created_at DESC
LIMIT 10;
```

---

## Errores frecuentes

| Síntoma | Causa |
|--------|--------|
| No aparece CLIENTESPA en log | No hay DBI en `EXPORTA_DIR` o ya está en `Subidos` |
| `nuevos=0`, omitidos altos | Códigos ya están en Supabase (normal en padrón completo) |
| `Faltan columnas origen/codigo` | Ejecutar `supabase_migration_presea_clientes.sql` |
| Import fallido, DBI sigue en Exporta | Revisar log; corregir y volver a ejecutar |
