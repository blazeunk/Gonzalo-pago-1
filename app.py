import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "gonzalo_clave_2026")

# --- CONFIGURACIÓN SUPABASE ---
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()

try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    print(f"Error inicializando Supabase: {e}")
    supabase = None

# --- FUNCIONES AUXILIARES ---
def calcular_totales(user_id):
    try:
        res = supabase.table("pagos").select("*").eq("user_id", user_id).execute()
        pagos = res.data or []
        tot_pagado = sum(float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pagado')
        tot_pendiente = sum(float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pendiente')
        return {"total_pagado": tot_pagado, "total_pendiente": tot_pendiente, "cantidad": len(pagos)}
    except:
        return {"total_pagado": 0, "total_pendiente": 0, "cantidad": 0}

# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/')
def index():
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
            flash("Correo o contraseña incorrectos", "danger")
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
            flash("Cuenta creada, ya puedes iniciar sesión", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error al registrar: {str(e)}", "danger")
    return render_template('register.html')

# --- RUTAS QUE TU BASE.HTML ESTÁ PIDIENDO ---

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    resumen = calcular_totales(session['user_id'])
    return render_template('dashboard.html', resumen=resumen, active_page='dashboard')

@app.route('/gastos')
def pagina_gastos():
    if 'user_id' not in session: return redirect(url_for('login'))
    # Por ahora reusamos dashboard hasta que crees gastos.html
    return render_template('dashboard.html', active_page='expenses')

@app.route('/ingresos')
def pagina_ingresos():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', active_page='incomes')

@app.route('/perfil')
def perfil():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', active_page='profile')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- INICIO ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
