import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import timedelta
# from flask_session import Session  # Opcional para sesiones del lado del servidor

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'una-clave-secreta-muy-segura-para-desarrollo') # ¡Cambia en producción!

# --- CONFIGURACIÓN CORREGIDA PARA RENDER ---
# Configuración de sesión robusta para producción
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'  # O 'redis' si prefieres
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Seguridad de Cookies - ¡ESTA ES LA CLAVE!
# NO configures SESSION_COOKIE_DOMAIN a menos que tengas un subdominio específico.
# Déjalo como None para que funcione en cualquier dominio (localhost, onrender.com, etc.)
app.config['SESSION_COOKIE_DOMAIN'] = None  # <--- CAMBIO CRÍTICO

# Configura SameSite y Secure para producción
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Habilita Secure solo si usas HTTPS (Render lo hace por defecto)
app.config['SESSION_COOKIE_SECURE'] = True  # Recomendado para producción

# Determina si estamos en desarrollo
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
if DEBUG:
    app.config['SESSION_COOKIE_SECURE'] = False  # Para desarrollo local sin HTTPS
# ------------------------------------------

# Inicializar base de datos (tu función existente está bien, la mantienes)
def init_db():
    # ... (tu código existente para crear tablas) ...
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    # Crear tabla usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL)''')
    # Crear tabla gastos
    c.execute('''CREATE TABLE IF NOT EXISTS gastos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  usuario_id INTEGER NOT NULL,
                  descripcion TEXT NOT NULL,
                  monto REAL NOT NULL,
                  fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (usuario_id) REFERENCES usuarios (id))''')
    conn.commit()
    conn.close()

# Decorador login requerido
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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
        
        if user and check_password_hash(user[2], password):  # user[2] es la contraseña hasheada
            session['user_id'] = user[0]
            session['username'] = user[1]
            session.permanent = True  # Usa la duración definida arriba
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
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
            flash('Registro exitoso. Por favor inicia sesión.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('El nombre de usuario o email ya existe', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Obtener gastos del usuario
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    gastos = c.execute('''SELECT id, descripcion, monto, fecha 
                          FROM gastos 
                          WHERE usuario_id = ? 
                          ORDER BY fecha DESC''', 
                       (session['user_id'],)).fetchall()
    conn.close()
    return render_template('dashboard.html', gastos=gastos)

@app.route('/add_gasto', methods=['POST'])
@login_required
def add_gasto():
    descripcion = request.form['descripcion']
    monto = float(request.form['monto'])
    
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    c.execute('INSERT INTO gastos (usuario_id, descripcion, monto) VALUES (?, ?, ?)',
             (session['user_id'], descripcion, monto))
    conn.commit()
    conn.close()
    
    flash('Gasto agregado correctamente', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('login'))

# Para obtener gastos en JSON (para posibles mejoras con JS)
@app.route('/api/gastos')
@login_required
def api_gastos():
    conn = sqlite3.connect('gastos.db')
    c = conn.cursor()
    gastos = c.execute('''SELECT id, descripcion, monto, fecha 
                          FROM gastos 
                          WHERE usuario_id = ? 
                          ORDER BY fecha DESC''', 
                       (session['user_id'],)).fetchall()
    conn.close()
    
    gastos_list = []
    for g in gastos:
        gastos_list.append({
            'id': g[0],
            'descripcion': g[1],
            'monto': g[2],
            'fecha': g[3]
        })
    return jsonify(gastos_list)

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=DEBUG)
