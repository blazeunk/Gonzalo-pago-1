import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta

app = Flask(__name__)

# Configuración de seguridad para Render
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())

# Configuración de sesión OPTIMIZADA para Render
app.config.update(
    SESSION_COOKIE_SECURE=True,  # Requerido para HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_DOMAIN=None,  # Crítico: permite cualquier dominio
    SESSION_COOKIE_PATH='/',
    SESSION_COOKIE_NAME='session',  # Nombre estándar
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_REFRESH_EACH_REQUEST=True
)

# Para depuración (actívalo temporalmente si el error persiste)
app.config['PROPAGATE_EXCEPTIONS'] = True

# Manejador de errores específico
@app.errorhandler(400)
def bad_request(e):
    flash('Error en la solicitud. Por favor intenta de nuevo.', 'warning')
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_error(e):
    flash('Error interno del servidor. Los administradores han sido notificados.', 'danger')
    return redirect(url_for('login'))

def init_db():
    """Inicializa la base de datos"""
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    
    # Tabla usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Tabla gastos
    c.execute('''CREATE TABLE IF NOT EXISTS gastos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  usuario_id INTEGER NOT NULL,
                  descripcion TEXT NOT NULL,
                  monto REAL NOT NULL,
                  categoria TEXT DEFAULT 'Otros',
                  fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (usuario_id) REFERENCES usuarios (id))''')
    
    # Tabla ingresos
    c.execute('''CREATE TABLE IF NOT EXISTS ingresos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  usuario_id INTEGER NOT NULL,
                  descripcion TEXT NOT NULL,
                  monto REAL NOT NULL,
                  categoria TEXT DEFAULT 'Salario',
                  fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (usuario_id) REFERENCES usuarios (id))''')
    
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== RUTAS ==========
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Limpiar cualquier sesión anterior
    session.clear()
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Usuario y contraseña son requeridos', 'danger')
            return redirect(url_for('login'))
        
        try:
            conn = sqlite3.connect('gastos.db')
            c = conn.cursor()
            user = c.execute('SELECT * FROM usuarios WHERE username = ?', (username,)).fetchone()
            conn.close()
            
            if user and check_password_hash(user[2], password):
                session.permanent = True
                session['user_id'] = user[0]
                session['username'] = user[1]
                flash(f'¡Bienvenido {username}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Usuario o contraseña incorrectos', 'danger')
        except Exception as e:
            flash('Error al iniciar sesión', 'danger')
            print(f"Error en login: {e}")
        
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        email = request.form.get('email', '').strip()
        
        if not username or not password or not email:
            flash('Todos los campos son requeridos', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        
        try:
            conn = sqlite3.connect('gastos.db')
            c = conn.cursor()
            c.execute('INSERT INTO usuarios (username, password, email) VALUES (?, ?, ?)',
                     (username, hashed_password, email))
            conn.commit()
            conn.close()
            flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('El nombre de usuario o email ya existe', 'danger')
        except Exception as e:
            flash('Error en el registro', 'danger')
            print(f"Error en register: {e}")
        
        return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        conn = sqlite3.connect('gastos.db')
        c = conn.cursor()
        
        # Obtener datos
        gastos = c.execute('''SELECT id, descripcion, monto, categoria, fecha 
                              FROM gastos WHERE usuario_id = ? ORDER BY fecha DESC LIMIT 10''', 
                           (session['user_id'],)).fetchall()
        
        ingresos = c.execute('''SELECT id, descripcion, monto, categoria, fecha 
                                FROM ingresos WHERE usuario_id = ? ORDER BY fecha DESC LIMIT 10''', 
                             (session['user_id'],)).fetchall()
        
        total_gastos = c.execute('SELECT COALESCE(SUM(monto), 0) FROM gastos WHERE usuario_id = ?', 
                                (session['user_id'],)).fetchone()[0]
        total_ingresos = c.execute('SELECT COALESCE(SUM(monto), 0) FROM ingresos WHERE usuario_id = ?', 
                                  (session['user_id'],)).fetchone()[0]
        
        conn.close()
        balance = total_ingresos - total_gastos
        
        return render_template('dashboard.html', 
                             gastos=gastos, ingresos=ingresos,
                             total_gastos=total_gastos, total_ingresos=total_ingresos,
                             balance=balance)
    except Exception as e:
        flash('Error al cargar el dashboard', 'danger')
        print(f"Error en dashboard: {e}")
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
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    gastos = c.execute('''SELECT id, descripcion, monto, categoria, fecha 
                          FROM gastos WHERE usuario_id = ? ORDER BY fecha DESC''', 
                       (session['user_id'],)).fetchall()
    conn.close()
    return render_template('gastos.html', gastos=gastos)

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
        monto = float(monto)
        conn = sqlite3.connect('gastos.db')
        c = conn.cursor()
        c.execute('INSERT INTO gastos (usuario_id, descripcion, monto, categoria) VALUES (?, ?, ?, ?)',
                  (session['user_id'], descripcion, monto, categoria))
        conn.commit()
        conn.close()
        flash('Gasto agregado correctamente', 'success')
    except ValueError:
        flash('Monto inválido', 'danger')
    except Exception as e:
        flash('Error al agregar gasto', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('ver_gastos'))

@app.route('/gastos/eliminar/<int:gasto_id>')
@login_required
def eliminar_gasto(gasto_id):
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    c.execute('DELETE FROM gastos WHERE id = ? AND usuario_id = ?', 
              (gasto_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('Gasto eliminado', 'info')
    return redirect(url_for('ver_gastos'))

# ========== RUTAS DE INGRESOS ==========
@app.route('/ingresos')
@login_required
def ver_ingresos():
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    ingresos = c.execute('''SELECT id, descripcion, monto, categoria, fecha 
                            FROM ingresos WHERE usuario_id = ? ORDER BY fecha DESC''', 
                         (session['user_id'],)).fetchall()
    conn.close()
    return render_template('ingresos.html', ingresos=ingresos)

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
        monto = float(monto)
        conn = sqlite3.connect('gastos.db')
        c = conn.cursor()
        c.execute('INSERT INTO ingresos (usuario_id, descripcion, monto, categoria) VALUES (?, ?, ?, ?)',
                  (session['user_id'], descripcion, monto, categoria))
        conn.commit()
        conn.close()
        flash('Ingreso agregado correctamente', 'success')
    except ValueError:
        flash('Monto inválido', 'danger')
    except Exception as e:
        flash('Error al agregar ingreso', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('ver_ingresos'))

@app.route('/ingresos/eliminar/<int:ingreso_id>')
@login_required
def eliminar_ingreso(ingreso_id):
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    c.execute('DELETE FROM ingresos WHERE id = ? AND usuario_id = ?', 
              (ingreso_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('Ingreso eliminado', 'info')
    return redirect(url_for('ver_ingresos'))

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
