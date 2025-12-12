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
- Base de datos Postgres accesible desde `DATABASE_URL` (para Neon incluye `sslmode=require`).
- Variable `SECRET_KEY` para las sesiones (si no se define se usa un valor por defecto).
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
3. Configura la variable `DATABASE_URL` apuntando a tu Postgres (ejemplo Neon: `postgresql://usuario:password@host/neondb?sslmode=require`).
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

1. Crea una base de datos en Neon y copia la cadena `DATABASE_URL` (incluye `sslmode=require`).
2. En Vercel agrega las variables de entorno `DATABASE_URL` y `SECRET_KEY` (opcionalmente `PGPOOL_MIN_SIZE` y `PGPOOL_MAX_SIZE`).
3. Usa el mismo repositorio; Vercel instalara dependencias desde `requirements.txt` y puede ejecutar la app con `gunicorn app:app` (definido en `Procfile`).
