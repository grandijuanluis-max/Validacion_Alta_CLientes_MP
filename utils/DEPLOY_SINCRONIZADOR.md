# Sincronizador Windows — guía definitiva (CLIENTESPA → Supabase)

## Qué hace (ERP → Supabase)

1. Presea deja **`CLIENTESPA.DBI`** en `EXPORTA_DIR` (por defecto `F:\...\Validador\Exporta\`).
2. `windows_sync.exe` lee ese archivo **en disco** (no lo baja del FTP).
3. Inserta en Supabase solo clientes con **código &lt; 40000** que **aún no existen** en `clientes_pendientes`.
4. Sube copia al FTP (raíz del usuario) como respaldo.
5. Si el import OK, mueve el DBI a `Exporta\Subidos\`.

---

## Paso 1 — Compilar (PC Windows)

**No alcanza con copiar solo `compilar_sincronizador.bat`.** PyInstaller necesita el `.py` y el resto del proyecto. Usá clone o ZIP de GitHub (lista mínima en `COMPILAR_MINIMO.txt`).

Llevá **la carpeta del repo** (clone o ZIP de GitHub). Mínimo:

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

**No borres** el `windows_sync_config.json` que ya tenías al actualizar el exe. Si no existe, la primera ejecución crea uno desde la plantilla (`TU_PROYECTO` → hay que editarlo).

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
| `[Errno 11001] getaddrinfo failed` al inicio | `SUPABASE_URL` sigue siendo plantilla o URL mal escrita. Debe ser `https://xxxx.supabase.co` (copiar del panel Supabase). |
| Se creó config desde plantilla + “credenciales cifradas” | La 1ª corrida generó el JSON; **editá** ese archivo con datos reales y volvé a ejecutar. |
| Muchos intentos FTP y timeout | `FTP_HOST` / puerto incorrectos para **esta** red. En LAN suele ser IP tipo `192.168.100.2` y puerto `59921`, no el DNS público. |
| No aparece CLIENTESPA en log | No hay DBI en `EXPORTA_DIR` o ya está en `Subidos` |
| `nuevos=0`, omitidos altos | Códigos ya están en Supabase (normal en padrón completo) |
| `Faltan columnas origen/codigo` | Ejecutar `supabase_migration_presea_clientes.sql` |
| Import fallido, DBI sigue en Exporta | Revisar log; corregir y volver a ejecutar |

**Importante:** CLIENTESPA se lee de `Exporta\` en disco. El FTP es solo respaldo; aunque falle el FTP, Supabase debe importarse si URL/KEY y el DBI están bien.

### Si configuraste `sb_secret_...` y sigue sin subir

1. En el log debe aparecer **`Supabase OK: lectura en clientes_pendientes`**. Si no aparece:
   - Probá **`SUPABASE_KEY`** = clave **service_role** legacy (`eyJ...`, pestaña *Legacy anon, service_role*), **Reveal → Copy**.
   - O recompilá el `.exe` con `compilar_sincronizador.bat` (instala `supabase>=2.16` para soportar `sb_secret_`).
2. Buscá **`CLIENTESPA detectado`**. Si no está → el DBI no está en `EXPORTA_DIR` o ya está en `Subidos`.
3. Buscá **`CLIENTESPA → Supabase: nuevos=`**. `nuevos=0` con muchos omitidos = ya estaban en la tabla (no es fallo).
