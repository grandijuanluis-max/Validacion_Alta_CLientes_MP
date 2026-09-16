"""Import helper — resuelve ventas_importer desde utils/ o bundle PyInstaller."""


def import_ventas_module():
    try:
        from utils.ventas_importer import import_ventas_dbi
        return import_ventas_dbi
    except ImportError:
        from ventas_importer import import_ventas_dbi
        return import_ventas_dbi
