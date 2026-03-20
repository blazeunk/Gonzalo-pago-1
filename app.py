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

# Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan variables de entorno")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= LOGIN REQUIRED =================
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ================= ROOT =================
@app.route('/')
def home():
    return redirect(url_for('login'))

# ================= AUTH =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            res = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            if res.user:
                flash('Registrado correctamente', 'success')
                return redirect(url_for('login'))
        except Exception as e:
            flash(str(e), 'danger')

    return render_template('register.html')


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
        except:
            flash("Error login", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ================= DASHBOARD =================
@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']

    gastos = supabase.table('gastos').select('*').eq('user_id', user_id).execute().data or []
    ingresos = supabase.table('ingresos').select('*').eq('user_id', user_id).execute().data or []

    total_gastos = sum(float(g['monto']) for g in gastos)
    total_ingresos = sum(float(i['monto']) for i in ingresos)

    # gráficos
    gastos_cat = {}
    for g in gastos:
        gastos_cat[g['categoria']] = gastos_cat.get(g['categoria'], 0) + float(g['monto'])

    return render_template(
        'dashboard.html',
        total_exp=total_gastos,
        total_income=total_ingresos,
        total_balance=total_ingresos - total_gastos,
        gastos_labels=list(gastos_cat.keys()),
        gastos_data=list(gastos_cat.values())
    )

# ================= GASTOS =================
@app.route('/expenses')
@login_required
def expenses():
    user_id = session['user_id']
    gastos = supabase.table('gastos').select('*').eq('user_id', user_id).execute().data or []
    return render_template('expenses.html', expenses=gastos)


@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    user_id = session['user_id']

    supabase.table('gastos').insert({
        "user_id": user_id,
        "monto": float(request.form['monto']),
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion'],
        "fecha": request.form['fecha']
    }).execute()

    return redirect(url_for('expenses'))


@app.route('/delete_expense/<id>')
@login_required
def delete_expense(id):
    supabase.table('gastos').delete().eq('id', id).execute()
    return redirect(url_for('expenses'))


@app.route('/edit_expense/<id>', methods=['POST'])
@login_required
def edit_expense(id):
    supabase.table('gastos').update({
        "monto": float(request.form['monto']),
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion']
    }).eq('id', id).execute()

    return redirect(url_for('expenses'))

# ================= INGRESOS =================
@app.route('/incomes')
@login_required
def incomes():
    user_id = session['user_id']
    ingresos = supabase.table('ingresos').select('*').eq('user_id', user_id).execute().data or []
    return render_template('incomes.html', incomes=ingresos)


@app.route('/add_income', methods=['POST'])
@login_required
def add_income():
    user_id = session['user_id']

    supabase.table('ingresos').insert({
        "user_id": user_id,
        "monto": float(request.form['monto']),
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion'],
        "fecha": request.form['fecha']
    }).execute()

    return redirect(url_for('incomes'))


@app.route('/delete_income/<id>')
@login_required
def delete_income(id):
    supabase.table('ingresos').delete().eq('id', id).execute()
    return redirect(url_for('incomes'))


@app.route('/edit_income/<id>', methods=['POST'])
@login_required
def edit_income(id):
    supabase.table('ingresos').update({
        "monto": float(request.form['monto']),
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion']
    }).eq('id', id).execute()

    return redirect(url_for('incomes'))

# ================= EXPORT EXCEL =================
@app.route('/export_expenses')
@login_required
def export_expenses():
    user_id = session['user_id']
    data = supabase.table('gastos').select('*').eq('user_id', user_id).execute().data

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)

    output.seek(0)
    return send_file(output, download_name="gastos.xlsx", as_attachment=True)


@app.route('/export_incomes')
@login_required
def export_incomes():
    user_id = session['user_id']
    data = supabase.table('ingresos').select('*').eq('user_id', user_id).execute().data

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)

    output.seek(0)
    return send_file(output, download_name="ingresos.xlsx", as_attachment=True)

# ================= RUN =================
if __name__ == '__main__':
    app.run()
