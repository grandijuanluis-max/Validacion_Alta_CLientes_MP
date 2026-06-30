# MP — Validación y Alta de Clientes (Pasina / SARC)

Aplicación Streamlit para alta rápida de clientes (AFIP + Nosis + export DBI a Presea) y tableros de **Análisis de Gestión** desde ventas en Supabase.

**Repositorio:** [grandijuanluis-max/Validacion_Alta_CLientes_MP](https://github.com/grandijuanluis-max/Validacion_Alta_CLientes_MP)

---

## Arquitectura

```
┌─────────────────┐     exporta      ┌──────────────────────────────────────┐
│   Presea ERP    │ ───────────────► │ F:\...\EXPORTACIONES\Ventas\        │
│                 │   ventas.dbi     │         ventas.dbi                     │
└─────────────────┘                  └──────────────┬───────────────────────┘
                                                    │
                              Task Scheduler (~15 min)
                                                    ▼
┌─────────────────┐   importa upsert   ┌──────────────────────────────────┐
│  Windows Server │ ─────────────────► │ Supabase — tabla `ventas`        │
│ windows_sync.exe│                    └──────────────┬───────────────────┘
└────────┬────────┘                                   │
         │ backup FTP /Ventas/ventas.dbi              │ SELECT (paginado)
         ▼                                            ▼
┌─────────────────┐                          ┌─────────────────────────────┐
│ FTP Pasina      │                          │ Streamlit Cloud — app.py    │
│ (solo respaldo) │                          │ Análisis de Gestión         │
└─────────────────┘                          └─────────────────────────────┘
```

| Componente | Rol |
|------------|-----|
| **Streamlit Cloud** | UI web: validador, usuarios, exportación clientes |
| **Supabase** | PostgreSQL: usuarios, clientes, ramos, CP, **ventas** |
| **Windows Server** | `windows_sync.exe`: puente Presea ↔ FTP ↔ Supabase |
| **FTP Pasina** | Respaldo de archivos; sync de clientes import/export |

---

## ¿De dónde sale `ventas.dbi` para los tableros?

### En producción (automático)

1. **Presea** exporta el archivo a:
   ```
   F:\Clientes\Pasina\EXPORTACIONES\Ventas\ventas.dbi
   ```
2. **`windows_sync.exe`** (Windows Server, Task Scheduler cada ~15 min) lo detecta, lo importa a Supabase (`ventas`) y lo mueve a `Ventas\Subidos\`.
3. Opcionalmente sube una copia al FTP en `/Ventas/ventas.dbi` (respaldo).
4. **Streamlit Cloud NO lee el DBI.** Los tableros consultan **solo Supabase** (`modulos/ui_gestion.py` → tabla `ventas`).

### Alternativa manual (carga histórica)

En la app, módulo **Análisis de Gestión** → expander **Carga Histórica de Ventas**: subir un `ventas.dbi` manualmente (requiere permiso `permisos_av`). Usa el mismo importador que el sync de Windows (`utils/ventas_importer.py`).

---

## Despliegue en la nube

### 1. GitHub

Código en `main`. Push desde la carpeta del proyecto:

```bash
cd AI/MP
git add -A && git commit -m "..." && git push origin main
```

### 2. Supabase

1. Crear proyecto en [supabase.com](https://supabase.com).
2. Ejecutar `supabase_schema.sql` en SQL Editor.
3. Si la tabla `ventas` ya existía con constraint de 7 campos, ejecutar también `supabase_fix_ventas_constraint.sql` (incluye `impo` en la clave única).
4. Copiar **Project URL** y **anon key** → secrets de Streamlit.

### 3. Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io) → **New app**.
2. Repo: `grandijuanluis-max/Validacion_Alta_CLientes_MP`, branch `main`, file `app.py`.
3. **Advanced settings → Secrets:** copiar desde `.streamlit/secrets.toml.example` y completar valores reales.
4. Python **3.11** (`.python-version` en el repo).

Variables requeridas en Secrets: `SUPABASE_URL`, `SUPABASE_KEY`, `GOOGLE_API_KEY`, `NOSIS_*`, `FTP_*`, `AFIP_CRT`, `AFIP_KEY` (ver ejemplo).

### 4. Windows Server (sync Presea)

1. Clonar repo o copiar `utils/windows_sync.py`, `utils/ventas_importer.py`, `utils/windows_sync_config.json`.
2. Configurar `windows_sync_config.json` (ver `utils/windows_sync_config.json.example`).
3. Compilar: `utils/compilar_sincronizador.bat` → genera `windows_sync.exe`.
4. Programar en Task Scheduler: ejecutar `windows_sync.exe` cada 15 minutos.

---

## Desarrollo local

```bash
cd AI/MP
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # completar valores
streamlit run app.py
```

Verificar sync ventas (opcional):

```bash
python scripts/verify_ventas_sync.py /ruta/a/ventas.dbi
```

---

## Archivos clave

| Archivo | Descripción |
|---------|-------------|
| `app.py` | Entry point Streamlit |
| `utils/windows_sync.py` | Sync Windows: clientes + ventas |
| `utils/ventas_importer.py` | Import DBI → Supabase (compartido) |
| `modulos/ui_gestion.py` | Tableros y carga histórica |
| `modulos/ui_presea.py` | Validación clientes altas Presea (<40000) |
| `utils/dbi_clientes.py` | Import CLIENTESPA.DBI → Supabase |
| `docs/CLIENTESPA_DBI_ESTRUCTURA.md` | Especificación DBI Presea |
| `supabase_schema.sql` | Esquema inicial |
| `supabase_fix_ventas_constraint.sql` | Migración constraint 8 campos |
| `.streamlit/secrets.toml.example` | Plantilla de secrets |

---

## Documentación adicional

- `Guia_Configuracion.md` — paso a paso GitHub + Supabase + Streamlit
- `Guia_AFIP.md` — certificados AFIP para consulta CUIT
