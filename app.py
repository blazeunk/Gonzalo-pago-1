import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Configuración de seguridad y entorno
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key_123_pago_gonzalo")

# Variables de Supabase
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()

# Inicialización segura de Supabase
try:
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL o SUPABASE_KEY no están configuradas.")
        supabase = None
    else:
        supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    print(f"❌ Error al conectar con Supabase: {e}")
    supabase = None

# --- FUNCIONES DE LÓGICA ---

def calcular_totales(user_id):
    """Calcula el resumen de pagos para el dashboard."""
    try:
        if not supabase: return {"total_pagado": 0, "total_pendiente": 0, "cantidad": 0}
        
        response = supabase.table("pagos").select("*").eq("user_id", user_id).execute()
        pagos = response.data or []
        
        total_pagado = sum(float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pagado')
        total_pendiente = sum(float(p.get('monto', 0)) for p in pagos if p.get('estado') == 'pendiente')
        
        return {
            "total_pagado": total_pagado,
            "total_pendiente": total_pendiente,
            "cantidad": len(pagos)
        }
    except Exception as e:
        print(f"Error en calcular_totales: {e}")
        return {"total_pagado": 0, "total_pendiente": 0, "cantidad": 0}

# --- RUTAS DE NAVEGACIÓN ---

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
            
            flash("Credenciales incorrectas", "danger")
        except Exception as e:
            flash(f"Error de inicio de sesión: {str(e)}", "danger")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_pw = generate_password_hash(password)
        
        try:
            supabase.table("users").insert({"email": email, "password": hashed_pw}).execute()
            flash("Registro exitoso. Inicia sesión.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error al registrar: {str(e)}", "danger")
            
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    resumen = calcular_totales(session['user_id'])
    return render_template('dashboard.html', user_email=session['email'], resumen=resumen)

# ✅ SOLUCIÓN AL ERROR: Esta es la ruta que pedía tu base.html
@app.route('/gastos')
def pagina_gastos():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Por ahora renderizamos el dashboard o una página de gastos si la tienes
    return render_template('dashboard.html', active_page='expenses')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- CONFIGURACIÓN DE ARRANQUE PARA RENDER ---

if __name__ == '__main__':
    # Render usa la variable PORT, si no existe usa 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
