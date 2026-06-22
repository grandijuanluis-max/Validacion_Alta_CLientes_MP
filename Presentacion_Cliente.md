# Presentación del Proyecto: Sistema de Alta Rápida de Clientes (SARC)

## 🎯 Objetivo Principal
Optimizar y descentralizar el proceso de alta de clientes, permitiendo a la fuerza de ventas iniciar el proceso desde cualquier lugar y dispositivo sin necesidad de acceder al sistema ERP (Presea) ni requerir licencias adicionales.

## ✨ Beneficios Clave (Bondades del Sistema)

1. **Agilidad en la Venta:** Los vendedores pueden cargar un cliente en segundos, directamente en la calle o desde su celular, evitando demoras burocráticas y agilizando la toma de pedidos.
2. **Carga Inteligente sin Errores:** Al ingresar únicamente el **CUIT** del cliente, el sistema se conecta automáticamente con los padrones oficiales (AFIP/ARCA) para autocompletar la Razón Social y los Domicilios (Fiscal y de Entrega), eliminando errores de tipeo y asegurando información verídica.
3. **Estandarización de Datos:** El sistema cruza automáticamente los datos de localidad con una tabla interna de Códigos Postales autorizados, asegurando que la información ingrese perfectamente formateada a Presea. Lo mismo ocurre con el "Giro Comercial", el cual se selecciona de una lista curada (Tabla RAMO).
4. **Seguridad y Control (Workflow de Aprobación):** Los datos cargados por los vendedores no impactan directamente en el sistema ERP. Entran a una "sala de espera" donde un usuario con perfil de *Validador* o *Supervisor* revisa, corrige (si es necesario) y aprueba la solicitud.
5. **Integración Transparente con Presea:** Una vez validados, el sistema cuenta con un botón para generar automáticamente el lote de clientes en formato nativo `.DBI`. Un autómata tomará este archivo y lo inyectará a Presea, asegurando que la base de datos se mantenga limpia y sin corrupciones.

## 🚀 Cómo Funciona (El Flujo de Trabajo)

### Paso 1: El Vendedor (Alta Rápida)
- Accede a la plataforma web con su usuario y contraseña.
- Ingresa el **CUIT** del nuevo cliente.
- El sistema **autocompleta**:
  - `NOMBRE` (Razón Social)
  - `Domicilio Fiscal`
  - `Domicilio de Entrega`
  - `Localidad` y `Provincia` (Estandarizado según código postal).
- El vendedor solo debe rellenar los datos de contacto:
  - `Nombre de Fantasía`
  - `Teléfono`
  - `Giro Comercial` (Desplegable)
- Envía la solicitud y vuelve a enfocarse en vender.

### Paso 2: El Validador (Control de Calidad)
- Un usuario con privilegios administrativos ingresa al sistema y ve el tablero de "Altas Pendientes".
- Revisa que los datos complementarios estén correctos.
- Aprueba los perfiles aptos.

### Paso 3: Sincronización Automática
- Con un solo clic en "Exportar a Presea", el sistema empaqueta los clientes aprobados en un archivo `.DBI`.
- El autómata de Neuralsoft Presea absorbe el archivo e incorpora los clientes de manera automática.

---
**Resultado:** Un proceso de onboarding de clientes *más rápido, 100% seguro y libre de errores de carga manual*.
