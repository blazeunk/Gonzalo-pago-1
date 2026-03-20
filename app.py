import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from supabase import create_client, Client
import pandas as pd
from io import BytesIO

# ======================================================
# CONFIG
# ======================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-secreta')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======================================================
# LOGIN REQUIRED
# ======================================================

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# ======================================================
# AUTH
# ======================================================

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
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
            flash('Error login', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ======================================================
# DASHBOARD
# ======================================================

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        user_id = session['user_id']
        hoy = datetime.now()
        hace_7 = (hoy - timedelta(days=7)).strftime('%Y-%m-%d')

        gastos = supabase.table('gastos').select('*').eq('user_id', user_id).execute().data or []
        ingresos = supabase.table('ingresos').select('*').eq('user_id', user_id).execute().data or []

        total_gastos = sum(float(g['monto']) for g in gastos)
        total_ingresos = sum(float(i['monto']) for i in ingresos)

        weekly_income = sum(float(i['monto']) for i in ingresos if i['fecha'] >= hace_7)
        weekly_exp = sum(float(g['monto']) for g in gastos if g['fecha'] >= hace_7)

        # PARA CHARTS
        gastos_cat = {}
        for g in gastos:
            cat = g['categoria']
            gastos_cat[cat] = gastos_cat.get(cat, 0) + float(g['monto'])

        ingresos_cat = {}
        for i in ingresos:
            cat = i['categoria']
            ingresos_cat[cat] = ingresos_cat.get(cat, 0) + float(i['monto'])

        return render_template(
            'dashboard.html',
            total_income=total_ingresos,
            total_exp=total_gastos,
            total_balance=total_ingresos - total_gastos,
            weekly_income=weekly_income,
            weekly_exp=weekly_exp,
            gastos_data=list(gastos_cat.values()),
            gastos_labels=list(gastos_cat.keys()),
            ingresos_data=list(ingresos_cat.values()),
            ingresos_labels=list(ingresos_cat.keys())
        )

    except Exception as e:
        logger.error(e)
        return "Error dashboard"

# ======================================================
# GASTOS
# ======================================================

@app.route('/expenses')
@login_required
def expenses():
    user_id = session['user_id']
    gastos = supabase.table('gastos').select('*').eq('user_id', user_id).execute().data or []
    return render_template('expenses.html', expenses=gastos)

@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    supabase.table('gastos').insert({
        "user_id": session['user_id'],
        "fecha": request.form['fecha'],
        "monto": float(request.form['monto']),
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion']
    }).execute()
    return redirect(url_for('expenses'))

@app.route('/delete_expense/<int:id>')
@login_required
def delete_expense(id):
    supabase.table('gastos').delete().eq('id', id).execute()
    flash('Gasto eliminado', 'success')
    return redirect(url_for('expenses'))

@app.route('/edit_expense/<int:id>', methods=['POST'])
@login_required
def edit_expense(id):
    supabase.table('gastos').update({
        "fecha": request.form['fecha'],
        "monto": float(request.form['monto']),
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion']
    }).eq('id', id).execute()

    flash('Gasto actualizado', 'success')
    return redirect(url_for('expenses'))

@app.route('/export_expenses')
@login_required
def export_expenses():
    data = supabase.table('gastos').select('*').eq('user_id', session['user_id']).execute().data

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, download_name="gastos.xlsx", as_attachment=True)

# ======================================================
# INGRESOS (MISMO SISTEMA)
# ======================================================

@app.route('/incomes')
@login_required
def incomes():
    ingresos = supabase.table('ingresos').select('*').eq('user_id', session['user_id']).execute().data or []
    return render_template('incomes.html', incomes=ingresos)

@app.route('/add_income', methods=['POST'])
@login_required
def add_income():
    supabase.table('ingresos').insert({
        "user_id": session['user_id'],
        "fecha": request.form['fecha'],
        "monto": float(request.form['monto']),
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion']
    }).execute()
    return redirect(url_for('incomes'))

@app.route('/delete_income/<int:id>')
@login_required
def delete_income(id):
    supabase.table('ingresos').delete().eq('id', id).execute()
    flash('Ingreso eliminado', 'success')
    return redirect(url_for('incomes'))

@app.route('/edit_income/<int:id>', methods=['POST'])
@login_required
def edit_income(id):
    supabase.table('ingresos').update({
        "fecha": request.form['fecha'],
        "monto": float(request.form['monto']),
        "categoria": request.form['categoria'],
        "descripcion": request.form['descripcion']
    }).eq('id', id).execute()

    flash('Ingreso actualizado', 'success')
    return redirect(url_for('incomes'))

@app.route('/export_incomes')
@login_required
def export_incomes():
    data = supabase.table('ingresos').select('*').eq('user_id', session['user_id']).execute().data

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, download_name="ingresos.xlsx", as_attachment=True)

# ======================================================

if __name__ == '__main__':
    app.run(debug=True)
