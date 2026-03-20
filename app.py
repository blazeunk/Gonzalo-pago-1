"""
Gonzalo Pago - Versión FINAL para Render + Supabase
Última actualización: marzo 2026
"""

import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-secreta-temporal')

# Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en variables de entorno")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ================================================================
# MIDDLEWARE - Login requerido
# ================================================================

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Inicia sesión primero', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


# ================================================================
# RUTAS AUTENTICACIÓN
# ================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Email y contraseña requeridos', 'danger')
            return render_template('register.html')

        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            if response.user:
                flash('Registro exitoso. Inicia sesión.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Error al registrar', 'danger')
        except Exception as e:
            flash(str(e), 'danger')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            if response.user:
                session['user_id'] = response.user.id
                session['email'] = response.user.email
                flash('Sesión iniciada', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Credenciales incorrectas', 'danger')
        except Exception as e:
            flash(str(e), 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))


# ================================================================
# DASHBOARD (versión mínima para que Render arranque)
# ================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', active_page='dashboard')


# ================================================================
# RUTAS BÁSICAS (puedes expandir después)
# ================================================================

@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/expenses')
@login_required
def expenses():
    return render_template('expenses.html', active_page='expenses')


@app.route('/incomes')
@login_required
def incomes():
    return render_template('incomes.html', active_page='incomes')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
