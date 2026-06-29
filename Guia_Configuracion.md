# Guía de Configuración: Supabase, GitHub y Streamlit Cloud

Guía para poner en producción la aplicación MP (Validación y Alta de Clientes + Análisis de Gestión).

**Repositorio GitHub:** `grandijuanluis-max/Validacion_Alta_CLientes_MP`

---

## Resumen del flujo de ventas (tableros)

Los tableros **no leen** `ventas.dbi` directamente desde la nube. El flujo es:

1. Presea exporta → `F:\Clientes\Pasina\EXPORTACIONES\Ventas\ventas.dbi`
2. `windows_sync.exe` en Windows Server importa a Supabase (tabla `ventas`)
3. Streamlit Cloud lee Supabase para mostrar los tableros

La carga manual de históricos (upload en la UI) es solo un respaldo opcional.

---

## PASO 1: GitHub

1. El código vive en: `https://github.com/grandijuanluis-max/Validacion_Alta_CLientes_MP`
2. Cada cambio local se sube con:
   ```bash
   git add -A
   git commit -m "Descripción del cambio"
   git push origin main
   ```
3. Streamlit Cloud se reconecta automáticamente al hacer push en `main`.

---

## PASO 2: Supabase

1. Entrá a [supabase.com](https://supabase.com) → tu proyecto (ej. `sspjbsbuklqiekvxgdtc`).
2. **SQL Editor → New Query:**
   - Proyecto nuevo: ejecutar todo `supabase_schema.sql`
   - Proyecto existente con tabla `ventas`: ejecutar `supabase_fix_ventas_constraint.sql` para alinear el UNIQUE de 8 campos (incluye `impo`)
3. **Project Settings → API:**
   - Copiar **Project URL**
   - Copiar **anon public key** (para Streamlit)
   - Para `windows_sync.exe` en el servidor se puede usar la misma anon key o service role (según políticas RLS)

---

## PASO 3: Streamlit Community Cloud

1. [share.streamlit.io](https://share.streamlit.io) → iniciar sesión con GitHub.
2. **New app:**
   - Repository: `grandijuanluis-max/Validacion_Alta_CLientes_MP`
   - Branch: `main`
   - Main file: `app.py`
3. **Advanced settings → Secrets:** pegar el contenido completo (basado en `.streamlit/secrets.toml.example`):

```toml
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_KEY = "eyJ..."

GOOGLE_API_KEY = "AIza..."

NOSIS_USUARIO = "000000"
NOSIS_TOKEN = "uuid..."
NOSIS_URL = "https://ws01.nosis.com"
NOSIS_VR = "1"

FTP_HOST = "messina.dns-dns.com"
FTP_PORT = 59921
FTP_USER = "ftppasina"
FTP_PASS = "..."

AFIP_CRT = """
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
"""

AFIP_KEY = """
-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
"""
```

4. **Deploy.** Python 3.11 se toma de `.python-version`. Dependencias de `requirements.txt`.

### Notas Streamlit Cloud

- **AFIP:** requiere certificados en Secrets (`AFIP_CRT` / `AFIP_KEY`). Si falla la consulta CUIT, revisar `Guia_AFIP.md`.
- **FTP:** usado para sync de clientes exportados/importados, no para ventas en runtime.
- **Ventas / tableros:** solo necesitan Supabase con datos en tabla `ventas`.

---

## PASO 4: Windows Server (sincronizador Presea)

Este paso **no corre en Streamlit**. Es el puente que alimenta Supabase con ventas y clientes.

1. Copiar al servidor:
   - `utils/windows_sync.py`
   - `utils/ventas_importer.py`
   - `utils/windows_sync_config.json` (desde `windows_sync_config.json.example`, con credenciales reales)
2. Compilar con `utils/compilar_sincronizador.bat` → `windows_sync.exe`
3. **Task Scheduler:** ejecutar `windows_sync.exe` cada 15 minutos.
4. Verificar que Presea exporte `ventas.dbi` en:
   ```
   F:\Clientes\Pasina\EXPORTACIONES\Ventas\ventas.dbi
   ```

El exe importa ventas a Supabase, mueve el DBI a `Ventas\Subidos\` y sube copia al FTP `/Ventas/`.

---

## Checklist de puesta en marcha

- [ ] `supabase_schema.sql` ejecutado (o migración `supabase_fix_ventas_constraint.sql` si ya había ventas)
- [ ] Secrets completos en Streamlit Cloud
- [ ] App desplegada y login funcional
- [ ] `windows_sync.exe` programado en Windows Server
- [ ] Presea exportando `ventas.dbi` periódicamente
- [ ] Tabla `ventas` en Supabase con datos recientes
- [ ] Tableros en Análisis de Gestión muestran ventas

---

## Verificación rápida de ventas

Desde una máquina con Python y acceso al DBI:

```bash
python scripts/verify_ventas_sync.py F:\Clientes\Pasina\EXPORTACIONES\Ventas\ventas.dbi
```

Compara conteos del DBF contra Supabase.
