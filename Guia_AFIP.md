# Preparación para Conexión con AFIP (Padrón A5)

Para conectar el sistema MP automáticamente con la base de datos de AFIP y extraer la Razón Social y Domicilio a partir de un CUIT, tenemos dos caminos posibles para implementar mañana. 

Por favor, lee ambas opciones y decide cuál prefieres usar:

## Opción 1: Conexión Directa (Gratis, pero más compleja)
Requiere generar certificados digitales oficiales en la página de AFIP.

**Lo que necesitas tener a mano:**
1. Clave Fiscal Nivel 3.
2. Ingresar al servicio "Administrador de Relaciones de Clave Fiscal".
3. Generar un certificado digital `.crt` y una clave privada `.key`.
4. Delegar el servicio `ws_sr_padron_a5` a tu propio CUIT.
*(Si eliges esta opción, mañana te guiaré paso a paso sobre cómo generar estos archivos).*

## Opción 2: Usar un Wrapper / API de Terceros (Muy fácil)
Empresas como `afip.ws` o `apiset.com.ar` ya tienen los certificados de AFIP instalados y te ofrecen una API simple donde solo envías el CUIT y te devuelven un JSON.

**Lo que necesitas:**
1. Crear una cuenta gratuita en uno de estos servicios.
2. Copiar el "API Token" que te den.
3. Lo ponemos en los `secrets.toml` y ¡listo! En 5 minutos está funcionando.
*(Tienen planes gratuitos que permiten cientos de consultas por mes, ideal para altas de clientes).*

---

**Nota Técnica sobre el Sistema:**
El módulo `modulos/api_afip.py` ya está estructurado y listo. Mañana solo tenemos que inyectar el código de la Opción 1 o la Opción 2.
