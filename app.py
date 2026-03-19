import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta, datetime

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'tu-clave-secreta-aqui')

# Configuración de sesión
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_DOMAIN'] = None
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True  # False en desarrollo local

DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
if DEBUG:
    app.config['SESSION_COOKIE_SECURE'] = False

def init_db():
    """Inicializa la base de datos con todas las tablas necesarias"""
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
    
    # Tabla ingresos (NUEVA)
    c.execute('''CREATE TABLE IF NOT EXISTS ingresos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  usuario_id INTEGER NOT NULL,
                  descripcion TEXT NOT NULL,
                  monto REAL NOT NULL,
                  categoria TEXT DEFAULT 'Salario',
                  fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (usuario_id) REFERENCES usuarios (id))''')
    
    # Tabla categorías (opcional, para personalización)
    c.execute('''CREATE TABLE IF NOT EXISTS categorias
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  usuario_id INTEGER NOT NULL,
                  nombre TEXT NOT NULL,
                  tipo TEXT NOT NULL CHECK (tipo IN ('gasto', 'ingreso')),
                  FOREIGN KEY (usuario_id) REFERENCES usuarios (id))''')
    
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión para acceder a esta página', 'warning')
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
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('gastos.db')
        c = conn.cursor()
        user = c.execute('SELECT * FROM usuarios WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session.permanent = True
            flash(f'¡Bienvenido {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
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
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('login'))

# ========== RUTAS PRINCIPALES ==========
@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal con resumen de gastos e ingresos"""
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    
    # Obtener gastos del usuario
    gastos = c.execute('''SELECT id, descripcion, monto, categoria, fecha 
                          FROM gastos 
                          WHERE usuario_id = ? 
                          ORDER BY fecha DESC LIMIT 10''', 
                       (session['user_id'],)).fetchall()
    
    # Obtener ingresos del usuario
    ingresos = c.execute('''SELECT id, descripcion, monto, categoria, fecha 
                            FROM ingresos 
                            WHERE usuario_id = ? 
                            ORDER BY fecha DESC LIMIT 10''', 
                         (session['user_id'],)).fetchall()
    
    # Calcular totales
    total_gastos = c.execute('SELECT COALESCE(SUM(monto), 0) FROM gastos WHERE usuario_id = ?', 
                            (session['user_id'],)).fetchone()[0]
    total_ingresos = c.execute('SELECT COALESCE(SUM(monto), 0) FROM ingresos WHERE usuario_id = ?', 
                              (session['user_id'],)).fetchone()[0]
    balance = total_ingresos - total_gastos
    
    conn.close()
    
    return render_template('dashboard.html', 
                         gastos=gastos, 
                         ingresos=ingresos,
                         total_gastos=total_gastos,
                         total_ingresos=total_ingresos,
                         balance=balance)

# ========== RUTAS DE GASTOS ==========
@app.route('/gastos')
@login_required
def ver_gastos():
    """Página para ver todos los gastos"""
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    gastos = c.execute('''SELECT id, descripcion, monto, categoria, fecha 
                          FROM gastos 
                          WHERE usuario_id = ? 
                          ORDER BY fecha DESC''', 
                       (session['user_id'],)).fetchall()
    conn.close()
    return render_template('gastos.html', gastos=gastos)

@app.route('/gastos/agregar', methods=['POST'])
@login_required
def agregar_gasto():
    descripcion = request.form['descripcion']
    monto = float(request.form['monto'])
    categoria = request.form.get('categoria', 'Otros')
    
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    c.execute('''INSERT INTO gastos (usuario_id, descripcion, monto, categoria) 
                 VALUES (?, ?, ?, ?)''',
              (session['user_id'], descripcion, monto, categoria))
    conn.commit()
    conn.close()
    
    flash('Gasto agregado correctamente', 'success')
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

# ========== RUTAS DE INGRESOS (NUEVAS) ==========
@app.route('/ingresos')
@login_required
def ver_ingresos():
    """Página para ver todos los ingresos"""
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    ingresos = c.execute('''SELECT id, descripcion, monto, categoria, fecha 
                            FROM ingresos 
                            WHERE usuario_id = ? 
                            ORDER BY fecha DESC''', 
                         (session['user_id'],)).fetchall()
    conn.close()
    return render_template('ingresos.html', ingresos=ingresos)

@app.route('/ingresos/agregar', methods=['POST'])
@login_required
def agregar_ingreso():
    descripcion = request.form['descripcion']
    monto = float(request.form['monto'])
    categoria = request.form.get('categoria', 'Salario')
    
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    c.execute('''INSERT INTO ingresos (usuario_id, descripcion, monto, categoria) 
                 VALUES (?, ?, ?, ?)''',
              (session['user_id'], descripcion, monto, categoria))
    conn.commit()
    conn.close()
    
    flash('Ingreso agregado correctamente', 'success')
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

# ========== API PARA GRÁFICAS ==========
@app.route('/api/resumen')
@login_required
def api_resumen():
    """API para obtener datos resumidos para gráficas"""
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    
    # Gastos por categoría
    gastos_cat = c.execute('''SELECT categoria, SUM(monto) as total 
                               FROM gastos 
                               WHERE usuario_id = ? 
                               GROUP BY categoria''', 
                            (session['user_id'],)).fetchall()
    
    # Ingresos por categoría
    ingresos_cat = c.execute('''SELECT categoria, SUM(monto) as total 
                                 FROM ingresos 
                                 WHERE usuario_id = ? 
                                 GROUP BY categoria''', 
                              (session['user_id'],)).fetchall()
    
    conn.close()
    
    return jsonify({
        'gastos_por_categoria': [{'categoria': cat, 'total': total} for cat, total in gastos_cat],
        'ingresos_por_categoria': [{'categoria': cat, 'total': total} for cat, total in ingresos_cat]
    })

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=DEBUG)
