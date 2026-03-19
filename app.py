"""
Gonzalo Pago - Versión Render + Supabase (Python 3.12 compatible)
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
import psycopg2.extras
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)

# ================================================================
# CONFIGURACIÓN
# ================================================================

app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key')

DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME', 'postgres')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_PORT = os.environ.get('DB_PORT', '5432')

if not DB_HOST or not DB_PASSWORD:
    raise RuntimeError("Faltan variables de entorno de Supabase. Revisa Render > Environment Variables")

# ================================================================
# CONEXIÓN A SUPABASE
# ================================================================

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        cursor_factory=psycopg2.extras.DictCursor,
        connect_timeout=10
    )


# ================================================================
# MIDDLEWARE
# ================================================================

@app.before_request
def require_login():
    if request.endpoint in ['login', 'register', 'static']:
        return
    if 'user_id' not in session:
        flash("Debes iniciar sesión primero", "warning")
        return redirect(url_for('login'))


# ================================================================
# HELPERS (simplificados)
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
        FROM gastos g JOIN categorias_gastos c ON g.categoria_id = c.id
        WHERE g.user_id = %s ORDER BY g.fecha DESC LIMIT 500
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
        FROM ingresos i JOIN categorias_ingresos c ON i.categoria_id = c.id
        WHERE i.user_id = %s ORDER BY i.fecha DESC LIMIT 500
    """, (user_id,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


# ================================================================
# RUTAS (simplificadas para evitar errores)
# ================================================================

@app.route("/")
def inicio():
    return redirect(url_for("login"))

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
            flash("Sesión iniciada", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Email o contraseña incorrectos", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if not email or not password:
            flash("Email y contraseña requeridos", "warning")
            return redirect(url_for("register"))
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (email, password) VALUES (%s, %s)", 
                       (email, generate_password_hash(password)))
            conn.commit()
            flash("Registro exitoso", "success")
            return redirect(url_for("login"))
        except:
            flash("Este email ya está registrado", "danger")
        finally:
            cur.close()
            conn.close()
    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", active_page="dashboard")


# Rutas básicas (puedes ir agregando el resto después)
@app.route("/expenses")
def pagina_gastos():
    return render_template("expenses.html", active_page="expenses")

@app.route("/incomes")
def pagina_ingresos():
    return render_template("incomes.html", active_page="incomes")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
