"""
Gonzalo Pago - Versión Producción para Render + Supabase
Adaptada específicamente para evitar errores de psycopg2 en Render
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
import psycopg2.extras
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)

# ================================================================
# CONFIGURACIÓN (Variables de entorno de Render)
# ================================================================

app.secret_key = os.environ.get('SECRET_KEY', '476d47eca2452cdd4519aa1bb823fe51b2d409462bf2cbd4152cacfc7959a9da')

# Configuración de Supabase desde Render (Environment Variables)
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME', 'postgres')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_PORT = os.environ.get('DB_PORT', '5432')

# Validación básica de variables
if not DB_HOST or not DB_PASSWORD:
    raise RuntimeError("❌ Faltan variables de entorno de Supabase. Revisa Render Dashboard > Environment Variables")


# ================================================================
# CONEXIÓN A BASE DE DATOS
# ================================================================

def get_db_connection():
    """Retorna una nueva conexión a Supabase"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            cursor_factory=psycopg2.extras.DictCursor,
            connect_timeout=10
        )
        return conn
    except Exception as e:
        print(f"Error de conexión a Supabase: {e}")
        raise


# ================================================================
# MIDDLEWARE
# ================================================================

@app.before_request
def require_login():
    public_routes = ['login', 'register', 'inicio', 'static']
    if request.endpoint in public_routes:
        return
    if 'user_id' not in session:
        flash("Debes iniciar sesión primero", "warning")
        return redirect(url_for('login'))


# ================================================================
# FUNCIONES AUXILIARES
# ================================================================

def obtener_categorias_gastos():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre FROM categorias_gastos ORDER BY nombre")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


def obtener_categorias_ingresos():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre FROM categorias_ingresos ORDER BY nombre")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


def obtener_gastos(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT g.id, g.fecha, g.monto, c.nombre AS categoria, g.categoria_id, g.descripcion
        FROM gastos g
        JOIN categorias_gastos c ON g.categoria_id = c.id
        WHERE g.user_id = %s
        ORDER BY g.fecha DESC
        LIMIT 500
    """, (user_id,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


def obtener_ingresos(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT i.id, i.fecha, i.monto, c.nombre AS categoria, i.categoria_id, i.descripcion
        FROM ingresos i
        JOIN categorias_ingresos c ON i.categoria_id = c.id
        WHERE i.user_id = %s
        ORDER BY i.fecha DESC
        LIMIT 500
    """, (user_id,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


def calcular_total_periodo(tipo, dias=7, user_id=None):
    if not user_id: return 0.0
    conn = get_db_connection()
    cur = conn.cursor()
    tabla = "gastos" if tipo == "gasto" else "ingresos"
    cur.execute(f"""
        SELECT COALESCE(SUM(monto), 0) AS total
        FROM {tabla}
        WHERE user_id = %s AND fecha >= CURRENT_DATE - INTERVAL '%s days'
    """, (user_id, dias))
    resultado = cur.fetchone()['total']
    cur.close()
    conn.close()
    return round(float(resultado or 0), 2)


def calcular_total_mes_actual(tipo, user_id=None):
    if not user_id: return 0.0
    conn = get_db_connection()
    cur = conn.cursor()
    tabla = "gastos" if tipo == "gasto" else "ingresos"
    cur.execute(f"""
        SELECT COALESCE(SUM(monto), 0) AS total
        FROM {tabla}
        WHERE user_id = %s 
          AND EXTRACT(YEAR FROM fecha) = EXTRACT(YEAR FROM CURRENT_DATE)
          AND EXTRACT(MONTH FROM fecha) = EXTRACT(MONTH FROM CURRENT_DATE)
    """, (user_id,))
    resultado = cur.fetchone()['total']
    cur.close()
    conn.close()
    return round(float(resultado or 0), 2)


def calcular_total_historico(tipo, user_id=None):
    if not user_id: return 0.0
    conn = get_db_connection()
    cur = conn.cursor()
    tabla = "gastos" if tipo == "gasto" else "ingresos"
    cur.execute(f"SELECT COALESCE(SUM(monto), 0) AS total FROM {tabla} WHERE user_id = %s", (user_id,))
    resultado = cur.fetchone()['total']
    cur.close()
    conn.close()
    return round(float(resultado or 0), 2)


# ================================================================
# RUTAS DE AUTENTICACIÓN
# ================================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not (email and password):
            flash("Email y contraseña son obligatorios", "warning")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, hashed_pw))
            conn.commit()
            flash("Registro exitoso. Ahora inicia sesión.", "success")
            return redirect(url_for("login"))
        except:
            flash("Este email ya está registrado", "danger")
        finally:
            cur.close()
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session["user_id"] = user['id']
            flash("Sesión iniciada correctamente", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Email o contraseña incorrectos", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Sesión cerrada correctamente", "info")
    return redirect(url_for("login"))


# ================================================================
# RUTAS PRINCIPALES
# ================================================================

@app.route("/")
def inicio():
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    user_id = session["user_id"]

    ingresos_semana = calcular_total_periodo("ingreso", 7, user_id)
    gastos_semana   = calcular_total_periodo("gasto", 7, user_id)
    ingresos_mes    = calcular_total_mes_actual("ingreso", user_id)
    gastos_mes      = calcular_total_mes_actual("gasto", user_id)
    ingresos_total  = calcular_total_historico("ingreso", user_id)
    gastos_total    = calcular_total_historico("gasto", user_id)
    balance_total   = round(ingresos_total - gastos_total, 2)

    return render_template(
        "dashboard.html",
        weekly_income=ingresos_semana,
        weekly_exp=gastos_semana,
        monthly_income=ingresos_mes,
        monthly_exp=gastos_mes,
        total_income=ingresos_total,
        total_exp=gastos_total,
        total_balance=balance_total,
        active_page="dashboard"
    )


@app.route("/expenses")
def pagina_gastos():
    user_id = session["user_id"]
    gastos = obtener_gastos(user_id)
    categorias = obtener_categorias_gastos()
    hoy = datetime.now().strftime("%Y-%m-%d")
    return render_template("expenses.html", expenses=gastos, categorias=categorias, today=hoy, active_page="expenses")


@app.route("/incomes")
def pagina_ingresos():
    user_id = session["user_id"]
    ingresos = obtener_ingresos(user_id)
    categorias = obtener_categorias_ingresos()
    hoy = datetime.now().strftime("%Y-%m-%d")
    return render_template("incomes.html", incomes=ingresos, categorias=categorias, today=hoy, active_page="incomes")


# ================================================================
# CRUD
# ================================================================

@app.route("/add_expense", methods=["POST"])
def agregar_gasto():
    user_id = session["user_id"]
    fecha = request.form.get("date")
    monto = float(request.form.get("amount") or 0)
    categoria_id = request.form.get("categoria_id")
    descripcion = request.form.get("desc", "").strip()

    if monto > 0 and fecha and categoria_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO gastos (user_id, fecha, monto, categoria_id, descripcion)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, fecha, monto, int(categoria_id), descripcion))
        conn.commit()
        cur.close()
        conn.close()
        flash("Gasto agregado correctamente", "success")
    else:
        flash("Datos inválidos", "warning")
    return redirect(url_for("pagina_gastos"))


@app.route("/add_income", methods=["POST"])
def agregar_ingreso():
    user_id = session["user_id"]
    fecha = request.form.get("date")
    monto = float(request.form.get("amount") or 0)
    categoria_id = request.form.get("categoria_id")
    descripcion = request.form.get("desc", "").strip()

    if monto > 0 and fecha and categoria_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ingresos (user_id, fecha, monto, categoria_id, descripcion)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, fecha, monto, int(categoria_id), descripcion))
        conn.commit()
        cur.close()
        conn.close()
        flash("Ingreso agregado correctamente", "success")
    else:
        flash("Datos inválidos", "warning")
    return redirect(url_for("pagina_ingresos"))


@app.route("/delete_expense/<int:id>", methods=["POST"])
def eliminar_gasto(id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM gastos WHERE id = %s AND user_id = %s", (id, user_id))
    conn.commit()
    cur.close()
    conn.close()
    flash("Gasto eliminado correctamente", "success")
    return redirect(url_for("pagina_gastos"))


@app.route("/delete_income/<int:id>", methods=["POST"])
def eliminar_ingreso(id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ingresos WHERE id = %s AND user_id = %s", (id, user_id))
    conn.commit()
    cur.close()
    conn.close()
    flash("Ingreso eliminado correctamente", "success")
    return redirect(url_for("pagina_ingresos"))


# ================================================================
# INICIO
# ================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Gonzalo Pago iniciado en puerto {port}")
    app.run(host="0.0.0.0", port=port)
