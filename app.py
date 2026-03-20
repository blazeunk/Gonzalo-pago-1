"""
Gonzalo Pago - Versión FINAL para Render + Supabase
Incluye todas las rutas necesarias y correcciones para evitar NameError
"""

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

# Configuración básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-secreta-temporal-para-pruebas')

# Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en variables de entorno")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ================================================================
# Decorador login_required
# ================================================================

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicia sesión', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__  # Necesario para Flask
    return decorated_function


# ================================================================
# Rutas de autenticación
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
                flash('Error al registrar usuario', 'danger')
        except Exception as e:
            logger.error(f"Error en registro: {e}")
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
                flash('Sesión iniciada correctamente', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Credenciales incorrectas', 'danger')
        except Exception as e:
            logger.error(f"Error en login: {e}")
            flash(str(e), 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))


# ================================================================
# Dashboard con cálculos reales
# ================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        user_id = session['user_id']
        hoy = datetime.now()
        hace_7_dias = (hoy - timedelta(days=7)).strftime('%Y-%m-%d')
        inicio_mes = hoy.replace(day=1).strftime('%Y-%m-%d')

        # Obtener datos de Supabase
        gastos_res = supabase.table('gastos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute()

        ingresos_res = supabase.table('ingresos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute()

        gastos = gastos_res.data or []
        ingresos = ingresos_res.data or []

        # Cálculos
        total_gastos = sum(float(g.get('monto', 0)) for g in gastos)
        total_ingresos = sum(float(i.get('monto', 0)) for i in ingresos)

        gastos_semana = sum(float(g.get('monto', 0)) for g in gastos if g.get('fecha', '') >= hace_7_dias)
        ingresos_semana = sum(float(i.get('monto', 0)) for i in ingresos if i.get('fecha', '') >= hace_7_dias)

        gastos_mes = sum(float(g.get('monto', 0)) for g in gastos if g.get('fecha', '') >= inicio_mes)
        ingresos_mes = sum(float(i.get('monto', 0)) for i in ingresos if i.get('fecha', '') >= inicio_mes)

        # Datos para gráficos (simplificado)
        gastos_por_cat = {}
        for g in gastos:
            cat = g.get('categoria', 'Otros')
            gastos_por_cat[cat] = gastos_por_cat.get(cat, 0) + float(g.get('monto', 0))

        ingresos_por_cat = {}
        for i in ingresos:
            cat = i.get('categoria', 'Otros')
            ingresos_por_cat[cat] = ingresos_por_cat.get(cat, 0) + float(i.get('monto', 0))

        return render_template('dashboard.html',
                               weekly_exp=gastos_semana,
                               weekly_income=ingresos_semana,
                               monthly_exp=gastos_mes,
                               monthly_income=ingresos_mes,
                               total_exp=total_gastos,
                               total_income=total_ingresos,
                               total_balance=total_ingresos - total_gastos,
                               gastos_data=list(gastos_por_cat.values()),
                               gastos_labels=list(gastos_por_cat.keys()),
                               ingresos_data=list(ingresos_por_cat.values()),
                               ingresos_labels=list(ingresos_por_cat.keys()),
                               today=hoy.strftime('%Y-%m-%d'),
                               active_page='dashboard')

    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        flash('Error al cargar el dashboard', 'danger')
        return render_template('dashboard.html',
                               weekly_exp=0, weekly_income=0,
                               monthly_exp=0, monthly_income=0,
                               total_exp=0, total_income=0,
                               total_balance=0,
                               gastos_data=[], gastos_labels=[],
                               ingresos_data=[], ingresos_labels=[],
                               today=datetime.now().strftime('%Y-%m-%d'),
                               active_page='dashboard')


# ================================================================
# Gastos e Ingresos (rutas completas)
# ================================================================

@app.route('/expenses')
@login_required
def expenses():
    user_id = session['user_id']
    try:
        gastos = supabase.table('gastos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute().data or []
        categorias = supabase.table('categorias_gastos').select('nombre').execute().data or []
        return render_template('expenses.html',
                               expenses=gastos,
                               categorias=categorias,
                               today=datetime.now().strftime('%Y-%m-%d'),
                               active_page='expenses')
    except Exception as e:
        logger.error(f"Error en expenses: {e}")
        flash('Error al cargar gastos', 'danger')
        return render_template('expenses.html', expenses=[], categorias=[], today=datetime.now().strftime('%Y-%m-%d'), active_page='expenses')


@app.route('/incomes')
@login_required
def incomes():
    user_id = session['user_id']
    try:
        ingresos = supabase.table('ingresos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute().data or []
        categorias = supabase.table('categorias_ingresos').select('nombre').execute().data or []
        return render_template('incomes.html',
                               incomes=ingresos,
                               categorias=categorias,
                               today=datetime.now().strftime('%Y-%m-%d'),
                               active_page='incomes')
    except Exception as e:
        logger.error(f"Error en incomes: {e}")
        flash('Error al cargar ingresos', 'danger')
        return render_template('incomes.html', incomes=[], categorias=[], today=datetime.now().strftime('%Y-%m-%d'), active_page='incomes')


@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    user_id = session['user_id']
    try:
        fecha = request.form.get('fecha')
        monto = float(request.form.get('monto') or 0)
        categoria = request.form.get('categoria')
        descripcion = request.form.get('descripcion', '')

        if monto <= 0 or not fecha or not categoria:
            flash('Datos inválidos', 'danger')
            return redirect(url_for('expenses'))

        supabase.table('gastos').insert({
            'user_id': user_id,
            'fecha': fecha,
            'monto': monto,
            'categoria': categoria,
            'descripcion': descripcion
        }).execute()

        flash('Gasto agregado correctamente', 'success')
    except Exception as e:
        logger.error(f"Error agregando gasto: {e}")
        flash('Error al agregar gasto', 'danger')

    return redirect(url_for('expenses'))


@app.route('/add_income', methods=['POST'])
@login_required
def add_income():
    user_id = session['user_id']
    try:
        fecha = request.form.get('fecha')
        monto = float(request.form.get('monto') or 0)
        categoria = request.form.get('categoria')
        descripcion = request.form.get('descripcion', '')

        if monto <= 0 or not fecha or not categoria:
            flash('Datos inválidos', 'danger')
            return redirect(url_for('incomes'))

        supabase.table('ingresos').insert({
            'user_id': user_id,
            'fecha': fecha,
            'monto': monto,
            'categoria': categoria,
            'descripcion': descripcion
        }).execute()

        flash('Ingreso agregado correctamente', 'success')
    except Exception as e:
        logger.error(f"Error agregando ingreso: {e}")
        flash('Error al agregar ingreso', 'danger')

    return redirect(url_for('incomes'))


# ================================================================
# Inicio
# ================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
