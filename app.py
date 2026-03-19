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
    try:
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
        print(f"Error: {e}")
        return {"total_income":0, "total_expenses":0, "total_balance":0, "gastos_lista":[], "ingresos_lista":[]}

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
        hashed = generate_password_hash(request.form.get('password'))
        try:
            supabase.table("users").insert({"email": email, "password": hashed}).execute()
            return redirect(url_for('login'))
        except: flash("El usuario ya existe", "danger")
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', active_page='dashboard', **obtener_contexto_financiero(session['user_id']))

@app.route('/expenses')
def pagina_gastos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    cats = supabase.table("categorias_gastos").select("*").execute().data
    return render_template('expenses.html', active_page='expenses', categorias=cats, **ctx)

@app.route('/incomes')
def pagina_ingresos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    cats = supabase.table("categorias_ingresos").select("*").execute().data
    return render_template('incomes.html', active_page='incomes', categorias=cats, **ctx)

@app.route('/add_expense', methods=['POST'])
def agregar_gasto():
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("gastos").insert({
        "user_id": session['user_id'],
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id'))
    }).execute()
    return redirect(url_for('pagina_gastos'))

@app.route('/add_income', methods=['POST'])
def agregar_ingreso():
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("ingresos").insert({
        "user_id": session['user_id'],
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id'))
    }).execute()
    return redirect(url_for('pagina_ingresos'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
