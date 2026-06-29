-- ============================================================
-- PASO 1: Ejecutar PRIMERO para ver el nombre REAL del constraint
-- ============================================================
SELECT
    conname                        AS constraint_name,
    pg_get_constraintdef(oid)      AS definition
FROM pg_constraint
WHERE conrelid = 'ventas'::regclass
  AND contype = 'u'
ORDER BY conname;

-- El resultado te dará el nombre exacto.
-- Copialo y usalo en el PASO 2 abajo.

-- ============================================================
-- PASO 2: Borrar el constraint con el nombre que retornó el PASO 1
-- (reemplazá <NOMBRE_REAL> con lo que retornó la consulta)
-- ============================================================
-- ALTER TABLE ventas DROP CONSTRAINT "<NOMBRE_REAL>";

-- ============================================================
-- PASO 3: Crear el nuevo constraint con impo incluido
-- ============================================================
-- ALTER TABLE ventas
--   ADD CONSTRAINT ventas_unique_item
--   UNIQUE (fecha, empresa, formulario, numero, cod_clien, cod_alfa, bultos, impo);

-- ============================================================
-- ALTERNATIVA: Si querés hacer todo en un solo paso sin conocer el nombre,
-- ejecutá esto (borra TODOS los unique constraints de ventas y crea el nuevo)
-- ============================================================
DO $$
DECLARE
    v_conname TEXT;
BEGIN
    -- Obtener el nombre del constraint único actual
    SELECT conname INTO v_conname
    FROM pg_constraint
    WHERE conrelid = 'ventas'::regclass
      AND contype = 'u'
    LIMIT 1;

    IF v_conname IS NOT NULL THEN
        EXECUTE 'ALTER TABLE ventas DROP CONSTRAINT ' || quote_ident(v_conname);
        RAISE NOTICE 'Constraint % eliminado correctamente.', v_conname;
    ELSE
        RAISE NOTICE 'No se encontró ningún unique constraint en ventas.';
    END IF;

    -- Crear el nuevo constraint con impo
    ALTER TABLE ventas
        ADD CONSTRAINT ventas_unique_item
        UNIQUE (fecha, empresa, formulario, numero, cod_clien, cod_alfa, bultos, impo);

    RAISE NOTICE 'Nuevo constraint ventas_unique_item creado con 8 campos (incluye impo).';
END;
$$;

-- ============================================================
-- VERIFICAR que el nuevo constraint está activo
-- ============================================================
SELECT
    conname                    AS constraint_name,
    pg_get_constraintdef(oid)  AS definition
FROM pg_constraint
WHERE conrelid = 'ventas'::regclass
  AND contype = 'u';
