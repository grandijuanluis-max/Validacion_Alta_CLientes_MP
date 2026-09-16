# Build `windows_sync.exe` (PyInstaller)

El `.exe` debe incluir los módulos de importación; si no, falla ventas (`ventas_importer`) o CLIENTESPA (`dbi_clientes`).

Desde la raíz del repo:

```bash
pip install pyinstaller
pyinstaller --onefile --name windows_sync \
  --paths utils --paths . \
  --hidden-import=dbf \
  --hidden-import=dbi_clientes \
  --hidden-import=ventas_importer \
  --collect-submodules=supabase \
  utils/windows_sync.py
```

**En el servidor (mínimo si el onefile no embebe módulos):** copiar junto a `windows_sync.exe`:

- `windows_sync_config.json` (recomendado; sin esto usa config embebida)
- `dbi_clientes.py` (import CLIENTESPA → Supabase)
- `ventas_importer.py` (import ventas)

Opcional: `dbi_clientes_loader.py`, `ventas_importer_loader.py`

Tras deploy, revisar `windows_sync.log` y `Exporta\exporta_sync.log`.
