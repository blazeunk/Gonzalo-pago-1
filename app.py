from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Configuración MySQL
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "gonzalo_pago_db"
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
app.config["MYSQL_SSL_MODE"] = "DISABLED"

mysql = MySQL(app)

# Clave secreta (cámbiala por una segura y única en producción)
app.secret_key = "476d47eca2452cdd4519aa1bb823fe51b2d409462bf2cbd4152cacfc7959a9da"

# ────────────────────────────────────────────────
# Middleware: proteger rutas que requieren login
# ────────────────────────────────────────────────
@app.before_request
def require_login():
    if request.endpoint in ['login', 'register', 'inicio', 'static']:
        return
    if 'user_id' not in session:
        flash("Debes iniciar sesión primero", "warning")
        return redirect(url_for('login'))


# ────────────────────────────────────────────────
# Funciones auxiliares
# ────────────────────────────────────────────────

def obtener_categorias_gastos():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre FROM categorias_gastos ORDER BY nombre")
    categorias = cur.fetchall()
    cur.close()
    return categorias


def obtener_categorias_ingresos():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre FROM categorias_ingresos ORDER BY nombre")
    categorias = cur.fetchall()
    cur.close()
    return categorias


def obtener_gastos(user_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT g.id, g.fecha, g.monto, c.nombre AS categoria, g.categoria_id, g.descripcion
        FROM gastos g
        JOIN categorias_gastos c ON g.categoria_id = c.id
        WHERE g.user_id = %s
        ORDER BY g.fecha DESC
        LIMIT 500
    """, (user_id,))
    gastos = cur.fetchall()
    cur.close()
    return gastos


def obtener_ingresos(user_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT i.id, i.fecha, i.monto, c.nombre AS categoria, i.categoria_id, i.descripcion
        FROM ingresos i
        JOIN categorias_ingresos c ON i.categoria_id = c.id
        WHERE i.user_id = %s
        ORDER BY i.fecha DESC
        LIMIT 500
    """, (user_id,))
    ingresos = cur.fetchall()
    cur.close()
    return ingresos


def calcular_total_periodo(tipo, dias=7, user_id=None):
    if not user_id: return 0.0
    cur = mysql.connection.cursor()
    tabla = "gastos" if tipo == "gasto" else "ingresos"
    query = f"""
        SELECT COALESCE(SUM(monto), 0) AS total
        FROM {tabla}
        WHERE user_id = %s AND fecha >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
    """
    cur.execute(query, (user_id, dias))
    resultado = cur.fetchone()["total"]
    cur.close()
    return round(float(resultado or 0), 2)


def calcular_total_mes_actual(tipo, user_id=None):
    if not user_id: return 0.0
    cur = mysql.connection.cursor()
    tabla = "gastos" if tipo == "gasto" else "ingresos"
    query = f"""
        SELECT COALESCE(SUM(monto), 0) AS total
        FROM {tabla}
        WHERE user_id = %s 
          AND YEAR(fecha) = YEAR(CURDATE()) 
          AND MONTH(fecha) = MONTH(CURDATE())
    """
    cur.execute(query, (user_id,))
    resultado = cur.fetchone()["total"]
    cur.close()
    return round(float(resultado or 0), 2)


def calcular_total_historico(tipo, user_id=None):
    if not user_id: return 0.0
    cur = mysql.connection.cursor()
    tabla = "gastos" if tipo == "gasto" else "ingresos"
    query = f"SELECT COALESCE(SUM(monto), 0) AS total FROM {tabla} WHERE user_id = %s"
    cur.execute(query, (user_id,))
    resultado = cur.fetchone()["total"]
    cur.close()
    return round(float(resultado or 0), 2)


# ────────────────────────────────────────────────
# Rutas de autenticación
# ────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if not (username and email and password):
            flash("Todos los campos son obligatorios", "warning")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)

        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO users (username, email, password)
                VALUES (%s, %s, %s)
            """, (username, email, hashed_pw))
            mysql.connection.commit()
            flash("Registro exitoso. Ahora inicia sesión.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Error al registrar: {str(e)} (quizá el usuario o email ya existe)", "danger")
        finally:
            cur.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            flash("Sesión iniciada correctamente", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Email o contraseña incorrectos", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Sesión cerrada", "info")
    return redirect(url_for("login"))


# ────────────────────────────────────────────────
# Rutas principales
# ────────────────────────────────────────────────

@app.route("/")
def inicio():
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    user_id = session.get("user_id")
    if not user_id:
        flash("Sesión no válida, inicia sesión nuevamente", "danger")
        return redirect(url_for("login"))

    # Totales principales
    ingresos_semana = calcular_total_periodo("ingreso", 7, user_id)
    gastos_semana   = calcular_total_periodo("gasto", 7, user_id)
    ingresos_mes    = calcular_total_mes_actual("ingreso", user_id)
    gastos_mes      = calcular_total_mes_actual("gasto", user_id)
    ingresos_total  = calcular_total_historico("ingreso", user_id)
    gastos_total    = calcular_total_historico("gasto", user_id)
    balance_total   = round(ingresos_total - gastos_total, 2)

    # ── Datos para gráficos de torta ──
    cur = mysql.connection.cursor()

    # Gastos por categoría (solo categorías con monto > 0)
    cur.execute("""
        SELECT c.nombre AS categoria, COALESCE(SUM(g.monto), 0) AS total
        FROM categorias_gastos c
        LEFT JOIN gastos g ON c.id = g.categoria_id AND g.user_id = %s
        GROUP BY c.id, c.nombre
        HAVING total > 0
        ORDER BY total DESC
        LIMIT 10
    """, (user_id,))
    gastos_por_cat = cur.fetchall()

    # Ingresos por categoría
    cur.execute("""
        SELECT c.nombre AS categoria, COALESCE(SUM(i.monto), 0) AS total
        FROM categorias_ingresos c
        LEFT JOIN ingresos i ON c.id = i.categoria_id AND i.user_id = %s
        GROUP BY c.id, c.nombre
        HAVING total > 0
        ORDER BY total DESC
        LIMIT 10
    """, (user_id,))
    ingresos_por_cat = cur.fetchall()

    cur.close()

    # Preparar listas para Chart.js
    gastos_labels = [row['categoria'] for row in gastos_por_cat]
    gastos_data   = [float(row['total']) for row in gastos_por_cat]

    ingresos_labels = [row['categoria'] for row in ingresos_por_cat]
    ingresos_data   = [float(row['total']) for row in ingresos_por_cat]

    return render_template(
        "dashboard.html",
        # Totales numéricos
        weekly_income=ingresos_semana,
        weekly_exp=gastos_semana,
        monthly_income=ingresos_mes,
        monthly_exp=gastos_mes,
        total_income=ingresos_total,
        total_exp=gastos_total,
        total_balance=balance_total,
        # Datos para gráficos
        gastos_labels=gastos_labels,
        gastos_data=gastos_data,
        ingresos_labels=ingresos_labels,
        ingresos_data=ingresos_data,
        active_page="dashboard"
    )

@app.route("/expenses")
def pagina_gastos():
    user_id = session["user_id"]
    gastos = obtener_gastos(user_id)
    categorias = obtener_categorias_gastos()
    hoy = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        "expenses.html",
        expenses=gastos,
        categorias=categorias,
        active_page="expenses",
        today=hoy
    )


@app.route("/incomes")
def pagina_ingresos():
    user_id = session["user_id"]
    ingresos = obtener_ingresos(user_id)
    categorias = obtener_categorias_ingresos()
    hoy = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        "incomes.html",
        incomes=ingresos,
        categorias=categorias,
        active_page="incomes",
        today=hoy
    )


@app.route("/add_expense", methods=["POST"])
def agregar_gasto():
    user_id = session["user_id"]
    fecha = request.form.get("date")
    monto_str = request.form.get("amount")
    categoria_id = request.form.get("categoria_id")
    descripcion = request.form.get("desc", "").strip()

    try:
        monto = float(monto_str) if monto_str else 0.0
    except:
        monto = 0.0

    if monto > 0 and fecha and categoria_id:
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO gastos (user_id, fecha, monto, categoria_id, descripcion)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, fecha, monto, int(categoria_id), descripcion))
            mysql.connection.commit()
            flash("Gasto agregado correctamente", "success")
        except Exception as e:
            flash(f"Error al guardar gasto: {str(e)}", "danger")
        finally:
            cur.close()
    else:
        flash("Faltan datos o monto inválido", "warning")

    return redirect(url_for("pagina_gastos"))


@app.route("/add_income", methods=["POST"])
def agregar_ingreso():
    user_id = session["user_id"]
    fecha = request.form.get("date")
    monto_str = request.form.get("amount")
    categoria_id = request.form.get("categoria_id")
    descripcion = request.form.get("desc", "").strip()

    try:
        monto = float(monto_str) if monto_str else 0.0
    except:
        monto = 0.0

    if monto > 0 and fecha and categoria_id:
        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO ingresos (user_id, fecha, monto, categoria_id, descripcion)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, fecha, monto, int(categoria_id), descripcion))
            mysql.connection.commit()
            flash("Ingreso agregado correctamente", "success")
        except Exception as e:
            flash(f"Error al guardar ingreso: {str(e)}", "danger")
        finally:
            cur.close()
    else:
        flash("Faltan datos o monto inválido", "warning")

    return redirect(url_for("pagina_ingresos"))


@app.route("/delete_expense/<int:id>", methods=["POST"])
def eliminar_gasto(id):
    user_id = session["user_id"]
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM gastos WHERE id = %s AND user_id = %s", (id, user_id))
        mysql.connection.commit()
        if cur.rowcount > 0:
            flash("Gasto eliminado correctamente", "success")
        else:
            flash("No se encontró el gasto o no tienes permiso", "warning")
    except Exception as e:
        flash(f"Error al eliminar: {str(e)}", "danger")
    finally:
        cur.close()
    return redirect(url_for("pagina_gastos"))


@app.route("/delete_income/<int:id>", methods=["POST"])
def eliminar_ingreso(id):
    user_id = session["user_id"]
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM ingresos WHERE id = %s AND user_id = %s", (id, user_id))
        mysql.connection.commit()
        if cur.rowcount > 0:
            flash("Ingreso eliminado correctamente", "success")
        else:
            flash("No se encontró el ingreso o no tienes permiso", "warning")
    except Exception as e:
        flash(f"Error al eliminar: {str(e)}", "danger")
    finally:
        cur.close()
    return redirect(url_for("pagina_ingresos"))


@app.route("/edit_expense/<int:id>", methods=["GET", "POST"])
def editar_gasto(id):
    user_id = session["user_id"]
    cur = mysql.connection.cursor()

    if request.method == "POST":
        fecha = request.form.get("date")
        monto_str = request.form.get("amount")
        categoria_id = request.form.get("categoria_id")
        descripcion = request.form.get("desc", "").strip()

        try:
            monto = float(monto_str) if monto_str else 0.0
        except:
            monto = 0.0

        if monto > 0 and fecha and categoria_id:
            try:
                cur.execute("""
                    UPDATE gastos 
                    SET fecha = %s, monto = %s, categoria_id = %s, descripcion = %s
                    WHERE id = %s AND user_id = %s
                """, (fecha, monto, int(categoria_id), descripcion, id, user_id))
                mysql.connection.commit()
                if cur.rowcount > 0:
                    flash("Gasto actualizado correctamente", "success")
                else:
                    flash("No se encontró el gasto o no tienes permiso", "warning")
                return redirect(url_for("pagina_gastos"))
            except Exception as e:
                flash(f"Error al actualizar: {str(e)}", "danger")
        else:
            flash("Datos inválidos", "warning")

    # GET: cargar datos para editar
    cur.execute("""
        SELECT id, fecha, monto, categoria_id, descripcion 
        FROM gastos 
        WHERE id = %s AND user_id = %s
    """, (id, user_id))
    gasto = cur.fetchone()

    categorias = obtener_categorias_gastos()
    cur.close()

    if not gasto:
        flash("Gasto no encontrado o no tienes permiso", "danger")
        return redirect(url_for("pagina_gastos"))

    return render_template(
        "edit_expense.html",
        gasto=gasto,
        categorias=categorias,
        active_page="expenses"
    )


@app.route("/edit_income/<int:id>", methods=["GET", "POST"])
def editar_ingreso(id):
    user_id = session["user_id"]
    cur = mysql.connection.cursor()

    if request.method == "POST":
        fecha = request.form.get("date")
        monto_str = request.form.get("amount")
        categoria_id = request.form.get("categoria_id")
        descripcion = request.form.get("desc", "").strip()

        try:
            monto = float(monto_str) if monto_str else 0.0
        except:
            monto = 0.0

        if monto > 0 and fecha and categoria_id:
            try:
                cur.execute("""
                    UPDATE ingresos 
                    SET fecha = %s, monto = %s, categoria_id = %s, descripcion = %s
                    WHERE id = %s AND user_id = %s
                """, (fecha, monto, int(categoria_id), descripcion, id, user_id))
                mysql.connection.commit()
                if cur.rowcount > 0:
                    flash("Ingreso actualizado correctamente", "success")
                else:
                    flash("No se encontró el ingreso o no tienes permiso", "warning")
                return redirect(url_for("pagina_ingresos"))
            except Exception as e:
                flash(f"Error al actualizar: {str(e)}", "danger")
        else:
            flash("Datos inválidos", "warning")

    # GET: cargar datos
    cur.execute("""
        SELECT id, fecha, monto, categoria_id, descripcion 
        FROM ingresos 
        WHERE id = %s AND user_id = %s
    """, (id, user_id))
    ingreso = cur.fetchone()

    categorias = obtener_categorias_ingresos()
    cur.close()

    if not ingreso:
        flash("Ingreso no encontrado o no tienes permiso", "danger")
        return redirect(url_for("pagina_ingresos"))

    return render_template(
        "edit_income.html",
        ingreso=ingreso,
        categorias=categorias,
        active_page="incomes"
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)