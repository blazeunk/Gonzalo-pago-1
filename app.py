import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pago_gonzalo_2026_key")

# --- CONFIGURACIÓN SUPABASE ---
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()

try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    print(f"Error conexión Supabase: {e}")
    supabase = None

def obtener_contexto_financiero(user_id):
    try:
        res = supabase.table("gastos").select("*").eq("user_id", user_id).execute()
        datos = res.data or []
        
        # Cálculos basados en la columna 'monto' y 'estado'
        sum_pagado = sum(float(p.get('monto', 0)) for p in datos if p.get('estado') == 'pagado')
        sum_pendiente = sum(float(p.get('monto', 0)) for p in datos if p.get('estado') == 'pendiente')
        
        # Mapeamos todos los nombres posibles que tus HTML puedan pedir
        return {
            "total_income": sum_pagado,
            "total_expenses": sum_pendiente,
            "total_exp": sum_pendiente,      # <--- AGREGADO PARA ARREGLAR EL ERROR ACTUAL
            "total_balance": sum_pagado - sum_pendiente,
            "weekly_income": sum_pagado / 4,
            "monthly_income": sum_pagado,
            "weekly_exp": sum_pendiente / 4,
            "monthly_exp": sum_pendiente,
            "total_savings": max(0, sum_pagado - sum_pendiente),
            "pagos": datos,
            "user_email": session.get('email', 'Usuario')
        }
    except Exception as e:
        print(f"Error de datos: {e}")
        return {"total_income":0.0, "total_exp":0.0, "total_expenses":0.0, "pagos":[]}

# --- RUTAS ---

@app.route('/')
def index():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        try:
            res = supabase.table("users").select("*").eq("email", email).execute()
            user = res.data[0] if res.data else None
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['email'] = user['email']
                return redirect(url_for('dashboard'))
            flash("Credenciales incorrectas", "danger")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    return render_template('dashboard.html', active_page='dashboard', **ctx)

@app.route('/expenses')
def pagina_gastos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    # Filtramos para mostrar solo los pendientes en la vista de gastos
    ctx['pagos'] = [p for p in ctx['pagos'] if p.get('estado') == 'pendiente']
    return render_template('expenses.html', active_page='expenses', **ctx)

@app.route('/incomes')
def pagina_ingresos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    # Filtramos para mostrar solo los pagados en la vista de ingresos
    ctx['pagos'] = [p for p in ctx['pagos'] if p.get('estado') == 'pagado']
    return render_template('incomes.html', active_page='incomes', **ctx)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
