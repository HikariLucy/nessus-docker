import sqlite3
import os
from datetime import datetime
import streamlit as st

DB_NAME = "hogar.db"

@st.cache_resource(ttl=3600)
def _init_postgres_connection(db_url):
    import psycopg2
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    return conn

def get_connection():
    """
    Establece una conexión segura. Intenta conectar a PostgreSQL usando DATABASE_URL
    en st.secrets, y si no existe o falla, recurre a la base de datos SQLite local.
    """
    db_url = None
    try:
        db_url = st.secrets.get("DATABASE_URL")
        if not db_url:
            db_url = st.secrets.get("api", {}).get("DATABASE_URL")
    except Exception:
        pass

    if db_url:
        try:
            conn = _init_postgres_connection(db_url)
            # Validar si la conexión obtenida de la caché está cerrada
            if conn.closed != 0:
                _init_postgres_connection.clear()
                conn = _init_postgres_connection(db_url)
            
            class PostgresCursorWrapper:
                def __init__(self, conn_wrapper, real_cursor):
                    self.conn_wrapper = conn_wrapper
                    self.real_cursor = real_cursor

                def execute(self, query, params=None):
                    import re
                    import psycopg2
                    # Convertir marcadores de posición de SQLite (?) a PostgreSQL (%s)
                    query = query.replace("?", "%s")
                    query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                    query = query.replace("AUTOINCREMENT", "")
                    
                    if "PRAGMA table_info" in query:
                        m = re.search(r"table_info\((.*?)\)", query)
                        if m:
                            tbl = m.group(1).strip().replace("'", "").replace('"', '')
                            query = f"SELECT column_name as name FROM information_schema.columns WHERE table_name = '{tbl}'"
                    
                    if "sqlite_master" in query:
                        if "sql" in query:
                            query = "SELECT '' as sql"
                        elif "name='estado_jrpg'" in query:
                            query = "SELECT table_name as name FROM information_schema.tables WHERE table_schema='public' AND table_name='estado_jrpg'"
                        elif "name='items_rapidos'" in query:
                            query = "SELECT table_name as name FROM information_schema.tables WHERE table_schema='public' AND table_name='items_rapidos'"
                        else:
                            query = "SELECT table_name as name FROM information_schema.tables WHERE table_schema='public'"
                            
                    if "INSERT OR REPLACE INTO estado_jrpg" in query or "REPLACE INTO estado_jrpg" in query:
                        query = "INSERT INTO estado_jrpg (usuario, clave, valor) VALUES (%s, %s, %s) ON CONFLICT (usuario, clave) DO UPDATE SET valor = EXCLUDED.valor"
                    elif "INSERT OR IGNORE INTO usuarios" in query:
                        query = "INSERT INTO usuarios (usuario, password_hash) VALUES (%s, %s) ON CONFLICT (usuario) DO NOTHING"
                    elif "INSERT OR REPLACE INTO" in query or "REPLACE INTO" in query:
                        m = re.search(r"(?:INSERT\s+OR\s+REPLACE\s+INTO|REPLACE\s+INTO)\s+(\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)", query, re.IGNORECASE)
                        if m:
                            tabla = m.group(1)
                            columnas = m.group(2)
                            valores = m.group(3)
                            if tabla == "estado_jrpg":
                                query = f"INSERT INTO {tabla} ({columnas}) VALUES ({valores}) ON CONFLICT (usuario, clave) DO UPDATE SET valor = EXCLUDED.valor"
                            elif tabla == "usuarios":
                                query = f"INSERT INTO {tabla} ({columnas}) VALUES ({valores}) ON CONFLICT (usuario) DO NOTHING"
                            elif tabla == "metas_ahorro":
                                query = f"INSERT INTO {tabla} ({columnas}) VALUES ({valores}) ON CONFLICT (id) DO UPDATE SET nombre = EXCLUDED.nombre, icono = EXCLUDED.icono, monto_meta = EXCLUDED.monto_meta, monto_actual = EXCLUDED.monto_actual"
                            else:
                                query = f"INSERT INTO {tabla} ({columnas}) VALUES ({valores}) ON CONFLICT (id) DO NOTHING"
                    
                    try:
                        if self.conn_wrapper.real_conn.closed != 0:
                            raise psycopg2.InterfaceError("Connection is closed.")
                        if params is not None:
                            return self.real_cursor.execute(query, params)
                        else:
                            return self.real_cursor.execute(query)
                    except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                        print(f"Error de conexion detectado durante execute: {e}. Re-conectando...")
                        _init_postgres_connection.clear()
                        self.conn_wrapper.real_conn = _init_postgres_connection(db_url)
                        import psycopg2.extras
                        self.real_cursor = self.conn_wrapper.real_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                        if params is not None:
                            return self.real_cursor.execute(query, params)
                        else:
                            return self.real_cursor.execute(query)

                def fetchone(self):
                    return self.real_cursor.fetchone()

                def fetchall(self):
                    return self.real_cursor.fetchall()

                def __getattr__(self, name):
                    return getattr(self.real_cursor, name)

            class PostgresConnWrapper:
                def __init__(self, real_conn):
                    self.real_conn = real_conn

                def cursor(self):
                    import psycopg2
                    import psycopg2.extras
                    try:
                        if self.real_conn.closed != 0:
                            raise psycopg2.InterfaceError("Connection is closed.")
                        real_cur = self.real_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                        return PostgresCursorWrapper(self, real_cur)
                    except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                        print(f"Error de conexion detectado al abrir cursor: {e}. Re-conectando...")
                        _init_postgres_connection.clear()
                        self.real_conn = _init_postgres_connection(db_url)
                        real_cur = self.real_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                        return PostgresCursorWrapper(self, real_cur)

                def commit(self):
                    pass

                def rollback(self):
                    pass

                def close(self):
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass

                def __getattr__(self, name):
                    return getattr(self.real_conn, name)

            return PostgresConnWrapper(conn)
        except Exception as e:
            print(f"Postgres connection failed, falling back to SQLite: {e}")

    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@st.cache_resource(show_spinner=False)
def _get_table_columns_cached(table):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table})")
            return [row['name'] for row in cursor.fetchall()]
    except Exception:
        return []

def check_and_add_column(table, column, col_type, default_val=None):
    try:
        columns = _get_table_columns_cached(table)
        if column not in columns:
            with get_connection() as conn:
                cursor = conn.cursor()
                alter_query = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                if default_val is not None:
                    alter_query += f" DEFAULT '{default_val}'"
                cursor.execute(alter_query)
                conn.commit()
            _get_table_columns_cached.clear()
    except Exception:
        pass

def migrate_estado_jrpg():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estado_jrpg'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(estado_jrpg)")
                cols = [row['name'] for row in cursor.fetchall()]
                if 'usuario' not in cols and len(cols) > 0:
                    cursor.execute("ALTER TABLE estado_jrpg RENAME TO estado_jrpg_old")
                    cursor.execute("""
                        CREATE TABLE estado_jrpg (
                            usuario TEXT NOT NULL DEFAULT 'dante',
                            clave TEXT NOT NULL,
                            valor TEXT NOT NULL,
                            PRIMARY KEY (usuario, clave)
                        )
                    """)
                    cursor.execute("INSERT INTO estado_jrpg (usuario, clave, valor) SELECT 'dante', clave, valor FROM estado_jrpg_old")
                    cursor.execute("DROP TABLE estado_jrpg_old")
                    conn.commit()
    except Exception:
        pass

def migrate_items_rapidos():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='items_rapidos'")
            row = cursor.fetchone()
            if row:
                sql_str = row['sql']
                if "CHECK" in sql_str or "CHECK(tipo_lista" in sql_str:
                    cursor.execute("ALTER TABLE items_rapidos RENAME TO items_rapidos_old")
                    cursor.execute("""
                        CREATE TABLE items_rapidos (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            usuario TEXT NOT NULL DEFAULT 'dante',
                            producto TEXT NOT NULL,
                            cantidad TEXT NOT NULL DEFAULT '1',
                            tipo_lista TEXT NOT NULL,
                            icono TEXT NOT NULL DEFAULT '📦'
                        )
                    """)
                    cursor.execute("""
                        INSERT INTO items_rapidos (id, usuario, producto, cantidad, tipo_lista, icono)
                        SELECT id, usuario, producto, cantidad, tipo_lista, icono FROM items_rapidos_old
                    """)
                    cursor.execute("DROP TABLE items_rapidos_old")
                    conn.commit()
    except Exception:
        pass

@st.cache_resource(show_spinner=False)
def init_db():
    """
    Inicializa la base de datos creando las tablas necesarias si no existen.
    Maneja excepciones para garantizar robustez y ejecuta migraciones.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla de Finanzas (Ingresos y Gastos)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS finanzas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL DEFAULT 'dante',
                    tipo TEXT NOT NULL CHECK(tipo IN ('Ingreso', 'Gasto')),
                    monto REAL NOT NULL CHECK(monto >= 0),
                    categoria TEXT NOT NULL,
                    descripcion TEXT,
                    fecha TEXT NOT NULL
                )
            """)
            
            # Tabla de Lista de Compras
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS compras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL DEFAULT 'dante',
                    producto TEXT NOT NULL,
                    cantidad TEXT NOT NULL,
                    tipo_lista TEXT NOT NULL DEFAULT 'Supermercado',
                    comprado INTEGER DEFAULT 0 CHECK(comprado IN (0, 1))
                )
            """)
            
            # Tabla de Calendario Familiar
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL DEFAULT 'dante',
                    evento TEXT NOT NULL,
                    fecha TEXT NOT NULL,
                    tipo TEXT NOT NULL CHECK(tipo IN ('Fecha Importante', 'Vencimiento')),
                    completado INTEGER DEFAULT 0 CHECK(completado IN (0, 1))
                )
            """)
            
            # Tabla de Variables de Estado JRPG y Metas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS estado_jrpg (
                    usuario TEXT NOT NULL DEFAULT 'dante',
                    clave TEXT NOT NULL,
                    valor TEXT NOT NULL,
                    PRIMARY KEY (usuario, clave)
                )
            """)
            
            # Tabla de Misiones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS misiones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL DEFAULT 'dante',
                    clave TEXT NOT NULL,
                    label TEXT NOT NULL,
                    xp INTEGER NOT NULL
                )
            """)
            
            # Tabla de Metas de Ahorro
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metas_ahorro (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL DEFAULT 'dante',
                    nombre TEXT NOT NULL,
                    icono TEXT NOT NULL DEFAULT '🎯',
                    monto_meta REAL NOT NULL CHECK(monto_meta >= 0),
                    monto_actual REAL NOT NULL DEFAULT 0.0 CHECK(monto_actual >= 0)
                )
            """)
            
            # Tabla de Items Rápidos (Sin CHECK constraint en tipo_lista)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS items_rapidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL DEFAULT 'dante',
                    producto TEXT NOT NULL,
                    cantidad TEXT NOT NULL DEFAULT '1',
                    tipo_lista TEXT NOT NULL,
                    icono TEXT NOT NULL DEFAULT '📦'
                )
            """)
            
            # Tabla de Historial de Precios para la IA
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS historial_precios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL DEFAULT 'dante',
                    producto TEXT NOT NULL,
                    marca TEXT,
                    precio REAL NOT NULL,
                    fecha TEXT NOT NULL
                )
            """)
            # Tabla de Usuarios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    usuario TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    email TEXT DEFAULT '',
                    ultimo_correo_resumen TEXT DEFAULT ''
                )
            """)
            # Tabla de Presupuestos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS presupuestos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL DEFAULT 'dante',
                    categoria TEXT NOT NULL,
                    monto_limite REAL NOT NULL CHECK(monto_limite >= 0)
                )
            """)
            conn.commit()
            
        # Ejecutar migraciones automáticas si la base de datos ya existía
        check_and_add_column("finanzas", "usuario", "TEXT", "dante")
        check_and_add_column("finanzas", "es_hormiga", "INTEGER", 0)
        check_and_add_column("compras", "usuario", "TEXT", "dante")
        check_and_add_column("compras", "tipo_lista", "TEXT", "Supermercado")
        check_and_add_column("compras", "marca", "TEXT", "")
        check_and_add_column("compras", "precio", "REAL", 0.0)
        check_and_add_column("calendario", "usuario", "TEXT", "dante")
        check_and_add_column("historial_precios", "establecimiento", "TEXT", "")
        check_and_add_column("usuarios", "email", "TEXT", "")
        check_and_add_column("usuarios", "ultimo_correo_resumen", "TEXT", "")
        migrate_estado_jrpg()
        migrate_items_rapidos()
        
        # Migrar usuarios predeterminados
        migrar_usuarios_predeterminados()
        
    except Exception as e:
        raise e

# --- Módulo de Finanzas ---

def agregar_transaccion(usuario, tipo, monto, categoria, descripcion, fecha, es_hormiga=0):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO finanzas (usuario, tipo, monto, categoria, descripcion, fecha, es_hormiga) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (usuario, tipo, monto, categoria, descripcion, fecha, es_hormiga)
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al agregar transacción: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def obtener_transacciones(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM finanzas WHERE usuario = ? ORDER BY fecha DESC, id DESC", (usuario,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Error al obtener transacciones: {e}")
        return []

def eliminar_transaccion(usuario, id_transaccion):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM finanzas WHERE id = ? AND usuario = ?", (id_transaccion, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al eliminar transacción: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def obtener_resumen_financiero(usuario):
    """
    Retorna un diccionario con Ingresos Totales, Gastos Totales y Saldo Disponible para el usuario.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tipo, SUM(monto) as total FROM finanzas WHERE usuario = ? GROUP BY tipo", (usuario,))
            rows = cursor.fetchall()
            
            ingresos = 0.0
            gastos = 0.0
            for row in rows:
                if row['tipo'] == 'Ingreso':
                    ingresos = row['total'] if row['total'] else 0.0
                elif row['tipo'] == 'Gasto':
                    gastos = row['total'] if row['total'] else 0.0
            
            saldo = ingresos - gastos
            return {
                "ingresos": ingresos,
                "gastos": gastos,
                "saldo": saldo
            }
    except sqlite3.Error as e:
        print(f"Error al obtener resumen financiero: {e}")
        return {"ingresos": 0.0, "gastos": 0.0, "saldo": 0.0}

# --- Módulo de Lista de Compras ---

def agregar_item_compra(usuario, producto, cantidad, tipo_lista="Supermercado"):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO compras (usuario, producto, cantidad, tipo_lista, comprado) VALUES (?, ?, ?, ?, 0)",
                (usuario, producto, cantidad, tipo_lista)
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al agregar item de compra: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def obtener_items_compra(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM compras WHERE usuario = ? ORDER BY comprado ASC, producto ASC", (usuario,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Error al obtener lista de compras: {e}")
        return []

def cambiar_estado_item_compra(usuario, id_item, comprado):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE compras SET comprado = ? WHERE id = ? AND usuario = ?", (1 if comprado else 0, id_item, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al actualizar estado del item: {e}")
        return False

def eliminar_item_compra(usuario, id_item):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM compras WHERE id = ? AND usuario = ?", (id_item, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al eliminar item de compra: {e}")
        return False

def limpiar_compras_completadas(usuario, tipo_lista=None, establecimiento=None):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # 1. Obtener los comprados antes de borrarlos para archivar sus precios en historial_precios
            if tipo_lista:
                cursor.execute("SELECT producto, marca, precio FROM compras WHERE comprado = 1 AND usuario = ? AND tipo_lista = ?", (usuario, tipo_lista))
            else:
                cursor.execute("SELECT producto, marca, precio FROM compras WHERE comprado = 1 AND usuario = ?", (usuario,))
            comprados = cursor.fetchall()
            
            # Registrar cada uno en el historial de precios si tiene un precio > 0
            fecha_str = datetime.now().strftime('%Y-%m-%d')
            for row in comprados:
                prod = row['producto']
                brand = row['marca']
                price = row['precio']
                if price and float(price) > 0:
                    cursor.execute(
                        "INSERT INTO historial_precios (usuario, producto, marca, precio, fecha, establecimiento) VALUES (?, ?, ?, ?, ?, ?)",
                        (usuario, prod, brand, float(price), fecha_str, establecimiento or "")
                    )
            
            # 2. Proceder a borrar
            if tipo_lista:
                cursor.execute("DELETE FROM compras WHERE comprado = 1 AND usuario = ? AND tipo_lista = ?", (usuario, tipo_lista))
            else:
                cursor.execute("DELETE FROM compras WHERE comprado = 1 AND usuario = ?", (usuario,))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al limpiar compras completadas: {e}")
        return False

# --- Módulo de Calendario Familiar ---

def agregar_evento(usuario, evento, fecha, tipo):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO calendario (usuario, evento, fecha, tipo, completado) VALUES (?, ?, ?, ?, 0)",
                (usuario, evento, fecha, tipo)
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al agregar evento: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def obtener_eventos(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM calendario WHERE usuario = ? ORDER BY fecha ASC, evento ASC", (usuario,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Error al obtener eventos: {e}")
        return []

def cambiar_estado_evento(usuario, id_evento, completado):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE calendario SET completado = ? WHERE id = ? AND usuario = ?", (1 if completado else 0, id_evento, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al cambiar estado del evento: {e}")
        return False

def eliminar_evento(usuario, id_evento):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM calendario WHERE id = ? AND usuario = ?", (id_evento, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al eliminar evento: {e}")
        return False

# --- Módulo Variables de Estado JRPG ---

@st.cache_data(ttl=120, show_spinner=False)
def obtener_variable(usuario, clave, valor_defecto):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM estado_jrpg WHERE usuario = ? AND clave = ?", (usuario, clave))
            row = cursor.fetchone()
            if row:
                return row['valor']
            return valor_defecto
    except sqlite3.Error as e:
        print(f"Error al obtener variable {clave} para {usuario}: {e}")
        return valor_defecto

def guardar_variable(usuario, clave, valor):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO estado_jrpg (usuario, clave, valor) VALUES (?, ?, ?)", (usuario, clave, str(valor)))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al guardar variable {clave} para {usuario}: {e}")
        return False

# --- Módulo de Misiones Personalizadas ---

def init_misiones_predeterminadas(usuario):
    default_quests = [
        {"clave": "q_ordenar_pieza", "label": "🧹 Ordenar pieza", "xp": 15},
        {"clave": "q_limpiar_banio", "label": "🧼 Limpiar baño", "xp": 25},
        {"clave": "q_limpiar_living", "label": "✨ Limpiar living", "xp": 15},
        {"clave": "q_limpiar_cocina", "label": "🍳 Limpiar cocina", "xp": 20},
        {"clave": "q_lavar_loza", "label": "🍽️ Lavar la loza", "xp": 15},
        {"clave": "q_botar_basura", "label": "🗑️ Botar la basura", "xp": 10},
        {"clave": "q_lavar_ropa", "label": "🧺 Lavar ropa", "xp": 15},
        {"clave": "q_guardar_ropa", "label": "👕 Guardar ropa", "xp": 10},
        {"clave": "q_preparar_almuerzo", "label": "🍲 Preparar almuerzo", "xp": 20},
        {"clave": "q_limpiar_pieza_chica", "label": "🪟 Limpiar pieza chica", "xp": 12},
    ]
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            for q in default_quests:
                cursor.execute(
                    "INSERT INTO misiones (usuario, clave, label, xp) VALUES (?, ?, ?, ?)",
                    (usuario, q["clave"], q["label"], q["xp"])
                )
            cursor.execute("COMMIT")
    except Exception:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass

@st.cache_data(ttl=120, show_spinner=False)
def obtener_misiones(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM misiones WHERE usuario = ?", (usuario,))
            row = cursor.fetchone()
            count = row[0] if row else 0
            
        if count == 0:
            init_misiones_predeterminadas(usuario)
            guardar_variable(usuario, "misiones_inicializadas", "True")
            
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM misiones WHERE usuario = ? ORDER BY id ASC", (usuario,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []

def agregar_mision(usuario, label, xp):
    import re
    # Limpiar caracteres especiales para la clave
    clean_label = re.sub(r'[^a-zA-Z0-9]', '', label).lower()
    clean_label = clean_label[:15]
    import time
    clave = f"q_{clean_label}_{int(time.time())}"
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO misiones (usuario, clave, label, xp) VALUES (?, ?, ?, ?)",
                (usuario, clave, label, xp)
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al agregar misión: {e}")
        return False

def eliminar_mision(usuario, id_mision):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM misiones WHERE id = ? AND usuario = ?", (id_mision, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al eliminar misión: {e}")
        return False

# --- Módulo de Metas de Ahorro Personalizadas ---

def init_metas_predeterminadas(usuario):
    # Intentar obtener los montos anteriores si existen
    vac_act = float(obtener_variable(usuario, "ahorro_vacaciones", 1300000))
    eme_act = float(obtener_variable(usuario, "ahorro_emergencia", 2000000))
    
    default_metas = [
        {"nombre": "Vacaciones", "icono": "🌴", "monto_meta": 2000000.0, "monto_actual": vac_act},
        {"nombre": "Fondo de Emergencia", "icono": "🛡️", "monto_meta": 5000000.0, "monto_actual": eme_act}
    ]
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            for m in default_metas:
                cursor.execute(
                    "INSERT INTO metas_ahorro (usuario, nombre, icono, monto_meta, monto_actual) VALUES (?, ?, ?, ?, ?)",
                    (usuario, m["nombre"], m["icono"], m["monto_meta"], m["monto_actual"])
                )
            cursor.execute("COMMIT")
    except Exception:
        try:
            cursor.execute("ROLLBACK")
        except Exception:
            pass

@st.cache_data(ttl=120, show_spinner=False)
def obtener_metas_ahorro(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM metas_ahorro WHERE usuario = ?", (usuario,))
            row = cursor.fetchone()
            count = row[0] if row else 0
            
        if count == 0:
            init_metas_predeterminadas(usuario)
            guardar_variable(usuario, "metas_inicializadas", "True")
            
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM metas_ahorro WHERE usuario = ? ORDER BY id ASC", (usuario,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []

def agregar_meta_ahorro(usuario, nombre, icono, monto_meta, monto_actual=0.0):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO metas_ahorro (usuario, nombre, icono, monto_meta, monto_actual) VALUES (?, ?, ?, ?, ?)",
                (usuario, nombre, icono, float(monto_meta), float(monto_actual))
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al agregar meta de ahorro: {e}")
        return False

def actualizar_meta_ahorro(usuario, id_meta, nombre, icono, monto_meta, monto_actual):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE metas_ahorro SET nombre = ?, icono = ?, monto_meta = ?, monto_actual = ? WHERE id = ? AND usuario = ?",
                (nombre, icono, float(monto_meta), float(monto_actual), id_meta, usuario)
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al actualizar meta de ahorro: {e}")
        return False

def eliminar_meta_ahorro(usuario, id_meta):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM metas_ahorro WHERE id = ? AND usuario = ?", (id_meta, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al eliminar meta de ahorro: {e}")
        return False

# --- Módulo de Items Rápidos Personalizados ---

@st.cache_data(ttl=120, show_spinner=False)
def obtener_items_rapidos(usuario, tipo_lista):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM items_rapidos WHERE usuario = ? AND tipo_lista = ?", (usuario, tipo_lista))
            row = cursor.fetchone()
            count = row[0] if row else 0
            
        if count == 0:
            default_items = []
            if "Supermercado" in tipo_lista:
                default_items = [
                    {"producto": "Leche", "cantidad": "1 unit", "icono": "🥛"},
                    {"producto": "Pan", "cantidad": "1 unit", "icono": "🍞"},
                    {"producto": "Huevos", "cantidad": "1 docena", "icono": "🥚"}
                ]
            elif "Feria" in tipo_lista:
                default_items = [
                    {"producto": "Plátanos", "cantidad": "1 docena", "icono": "🍌"},
                    {"producto": "Manzanas", "cantidad": "1 kg", "icono": "🍎"},
                    {"producto": "Tomates", "cantidad": "1 kg", "icono": "🍅"}
                ]
            elif "Otras Compras" in tipo_lista:
                default_items = [
                    {"producto": "Carne Molida", "cantidad": "1 kg", "icono": "🥩"},
                    {"producto": "Pechuga de Pollo", "cantidad": "1 kg", "icono": "🍗"},
                    {"producto": "Filete de Merluza", "cantidad": "1 kg", "icono": "🐟"}
                ]
            elif "Pañalera" in tipo_lista:
                default_items = [
                    {"producto": "Pañales", "cantidad": "1 pack", "icono": "👶"},
                    {"producto": "Toallitas Húmedas", "cantidad": "1 pack", "icono": "🧼"},
                    {"producto": "Colonia de Bebé", "cantidad": "1 unit", "icono": "🧴"}
                ]
            
            if default_items:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("BEGIN")
                    for item in default_items:
                        cursor.execute(
                            "INSERT INTO items_rapidos (usuario, producto, cantidad, tipo_lista, icono) VALUES (?, ?, ?, ?, ?)",
                            (usuario, item["producto"], item["cantidad"], tipo_lista, item["icono"])
                        )
                    cursor.execute("COMMIT")
            guardar_variable(usuario, f"items_rapidos_ini_{tipo_lista.split()[0]}", "True")
            
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM items_rapidos WHERE usuario = ? AND tipo_lista = ? ORDER BY id ASC", (usuario, tipo_lista))
            return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []

def agregar_item_rapido(usuario, producto, cantidad, tipo_lista, icono="📦"):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO items_rapidos (usuario, producto, cantidad, tipo_lista, icono) VALUES (?, ?, ?, ?, ?)",
                (usuario, producto, cantidad, tipo_lista, icono)
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al agregar item rápido: {e}")
        return False

def eliminar_item_rapido(usuario, id_item):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM items_rapidos WHERE id = ? AND usuario = ?", (id_item, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al eliminar item rápido: {e}")
        return False

# --- Auto-Reset del Usuario Demo 'prueba' cada 12 Horas ---

def resetear_usuario_prueba():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            cursor.execute("DELETE FROM finanzas WHERE usuario = 'prueba'")
            cursor.execute("DELETE FROM compras WHERE usuario = 'prueba'")
            cursor.execute("DELETE FROM calendario WHERE usuario = 'prueba'")
            cursor.execute("DELETE FROM estado_jrpg WHERE usuario = 'prueba'")
            cursor.execute("DELETE FROM misiones WHERE usuario = 'prueba'")
            cursor.execute("DELETE FROM metas_ahorro WHERE usuario = 'prueba'")
            cursor.execute("DELETE FROM items_rapidos WHERE usuario = 'prueba'")
            cursor.execute("COMMIT")
            
        # 2. Inicializar valores demo limpios para 'prueba'
        # Variables de estado JRPG
        guardar_variable("prueba", "xp", "0")
        guardar_variable("prueba", "lvl", "1")
        guardar_variable("prueba", "ahorro_vacaciones", "450000")
        guardar_variable("prueba", "ahorro_emergencia", "2300000")
        guardar_variable("prueba", "toggle_saldo_real", "False")
        
        # Misiones predeterminadas
        init_misiones_predeterminadas("prueba")
        guardar_variable("prueba", "misiones_inicializadas", "True")
        
        # Metas predeterminadas
        init_metas_predeterminadas("prueba")
        guardar_variable("prueba", "metas_inicializadas", "True")
        
        # Items rápidos predeterminados
        obtener_items_rapidos("prueba", "Supermercado")
        obtener_items_rapidos("prueba", "Feria (Frutas y Verduras)")
        
        # Agregar transacciones demo y compras de forma agrupada
        fecha_hoy = datetime.now().strftime('%Y-%m-%d')
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            cursor.execute(
                "INSERT INTO finanzas (usuario, tipo, monto, categoria, descripcion, fecha, es_hormiga) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("prueba", "Ingreso", 3000000.0, "Sueldo / Salarios", "Ingreso Mensual Demo", fecha_hoy, 0)
            )
            cursor.execute(
                "INSERT INTO finanzas (usuario, tipo, monto, categoria, descripcion, fecha, es_hormiga) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("prueba", "Gasto", 450000.0, "Alquiler / Hipoteca", "Pago Arriendo Demo", fecha_hoy, 0)
            )
            cursor.execute(
                "INSERT INTO finanzas (usuario, tipo, monto, categoria, descripcion, fecha, es_hormiga) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("prueba", "Gasto", 250000.0, "Servicios (Luz, Agua, Gas)", "Cuentas Luz y Agua Demo", fecha_hoy, 0)
            )
            cursor.execute(
                "INSERT INTO compras (usuario, producto, cantidad, tipo_lista, comprado) VALUES (?, ?, ?, ?, 0)",
                ("prueba", "Queso Chanco", "500g", "Supermercado")
            )
            cursor.execute(
                "INSERT INTO compras (usuario, producto, cantidad, tipo_lista, comprado) VALUES (?, ?, ?, ?, 0)",
                ("prueba", "Paltas", "1.5 kg", "Feria (Frutas y Verduras)")
            )
            cursor.execute("COMMIT")
        
        # Guardar timestamp de último reset
        guardar_variable("prueba", "ultimo_reset_prueba", str(datetime.now().timestamp()))
        st.cache_data.clear()
    except Exception:
        pass

def verificar_y_resetear_prueba():
    try:
        last_reset_str = obtener_variable("prueba", "ultimo_reset_prueba", "0")
        try:
            last_reset = float(last_reset_str)
        except ValueError:
            last_reset = 0.0
            
        now = datetime.now().timestamp()
        # 12 horas = 43200 segundos
        if now - last_reset >= 43200:
            resetear_usuario_prueba()
    except Exception as e:
        print(f"Error al verificar reset de prueba: {e}")

# --- Historial de Precios y Detalles de Compras ---

def actualizar_detalles_item_compra(usuario, id_item, brand, price):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE compras SET marca = ?, precio = ? WHERE id = ? AND usuario = ?",
                (brand, float(price), id_item, usuario)
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al actualizar detalles de item de compra: {e}")
        return False

def registrar_historial_precio(usuario, producto, marca, precio):
    try:
        if precio <= 0:
            return False
        fecha_str = datetime.now().strftime('%Y-%m-%d')
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO historial_precios (usuario, producto, marca, precio, fecha) VALUES (?, ?, ?, ?, ?)",
                (usuario, producto, marca, float(precio), fecha_str)
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al registrar historial de precio: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def obtener_historial_precios(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM historial_precios WHERE usuario = ? ORDER BY fecha DESC, id DESC", (usuario,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Error al obtener historial de precios: {e}")
        return []





# --- Módulo de Control de Usuarios y Estimados Históricos ---

def migrar_usuarios_predeterminados():
    default_users = {
        "dante": "7ceea3fb1436a08322ad02d7ad8b114c3353cd1538aa9adfae72d6661171e933",
        "jason": "baf95ccba46c92b34eef67a447ee608626f0a29a07aa9a558544bc06b0fbe255",
        "prueba": "655e786674d9d3e77bc05ed1de37b4b6bc89f788829f9f3c679e7687b410c89b",
        "caro": "390589403930e2e615cee5b15d725354adab2c487c8d0e261f8c6071342e29c2"
    }
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT usuario, password_hash FROM usuarios")
            existing_users = {row[0]: row[1] for row in cursor.fetchall()}
            
            needs_commit = False
            for user, p_hash in default_users.items():
                if user not in existing_users:
                    cursor.execute(
                        "INSERT INTO usuarios (usuario, password_hash) VALUES (?, ?)",
                        (user, p_hash)
                    )
                    needs_commit = True
                elif existing_users[user] != p_hash:
                    cursor.execute(
                        "UPDATE usuarios SET password_hash = ? WHERE usuario = ?",
                        (p_hash, user)
                    )
                    needs_commit = True
            
            if needs_commit:
                conn.commit()
    except Exception:
        pass

def registrar_usuario(usuario, password_hash):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM usuarios WHERE usuario = ?", (usuario,))
            if cursor.fetchone():
                return False
            cursor.execute(
                "INSERT INTO usuarios (usuario, password_hash) VALUES (?, ?)",
                (usuario, password_hash)
            )
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al registrar usuario: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def obtener_hash_usuario(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM usuarios WHERE usuario = ?", (usuario,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None
    except sqlite3.Error as e:
        print(f"Error al obtener hash de usuario: {e}")
        return None

@st.cache_data(ttl=120, show_spinner=False)
def obtener_usuarios():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT usuario FROM usuarios ORDER BY usuario ASC")
            return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Error al obtener usuarios: {e}")
        return []

def eliminar_usuario(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            tables = ["finanzas", "compras", "calendario", "estado_jrpg", "misiones", "metas_ahorro", "items_rapidos", "historial_precios"]
            for table in tables:
                cursor.execute(f"DELETE FROM {table} WHERE usuario = ?", (usuario,))
            cursor.execute("DELETE FROM usuarios WHERE usuario = ?", (usuario,))
            conn.commit()
            st.cache_data.clear()
            return True
    except sqlite3.Error as e:
        print(f"Error al eliminar usuario: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def obtener_mejor_precio_historico(usuario, producto):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT precio, marca, establecimiento, fecha FROM historial_precios WHERE usuario = ? AND LOWER(producto) = LOWER(?) ORDER BY precio ASC LIMIT 1",
                (usuario, producto.strip())
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            
            cursor.execute(
                "SELECT precio, marca, establecimiento, fecha FROM historial_precios WHERE usuario = ? AND (LOWER(producto) LIKE ? OR ? LIKE '%' || LOWER(producto) || '%') ORDER BY precio ASC LIMIT 1",
                (usuario, f"%{producto.strip().lower()}%", producto.strip().lower())
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except sqlite3.Error as e:
        print(f"Error al obtener mejor precio histórico: {e}")
        return None

@st.cache_data(ttl=120, show_spinner=False)
def obtener_email_usuario(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM usuarios WHERE usuario = ?", (usuario,))
            row = cursor.fetchone()
            if row:
                return row[0] or ""
            return ""
    except Exception as e:
        print(f"Error al obtener email de usuario: {e}")
        return ""

def actualizar_email_usuario(usuario, email):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET email = ? WHERE usuario = ?", (email, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except Exception as e:
        print(f"Error al actualizar email de usuario: {e}")
        return False

def actualizar_password_usuario(usuario, password_hash):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET password_hash = ? WHERE usuario = ?", (password_hash, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except Exception as e:
        print(f"Error al actualizar contraseña de usuario: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def obtener_eventos_proximos(usuario, dias=3):
    from datetime import date, timedelta
    try:
        hoy = date.today()
        fecha_inicio_str = hoy.strftime('%Y-%m-%d')
        fecha_fin = hoy + timedelta(days=dias)
        fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM calendario WHERE usuario = ? AND fecha >= ? AND fecha <= ? ORDER BY fecha ASC, evento ASC",
                (usuario, fecha_inicio_str, fecha_fin_str)
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error al obtener eventos próximos: {e}")
        return []

@st.cache_data(ttl=120, show_spinner=False)
def obtener_ultimo_correo_resumen(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ultimo_correo_resumen FROM usuarios WHERE usuario = ?", (usuario,))
            row = cursor.fetchone()
            if row:
                return row[0] or ""
            return ""
    except Exception as e:
        print(f"Error al obtener ultimo correo resumen: {e}")
        return ""

def actualizar_fecha_ultimo_correo(usuario, fecha_str):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET ultimo_correo_resumen = ? WHERE usuario = ?", (fecha_str, usuario))
            conn.commit()
            st.cache_data.clear()
            return True
    except Exception as e:
        print(f"Error al actualizar fecha del ultimo correo: {e}")
        return False

def establecer_presupuesto(usuario, categoria, monto_limite):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM presupuestos WHERE usuario = ? AND categoria = ?", (usuario, categoria))
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE presupuestos SET monto_limite = ? WHERE usuario = ? AND categoria = ?",
                    (float(monto_limite), usuario, categoria)
                )
            else:
                cursor.execute(
                    "INSERT INTO presupuestos (usuario, categoria, monto_limite) VALUES (?, ?, ?)",
                    (usuario, categoria, float(monto_limite))
                )
            conn.commit()
            st.cache_data.clear()
            return True
    except Exception as e:
        print(f"Error al establecer presupuesto: {e}")
        return False

@st.cache_data(ttl=120, show_spinner=False)
def obtener_presupuestos(usuario):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT categoria, monto_limite FROM presupuestos WHERE usuario = ?", (usuario,))
            rows = cursor.fetchall()
            return {row[0]: float(row[1]) for row in rows}
    except Exception as e:
        print(f"Error al obtener presupuestos: {e}")
        return {}