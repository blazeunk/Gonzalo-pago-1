import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
from functools import wraps
from datetime import timedelta, datetime
from dotenv import load_dotenv
import logging

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())

# Configuración de sesión OPTIMIZADA
app.config.update(
    SESSION_COOKIE_SECURE=False,  # True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_DOMAIN=None,
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_REFRESH_EACH_REQUEST=True
)

# ========== CONFIGURACIÓN SUPABASE ==========
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan variables de entorno de Supabase")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========== FUNCIONES DE AYUDA ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar si hay sesión en Flask
        if 'user_id' not in session:
            logger.warning("Acceso denegado - No hay sesión")
            flash('Por favor inicia sesión para acceder', 'warning')
            return redirect(url_for('login'))
        
        # Verificar que el token de Supabase sigue siendo válido
        try:
            # Intentar obtener el usuario actual de Supabase
            user = supabase.auth.get_user()
            if not user or not user.user:
                logger.warning("Token de Supabase inválido, cerrando sesión")
                session.clear()
                supabase.auth.sign_out()
                flash('Tu sesión ha expirado. Por favor inicia sesión nuevamente.', 'warning')
                return redirect(url_for('login'))
        except Exception as e:
            logger.error(f"Error verificando token: {e}")
            # Si hay error, asumimos que el token no es válido
            session.clear()
            supabase.auth.sign_out()
            flash('Error de autenticación. Por favor inicia sesión nuevamente.', 'warning')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_today():
    """Retorna la fecha actual en formato YYYY-MM-DD"""
    return datetime.now().strftime('%Y-%m-%d')

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
        email = request.form.get('email', '').strip()
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
            
            if response and response.user:
                # Obtener metadata del usuario
                user_metadata = response.user.user_metadata
                username = user_metadata.get('username', email.split('@')[0])
                
                # Guardar información en la sesión de Flask
                session.clear()
                session['user_id'] = response.user.id
                session['email'] = response.user.email
                session['username'] = username
                session.permanent = True
                
                # Guardar el token de acceso para futuras peticiones
                if hasattr(response, 'session') and response.session:
                    session['access_token'] = response.session.access_token
                    session['refresh_token'] = response.session.refresh_token
                
                logger.info(f"Login exitoso para: {email} - ID: {response.user.id}")
                flash(f'¡Bienvenido {username}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                logger.warning(f"Login fallido - Respuesta sin usuario: {response}")
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
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        logger.info(f"Intento de registro - Email: {email}")
        
        # Validaciones básicas
        if not email or not password:
            flash('Email y contraseña son requeridos', 'danger')
            return render_template('register.html')
        
        if len(password) < 4:
            flash('La contraseña debe tener al menos 4 caracteres', 'danger')
            return render_template('register.html')
        
        try:
            # Registrar con Supabase Auth
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "username": email.split('@')[0]
                    },
                    "email_confirm": True  # Auto-confirmar email
                }
            })
            
            if response and response.user:
                logger.info(f"Usuario registrado exitosamente: {response.user.id}")
                
                # Auto login después del registro
                try:
                    login_response = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    
                    if login_response and login_response.user:
                        session.clear()
                        session['user_id'] = login_response.user.id
                        session['email'] = login_response.user.email
                        session['username'] = email.split('@')[0]
                        session.permanent = True
                        
                        if hasattr(login_response, 'session') and login_response.session:
                            session['access_token'] = login_response.session.access_token
                            session['refresh_token'] = login_response.session.refresh_token
                        
                        flash('¡Registro exitoso! Bienvenido a Gonzalo Pago.', 'success')
                        return redirect(url_for('dashboard'))
                except Exception as e:
                    logger.error(f"Error en auto-login después de registro: {e}")
                
                flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
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

@app.route('/logout')
def logout():
    try:
        supabase.auth.sign_out()
    except:
        pass
    session.clear()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('login'))

# ========== RUTAS DEL DASHBOARD ==========
@app.route('/dashboard')
@login_required
def dashboard():
    try:
        user_id = session['user_id']
        
        # Obtener fecha actual
        hoy = datetime.now()
        hace_7_dias = (hoy - timedelta(days=7)).strftime('%Y-%m-%d')
        inicio_mes = hoy.replace(day=1).strftime('%Y-%m-%d')
        
        # Obtener gastos del usuario
        gastos_result = supabase.table('gastos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute()
        
        # Obtener ingresos del usuario
        ingresos_result = supabase.table('ingresos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute()
        
        gastos = gastos_result.data if gastos_result.data else []
        ingresos = ingresos_result.data if ingresos_result.data else []
        
        # Calcular totales
        total_gastos = sum(item.get('monto', 0) for item in gastos)
        total_ingresos = sum(item.get('monto', 0) for item in ingresos)
        
        # Calcular semanales
        gastos_semana = sum(item.get('monto', 0) for item in gastos 
                           if item.get('fecha', '')[:10] >= hace_7_dias)
        ingresos_semana = sum(item.get('monto', 0) for item in ingresos 
                            if item.get('fecha', '')[:10] >= hace_7_dias)
        
        # Calcular mensuales
        gastos_mes = sum(item.get('monto', 0) for item in gastos 
                        if item.get('fecha', '')[:10] >= inicio_mes)
        ingresos_mes = sum(item.get('monto', 0) for item in ingresos 
                         if item.get('fecha', '')[:10] >= inicio_mes)
        
        # Preparar datos para gráficos
        gastos_por_categoria = {}
        for g in gastos:
            cat = g.get('categoria', 'Otros')
            gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0) + g.get('monto', 0)
        
        ingresos_por_categoria = {}
        for i in ingresos:
            cat = i.get('categoria', 'Otros')
            ingresos_por_categoria[cat] = ingresos_por_categoria.get(cat, 0) + i.get('monto', 0)
        
        logger.info(f"Dashboard cargado para usuario: {session.get('username')}")
        
        return render_template('dashboard.html',
                             weekly_exp=gastos_semana,
                             weekly_income=ingresos_semana,
                             monthly_exp=gastos_mes,
                             monthly_income=ingresos_mes,
                             total_exp=total_gastos,
                             total_income=total_ingresos,
                             total_balance=total_ingresos - total_gastos,
                             gastos_data=list(gastos_por_categoria.values()),
                             gastos_labels=list(gastos_por_categoria.keys()),
                             ingresos_data=list(ingresos_por_categoria.values()),
                             ingresos_labels=list(ingresos_por_categoria.keys()),
                             today=get_today())
    
    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        flash('Error al cargar el dashboard', 'danger')
        return redirect(url_for('login'))

# ========== RUTAS DE GASTOS ==========
@app.route('/gastos')
@login_required
def ver_gastos():
    try:
        user_id = session['user_id']
        
        result = supabase.table('gastos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute()
        
        gastos = result.data if result.data else []
        
        return render_template('expenses.html', 
                             gastos=gastos,
                             today=get_today())
    
    except Exception as e:
        logger.error(f"Error al cargar gastos: {e}")
        flash('Error al cargar los gastos', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/gastos/agregar', methods=['POST'])
@login_required
def agregar_gasto():
    try:
        fecha = request.form.get('fecha', get_today())
        monto = float(request.form.get('monto', 0))
        categoria = request.form.get('categoria', 'Otros')
        descripcion = request.form.get('descripcion', '').strip()
        
        if monto <= 0:
            flash('El monto debe ser mayor a 0', 'danger')
            return redirect(url_for('ver_gastos'))
        
        nuevo_gasto = {
            'user_id': session['user_id'],
            'fecha': fecha,
            'monto': monto,
            'categoria': categoria,
            'descripcion': descripcion,
            'created_at': datetime.now().isoformat()
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

@app.route('/gastos/eliminar/<gasto_id>')
@login_required
def eliminar_gasto(gasto_id):
    try:
        result = supabase.table('gastos')\
            .delete()\
            .eq('id', gasto_id)\
            .eq('user_id', session['user_id'])\
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
        user_id = session['user_id']
        
        result = supabase.table('ingresos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute()
        
        ingresos = result.data if result.data else []
        
        return render_template('incomes.html', 
                             ingresos=ingresos,
                             today=get_today())
    
    except Exception as e:
        logger.error(f"Error al cargar ingresos: {e}")
        flash('Error al cargar los ingresos', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/ingresos/agregar', methods=['POST'])
@login_required
def agregar_ingreso():
    try:
        fecha = request.form.get('fecha', get_today())
        monto = float(request.form.get('monto', 0))
        categoria = request.form.get('categoria', 'Otros')
        descripcion = request.form.get('descripcion', '').strip()
        
        if monto <= 0:
            flash('El monto debe ser mayor a 0', 'danger')
            return redirect(url_for('ver_ingresos'))
        
        nuevo_ingreso = {
            'user_id': session['user_id'],
            'fecha': fecha,
            'monto': monto,
            'categoria': categoria,
            'descripcion': descripcion,
            'created_at': datetime.now().isoformat()
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

@app.route('/ingresos/eliminar/<ingreso_id>')
@login_required
def eliminar_ingreso(ingreso_id):
    try:
        result = supabase.table('ingresos')\
            .delete()\
            .eq('id', ingreso_id)\
            .eq('user_id', session['user_id'])\
            .execute()
        
        if result.data:
            flash('Ingreso eliminado', 'info')
        else:
            flash('No se pudo eliminar el ingreso', 'danger')
            
    except Exception as e:
        logger.error(f"Error al eliminar ingreso: {e}")
        flash('Error al eliminar ingreso', 'danger')
    
    return redirect(url_for('ver_ingresos'))

# ========== RUTAS DE DEPURACIÓN ==========
@app.route('/debug/session')
def debug_session():
    """Ver estado de la sesión (solo para desarrollo)"""
    if app.debug:
        return jsonify({
            'session': dict(session),
            'user_id': session.get('user_id'),
            'email': session.get('email'),
            'has_access_token': 'access_token' in session,
            'has_refresh_token': 'refresh_token' in session
        })
    return jsonify({'error': 'No disponible en producción'}), 404

# ========== INICIALIZACIÓN ==========
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
