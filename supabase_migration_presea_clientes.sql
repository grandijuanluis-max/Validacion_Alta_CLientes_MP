-- Migración: soporte clientes dados de alta en Presea ERP (codigo < 40000)
-- Ejecutar en Supabase SQL Editor

ALTER TABLE public.clientes_pendientes
    ADD COLUMN IF NOT EXISTS codigo NUMERIC,
    ADD COLUMN IF NOT EXISTS origen TEXT DEFAULT 'app',
    ADD COLUMN IF NOT EXISTS vendedor TEXT,
    ADD COLUMN IF NOT EXISTS validado_arca BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS validado_nosis BOOLEAN DEFAULT FALSE;

-- Índice para búsqueda por código Presea
CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_presea_codigo
    ON public.clientes_pendientes (codigo)
    WHERE origen = 'presea' AND codigo IS NOT NULL;

-- Marcar registros existentes de la app
UPDATE public.clientes_pendientes
SET origen = 'app'
WHERE origen IS NULL;

COMMENT ON COLUMN public.clientes_pendientes.codigo IS 'Código Presea. <40000 = ERP, >=40000 = alta web';
COMMENT ON COLUMN public.clientes_pendientes.origen IS 'app | presea';
