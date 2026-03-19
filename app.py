import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
from functools import wraps
from datetime import datetime
from dotenv import load_dotenv
import logging

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-super-secreta-cambiar-en-produccion')

# Configuración de sesión MUY SIMPLE
app.config['SESSION_COOKIE_SECURE'] = False  # True en producción con HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 7 * 24 * 60 * 60  # 7 días en segundos

# Configuración Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan variables de entorno de Supabase")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_today():
    return datetime.now().strftime('%Y-%m-%d')

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está logueado, ir al dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Email y contraseña requeridos', 'danger')
            return render_template('login.html')
        
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response and response.user:
                # GUARDAR EN SESIÓN - ESTO ES CRÍTICO
                session.clear()
                session['user_id'] = response.user.id
                session['email'] = response.user.email
                session['username'] = response.user.user_metadata.get('username', email.split('@')[0])
                
                logger.info(f"✅ Login exitoso para: {email}")
                logger.info(f"✅ Sesión guardada: {session.get('user_id')}")
                
                flash('¡Login exitoso!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Credenciales incorrectas', 'danger')
                
        except Exception as e:
            logger.error(f"Error en login: {e}")
            flash('Error en el servidor', 'danger')
        
        return render_template('login.html')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Email y contraseña requeridos', 'danger')
            return render_template('register.html')
        
        if len(password) < 4:
            flash('La contraseña debe tener al menos 4 caracteres', 'danger')
            return render_template('register.html')
        
        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {"username": email.split('@')[0]}
                }
            })
            
            if response and response.user:
                logger.info(f"✅ Registro exitoso: {email}")
                flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Error en registro', 'danger')
                
        except Exception as e:
            logger.error(f"Error en registro: {e}")
            flash(f'Error: {str(e)}', 'danger')
        
        return render_template('register.html')
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    logger.info(f"✅ Acceso a dashboard - Usuario: {session.get('user_id')}")
    
    # POR AHORA: Dashboard SIMPLE que siempre funciona
    # Más adelante agregamos las consultas a Supabase
    
    return render_template('dashboard.html',
                         weekly_exp=0,
                         weekly_income=0,
                         monthly_exp=0,
                         monthly_income=0,
                         total_exp=0,
                         total_income=0,
                         total_balance=0,
                         gastos_data=[],
                         gastos_labels=[],
                         ingresos_data=[],
                         ingresos_labels=[],
                         today=get_today())

@app.route('/logout')
def logout():
    try:
        supabase.auth.sign_out()
    except:
        pass
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

@app.route('/debug/session')
def debug_session():
    """Ruta para depuración"""
    return jsonify({
        'session': dict(session),
        'user_id': session.get('user_id'),
        'email': session.get('email'),
        'cookies': dict(request.cookies)
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
# ========== INICIALIZACIÓN ==========
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
