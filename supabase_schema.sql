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

-- 4. Tabla de Ramos (Alta velocidad)
CREATE TABLE public.ramos (
    ramo NUMERIC PRIMARY KEY,
    descrip TEXT NOT NULL UNIQUE
);
-- Índice para búsquedas rápidas (por si a futuro hay autocompletado en ramos)
CREATE INDEX idx_ramos_descrip ON public.ramos(descrip);

-- 5. Tabla de Códigos Postales (Alta velocidad para +20.000 registros)
CREATE TABLE public.codigos_postales (
    id SERIAL PRIMARY KEY,
    localidad TEXT NOT NULL,
    provincia TEXT NOT NULL,
    cp TEXT NOT NULL
);
-- Índice COMPUESTO crítico para que el filtro de AFIP vuele (Localidad + Provincia)
CREATE INDEX idx_codigos_postales_loc_prov ON public.codigos_postales(localidad, provincia);

-- 6. Tabla de Ventas (Análisis de Gestión)
CREATE TABLE public.ventas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    rubro TEXT,
    fecha DATE NOT NULL,
    empresa TEXT NOT NULL,
    subrubro TEXT,
    numero NUMERIC NOT NULL,
    localidad TEXT,
    provincia TEXT,
    formulario TEXT NOT NULL,
    e_mail TEXT,
    telefono TEXT,
    pais TEXT,
    codigo NUMERIC,
    cod_alfa TEXT,
    unidades NUMERIC,
    codigocomp NUMERIC,
    tipo NUMERIC,
    dto NUMERIC(15,4),
    dto1 NUMERIC(15,4),
    dto2 NUMERIC(15,4),
    alt_bonifi TEXT,
    grupo TEXT,
    sinonimo TEXT,
    ean TEXT,
    clien TEXT,
    cod_clien NUMERIC NOT NULL,
    producto TEXT,
    vendedo TEXT,
    domicilio TEXT,
    deposito TEXT,
    bultos NUMERIC(15,6),
    impo NUMERIC(15,2)
);

-- Restricción única compuesta para evitar duplicados al sincronizar (8 campos, incluye impo)
ALTER TABLE public.ventas 
ADD CONSTRAINT ventas_unique_item UNIQUE (fecha, empresa, formulario, numero, cod_clien, cod_alfa, bultos, impo);

