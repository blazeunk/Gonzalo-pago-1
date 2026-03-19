import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
from functools import wraps
from datetime import timedelta
from dotenv import load_dotenv
import logging

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())

# Configuración de sesión
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Cambiar a True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_DOMAIN=None,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7)
)

# Configuración Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan variables de entorno de Supabase")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== FUNCIONES DE AYUDA ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión para acceder', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== RUTAS DE AUTENTICACIÓN ==========
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('username', '').strip()  # Cambiado a email
        password = request.form.get('password', '').strip()
        
        logger.info(f"Intento de login - Email: {email}")
        
        if not email or not password:
            flash('Email y contraseña son requeridos', 'danger')
            return render_template('login.html')
        
        try:
            # Usar Auth de Supabase
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                # Obtener metadata
                user_metadata = response.user.user_metadata
                username = user_metadata.get('username', email.split('@')[0])
                
                session.clear()
                session['user_id'] = response.user.id
                session['username'] = username
                session['email'] = response.user.email
                session.permanent = True
                
                logger.info(f"Login exitoso para: {email}")
                flash(f'¡Bienvenido {username}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Email o contraseña incorrectos', 'danger')
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error en login: {error_msg}")
            
            if "Invalid login credentials" in error_msg:
                flash('Email o contraseña incorrectos', 'danger')
            else:
                flash(f'Error: {error_msg}', 'danger')
        
        return render_template('login.html')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        logger.info(f"Intento de registro - Usuario: {username}, Email: {email}")
        
        # Validaciones
        errores = []
        if not username or len(username) < 3:
            errores.append("El usuario debe tener al menos 3 caracteres")
        if not email or '@' not in email:
            errores.append("Email inválido")
        if not password or len(password) < 4:
            errores.append("La contraseña debe tener al menos 4 caracteres")
        
        if errores:
            for error in errores:
                flash(error, 'danger')
            return render_template('register.html')
        
        try:
            # Registrar con Supabase Auth
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "username": username,
                        "full_name": username
                    }
                }
            })
            
            if response.user:
                logger.info(f"Usuario registrado exitosamente: {response.user.id}")
                flash('¡Registro exitoso! Revisa tu email para confirmar la cuenta.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Error en el registro', 'danger')
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error en registro: {error_msg}")
            
            if "User already registered" in error_msg:
                flash('Este email ya está registrado', 'danger')
            else:
                flash(f'Error en el registro: {error_msg}', 'danger')
        
        return render_template('register.html')
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        # Obtener gastos (necesitas crear tabla 'gastos' en Supabase)
        gastos = []
        ingresos = []
        total_gastos = 0
        total_ingresos = 0
        
        # Intentar obtener gastos si existe la tabla
        try:
            gastos_result = supabase.table('gastos')\
                .select('*')\
                .eq('user_id', session['user_id'])\
                .order('created_at', desc=True)\
                .limit(10)\
                .execute()
            gastos = gastos_result.data if gastos_result.data else []
            
            # Calcular total
            if gastos:
                total_gastos = sum(g.get('amount', 0) for g in gastos)
        except:
            pass  # La tabla no existe aún
        
        balance = total_ingresos - total_gastos
        
        return render_template('dashboard.html',
                             gastos=gastos,
                             ingresos=ingresos,
                             total_gastos=total_gastos,
                             total_ingresos=total_ingresos,
                             balance=balance)
    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        flash('Error al cargar el dashboard', 'danger')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    supabase.auth.sign_out()
    session.clear()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('login'))

# ========== RUTAS DE DEPURACIÓN ==========
@app.route('/debug/session')
def debug_session():
    """Ver estado de la sesión"""
    return jsonify({
        'session': dict(session),
        'user_id': session.get('user_id'),
        'username': session.get('username')
    })

@app.route('/debug/auth')
def debug_auth():
    """Verificar autenticación con Supabase"""
    try:
        # Intentar obtener la sesión actual de Supabase
        user = supabase.auth.get_user()
        return jsonify({
            'status': 'ok',
            'user': user.user.email if user.user else None,
            'session_exists': user.user is not None
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
