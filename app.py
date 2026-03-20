"""
Gonzalo Pago - Versión FINAL para Render + Supabase
Última actualización: marzo 2026
"""
import logging
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

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
    try:
        user_id = session['user_id']
        hoy = datetime.now()
        hace_7_dias = (hoy - timedelta(days=7)).strftime('%Y-%m-%d')
        inicio_mes = hoy.replace(day=1).strftime('%Y-%m-%d')
        
        # Obtener gastos e ingresos desde Supabase
        gastos_result = supabase.table('gastos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute()
        
        ingresos_result = supabase.table('ingresos')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('fecha', desc=True)\
            .execute()
        
        gastos = gastos_result.data or []
        ingresos = ingresos_result.data or []
        
        # Calcular totales
        total_gastos = sum(float(g.get('monto', 0)) for g in gastos)
        total_ingresos = sum(float(i.get('monto', 0)) for i in ingresos)
        
        # Semanales
        gastos_semana = sum(float(g.get('monto', 0)) for g in gastos 
                           if g.get('fecha', '') >= hace_7_dias)
        ingresos_semana = sum(float(i.get('monto', 0)) for i in ingresos 
                            if i.get('fecha', '') >= hace_7_dias)
        
        # Mensuales
        gastos_mes = sum(float(g.get('monto', 0)) for g in gastos 
                        if g.get('fecha', '') >= inicio_mes)
        ingresos_mes = sum(float(i.get('monto', 0)) for i in ingresos 
                         if i.get('fecha', '') >= inicio_mes)
        
        # Datos para gráficos
        gastos_por_categoria = {}
        for g in gastos:
            cat = g.get('categoria', 'Otros')
            gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0) + float(g.get('monto', 0))
        
        ingresos_por_categoria = {}
        for i in ingresos:
            cat = i.get('categoria', 'Otros')
            ingresos_por_categoria[cat] = ingresos_por_categoria.get(cat, 0) + float(i.get('monto', 0))
        
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
        print(f"Error en dashboard: {e}")  # Para ver en logs de Render
        flash('Error al cargar el dashboard', 'danger')
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
                               today=datetime.now().strftime('%Y-%m-%d'))
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
