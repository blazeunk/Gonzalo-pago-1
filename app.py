import os
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-secreta-temporal-para-pruebas')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ================================================================
# Decorador
# ================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ================================================================
# AUTH
# ================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            if response.user:
                flash('Registro exitoso', 'success')
                return redirect(url_for('login'))
        except Exception as e:
            logger.error(e)
            flash(str(e), 'danger')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            response = supabase.auth.sign_in_with_password({
                "email": request.form.get('email'),
                "password": request.form.get('password')
            })

            if response.user:
                session['user_id'] = str(response.user.id)  # 🔥 UUID FIX
                session['email'] = response.user.email
                return redirect(url_for('dashboard'))

        except Exception as e:
            logger.error(e)
            flash(str(e), 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ================================================================
# DASHBOARD
# ================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = str(session['user_id'])

    try:
        gastos = supabase.table('gastos').select('*').eq('user_id', user_id).execute().data or []
        ingresos = supabase.table('ingresos').select('*').eq('user_id', user_id).execute().data or []

        total_gastos = sum(float(g.get('monto', 0)) for g in gastos)
        total_ingresos = sum(float(i.get('monto', 0)) for i in ingresos)

        return render_template('dashboard.html',
                               total_exp=total_gastos,
                               total_income=total_ingresos,
                               total_balance=total_ingresos - total_gastos,
                               today=datetime.now().strftime('%Y-%m-%d'),
                               active_page='dashboard')

    except Exception as e:
        logger.error(e)
        return render_template('dashboard.html', total_exp=0, total_income=0, total_balance=0)


# ================================================================
# EXPENSES
# ================================================================

@app.route('/expenses')
@login_required
def expenses():
    user_id = str(session['user_id'])

    try:
        gastos = supabase.table('gastos').select('*').eq('user_id', user_id).execute().data or []
        categorias = supabase.table('categorias_gastos').select('nombre').execute().data or []

        return render_template('expenses.html',
                               gastos=gastos,
                               categorias=categorias,
                               today=datetime.now().strftime('%Y-%m-%d'),
                               active_page='expenses')

    except Exception as e:
        logger.error(e)
        return render_template('expenses.html', expenses=[], categorias=[])


# 🔥 endpoint corregido
@app.route('/agregar_gasto', methods=['POST'])
@login_required
def agregar_gasto():
    user_id = str(session['user_id'])

    try:
        supabase.table('gastos').insert({
            'user_id': user_id,
            'fecha': request.form.get('fecha'),
            'monto': float(request.form.get('monto') or 0),
            'categoria': request.form.get('categoria'),
            'descripcion': request.form.get('descripcion', '')
        }).execute()

        flash('Gasto agregado', 'success')

    except Exception as e:
        logger.error(e)
        flash('Error al agregar gasto', 'danger')

    return redirect(url_for('expenses'))

    @app.route('/ver_gastos')
    @login_required
    def ver_gastos():
        return redirect(url_for('expenses'))


# ================================================================
# INCOMES
# ================================================================

@app.route('/incomes')
@login_required
def incomes():
    user_id = str(session['user_id'])

    try:
        ingresos = supabase.table('ingresos').select('*').eq('user_id', user_id).execute().data or []
        categorias = supabase.table('categorias_ingresos').select('nombre').execute().data or []

        return render_template('incomes.html',
                               ingresos=ingresos,
                               categorias=categorias,
                               today=datetime.now().strftime('%Y-%m-%d'),
                               active_page='incomes')

    except Exception as e:
        logger.error(e)
        return render_template('incomes.html', incomes=[], categorias=[])


# 🔥 endpoint corregido
@app.route('/agregar_ingreso', methods=['POST'])
@login_required
def agregar_ingreso():
    user_id = str(session['user_id'])

    try:
        supabase.table('ingresos').insert({
            'user_id': user_id,
            'fecha': request.form.get('fecha'),
            'monto': float(request.form.get('monto') or 0),
            'categoria': request.form.get('categoria'),
            'descripcion': request.form.get('descripcion', '')
        }).execute()

        flash('Ingreso agregado', 'success')

    except Exception as e:
        logger.error(e)
        flash('Error al agregar ingreso', 'danger')

    return redirect(url_for('incomes'))

        @app.route('/ver_ingresos')
    @login_required
    def ver_ingresos():
        return redirect(url_for('incomes'))

# ================================================================
# RUN
# ================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
