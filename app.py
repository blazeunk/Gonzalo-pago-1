import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from io import BytesIO
from flask import send_file

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "pago_gonzalo_2026_key")

# --- CONFIGURACIÓN SUPABASE ---
supabase_url = os.environ.get("SUPABASE_URL", "").strip()
supabase_key = os.environ.get("SUPABASE_KEY", "").strip()
supabase: Client = create_client(supabase_url, supabase_key)

def obtener_contexto_financiero(user_id):
    try:
        # Traemos datos con joins para las categorías
        res_g = supabase.table("gastos").select("*, categorias_gastos(nombre)").eq("user_id", user_id).execute()
        res_i = supabase.table("ingresos").select("*, categorias_ingresos(nombre)").eq("user_id", user_id).execute()
        
        gastos = res_g.data or []
        ingresos = res_i.data or []
        
        sum_ingresos = sum(float(i.get('monto', 0)) for i in ingresos)
        sum_gastos = sum(float(g.get('monto', 0)) for g in gastos)
        balance = sum_ingresos - sum_gastos
        
        # Combinamos ambas listas para el historial del dashboard si es necesario
        todos_los_pagos = gastos + ingresos

        return {
            "total_income": sum_ingresos,
            "total_expenses": sum_gastos,
            "total_exp": sum_gastos,  # <--- AGREGADO PARA EVITAR EL ERROR JINJA2
            "total_balance": balance,
            "weekly_income": sum_ingresos / 4,
            "monthly_income": sum_ingresos,
            "weekly_exp": sum_gastos / 4,
            "monthly_exp": sum_gastos,
            "total_savings": max(0, balance),
            "gastos_lista": gastos,
            "ingresos_lista": ingresos,
            "pagos": todos_los_pagos, # Para compatibilidad con tablas generales
            "user_email": session.get('email', 'Usuario')
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            "total_income": 0, "total_expenses": 0, "total_exp": 0, 
            "total_balance": 0, "weekly_income": 0, "monthly_income": 0,
            "weekly_exp": 0, "monthly_exp": 0, "total_savings": 0,
            "gastos_lista": [], "ingresos_lista": [], "pagos": [],
            "user_email": "Usuario"
        }

@app.route('/')
def index():
    return redirect(url_for('dashboard')) if 'user_id' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password')
        res = supabase.table("users").select("*").eq("email", email).execute()
        user = res.data[0] if res.data else None
        if user and check_password_hash(user['password'], password):
            session.update({'user_id': user['id'], 'email': user['email']})
            return redirect(url_for('dashboard'))
        flash("Email o contraseña incorrectos", "danger")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        hashed = generate_password_hash(request.form.get('password'))
        try:
            supabase.table("users").insert({"email": email, "password": hashed}).execute()
            return redirect(url_for('login'))
        except: flash("El usuario ya existe", "danger")
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))

    # Obtener sumas por categoría para el gráfico
    gastos = supabase.table("gastos").select("monto, categorias_gastos(nombre)").eq("usuario_id", session['user_id']).execute().data
    
    # Agrupar datos para el gráfico
    resumen = {}
    for g in gastos:
        cat = g['categorias_gastos']['nombre'] if g['categorias_gastos'] else "Otros"
        resumen[cat] = resumen.get(cat, 0) + float(g['monto'])
    
    return render_template('dashboard.html', 
                           labels=list(resumen.keys()), 
                           values=list(resumen.values()))

@app.route('/expenses')
def pagina_gastos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    cats = supabase.table("categorias_gastos").select("*").execute().data
    return render_template('expenses.html', active_page='expenses', categorias=cats, **ctx)

@app.route('/incomes')
def pagina_ingresos():
    if 'user_id' not in session: return redirect(url_for('login'))
    ctx = obtener_contexto_financiero(session['user_id'])
    cats = supabase.table("categorias_ingresos").select("*").execute().data
    return render_template('incomes.html', active_page='incomes', categorias=cats, **ctx)

@app.route('/add_expense', methods=['POST'])
def agregar_gasto():
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("gastos").insert({
        "user_id": session['user_id'],
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id'))
    }).execute()
    return redirect(url_for('pagina_gastos'))

@app.route('/add_income', methods=['POST'])
def agregar_income():
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("ingresos").insert({
        "user_id": session['user_id'],
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id'))
    }).execute()
    return redirect(url_for('pagina_ingresos'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ELIMINAR ---
@app.route('/delete_expense/<int:id>')
def eliminar_gasto(id):
    supabase.table("gastos").delete().eq("id", id).execute()
    return redirect(url_for('pagina_gastos'))

@app.route('/delete_income/<int:id>')
def eliminar_ingreso(id):
    supabase.table("ingresos").delete().eq("id", id).execute()
    return redirect(url_for('pagina_ingresos'))

@app.route('/edit_expense/<int:id>', methods=['POST'])
def editar_gasto(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    supabase.table("gastos").update({
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id'))
    }).eq("id", id).execute()
    
    return redirect(url_for('pagina_gastos'))

@app.route('/edit_income/<int:id>', methods=['POST'])
def editar_ingreso(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    supabase.table("ingresos").update({
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id'))
    }).eq("id", id).execute()
    
    return redirect(url_for('pagina_ingresos'))
    @app.route('/exportar_excel')
def exportar_excel():
    if 'user_id' not in session: return redirect(url_for('login'))

    # Traer todos los gastos e ingresos
    gastos = supabase.table("gastos").select("descripcion, monto, fecha").eq("usuario_id", session['user_id']).execute().data
    ingresos = supabase.table("ingresos").select("descripcion, monto, fecha").eq("usuario_id", session['user_id']).execute().data

    # Crear DataFrames
    df_gastos = pd.DataFrame(gastos)
    df_ingresos = pd.DataFrame(ingresos)

    # Crear el archivo Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_gastos.to_excel(writer, index=False, sheet_name='Gastos')
        df_ingresos.to_excel(writer, index=False, sheet_name='Ingresos')
    
    output.seek(0)
    
    return send_file(output, 
                     download_name="Mi_Presupuesto_2026.xlsx", 
                     as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
