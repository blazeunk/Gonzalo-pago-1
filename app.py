import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "476d47eca2452cdd4519aa1bb823fe51b2d409462bf2cbd4152cacfc7959a9da")

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    """Conecta a la base de datos de forma segura."""
    conn = None
    cur = None
    try:
        # IMPORTANTE: Asegúrate de que DATABASE_URL sea la cadena correcta de Supabase
        conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        return conn, cur
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None, None

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        conn, cur = get_db_connection()
        
        if conn is None:
            flash("Error de conexión con la base de datos. Intenta más tarde.", "danger")
            return redirect(url_for("register"))

        try:
            hashed_pw = generate_password_hash(password)
            cur.execute("INSERT INTO users (email, password) VALUES (%s, %s)", (email, hashed_pw))
            conn.commit()
            flash("Registro exitoso", "success")
            return redirect(url_for("login"))
        except Exception as e:
            print(f"Error en el insert: {e}")
            flash("El email ya existe o hubo un error interno.", "danger")
        finally:
            # CORRECCIÓN: Solo cerramos si existen
            if cur: cur.close()
            if conn: conn.close()
            
    return render_template("register.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email, password = request.form.get("email"), request.form.get("password")
        conn, cur = get_db_connection()
        cur.execute("SELECT id, password FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Credenciales inválidas", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ================================================================
# RUTAS DE VISTA (Coinciden con url_for de base.html)
# ================================================================

@app.route("/dashboard")
def dashboard():
    user_id = session["user_id"]
    res = calcular_totales(user_id)
    
    # Datos para gráficos
    conn, cur = get_db_connection()
    cur.execute("""
        SELECT c.nombre as categoria, SUM(g.monto) as total 
        FROM gastos g JOIN categorias_gastos c ON g.categoria_id = c.id 
        WHERE g.user_id = %s GROUP BY c.nombre
    """, (user_id,))
    g_cat = cur.fetchall()
    
    cur.execute("""
        SELECT c.nombre as categoria, SUM(i.monto) as total 
        FROM ingresos i JOIN categorias_ingresos c ON i.categoria_id = c.id 
        WHERE i.user_id = %s GROUP BY c.nombre
    """, (user_id,))
    i_cat = cur.fetchall()
    cur.close(); conn.close()

    return render_template("dashboard.html", 
        **res, total_balance=res['total_income'] - res['total_exp'],
        gastos_labels=[r['categoria'] for r in g_cat], gastos_data=[float(r['total']) for r in g_cat],
        ingresos_labels=[r['categoria'] for r in i_cat], ingresos_data=[float(r['total']) for r in i_cat],
        active_page="dashboard")

@app.route("/expenses")
def pagina_gastos():
    user_id = session["user_id"]
    conn, cur = get_db_connection()
    cur.execute("SELECT g.*, c.nombre as categoria FROM gastos g JOIN categorias_gastos c ON g.categoria_id = c.id WHERE g.user_id = %s ORDER BY g.fecha DESC", (user_id,))
    expenses = cur.fetchall()
    cur.execute("SELECT * FROM categorias_gastos ORDER BY nombre")
    cats = cur.fetchall()
    cur.close(); conn.close()
    return render_template("expenses.html", expenses=expenses, categorias=cats, today=datetime.now().strftime("%Y-%m-%d"), active_page="expenses")

@app.route("/incomes")
def pagina_ingresos():
    user_id = session["user_id"]
    conn, cur = get_db_connection()
    cur.execute("SELECT i.*, c.nombre as categoria FROM ingresos i JOIN categorias_ingresos c ON i.categoria_id = c.id WHERE i.user_id = %s ORDER BY i.fecha DESC", (user_id,))
    incomes = cur.fetchall()
    cur.execute("SELECT * FROM categorias_ingresos ORDER BY nombre")
    cats = cur.fetchall()
    cur.close(); conn.close()
    return render_template("incomes.html", incomes=incomes, categorias=cats, today=datetime.now().strftime("%Y-%m-%d"), active_page="incomes")

# ================================================================
# CRUD (POST)
# ================================================================

@app.route("/add_expense", methods=["POST"])
def agregar_gasto():
    conn, cur = get_db_connection()
    cur.execute("INSERT INTO gastos (user_id, fecha, monto, categoria_id, descripcion) VALUES (%s, %s, %s, %s, %s)",
                (session["user_id"], request.form['date'], float(request.form['amount']), int(request.form['categoria_id']), request.form['desc']))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for("pagina_gastos"))

@app.route("/add_income", methods=["POST"])
def agregar_ingreso():
    conn, cur = get_db_connection()
    cur.execute("INSERT INTO ingresos (user_id, fecha, monto, categoria_id, descripcion) VALUES (%s, %s, %s, %s, %s)",
                (session["user_id"], request.form['date'], float(request.form['amount']), int(request.form['categoria_id']), request.form['desc']))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for("pagina_ingresos"))

@app.route("/delete_expense/<int:id>", methods=["POST"])
def eliminar_gasto(id):
    conn, cur = get_db_connection()
    cur.execute("DELETE FROM gastos WHERE id = %s AND user_id = %s", (id, session["user_id"]))
    conn.commit(); cur.close(); conn.close()
    return "", 204 # Respuesta vacía para el AJAX de tu HTML

@app.route("/delete_income/<int:id>", methods=["POST"])
def eliminar_ingreso(id):
    conn, cur = get_db_connection()
    cur.execute("DELETE FROM ingresos WHERE id = %s AND user_id = %s", (id, session["user_id"]))
    conn.commit(); cur.close(); conn.close()
    return "", 204

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
