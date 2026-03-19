import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "476d47eca2452cdd4519aa1bb823fe51b2d409462bf2cbd4152cacfc7959a9da")

# Configuración de base de datos
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    """Conecta a Supabase (PostgreSQL) y devuelve conexión y cursor."""
    try:
        # sslmode='require' es vital para Supabase
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        # Usamos RealDictCursor para que funcione igual que tu MYSQL_CURSORCLASS (acceso por nombre de columna)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        return conn, cur
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None, None

# ================================================================
# MIDDLEWARE - PROTECCIÓN DE RUTAS
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
# FUNCIONES AUXILIARES (Adaptadas a PostgreSQL)
# ================================================================

def obtener_categorias_gastos():
    conn, cur = get_db_connection()
    if not cur: return []
    cur.execute("SELECT id, nombre FROM categorias_gastos ORDER BY nombre")
    res = cur.fetchall()
    cur.close(); conn.close()
    return res

def obtener_gastos(user_id):
    conn, cur = get_db_connection()
    if not cur: return []
    cur.execute("""
        SELECT g.id, g.fecha, g.monto, c.nombre AS categoria, g.categoria_id, g.descripcion
        FROM gastos g
        JOIN categorias_gastos c ON g.categoria_id = c.id
        WHERE g.user_id = %s
        ORDER BY g.fecha DESC LIMIT 500
    """, (user_id,))
    res = cur.fetchall()
    cur.close(); conn.close()
    return res

# --- Nota: Deberás adaptar las otras funciones (ingresos, totales) siguiendo este mismo patrón ---

# ================================================================
# AUTENTICACIÓN
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
        conn, cur = get_db_connection()
        
        try:
            cur.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, hashed_pw))
            conn.commit()
            flash("Registro exitoso. Ahora inicia sesión.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            print(e)
            flash("Este email ya está registrado o hubo un error", "danger")
        finally:
            if cur: cur.close()
            if conn: conn.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn, cur = get_db_connection()
        if not cur: return "Error de BD", 500
        
        cur.execute("SELECT id, password FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close(); conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
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

@app.route("/")
def inicio():
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    # Simplificado para que el despliegue no falle si no has creado todas las tablas
    return render_template("dashboard.html", active_page="dashboard")

# ================================================================
# EJECUCIÓN
# ================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
