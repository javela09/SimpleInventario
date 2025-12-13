from flask import Flask, render_template, request, jsonify, send_file, session
import os
from datetime import datetime
from io import StringIO

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

_pool: ConnectionPool | None = None
_schema_ready = False


def _ensure_schema(pool: ConnectionPool) -> None:
    """Crea tablas/índices necesarios una vez por instancia."""
    global _schema_ready
    if _schema_ready:
        return

    with pool.connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    nombre_usuario VARCHAR(255) NOT NULL UNIQUE,
                    es_admin BOOLEAN DEFAULT FALSE,
                    fecha_creacion TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS articulos (
                    id SERIAL PRIMARY KEY,
                    codigo_articulo VARCHAR(255) NOT NULL,
                    descripcion TEXT,
                    ean VARCHAR(255),
                    fecha_creacion TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Para búsquedas rápidas y para futuros UPSERTs (si algún día lo necesitas)
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS articulos_ean_unique_idx ON articulos (ean)"
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lecturas (
                    id SERIAL PRIMARY KEY,
                    usuario VARCHAR(255) NOT NULL,
                    ean VARCHAR(255) NOT NULL,
                    codigo_articulo VARCHAR(255) NOT NULL,
                    descripcion TEXT,
                    fecha_lectura TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Admins por defecto (idempotente)
            cursor.execute(
                "INSERT INTO usuarios (nombre_usuario, es_admin) VALUES (%s, %s) "
                "ON CONFLICT (nombre_usuario) DO NOTHING",
                ("admin", True),
            )
            cursor.execute(
                "INSERT INTO usuarios (nombre_usuario, es_admin) VALUES (%s, %s) "
                "ON CONFLICT (nombre_usuario) DO NOTHING",
                ("henkobit", True),
            )

        conn.commit()

    _schema_ready = True


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL no configurada")

        _pool = ConnectionPool(
            conninfo=database_url,
            min_size=int(os.environ.get("PGPOOL_MIN_SIZE", 1)),
            max_size=int(os.environ.get("PGPOOL_MAX_SIZE", 3)),
            kwargs={"row_factory": dict_row},
        )

    _ensure_schema(_pool)
    return _pool


def get_db():
    return get_pool().connection()


@app.route("/")
def index():
    return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    usuario = (data.get("usuario") or "").strip()

    if not usuario:
        return jsonify({"success": False, "message": "Usuario requerido"}), 400

    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, es_admin FROM usuarios WHERE nombre_usuario = %s",
                (usuario,),
            )
            user = cursor.fetchone()

    if not user:
        return jsonify({"success": False, "message": "Usuario no autorizado"}), 403

    session["usuario"] = usuario
    session["es_admin"] = bool(user["es_admin"])
    return jsonify({"success": True, "es_admin": bool(user["es_admin"])})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/lecturas")
def lecturas():
    if "usuario" not in session:
        return render_template("login.html")

    if session.get("es_admin"):
        return render_template("admin.html", usuario=session["usuario"])

    return render_template("lecturas.html", usuario=session["usuario"])


@app.route("/api/escanear", methods=["POST"])
def escanear():
    data = request.json or {}
    ean = (data.get("ean") or "").strip()

    if not ean:
        return jsonify({"success": False, "message": "Código de barras vacío"}), 400

    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT codigo_articulo, descripcion FROM articulos WHERE ean = %s",
                (ean,),
            )
            articulo = cursor.fetchone()

            if not articulo:
                return jsonify({"success": False, "message": f"No. Código {ean} NO encontrado en el maestro"}), 404

            cursor.execute(
                """
                INSERT INTO lecturas (usuario, ean, codigo_articulo, descripcion)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    session.get("usuario", "anonimo"),
                    ean,
                    articulo["codigo_articulo"],
                    articulo["descripcion"],
                ),
            )
            lectura_id = cursor.fetchone()["id"]
        conn.commit()

    return jsonify(
        {
            "success": True,
            "message": "No. Artículo encontrado y registrado",
            "lectura": {
                "id": lectura_id,
                "ean": ean,
                "codigo_articulo": articulo["codigo_articulo"],
                "descripcion": articulo["descripcion"],
            },
        }
    )


@app.route("/api/lecturas", methods=["GET"])
def obtener_lecturas():
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, ean, codigo_articulo, descripcion, fecha_lectura
                FROM lecturas
                ORDER BY fecha_lectura DESC
                LIMIT 100
                """
            )
            lecturas = cursor.fetchall()
    return jsonify(lecturas)


@app.route("/api/lecturas/limpiar", methods=["DELETE"])
def limpiar_lecturas():
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM lecturas")
        conn.commit()
    return jsonify({"success": True, "message": "Lecturas eliminadas"})


@app.route("/api/exportar", methods=["GET"])
def exportar_excel():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from io import BytesIO

    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT ean, codigo_articulo, descripcion, fecha_lectura
                FROM lecturas
                ORDER BY fecha_lectura DESC
                """
            )
            lecturas = cursor.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Lecturas"
    headers = ["EAN", "Codigo Articulo", "Descripcion", "Fecha"]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="121212", end_color="121212", fill_type="solid")

    for row in lecturas:
        fecha_valor = row["fecha_lectura"]
        fecha_formateada = fecha_valor.strftime("%d/%m/%Y %H:%M") if isinstance(fecha_valor, datetime) else (str(fecha_valor) if fecha_valor else "")
        ws.append([row["ean"], row["codigo_articulo"], row["descripcion"] or "", fecha_formateada])

    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 40
    ws.column_dimensions["D"].width = 18

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"lecturas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


# === ARTÍCULOS ===

@app.route("/api/articulos/importar", methods=["POST"])
def importar_articulos():
    """
    Importación rápida para 120k+ filas:
    - Lee xlsx con openpyxl read_only
    - Construye un TSV en memoria (tab-separated)
    - TRUNCATE + COPY FROM STDIN (muy rápido)
    """
    if not session.get("es_admin"):
        return jsonify({"success": False, "message": "No autorizado"}), 403

    if "archivo" not in request.files:
        return jsonify({"success": False, "message": "No se recibió archivo"}), 400

    archivo = request.files["archivo"]
    if not archivo or archivo.filename == "":
        return jsonify({"success": False, "message": "Nombre de archivo vacío"}), 400

    if not archivo.filename.lower().endswith(".xlsx"):
        return jsonify({"success": False, "message": "Debe ser un archivo .xlsx"}), 400

    def norm(x):
        if x is None:
            return ""
        if isinstance(x, float):
            if x.is_integer():
                return str(int(x))
            return format(x, "f").rstrip("0").rstrip(".")
        return str(x).strip()

    try:
        from openpyxl import load_workbook

        wb = load_workbook(archivo, data_only=True, read_only=True)
        ws = wb.active

        buf = StringIO()
        total = 0
        descartadas = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            codigo = norm(row[0] if len(row) > 0 else None)
            descripcion = norm(row[1] if len(row) > 1 else None)
            ean = norm(row[2] if len(row) > 2 else None)

            if not codigo or not ean:
                descartadas += 1
                continue

            # TSV (tab-separated) — ojo: limpiamos tabs/saltos para no romper COPY
            codigo = codigo.replace("\t", " ").replace("\n", " ").replace("\r", " ")
            descripcion = descripcion.replace("\t", " ").replace("\n", " ").replace("\r", " ")
            ean = ean.replace("\t", "").replace("\n", "").replace("\r", "")

            buf.write(f"{codigo}\t{descripcion}\t{ean}\n")
            total += 1

        buf.seek(0)

        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("TRUNCATE articulos")

                cursor.copy(
                    """
                    COPY articulos (codigo_articulo, descripcion, ean)
                    FROM STDIN
                    WITH (FORMAT text)
                    """,
                    buf,
                )

            conn.commit()

        return jsonify({
            "success": True,
            "message": f"Importación completada: {total} artículos cargados. Descartadas: {descartadas}."
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@app.route("/api/articulos/count", methods=["GET"])
def contar_articulos():
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM articulos")
            count = cursor.fetchone()["total"]
    return jsonify({"count": count})


@app.route("/api/articulos/limpiar", methods=["DELETE"])
def limpiar_articulos():
    if not session.get("es_admin"):
        return jsonify({"success": False, "message": "No autorizado"}), 403

    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE articulos")
        conn.commit()

    return jsonify({"success": True, "message": "Tabla maestra limpiada"})


# === USUARIOS (ADMIN) ===

@app.route("/api/admin/usuarios", methods=["GET"])
def obtener_usuarios():
    if not session.get("es_admin"):
        return jsonify({"success": False, "message": "No autorizado"}), 403

    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, nombre_usuario, es_admin, fecha_creacion FROM usuarios ORDER BY fecha_creacion DESC"
            )
            usuarios = cursor.fetchall()

    return jsonify(usuarios)


@app.route("/api/admin/usuarios", methods=["POST"])
def crear_usuario():
    if not session.get("es_admin"):
        return jsonify({"success": False, "message": "No autorizado"}), 403

    data = request.json or {}
    nombre = (data.get("nombre_usuario") or "").strip()
    if not nombre:
        return jsonify({"success": False, "message": "Nombre de usuario requerido"}), 400

    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO usuarios (nombre_usuario, es_admin)
                VALUES (%s, %s)
                ON CONFLICT (nombre_usuario) DO NOTHING
                RETURNING id
                """,
                (nombre, False),
            )
            nuevo = cursor.fetchone()
        conn.commit()

    if nuevo:
        return jsonify({"success": True, "message": "Usuario creado", "id": nuevo["id"]})

    return jsonify({"success": False, "message": "El usuario ya existe"}), 400


@app.route("/api/admin/usuarios/<int:usuario_id>", methods=["DELETE"])
def eliminar_usuario(usuario_id):
    if not session.get("es_admin"):
        return jsonify({"success": False, "message": "No autorizado"}), 403

    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT nombre_usuario FROM usuarios WHERE id = %s", (usuario_id,))
            user = cursor.fetchone()

            if not user:
                return jsonify({"success": False, "message": "Usuario no encontrado"}), 404

            if user["nombre_usuario"] in ["admin", "henkobit"]:
                return jsonify({"success": False, "message": "No se puede eliminar este administrador"}), 400

            cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
        conn.commit()

    return jsonify({"success": True, "message": "Usuario eliminado"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
