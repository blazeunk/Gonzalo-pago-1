import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
from functools import wraps
from datetime import timedelta
from dotenv import load_dotenv
import logging
from werkzeug.security import generate_password_hash, check_password_hash

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())

# Configuración de sesión
app.config.update(
    SESSION_COOKIE_SECURE=True,  # True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_DOMAIN=None,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7)
)

# ========== CONFIGURACIÓN SUPABASE ==========
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')  # Para operaciones administrativas

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Faltan variables de entorno de Supabase")
    raise ValueError("SUPABASE_URL y SUPABASE_KEY son requeridas")

# Cliente para operaciones normales (con RLS)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Cliente para operaciones administrativas (opcional, si necesitas saltarte RLS)
if SUPABASE_SERVICE_KEY:
    supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
else:
    supabase_admin = supabase

# ========== FUNCIONES DE AYUDA ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión para acceder', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def test_connection():
    """Prueba la conexión a Supabase"""
    try:
        result = supabase.table('usuarios').select('count', count='exact').execute()
        logger.info(f"✅ Conexión a Supabase exitosa")
        return True
    except Exception as e:
        logger.error(f"❌ Error conectando a Supabase: {e}")
        return False

# ========== RUTAS DE AUTENTICACIÓN ==========
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está logueado, redirigir
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        logger.info(f"Intento de login - Usuario: {username}")
        
        if not username or not password:
            flash('Usuario y contraseña son requeridos', 'danger')
            return render_template('login.html')
        
        try:
            # Buscar usuario en Supabase
            result = supabase.table('usuarios')\
                .select('*')\
                .eq('username', username)\
                .execute()
            
            users = result.data
            
            if users and len(users) > 0:
                user = users[0]
                # Verificar contraseña
                if check_password_hash(user['password'], password):
                    # Login exitoso
                    session.clear()
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session.permanent = True
                    
                    logger.info(f"Login exitoso para: {username}")
                    flash(f'¡Bienvenido {username}!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    logger.warning(f"Contraseña incorrecta para: {username}")
                    flash('Usuario o contraseña incorrectos', 'danger')
            else:
                logger.warning(f"Usuario no encontrado: {username}")
                flash('Usuario o contraseña incorrectos', 'danger')
                
        except Exception as e:
            logger.error(f"Error en login: {e}")
            flash('Error al conectar con la base de datos', 'danger')
        
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
            # Verificar si usuario ya existe
            existing = supabase.table('usuarios')\
                .select('*')\
                .eq('username', username)\
                .execute()
            
            if existing.data and len(existing.data) > 0:
                flash('El nombre de usuario ya existe', 'danger')
                return render_template('register.html')
            
            # Verificar si email ya existe
            existing_email = supabase.table('usuarios')\
                .select('*')\
                .eq('email', email)\
                .execute()
            
            if existing_email.data and len(existing_email.data) > 0:
                flash('El email ya está registrado', 'danger')
                return render_template('register.html')
            
            # Crear nuevo usuario
            hashed_password = generate_password_hash(password)
            
            new_user = {
                'username': username,
                'email': email,
                'password': hashed_password,
                'fecha_registro': 'now()'
            }
            
            result = supabase.table('usuarios').insert(new_user).execute()
            
            if result.data and len(result.data) > 0:
                logger.info(f"Usuario registrado exitosamente: {username}")
                flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Error al registrar usuario', 'danger')
                
        except Exception as e:
            logger.error(f"Error en registro: {e}")
            flash(f'Error en el registro: {str(e)}', 'danger')
        
        return render_template('register.html')
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        user_id = session['user_id']
        
        # Obtener gastos del usuario
        gastos_result = supabase.table('gastos')\
            .select('*')\
            .eq('usuario_id', user_id)\
            .order('fecha', desc=True)\
            .limit(10)\
            .execute()
        
        # Obtener ingresos del usuario
        ingresos_result = supabase.table('ingresos')\
            .select('*')\
            .eq('usuario_id', user_id)\
            .order('fecha', desc=True)\
            .limit(10)\
            .execute()
        
        # Calcular totales
        gastos_total = supabase.table('gastos')\
            .select('monto')\
            .eq('usuario_id', user_id)\
            .execute()
        
        ingresos_total = supabase.table('ingresos')\
            .select('monto')\
            .eq('usuario_id', user_id)\
            .execute()
        
        total_gastos = sum(item['monto'] for item in gastos_total.data) if gastos_total.data else 0
        total_ingresos = sum(item['monto'] for item in ingresos_total.data) if ingresos_total.data else 0
        balance = total_ingresos - total_gastos
        
        return render_template('dashboard.html',
                             gastos=gastos_result.data if gastos_result.data else [],
                             ingresos=ingresos_result.data if ingresos_result.data else [],
                             total_gastos=total_gastos,
                             total_ingresos=total_ingresos,
                             balance=balance)
    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        flash('Error al cargar el dashboard', 'danger')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('login'))

# ========== RUTAS DE GASTOS ==========
@app.route('/gastos')
@login_required
def ver_gastos():
    try:
        result = supabase.table('gastos')\
            .select('*')\
            .eq('usuario_id', session['user_id'])\
            .order('fecha', desc=True)\
            .execute()
        
        return render_template('gastos.html', gastos=result.data if result.data else [])
    except Exception as e:
        logger.error(f"Error al cargar gastos: {e}")
        flash('Error al cargar los gastos', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/gastos/agregar', methods=['POST'])
@login_required
def agregar_gasto():
    descripcion = request.form.get('descripcion', '').strip()
    monto = request.form.get('monto', '').strip()
    categoria = request.form.get('categoria', 'Otros')
    
    if not descripcion or not monto:
        flash('Descripción y monto son requeridos', 'danger')
        return redirect(url_for('ver_gastos'))
    
    try:
        monto_float = float(monto)
        
        nuevo_gasto = {
            'usuario_id': session['user_id'],
            'descripcion': descripcion,
            'monto': monto_float,
            'categoria': categoria
        }
        
        result = supabase.table('gastos').insert(nuevo_gasto).execute()
        
        if result.data:
            flash('Gasto agregado correctamente', 'success')
        else:
            flash('Error al agregar gasto', 'danger')
            
    except ValueError:
        flash('Monto inválido', 'danger')
    except Exception as e:
        logger.error(f"Error al agregar gasto: {e}")
        flash('Error al agregar gasto', 'danger')
    
    return redirect(url_for('ver_gastos'))

@app.route('/gastos/eliminar/<int:gasto_id>')
@login_required
def eliminar_gasto(gasto_id):
    try:
        result = supabase.table('gastos')\
            .delete()\
            .eq('id', gasto_id)\
            .eq('usuario_id', session['user_id'])\
            .execute()
        
        if result.data:
            flash('Gasto eliminado', 'info')
        else:
            flash('No se pudo eliminar el gasto', 'danger')
    except Exception as e:
        logger.error(f"Error al eliminar gasto: {e}")
        flash('Error al eliminar gasto', 'danger')
    
    return redirect(url_for('ver_gastos'))

# ========== RUTAS DE INGRESOS ==========
@app.route('/ingresos')
@login_required
def ver_ingresos():
    try:
        result = supabase.table('ingresos')\
            .select('*')\
            .eq('usuario_id', session['user_id'])\
            .order('fecha', desc=True)\
            .execute()
        
        return render_template('ingresos.html', ingresos=result.data if result.data else [])
    except Exception as e:
        logger.error(f"Error al cargar ingresos: {e}")
        flash('Error al cargar los ingresos', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/ingresos/agregar', methods=['POST'])
@login_required
def agregar_ingreso():
    descripcion = request.form.get('descripcion', '').strip()
    monto = request.form.get('monto', '').strip()
    categoria = request.form.get('categoria', 'Salario')
    
    if not descripcion or not monto:
        flash('Descripción y monto son requeridos', 'danger')
        return redirect(url_for('ver_ingresos'))
    
    try:
        monto_float = float(monto)
        
        nuevo_ingreso = {
            'usuario_id': session['user_id'],
            'descripcion': descripcion,
            'monto': monto_float,
            'categoria': categoria
        }
        
        result = supabase.table('ingresos').insert(nuevo_ingreso).execute()
        
        if result.data:
            flash('Ingreso agregado correctamente', 'success')
        else:
            flash('Error al agregar ingreso', 'danger')
            
    except ValueError:
        flash('Monto inválido', 'danger')
    except Exception as e:
        logger.error(f"Error al agregar ingreso: {e}")
        flash('Error al agregar ingreso', 'danger')
    
    return redirect(url_for('ver_ingresos'))

@app.route('/ingresos/eliminar/<int:ingreso_id>')
@login_required
def eliminar_ingreso(ingreso_id):
    try:
        result = supabase.table('ingresos')\
            .delete()\
            .eq('id', ingreso_id)\
            .eq('usuario_id', session['user_id'])\
            .execute()
        
        if result.data:
            flash('Ingreso eliminado', 'info')
        else:
            flash('No se pudo eliminar el ingreso', 'danger')
    except Exception as e:
        logger.error(f"Error al eliminar ingreso: {e}")
        flash('Error al eliminar ingreso', 'danger')
    
    return redirect(url_for('ver_ingresos'))

# ========== RUTA DE DEPURACIÓN ==========
@app.route('/debug/connection')
def debug_connection():
    """Ruta para verificar conexión a Supabase"""
    if test_connection():
        return jsonify({"status": "ok", "message": "Conectado a Supabase"})
    else:
        return jsonify({"status": "error", "message": "Error de conexión"}), 500

if __name__ == '__main__':
    # Probar conexión al iniciar
    if test_connection():
        port = int(os.getenv('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        logger.error("No se pudo conectar a Supabase. Verifica tus credenciales.")
