import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pago_gonzalo_secure_2026")

# --- CONFIGURACIÓN SUPABASE ---
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()

try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    print(f"Error conexión Supabase: {e}")
    supabase = None

def obtener_todo_el_contexto(user_id):
    """Genera el diccionario completo de variables para el HTML."""
    try:
        res = supabase.table("pagos").select("*").eq("user_id", user_id).execute()
        pagos = res.data or []
        
        total_pagado = sum(float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pagado')
        total_pendiente = sum(float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pendiente')
        
        # Cálculos requeridos por el dashboard
        # total_balance es lo que te dio el último error
        total_balance = total_pagado - total_pendiente 
        
        return {
            "resumen": {"total_pagado": total_pagado, "total_pendiente": total_pendiente, "cantidad": len(pagos)},
            "total_balance": total_balance,
            "weekly_income": total_pagado / 4 if total_pagado > 0 else 0.0,
            "monthly_income": total_pagado,
            "weekly_exp": total_pendiente / 4 if total_pendiente > 0 else 0.0,
            "monthly_exp": total_pendiente,
            "total_savings": total_balance if total_balance > 0 else 0.0,
            "savings_rate": 0.0,
            "pagos": pagos,
            "user_email": session.get('email', 'Usuario')
        }
    except Exception as e:
        print(f"Error en contexto: {e}")
        return {
            "resumen": {"total_pagado": 0, "total_pendiente": 0, "cantidad": 0},
            "total_balance": 0.0,
            "weekly_income": 0.0, "monthly_income": 0.0,
            "weekly_exp": 0.0, "monthly_exp": 0.0,
            "total_savings": 0.0, "savings_rate": 0.0,
            "pagos": [], "user_email": session.get('email', 'Usuario')
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
            flash("Email o contraseña incorrectos", "danger")
        except:
            flash("Error de conexión", "danger")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_todo_el_contexto(session['user_id'])
    return render_template('dashboard.html', **ctx, active_page='dashboard')

@app.route('/gastos')
def pagina_gastos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_todo_el_contexto(session['user_id'])
    return render_template('dashboard.html', **ctx, active_page='expenses')

@app.route('/ingresos')
def pagina_ingresos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_todo_el_contexto(session['user_id'])
    return render_template('dashboard.html', **ctx, active_page='incomes')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
