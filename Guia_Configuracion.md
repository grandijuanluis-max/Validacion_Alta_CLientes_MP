# Guía de Configuración: Supabase, GitHub y Streamlit

Esta guía te llevará paso a paso para interconectar los tres servicios y poner tu aplicación de Alta de Clientes (MP) en producción.

---

## PASO 1: GitHub (Alojar el código)

Para que Streamlit pueda ejecutar tu código, primero debe estar guardado en la nube de GitHub.

1. Abre **GitHub Desktop** (o la web de GitHub).
2. Selecciona **"Add Local Repository"** (Agregar Repositorio Local) y elige la carpeta `MP` que creamos en tu computadora (`AI/MP`). Te dirá que no es un repositorio Git, haz clic en **"Create a repository"**.
3. Dale el nombre `MP-Alta-Clientes` y haz clic en "Create Repository".
4. Escribe un mensaje en el recuadro inferior izquierdo (ej. "Versión inicial") y presiona el botón azul **"Commit to main"**.
5. Presiona **"Publish Repository"** en la barra superior. Asegúrate de desmarcar "Keep this code private" si quieres que Streamlit lo lea sin problemas (o déjalo privado, pero tendrás que darle permisos extra a Streamlit luego).
6. ¡Listo! El código ya está en la nube.

---

## PASO 2: Supabase (La Base de Datos)

Aquí es donde guardaremos los usuarios, los clientes y las reglas que me pediste.

1. Entra a [supabase.com](https://supabase.com) y accede al **Dashboard**.
2. Haz clic en el botón verde **"New Project"** (Nuevo Proyecto).
3. Selecciona tu organización, ponle un nombre al proyecto (ej. `Presea-Alta-Clientes`) y crea una contraseña segura para la base de datos (guárdala bien). 
4. Elige una región cercana (ej. São Paulo o EE.UU) y dale a **Create new project**. Tardará un par de minutos en configurarse.
5. **Crear las Tablas:**
   - En el menú lateral izquierdo, busca el ícono de **SQL Editor** (parece una ventanita de código `>_`).
   - Haz clic en **"New Query"**.
   - Abre el archivo `supabase_schema.sql` que te dejé en la carpeta del proyecto, **copia todo el texto** y pégalo en esa ventana de Supabase.
   - Presiona el botón verde **"RUN"** abajo a la derecha. Te dirá "Success". ¡Ya tienes tus tablas creadas!
6. **Obtener las Credenciales:**
   - Ve a los **Project Settings** (el ícono del engranaje ⚙️ abajo a la izquierda).
   - Haz clic en **"API"**.
   - Necesitamos dos cosas de aquí: 
     1. La **Project URL** (empieza con `https://...`).
     2. La clave pública **Project API keys (anon / public)**.
   - Pega esos dos valores en tu archivo `.streamlit/secrets.toml` de la carpeta local.

---

## PASO 3: Streamlit Community Cloud (El Servidor)

Finalmente, conectaremos el código de GitHub con los servidores de Streamlit para que la app esté viva en internet.

1. Entra a [share.streamlit.io](https://share.streamlit.io) e inicia sesión vinculando tu cuenta de GitHub.
2. Haz clic en **"New App"**.
3. Te pedirá elegir el repositorio. Busca el que creaste en el PASO 1 (`tu-usuario/MP-Alta-Clientes`).
4. En **Branch**, deja `main`. En **Main file path**, escribe `app.py`.
5. **¡MUY IMPORTANTE! Cargar los Secretos:**
   - Antes de darle a Deploy, haz clic abajo en **"Advanced settings..."**.
   - En el cuadro de texto que dice **"Secrets"**, copia y pega exactamente el mismo texto que tienes en tu archivo local `.streamlit/secrets.toml` (es decir, tu URL y KEY de Supabase).
   - Haz clic en Save.
6. Ahora sí, presiona el botón rojo **"Deploy!"**.

Verás que aparecen unas letras corriendo en la pantalla mientras se instalan los programas (`requirements.txt`) y en un par de minutos tu aplicación estará en vivo, con una URL pública que le podrás compartir a tus vendedores.
