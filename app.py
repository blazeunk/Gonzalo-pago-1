import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from supabase import create_client, Client
from dotenv import load_dotenv
import pandas as pd
from io import BytesIO

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "tu_clave_secreta_aqui")

# Configuración de Supabase
url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            session['user_id'] = res.user.id
            return redirect(url_for('dashboard'))
        except Exception as e:
            return render_template('login.html', error="Credenciales inválidas")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# --- DASHBOARD Y GRÁFICOS ---

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    
    # Obtener gastos para el gráfico (incluyendo el nombre de la categoría)
    gastos_res = supabase.table("gastos").select("monto, categorias_gastos(nombre)").eq("usuario_id", user_id).execute()
    gastos = gastos_res.data
    
    # Agrupar datos por categoría
    resumen = {}
    total_gastos = 0
    for g in gastos:
        cat_nombre = g['categorias_gastos']['nombre'] if g['categorias_gastos'] else "Otros"
        monto = float(g['monto'])
        resumen[cat_nombre] = resumen.get(cat_nombre, 0) + monto
        total_gastos += monto

    # Obtener total de ingresos
    ingresos_res = supabase.table("ingresos").select("monto").eq("usuario_id", user_id).execute()
    total_ingresos = sum(float(i['monto']) for i in ingresos_res.data)

    return render_template('dashboard.html', 
                           labels=list(resumen.keys()), 
                           values=list(resumen.values()),
                           total_ingresos=total_ingresos,
                           total_gastos=total_gastos,
                           balance=total_ingresos - total_gastos)

# --- GESTIÓN DE GASTOS ---

@app.route('/expenses')
def pagina_gastos():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    
    gastos = supabase.table("gastos").select("*, categorias_gastos(nombre)").eq("usuario_id", user_id).order("id").execute().data
    categorias = supabase.table("categorias_gastos").select("*").execute().data
    return render_template('expenses.html', gastos_lista=gastos, categorias=categorias)

@app.route('/add_expense', methods=['POST'])
def agregar_gasto():
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("gastos").insert({
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id')),
        "usuario_id": session['user_id']
    }).execute()
    return redirect(url_for('pagina_gastos'))

@app.route('/edit_expense/<int:id>', methods=['POST'])
def editar_gasto(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("gastos").update({
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id'))
    }).eq("id", id).execute()
    return redirect(url_for('pagina_gastos'))

@app.route('/delete_expense/<int:id>')
def eliminar_gasto(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("gastos").delete().eq("id", id).execute()
    return redirect(url_for('pagina_gastos'))

# --- GESTIÓN DE INGRESOS ---

@app.route('/incomes')
def pagina_incomes():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    
    ingresos = supabase.table("ingresos").select("*, categorias_ingresos(nombre)").eq("usuario_id", user_id).order("id").execute().data
    categorias = supabase.table("categorias_ingresos").select("*").execute().data
    return render_template('incomes.html', ingresos_lista=ingresos, categorias=categorias)

@app.route('/add_income', methods=['POST'])
def agregar_income():
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("ingresos").insert({
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id')),
        "usuario_id": session['user_id']
    }).execute()
    return redirect(url_for('pagina_incomes'))

@app.route('/edit_income/<int:id>', methods=['POST'])
def editar_ingreso(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("ingresos").update({
        "descripcion": request.form.get('descripcion'),
        "monto": float(request.form.get('monto')),
        "categoria_id": int(request.form.get('categoria_id'))
    }).eq("id", id).execute()
    return redirect(url_for('pagina_incomes'))

@app.route('/delete_income/<int:id>')
def eliminar_ingreso(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("ingresos").delete().eq("id", id).execute()
    return redirect(url_for('pagina_incomes'))

# --- EXPORTAR A EXCEL ---

@app.route('/exportar_excel')
def exportar_excel():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    gastos = supabase.table("gastos").select("descripcion, monto, fecha").eq("usuario_id", user_id).execute().data
    ingresos = supabase.table("ingresos").select("descripcion, monto, fecha").eq("usuario_id", user_id).execute().data

    df_gastos = pd.DataFrame(gastos) if gastos else pd.DataFrame(columns=["descripcion", "monto", "fecha"])
    df_ingresos = pd.DataFrame(ingresos) if ingresos else pd.DataFrame(columns=["descripcion", "monto", "fecha"])

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_gastos.to_excel(writer, index=False, sheet_name='Gastos')
        df_ingresos.to_excel(writer, index=False, sheet_name='Ingresos')
    
    output.seek(0)
    return send_file(
        output, 
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        download_name="Mi_Presupuesto.xlsx", 
        as_attachment=True
    )

if __name__ == '__main__':
    app.run(debug=True)
