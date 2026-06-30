"""Import helper — resuelve dbi_clientes desde utils/ o bundle PyInstaller."""


def import_clientespa_module():
    try:
        from utils.dbi_clientes import import_clientespa_to_supabase, scan_clientespa_metadata
        return import_clientespa_to_supabase, scan_clientespa_metadata
    except ImportError:
        from dbi_clientes import import_clientespa_to_supabase, scan_clientespa_metadata
        return import_clientespa_to_supabase, scan_clientespa_metadata
