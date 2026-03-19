import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pago_gonzalo_final_2026")

# --- CONFIGURACIÓN SUPABASE ---
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()

try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    print(f"Error conexión Supabase: {e}")
    supabase = None

def obtener_todo_el_contexto(user_id):
    """Genera un contexto ultra-completo para evitar UndefinedError en Jinja2."""
    try:
        res = supabase.table("pagos").select("*").eq("user_id", user_id).execute()
        pagos = res.data or []
        
        # Cálculos base
        p_pagados = [float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pagado']
        p_pendientes = [float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pendiente']
        
        sum_pagado = sum(p_pagados)
        sum_pendiente = sum(p_pendientes)
        balance = sum_pagado - sum_pendiente
        
        return {
            # Variables de ingresos (Atrapando el error 'total_income')
            "total_income": sum_pagado,
            "weekly_income": sum_pagado / 4,
            "monthly_income": sum_pagado,
            
            # Variables de gastos
            "total_expenses": sum_pendiente,
            "total_exp": sum_pendiente,
            "weekly_exp": sum_pendiente / 4,
            "monthly_exp": sum_pendiente,
            
            # Balances y ahorros
            "total_balance": balance,
            "total_savings": balance if balance > 0 else 0.0,
            "savings_rate": 15.0 if sum_pagado > 0 else 0.0,
            
            # Otros
            "resumen": {"total_pagado": sum_pagado, "total_pendiente": sum_pendiente, "cantidad": len(pagos)},
            "pagos": pagos,
            "user_email": session.get('email', 'Usuario'),
            "active_page": "dashboard"
        }
    except Exception as e:
        print(f"Fallo en Supabase/Cálculos: {e}")
        return {
            "total_income": 0.0, "weekly_income": 0.0, "monthly_income": 0.0,
            "total_expenses": 0.0, "total_exp": 0.0, "weekly_exp": 0.0, "monthly_exp": 0.0,
            "total_balance": 0.0, "total_savings": 0.0, "savings_rate": 0.0,
            "resumen": {"total_pagado": 0, "total_pendiente": 0, "cantidad": 0},
            "pagos": [], "user_email": "Usuario", "active_page": "dashboard"
        }

# --- RUTAS ---

@app.route('/')
def index():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            res = supabase.table("users").select("*").eq("email", email).execute()
            user = res.data[0] if res.data else None
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['email'] = user['email']
                return redirect(url_for('dashboard'))
            flash("Credenciales inválidas", "danger")
        except:
            flash("Error de conexión", "danger")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            hashed = generate_password_hash(password)
            supabase.table("users").insert({"email": email, "password": hashed}).execute()
            flash("¡Registro exitoso! Ya puedes entrar.", "success")
            return redirect(url_for('login'))
        except:
            flash("El email ya existe o hubo un error.", "danger")
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_todo_el_contexto(session['user_id'])
    return render_template('dashboard.html', **ctx)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
