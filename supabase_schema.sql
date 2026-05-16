-- Schema de la Base de Datos Supabase para Sistema MP

-- 1. Tabla de Usuarios (Permisos y Roles)
CREATE TABLE public.usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL, -- En producción usar Auth de Supabase, para el MVP guardamos el hash o texto aquí si armamos un auth simple.
    role TEXT NOT NULL CHECK (role IN ('vendedor', 'admin')),
    usuario TEXT,
    codigo_vendedor NUMERIC, -- El código que va en el campo VENDEDOR del DBI
    permiso_alta BOOLEAN DEFAULT FALSE,
    permiso_validacion BOOLEAN DEFAULT FALSE
);

-- 2. Tabla de Clientes Pendientes
CREATE TABLE public.clientes_pendientes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    estado TEXT DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Validado', 'Exportado')),
    
    -- Datos del cliente
    cuit TEXT NOT NULL,
    nombre TEXT NOT NULL, -- Razón Social
    n_fantasia TEXT,
    domicilio_f TEXT, -- Domicilio Fiscal
    domicilio_e TEXT, -- Domicilio Entrega
    localidad TEXT,
    provincia TEXT, -- Provincia
    c_postal TEXT,
    pais TEXT, -- Nuevo campo de PAIS
    contacto TEXT,
    telefono TEXT,
    giro_comercial TEXT, -- Rubro / Ramo
    
    -- Control
    creado_por UUID REFERENCES public.usuarios(id),
    exportado_el TIMESTAMP WITH TIME ZONE
);

-- 3. Tabla de Secuencia para el CODIGO correlativo
CREATE TABLE public.secuencia_codigo (
    id SERIAL PRIMARY KEY,
    ultimo_valor NUMERIC NOT NULL DEFAULT 0
);
-- Inicializamos en 0 (arrancará del 1 cuando insertemos)
INSERT INTO public.secuencia_codigo (ultimo_valor) VALUES (0);

-- NOTA: La tabla RAMO y Códigos Postales pueden cargarse vía CSV directo a Supabase.
