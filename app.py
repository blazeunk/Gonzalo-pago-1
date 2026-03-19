import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "una_clave_muy_segura_123")

# Configuración de Supabase desde variables de entorno
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- FUNCIONES AUXILIARES (La que te faltaba) ---

def calcular_totales(user_id):
    """
    Calcula el resumen de pagos y deudas del usuario.
    Asegúrate de que tu tabla en Supabase se llame 'pagos' o ajusta el nombre.
    """
    try:
        # Consultar los registros del usuario
        response = supabase.table("pagos").select("*").eq("user_id", user_id).execute()
        pagos = response.data
        
        total_pagado = sum(p.get('monto', 0) for p in pagos if p.get('estado') == 'pagado')
        total_pendiente = sum(p.get('monto', 0) for p in pagos if p.get('estado') == 'pendiente')
        
        return {
            "total_pagado": total_pagado,
            "total_pendiente": total_pendiente,
            "cantidad_registros": len(pagos)
        }
    except Exception as e:
        print(f"Error en calcular_totales: {e}")
        return {"total_pagado": 0, "total_pendiente": 0, "cantidad_registros": 0}

# --- RUTAS ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_pw = generate_password_hash(password)

        try:
            # Insertar en la tabla 'users' de Supabase
            data, count = supabase.table("users").insert({
                "email": email, 
                "password": hashed_pw
            }).execute()
            
            flash("Registro exitoso. Por favor inicia sesión.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error al registrar: {str(e)}", "danger")
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Buscar usuario por email
            response = supabase.table("users").select("*").eq("email", email).execute()
            user = response.data[0] if response.data else None

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['email'] = user['email']
                return redirect(url_for('dashboard'))
            else:
                flash("Credenciales inválidas", "danger")
        except Exception as e:
            flash(f"Error en el inicio de sesión: {str(e)}", "danger")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Llamada a la función que causaba el error
    resumen = calcular_totales(user_id)
    
    return render_template('dashboard.html', user=session['email'], resumen=resumen)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Render usa el puerto de la variable de entorno PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
