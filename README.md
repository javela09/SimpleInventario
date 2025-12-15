# Lector de Codigos de Barras

Aplicacion web simple para leer codigos de barras y validarlos contra un maestro de articulos.

## Caracteristicas

- Escaneo rapido con lector o entrada manual.
- Validacion contra maestro de articulos.
- Registro automatico de EAN, codigo interno y descripcion.
- Importacion masiva de articulos desde Excel.
- Exportacion de lecturas a Excel (.xlsx).

## Requisitos

- Python 3.11.
- Base de datos Postgres accesible desde `DATABASE_URL` (si no incluyes `sslmode=require` la app lo forzara, recomendado para Neon).
- Variable `SECRET_KEY` para las sesiones (si no se define se usa un valor por defecto solo apto para desarrollo).
- Variables opcionales `PGPOOL_MIN_SIZE` y `PGPOOL_MAX_SIZE` para ajustar el pool de conexiones.

## Instalacion local

1. Clona el repositorio:
   ```bash
   git clone https://github.com/tu-usuario/simple-inventario.git
   cd simple-inventario
   ```
2. Crea un entorno virtual e instala dependencias:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
3. Configura la variable `DATABASE_URL` apuntando a tu Postgres (ejemplo Neon: `postgresql://usuario:password@host/neondb?sslmode=require`; si omites `sslmode` la app agregara `sslmode=require`).
4. Ejecuta la aplicacion:
   ```bash
   python app.py
   ```
5. Abre `http://localhost:5000` en el navegador.

## Formato del Excel para importar

El archivo Excel debe tener 3 columnas (con encabezados en la primera fila):

| Codigo Articulo | Descripcion        | EAN           |
|-----------------|--------------------|---------------|
| ART001          | Producto ejemplo 1 | 8412345678901 |
| ART002          | Producto ejemplo 2 | 8412345678902 |

## Base de datos

### Tabla: articulos (Maestro)
- `codigo_articulo`: Codigo interno del articulo.
- `descripcion`: Descripcion del articulo.
- `ean`: Codigo de barras (unico).

### Tabla: lecturas
- `ean`: Codigo de barras leido.
- `codigo_articulo`: Codigo interno.
- `descripcion`: Descripcion del articulo.
- `fecha_lectura`: Fecha y hora de la lectura.

Los usuarios `admin` y `henkobit` se crean automaticamente como administradores al iniciar la aplicacion.

## Tecnologias

- Backend: Flask 3.0.0
- Base de datos: Postgres (Neon en despliegue)
- Frontend: HTML5, CSS3, JavaScript (vanilla)

## Despliegue en Vercel + Neon

1. Crea una base de datos en Neon Serverless y copia la cadena `DATABASE_URL`. Incluye `sslmode=require` o deja que la app lo añada.
2. En Vercel define las variables de entorno `DATABASE_URL` y `SECRET_KEY` (opcionalmente `PGPOOL_MIN_SIZE` y `PGPOOL_MAX_SIZE`).
3. Despliega con la CLI de Vercel (`vercel --prod`). El archivo `vercel.json` ya enruta todas las peticiones a `app.py` usando el runtime de Python 3.11 y sirve `/static` y plantillas como assets.
4. Los usuarios `admin` y `henkobit` se crean automáticamente en cada instancia para que puedas entrar al panel de administración y gestionar usuarios y artículos.

> Nota: SQLite ya no se usa; toda la persistencia vive en Postgres/Neon.
