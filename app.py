import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from supabase import create_client, Client
import pandas as pd
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-secreta')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# LOGIN REQUIRED
# =========================
def login_required(f):
    def wrap(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

# =========================
# HOME → LOGIN
# =========================
@app.route('/')
def home():
    return redirect(url_for('login'))

# =========================
# REGISTER
# =========================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            res = supabase.auth.sign_up({
                "email": request.form['email'],
                "password": request.form['password']
            })
            flash('Registrado correctamente', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(str(e), 'danger')
    return render_template('register.html')

# =========================
# LOGIN
# =========================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            res = supabase.auth.sign_in_with_password({
                "email": request.form['email'],
                "password": request.form['password']
            })
            session['user_id'] = res.user.id
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash('Credenciales incorrectas', 'danger')
    return render_template('login.html')

# =========================
# LOGOUT
# =========================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =========================
# DASHBOARD
# =========================
@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    hoy = datetime.now()
    hace_7 = (hoy - timedelta(days=7)).strftime('%Y-%m-%d')
    inicio_mes = hoy.replace(day=1).strftime('%Y-%m-%d')

    gastos = supabase.table('gastos').select('*').eq('user_id', user_id).execute().data or []
    ingresos = supabase.table('ingresos').select('*').eq('user_id', user_id).execute().data or []

    total_gastos = sum(float(g['monto']) for g in gastos)
    total_ingresos = sum(float(i['monto']) for i in ingresos)

    gastos_semana = sum(float(g['monto']) for g in gastos if g['fecha'] >= hace_7)
    ingresos_semana = sum(float(i['monto']) for i in ingresos if i['fecha'] >= hace_7)

    # categorías
    cat_gastos = {}
    for g in gastos:
        cat = g['categoria']
        cat_gastos[cat] = cat_gastos.get(cat, 0) + float(g['monto'])

    cat_ingresos = {}
    for i in ingresos:
        cat = i['categoria']
        cat_ingresos[cat] = cat_ingresos.get(cat, 0) + float(i['monto'])

    return render_template('dashboard.html',
        weekly_exp=gastos_semana,
        weekly_income=ingresos_semana,
        total_exp=total_gastos,
        total_income=total_ingresos,
        total_balance=total_ingresos - total_gastos,
        gastos_data=list(cat_gastos.values()),
        gastos_labels=list(cat_gastos.keys()),
        ingresos_data=list(cat_ingresos.values()),
        ingresos_labels=list(cat_ingresos.keys()),
        today=hoy.strftime('%Y-%m-%d')
    )

# =========================
# GASTOS
# =========================
@app.route('/expenses')
@login_required
def expenses():
    gastos = supabase.table('gastos').select('*').execute().data
    return render_template('expenses.html', expenses=gastos)

@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    try:
        fecha = request.form.get('fecha')
        monto = float(request.form.get('monto') or 0)
        categoria = request.form.get('categoria')
        descripcion = request.form.get('descripcion', '')

        if not fecha or monto <= 0 or not categoria:
            flash('Datos inválidos', 'danger')
            return redirect(url_for('expenses'))

        supabase.table('gastos').insert({
            "user_id": session['user_id'],
            "fecha": fecha,
            "monto": monto,
            "categoria": categoria,
            "descripcion": descripcion
        }).execute()

        flash('Gasto agregado', 'success')

    except Exception as e:
        flash('Error al agregar gasto', 'danger')

    return redirect(url_for('expenses'))

@app.route('/edit_expense/<id>', methods=['POST'])
@login_required
def edit_expense(id):
    supabase.table('gastos').update({
        "fecha": request.form['fecha'],
        "monto": request.form['monto'],
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion']
    }).eq('id', id).execute()
    return redirect(url_for('expenses'))

@app.route('/delete_expense/<id>')
@login_required
def delete_expense(id):
    supabase.table('gastos').delete().eq('id', id).execute()
    return redirect(url_for('expenses'))

@app.route('/export_expenses')
@login_required
def export_expenses():
    data = supabase.table('gastos').select('*').execute().data
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name="gastos.xlsx", as_attachment=True)

# =========================
# INGRESOS
# =========================
@app.route('/incomes')
@login_required
def incomes():
    ingresos = supabase.table('ingresos').select('*').execute().data
    return render_template('incomes.html', incomes=ingresos)

@app.route('/add_income', methods=['POST'])
@login_required
def add_income():
    supabase.table('ingresos').insert({
        "user_id": session['user_id'],
        "fecha": request.form['fecha'],
        "monto": request.form['monto'],
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion']
    }).execute()
    return redirect(url_for('incomes'))

@app.route('/edit_income/<id>', methods=['POST'])
@login_required
def edit_income(id):
    supabase.table('ingresos').update({
        "fecha": request.form['fecha'],
        "monto": request.form['monto'],
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion']
    }).eq('id', id).execute()
    return redirect(url_for('incomes'))

@app.route('/delete_income/<id>')
@login_required
def delete_income(id):
    supabase.table('ingresos').delete().eq('id', id).execute()
    return redirect(url_for('incomes'))

@app.route('/export_incomes')
@login_required
def export_incomes():
    data = supabase.table('ingresos').select('*').execute().data
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name="ingresos.xlsx", as_attachment=True)

# =========================
if __name__ == '__main__':
    app.run(debug=True)
