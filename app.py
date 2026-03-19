import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pago_gonzalo_2026_key")

# --- CONFIGURACIÓN SUPABASE ---
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()
supabase: Client = create_client(supabase_url, supabase_key)

def obtener_contexto_financiero(user_id):
    """Calcula saldos y obtiene listas de gastos/ingresos con sus categorías."""
    try:
        # Consulta con JOIN para obtener el nombre de la categoría directamente
        res_g = supabase.table("gastos").select("*, categorias_gastos(nombre)").eq("user_id", user_id).execute()
        res_i = supabase.table("ingresos").select("*, categorias_ingresos(nombre)").eq("user_id", user_id).execute()
        
        gastos = res_g.data or []
        ingresos = res_i.data or []
        
        sum_ingresos = sum(float(i.get('monto', 0)) for i in ingresos)
        sum_gastos = sum(float(g.get('monto', 0)) for g in gastos)
        balance = sum_ingresos - sum_gastos
        
        return {
            "total_income": sum_ingresos,
            "total_expenses": sum_gastos,
            "total_balance": balance,
            "weekly_income": sum_ingresos / 4,
            "monthly_income": sum_ingresos,
            "weekly_exp": sum_gastos / 4,
            "monthly_exp": sum_gastos,
            "total_savings": max(0, balance),
            "gastos_lista": gastos,
            "ingresos_lista": ingresos,
            "user_email": session.get('email', 'Usuario')
        }
    except Exception as e:
        print(f"Error en contexto financiero: {e}")
        return {
            "total_income": 0, "total_expenses": 0, "total_balance": 0,
            "weekly_income": 0, "monthly_income": 0, "weekly_exp": 0, "monthly_exp": 0,
            "total_savings": 0, "gastos_lista": [], "ingresos_lista": [],
            "user_email": "Usuario"
        }

# --- RUTAS DE NAVEGACIÓN Y SESIÓN ---

@app.route('/')
def index():
    return redirect(url_for('dashboard')) if 'user_id' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        res = supabase.table("users").select("*").eq("email", email).execute()
        user = res.data[0] if res.data else None
        
        if user and check_password_hash(user['password'], password):
            session.update({'user_id': user['id'], 'email': user['email']})
            return redirect(url_for('dashboard'))
        flash("Email o contraseña incorrectos", "danger")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        hashed = generate_password_hash(password)
        try:
            supabase.table("users").insert({"email": email, "password": hashed}).execute()
            flash("Registro exitoso, por favor inicia sesión", "success")
            return redirect(url_for('login'))
        except:
            flash("Error: El usuario ya existe", "danger")
    return render_template('register.html')

# --- RUTAS DE CONTENIDO ---

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    return render_template('dashboard.html', active_page='dashboard', **ctx)

@app.route('/expenses')
def pagina_gastos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    # Obtenemos las categorías de la tabla correspondiente
    categorias = supabase.table("categorias_gastos").select("*").execute().data
    return render_template('expenses.html', active_page='expenses', categorias=categorias, **ctx)

@app.route('/incomes')
def pagina_ingresos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    # Obtenemos las categorías de la tabla correspondiente
    categorias = supabase.table("categorias_ingresos").select("*").execute().data
    return render_template('incomes.html', active_page='incomes', categorias=categorias, **ctx)

# --- ACCIONES ---

@app.route('/add_expense', methods=['POST'])
def agregar_gasto():
    if 'user_id' not in session: return redirect(url_for('login'))
    try:
        supabase.table("gastos").insert({
            "user_id": session['user_id'],
            "descripcion": request.form.get('descripcion'),
            "monto": float(request.form.get('monto', 0)),
            "categoria_id": int(request.form.get('categoria_id'))
        }).execute()
    except Exception as e:
        print(f"Error al añadir gasto: {e}")
    return redirect(url_for('pagina_gastos'))

@app.route('/add_income', methods=['POST'])
def agregar_ingreso():
    if 'user_id' not in session: return redirect(url_for('login'))
    try:
        supabase
