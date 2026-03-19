import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pago_gonzalo_2026_safe")

# --- CONFIGURACIÓN SUPABASE ---
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()

try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    print(f"Error conexión Supabase: {e}")
    supabase = None

# --- LÓGICA DE DATOS ---
def obtener_datos_dashboard(user_id):
    """Extrae datos y evita que el HTML explote si no hay registros."""
    try:
        # Consultamos la tabla pagos
        res = supabase.table("pagos").select("*").eq("user_id", user_id).execute()
        pagos = res.data or []
        
        # Cálculos básicos
        total_pagado = sum(float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pagado')
        total_pendiente = sum(float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pendiente')
        
        return {
            "resumen": {
                "total_pagado": total_pagado,
                "total_pendiente": total_pendiente,
                "cantidad": len(pagos)
            },
            "pagos_recientes": pagos[:5], # Para posibles tablas en el home
            "weekly_income": total_pagado / 4, # Estimación simple para evitar UndefinedError
            "monthly_income": total_pagado
        }
    except:
        return {
            "resumen": {"total_pagado": 0, "total_pendiente": 0, "cantidad": 0},
            "pagos_recientes": [],
            "weekly_income": 0.0,
            "monthly_income": 0.0
        }

# --- RUTAS ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
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
            flash("Usuario o clave incorrectos", "danger")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            hashed = generate_password_hash(password)
            supabase.table("users").insert({"email": email, "password": hashed}).execute()
            flash("Cuenta creada correctamente", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error al registrar: {str(e)}", "danger")
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    datos = obtener_datos_dashboard(session['user_id'])
    
    # Pasamos TODAS las variables que detectamos en tus errores de Jinja2
    return render_template('dashboard.html', 
                           resumen=datos['resumen'],
                           weekly_income=datos['weekly_income'],
                           monthly_income=datos['monthly_income'],
                           pagos=datos['pagos_recientes'],
                           active_page='dashboard')

# Rutas de navegación para que base.html no falle
@app.route('/gastos')
def pagina_gastos():
    if 'user_id' not in session: return redirect(url_for('login'))
    datos = obtener_datos_dashboard(session['user_id'])
    return render_template('dashboard.html', **datos, active_page='expenses')

@app.route('/ingresos')
def pagina_ingresos():
    if 'user_id' not in session: return redirect(url_for('login'))
    datos = obtener_datos_dashboard(session['user_id'])
    return render_template('dashboard.html', **datos, active_page='incomes')

@app.route('/perfil')
def perfil():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', active_page='profile')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
