import streamlit as st
import pandas as pd
from datetime import datetime, date
import db
import google.generativeai as genai
import textwrap
import os
import json
from PIL import Image

AI_MODEL_CANDIDATES = ["gemini-1.5-flash", "gemini-2.5-flash"]

# Configuración inicial de la página (¡debe ir antes de cualquier comando st!)
st.set_page_config(
    page_title="Tu Hogar",
    page_icon="icono.png",
    layout="wide",
    initial_sidebar_state="expanded"
)
# Importaciones resilientes para evitar caídas por dependencias faltantes
try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False
try:
    from io import BytesIO
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
# Inicializar Base de Datos SQLite
db.init_db()
# Lista global de llaves de misiones
quest_keys = [
    "q_ordenar_pieza", "q_limpiar_banio", "q_limpiar_living", 
    "q_limpiar_cocina", "q_lavar_loza", "q_botar_basura", 
    "q_lavar_ropa", "q_guardar_ropa", "q_preparar_almuerzo", 
    "q_limpiar_pieza_chica"
]

def render_month_calendar(year, month, events, username):
    import calendar
    from datetime import date, datetime
    
    first_weekday, num_days = calendar.monthrange(year, month)
    
    # Feriados chilenos
    holidays = {
        (1, 1): "Año Nuevo",
        (5, 1): "Día del Trabajo",
        (5, 21): "Día de las Glorias Navales",
        (7, 16): "Día de la Virgen del Carmen",
        (8, 15): "Asunción de la Virgen",
        (9, 18): "Fiestas Patrias",
        (9, 19): "Glorias del Ejército",
        (10, 12): "Encuentro de Dos Mundos",
        (11, 1): "Día de Todos los Santos",
        (12, 8): "Inmaculada Concepción",
        (12, 25): "Navidad"
    }
    if year == 2026:
        holidays[(4, 3)] = "Viernes Santo"
        holidays[(4, 4)] = "Sábado Santo"
        holidays[(6, 21)] = "Día de Pueblos Indígenas"
        holidays[(6, 29)] = "San Pedro y San Pablo"
        holidays[(10, 31)] = "Día de Iglesias Evangélicas"
    elif year == 2025:
        holidays[(4, 18)] = "Viernes Santo"
        holidays[(4, 19)] = "Sábado Santo"
        holidays[(6, 20)] = "Día de Pueblos Indígenas"
        holidays[(6, 27)] = "San Pedro y San Pablo"
        holidays[(10, 31)] = "Día de Iglesias Evangélicas"
        
    events_by_day = {}
    for ev in events:
        try:
            ev_date = datetime.strptime(ev["fecha"], "%Y-%m-%d").date()
            if ev_date.year == year and ev_date.month == month:
                events_by_day.setdefault(ev_date.day, []).append(ev)
        except Exception:
            continue
            
    headers = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    html = []
    
    html.append("""
    <style>
    .cal-container {
        font-family: 'Outfit', 'Inter', sans-serif;
        background: #0b0f19;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 15px;
        color: #f3f4f6;
        margin-top: 10px;
    }
    .cal-header-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 5px;
        text-align: center;
        font-weight: bold;
        font-size: 0.85rem;
        color: #818cf8;
        margin-bottom: 10px;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 8px;
    }
    .cal-days-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 6px;
    }
    .cal-day-cell {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 8px;
        min-height: 90px;
        padding: 6px;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        position: relative;
        transition: all 0.2s ease;
    }
    .cal-day-cell:hover {
        background: #1f2937;
        border-color: #374151;
    }
    .cal-day-number {
        font-size: 0.85rem;
        font-weight: 700;
        color: #9ca3af;
    }
    .cal-day-today {
        border: 2px solid #6366f1 !important;
        background: rgba(99, 102, 241, 0.08);
    }
    .cal-day-today .cal-day-number {
        color: #818cf8;
    }
    .cal-day-holiday {
        background: rgba(239, 68, 68, 0.05);
        border-color: rgba(239, 68, 68, 0.3);
    }
    .cal-day-holiday .cal-day-number {
        color: #fca5a5;
    }
    .cal-holiday-label {
        font-size: 0.65rem;
        color: #f87171;
        font-weight: 600;
        margin-top: 2px;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .cal-events-list {
        display: flex;
        flex-direction: column;
        gap: 2px;
        overflow-y: auto;
        max-height: 55px;
        margin-top: 4px;
    }
    .cal-event-badge {
        font-size: 0.65rem;
        padding: 2px 4px;
        border-radius: 4px;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        display: block;
    }
    .badge-venc-pending {
        background: rgba(239, 68, 68, 0.15);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.2);
    }
    .badge-venc-done {
        background: rgba(16, 185, 129, 0.15);
        color: #a7f3d0;
        border: 1px solid rgba(16, 185, 129, 0.2);
        text-decoration: line-through;
    }
    .badge-imp-event {
        background: rgba(168, 85, 247, 0.15);
        color: #e9d5ff;
        border: 1px solid rgba(168, 85, 247, 0.2);
    }
    .cal-empty-cell {
        background: transparent;
        border: 1px dashed #1f2937;
        border-radius: 8px;
        min-height: 90px;
    }
    </style>
    """)
    
    html.append("<div class='cal-container'>")
    html.append("<div class='cal-header-grid'>")
    for h in headers:
        html.append(f"<div>{h}</div>")
    html.append("</div>")
    
    html.append("<div class='cal-days-grid'>")
    for _ in range(first_weekday):
        html.append("<div class='cal-empty-cell'></div>")
        
    today = date.today()
    for d in range(1, num_days + 1):
        cell_date = date(year, month, d)
        is_today = (cell_date == today)
        is_holiday = (month, d) in holidays
        holiday_name = holidays.get((month, d), "")
        
        classes = ["cal-day-cell"]
        if is_today:
            classes.append("cal-day-today")
        if is_holiday:
            classes.append("cal-day-holiday")
            
        html.append(f"<div class='{' '.join(classes)}'>")
        html.append("<div style='display: flex; justify-content: space-between; align-items: center;'>")
        html.append(f"<span class='cal-day-number'>{d}</span>")
        if is_today:
            html.append("<span style='font-size: 0.6rem; color: #818cf8; font-weight: bold;'>HOY</span>")
        html.append("</div>")
        
        if is_holiday:
            html.append(f"<div class='cal-holiday-label' title='{holiday_name}'>🇨🇱 {holiday_name}</div>")
            
        day_events = events_by_day.get(d, [])
        if day_events:
            html.append("<div class='cal-events-list'>")
            for ev in day_events:
                if ev["tipo"] == "Vencimiento":
                    badge_class = "badge-venc-done" if ev["completado"] == 1 else "badge-venc-pending"
                else:
                    badge_class = "badge-imp-event"
                html.append(f"<span class='cal-event-badge {badge_class}' title='{ev['evento']}'>{ev['evento']}</span>")
            html.append("</div>")
            
        html.append("</div>")
        
    html.append("</div>")
    html.append("</div>")
    
    return "".join(html)

def obtener_etapa_hogar(lvl):
    """
    Retorna el emoji y el título de la etapa de evolución del hogar según el nivel.
    """
    if lvl <= 2:
        return "🛖", "El Campamento Base"
    elif lvl <= 5:
        return "🏡", "La Casita Acogedora"
    elif lvl <= 10:
        return "🏛️", "La Residencia Familiar"
    else:
        return "🏰", "El Castillo de la Familia"

def verify_password(plain_password, hashed_password):
    import hashlib
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

def enviar_correo(destinatario, asunto, mensaje):
    import smtplib
    from email.mime.text import MIMEText
    import streamlit as st
    
    try:
        email_user = st.secrets.get("EMAIL_USER")
        if not email_user:
            email_user = st.secrets.get("api", {}).get("EMAIL_USER")
            
        email_pass = st.secrets.get("EMAIL_PASS")
        if not email_pass:
            email_pass = st.secrets.get("api", {}).get("EMAIL_PASS")
            
        if not email_user or not email_pass:
            st.error("Configuración de correo no encontrada en Secrets (EMAIL_USER / EMAIL_PASS).")
            return False
            
        # Limpiar espacios en la contraseña de Google
        email_pass = email_pass.replace(" ", "").strip()
        
        msg = MIMEText(mensaje, "html", "utf-8")
        msg["Subject"] = asunto
        msg["From"] = email_user
        msg["To"] = destinatario
        
        # Conexión SMTP estándar (Gmail TLS puerto 587)
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(email_user, email_pass)
        server.sendmail(email_user, [destinatario], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error SMTP detallado: {e}")
        st.error(f"No se pudo enviar el correo de notificación. Detalle: {str(e)}")
        return False

def enviar_resumen_diario(usuario):
    import db
    from datetime import date, datetime
    
    email = db.obtener_email_usuario(usuario)
    if not email or not email.strip():
        return
        
    ultimo = db.obtener_ultimo_correo_resumen(usuario)
    hoy_str = date.today().isoformat()
    if ultimo == hoy_str:
        return
        
    eventos = db.obtener_eventos_proximos(usuario, dias=3)
    if not eventos:
        return
        
    # Redactar correo amigable en formato HTML
    nombre_display = usuario.replace('_', ' ').title()
    filas_html = []
    for ev in eventos:
        completado_str = "✅ Realizado" if ev["completado"] == 1 else "⏳ Pendiente"
        try:
            fecha_obj = datetime.strptime(ev["fecha"], "%Y-%m-%d").date()
            fecha_display = fecha_obj.strftime("%d/%m/%Y")
        except Exception:
            fecha_display = ev["fecha"]
        
        filas_html.append(f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 12px; font-weight: 600; color: #1e293b;">{ev['evento']}</td>
                <td style="padding: 12px; color: #475569;">{fecha_display}</td>
                <td style="padding: 12px; color: #64748b;">
                    <span style="background-color: #f1f5f9; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 500;">
                        {ev['tipo']}
                    </span>
                </td>
                <td style="padding: 12px; text-align: center; color: #475569;">{completado_str}</td>
            </tr>
        """)
        
    tabla_eventos = "\n".join(filas_html)
    
    mensaje_html = f"""
    <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; background-color: #f8fafc; padding: 20px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                <div style="background: linear-gradient(135deg, #6366f1, #ec4899); padding: 30px; text-align: center; color: #ffffff;">
                    <h2 style="margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.5px;">🎯 Agenda de Eventos Próximos</h2>
                    <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">Tu resumen diario de Dante Hogar</p>
                </div>
                <div style="padding: 30px;">
                    <p style="font-size: 16px; line-height: 1.5; margin-top: 0;">¡Hola, <strong>{nombre_display}</strong>!</p>
                    <p style="font-size: 16px; line-height: 1.5; color: #475569;">Aquí tienes la lista de los próximos eventos y vencimientos programados para los siguientes 3 días:</p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; text-align: left;">
                        <thead>
                            <tr style="background-color: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                                <th style="padding: 12px; color: #475569; font-weight: 600;">Evento</th>
                                <th style="padding: 12px; color: #475569; font-weight: 600;">Fecha</th>
                                <th style="padding: 12px; color: #475569; font-weight: 600;">Tipo</th>
                                <th style="padding: 12px; color: #475569; font-weight: 600; text-align: center;">Estado</th>
                            </tr>
                        </thead>
                        <tbody>
                            {tabla_eventos}
                        </tbody>
                    </table>
                    
                    <p style="font-size: 13px; line-height: 1.5; color: #94a3b8; margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 20px; text-align: center;">
                        Este correo electrónico se generó automáticamente al iniciar sesión en tu cuenta de Dante Hogar.
                    </p>
                </div>
            </div>
        </body>
    </html>
    """
    
    asunto = "🎯 Recordatorio: Próximos eventos en Dante Hogar"
    exito = enviar_correo(email, asunto, mensaje_html)
    if exito:
        db.actualizar_fecha_ultimo_correo(usuario, hoy_str)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    # Inyección básica de estilos para la tarjeta de login
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            font-family: 'Outfit', sans-serif !important;
        }
        [data-testid="stAppViewContainer"] {
            background-color: #0b0f19;
        }
        .stButton>button {
            background: linear-gradient(135deg, #4f46e5, #3730a3) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 10px 20px !important;
            font-weight: 600 !important;
        }
        .stButton>button:hover {
            background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1.2, 1.6, 1.2])
    with col_l2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col_img1, col_img2, col_img3 = st.columns([1, 1, 1])
        with col_img2:
            st.image("icono.png", width=95)
        st.markdown("<h2 style='text-align: center; color: white; font-weight: 800; margin-top: -10px;'>Tu Hogar</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #9ca3af; font-size: 0.95rem; margin-top: -10px; margin-bottom: 20px;'>Centro de Mando Familiar</p>", unsafe_allow_html=True)
        
        tab_login, tab_register = st.tabs(["🔑 Iniciar Sesión", "📝 Crear Cuenta"])
        
        with tab_login:
            with st.form("login_form"):
                st.markdown("<h4 style='color: #818cf8; text-align: center; margin-bottom: 10px;'>Ingresar al Sistema</h4>", unsafe_allow_html=True)
                username_input = st.text_input("Usuario", placeholder="Ingresa tu usuario").strip().lower()
                password_input = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
                btn_login = st.form_submit_button("Ingresar al Sistema", use_container_width=True)
                
                if btn_login:
                    if not username_input or not password_input:
                        st.error("Por favor completa todos los campos.")
                    else:
                        stored_hash = db.obtener_hash_usuario(username_input)
                        if stored_hash and verify_password(password_input, stored_hash):
                            st.session_state.authenticated = True
                            st.session_state.username = username_input
                            st.toast(f"¡Bienvenido de vuelta, {username_input.replace('_', ' ').title()}!", icon="🔑")
                            try:
                                enviar_resumen_diario(username_input)
                            except Exception:
                                pass
                            st.rerun()
                        else:
                            st.error("Usuario o contraseña incorrectos.")
                            
        with tab_register:
            with st.form("register_form"):
                st.markdown("<h4 style='color: #818cf8; text-align: center; margin-bottom: 10px;'>Crear Nueva Cuenta</h4>", unsafe_allow_html=True)
                new_username = st.text_input("Nombre de Usuario", placeholder="Ej: caro").strip().lower()
                new_password = st.text_input("Contraseña", type="password", placeholder="Mínimo 4 caracteres")
                confirm_password = st.text_input("Confirmar Contraseña", type="password", placeholder="Repite tu contraseña")
                email_input = st.text_input("Correo Electrónico para Notificaciones", key="reg_email")
                btn_register = st.form_submit_button("Crear Cuenta e Ingresar", use_container_width=True)
                
                if btn_register:
                    import re
                    import hashlib
                    if not new_username or not new_password or not confirm_password or not email_input:
                        st.error("Por favor completa todos los campos.")
                    elif not re.match(r"^[a-z0-9_]{3,15}$", new_username):
                        st.error("El usuario debe tener entre 3 y 15 caracteres (solo letras minúsculas, números o guiones bajos).")
                    elif not re.match(r"[^@]+@[^@]+\.[^@]+", email_input.strip()):
                        st.error("Por favor ingresa un correo electrónico válido.")
                    elif new_password != confirm_password:
                        st.error("Las contraseñas no coinciden.")
                    elif len(new_password) < 4:
                        st.error("La contraseña debe tener al menos 4 caracteres.")
                    else:
                        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
                        exito = db.registrar_usuario(new_username, new_hash)
                        if exito:
                            db.actualizar_email_usuario(new_username, email_input.strip())
                            st.session_state.authenticated = True
                            st.session_state.username = new_username
                            st.toast(f"¡Cuenta creada con éxito! Bienvenido, {new_username.title()}.", icon="✨")
                            try:
                                enviar_resumen_diario(new_username)
                            except Exception:
                                pass
                            st.rerun()
                        else:
                            st.error("El nombre de usuario ya está registrado.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔑 ¿Olvidaste tu contraseña?"):
            st.markdown("<p style='font-size: 0.9rem; color: #9ca3af;'>Ingresa tu usuario y el correo registrado para recibir una nueva contraseña temporal.</p>", unsafe_allow_html=True)
            with st.form("form_forgot_password", clear_on_submit=True):
                forgot_user = st.text_input("Usuario", placeholder="Ingresa tu usuario").strip().lower()
                forgot_email = st.text_input("Correo Registrado", placeholder="ejemplo@correo.com").strip()
                btn_reset_pass = st.form_submit_button("Restablecer Contraseña", use_container_width=True)
                if btn_reset_pass:
                    if not forgot_user or not forgot_email:
                        st.error("Por favor completa todos los campos.")
                    else:
                        stored_email = db.obtener_email_usuario(forgot_user)
                        if stored_email and stored_email.lower() == forgot_email.lower():
                            import random
                            import string
                            import hashlib
                            
                            chars = string.ascii_letters + string.digits
                            temp_pass = "".join(random.choice(chars) for _ in range(8))
                            temp_hash = hashlib.sha256(temp_pass.encode()).hexdigest()
                            
                            if db.actualizar_password_usuario(forgot_user, temp_hash):
                                asunto = "🔑 Restablecimiento de Contraseña - Dante Hogar"
                                mensaje = f"""
                                <h3>Restablecimiento de Contraseña</h3>
                                <p>Hola,</p>
                                <p>Hemos recibido una solicitud para restablecer la contraseña de tu cuenta <strong>{forgot_user.title()}</strong> en Dante Hogar.</p>
                                <p>Tu nueva contraseña temporal es: <strong style='font-size: 1.2rem; color: #6366f1; background: #f3f4f6; padding: 4px 8px; border-radius: 4px;'>{temp_pass}</strong></p>
                                <p>Te recomendamos iniciar sesión con esta contraseña y cambiarla de inmediato desde tu perfil (⚙️ Mi Perfil) en la barra lateral.</p>
                                <br>
                                <p>Saludos,<br>Dante Hogar &copy; 2026</p>
                                """
                                if enviar_correo(forgot_email, asunto, mensaje):
                                    st.success(f"Se ha enviado una nueva contraseña temporal al correo {forgot_email}. Revisa tu bandeja de entrada.")
                                else:
                                    st.error("No se pudo enviar el correo de notificación, pero la contraseña se actualizó en el sistema. Contacta al administrador.")
                            else:
                                st.error("Error al actualizar la contraseña temporal en el sistema.")
                        else:
                            st.error("El usuario y/o correo electrónico no coinciden con nuestros registros.")

        st.markdown("<p style='text-align: center; color: #6b7280; font-size: 0.85rem; margin-top: 20px;'>Tu Hogar &copy; 2026</p>", unsafe_allow_html=True)
    st.stop()
# Si está autenticado, cargar las variables del usuario
username = st.session_state.username
username_display = username.replace('_', ' ').title()
username_upper = username.replace('_', ' ').upper()
# Inicializar Variables de Sesión para Gamificación y Metas desde la Base de Datos para el usuario actual
if st.session_state.get("last_loaded_user") != username:
    if username == "prueba":
        db.verificar_y_resetear_prueba()
    st.session_state.xp = int(db.obtener_variable(username, "xp", 0))
    st.session_state.lvl = int(db.obtener_variable(username, "lvl", 1))
    st.session_state.ahorro_vacaciones = int(db.obtener_variable(username, "ahorro_vacaciones", 1300000))
    st.session_state.ahorro_emergencia = int(db.obtener_variable(username, "ahorro_emergencia", 2000000))
    for q_key in quest_keys:
        st.session_state[q_key] = db.obtener_variable(username, q_key, "False") == "True"
    # Cargar la clave API del usuario desde la base de datos
    st.session_state["gemini_api_key"] = db.obtener_variable(username, "gemini_api_key", "")
    # Si no tiene clave en la base de datos, intentar cargar de secrets de Streamlit
    if not st.session_state["gemini_api_key"]:
        if "gemini_api_key" in st.secrets:
            st.session_state["gemini_api_key"] = st.secrets["gemini_api_key"]
    st.session_state.last_loaded_user = username

def render_html(html_str):
    # Eliminar toda la sangría de cada línea y juntarlas para evitar interpretaciones erróneas del Markdown
    clean_html = "".join(line.strip() for line in html_str.split("\n"))
    st.markdown(clean_html, unsafe_allow_html=True)

def consultar_gemini(api_key, system_instruction, contents, tools=None):
    genai.configure(api_key=api_key)
    last_err = None
    for candidate in AI_MODEL_CANDIDATES:
        try:
            model = genai.GenerativeModel(
                model_name=candidate,
                system_instruction=system_instruction,
                tools=tools
            )
            response = model.generate_content(contents)
            return response.text
        except Exception as e:
            last_err = e
            continue
    # Intentar listar dinámicamente modelos si los candidatos fallan
    try:
        listado_modelos = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                nombre_simple = m.name.replace("models/", "")
                listado_modelos.append(nombre_simple)
        for model_name in listado_modelos:
            if model_name in AI_MODEL_CANDIDATES:
                continue
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=system_instruction,
                    tools=tools
                )
                response = model.generate_content(contents)
                return response.text
            except Exception as e:
                last_err = e
                continue
    except Exception:
        pass
    if last_err:
        raise last_err
    raise Exception("Los servidores de IA están saturados en este momento. Por favor, intenta de nuevo más tarde.")

def format_clp(val):
    """
    Formatea un valor numérico a pesos chilenos sin decimales y con puntos como separador de miles.
    Ejemplo: 1500000 -> $1.500.000
    """
    try:
        return f"${int(round(float(val))):,}".replace(",", ".")
    except (ValueError, TypeError):
        return f"${val}"
# Inyección de Estilos CSS Premium para UI/UX

def inject_custom_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        /* Tipografía y Fondo Global */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            font-family: 'Outfit', sans-serif !important;
        }
        [data-testid="stAppViewContainer"] {
            background-color: #0b0f19;
        }
        /* Personalización del Menú Lateral (Sidebar) */
        [data-testid="stSidebar"] {
            background-color: #0f172a !important;
            border-right: 1px solid #1e293b;
        }
        /* Tarjetas de Contenedores Premium */
        .premium-card {
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            transition: all 0.3s ease;
        }
        .premium-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            border-color: #6366f1;
        }
        /* Tarjetas Métricas Financieras */
        .metric-card-custom {
            padding: 24px;
            border-radius: 16px;
            color: white;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            margin-bottom: 20px;
        }
        .m-balance {
            background: linear-gradient(135deg, #4f46e5, #3730a3);
            border-left: 6px solid #818cf8;
        }
        .m-income {
            background: linear-gradient(135deg, #059669, #064e3b);
            border-left: 6px solid #34d399;
        }
        .m-expense {
            background: linear-gradient(135deg, #dc2626, #7f1d1d);
            border-left: 6px solid #f87171;
        }
        .metric-card-custom .label {
            font-size: 0.9rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            opacity: 0.85;
            margin-bottom: 8px;
        }
        .metric-card-custom .value {
            font-size: 2.2rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .metric-card-custom .footer-info {
            font-size: 0.8rem;
            opacity: 0.7;
            margin-top: 10px;
        }
        /* Título Principal */
        .main-title {
            background: linear-gradient(to right, #818cf8, #c084fc, #e879f9);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5rem;
            font-weight: 800;
            margin-bottom: 8px;
        }
        /* Cabeceras de Sección */
        .section-header {
            color: #f3f4f6;
            font-size: 1.4rem;
            font-weight: 600;
            margin-bottom: 18px;
            border-bottom: 2px solid #1e293b;
            padding-bottom: 8px;
        }
        /* Estilos de Filas de Transacciones */
        .tx-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 18px;
            background-color: #111827;
            border: 1px solid #1e293b;
            border-radius: 12px;
            margin-bottom: 10px;
            transition: all 0.2s ease;
        }
        .tx-row:hover {
            border-color: #4b5563;
            background-color: #1f2937;
        }
        .tx-date {
            color: #9ca3af;
            font-size: 0.85rem;
            min-width: 90px;
        }
        .tx-info {
            flex-grow: 1;
            margin-left: 12px;
        }
        .tx-title {
            font-weight: 600;
            color: #f3f4f6;
            font-size: 0.95rem;
        }
        .tx-category {
            font-size: 0.75rem;
            background-color: #374151;
            color: #d1d5db;
            padding: 2px 10px;
            border-radius: 12px;
            margin-left: 8px;
            display: inline-block;
            font-weight: 500;
        }
        .tx-desc {
            color: #9ca3af;
            font-size: 0.85rem;
            margin-top: 3px;
        }
        .tx-amount {
            font-weight: 700;
            font-size: 1.1rem;
            margin-right: 10px;
        }
        .amount-ingreso {
            color: #10b981;
        }
        .amount-gasto {
            color: #ef4444;
        }
        /* Etiquetas del Calendario */
        .badge {
            font-size: 0.75rem;
            padding: 3px 10px;
            border-radius: 8px;
            font-weight: 600;
            display: inline-block;
        }
        .badge-importante {
            background-color: rgba(99, 102, 241, 0.2);
            color: #a5b4fc;
            border: 1px solid rgba(99, 102, 241, 0.4);
        }
        .badge-vencimiento {
            background-color: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }
        /* Ajustar espaciado de Streamlit */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }
        </style>
    """, unsafe_allow_html=True)
# Ejecutar la inyección de CSS
inject_custom_css()
# Menú Lateral / Configuración
with st.sidebar:
    col_logo1, col_logo2, col_logo3 = st.columns([1, 1.5, 1])
    with col_logo2:
        st.image("icono.png", width=90)
    st.markdown(f"<h2 style='text-align: center; margin-top: -10px;'>{username_display} Hogar</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #9ca3af; font-size: 0.9rem;'>Centro de Mando Familiar</p>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align: center; margin-top: -10px; margin-bottom: 10px;'><span class='badge badge-importante' style='font-size: 0.9rem; padding: 4px 12px;'>👤 {username_display}</span></div>", unsafe_allow_html=True)
    # --- Persistent Notification Bell ---
    try:
        eventos_globales = db.obtener_eventos(username)
        avisos_criticos = []
        hoy = date.today()
        for ev in eventos_globales:
            if ev["tipo"] == "Vencimiento" and ev["completado"] == 0:
                fecha_ev = datetime.strptime(ev["fecha"], "%Y-%m-%d").date()
                dif = (fecha_ev - hoy).days
                if dif < 0:
                    avisos_criticos.append(f"🔴 **Atrasado**: '{ev['evento']}' (era el {fecha_ev.strftime('%d/%m/%Y')})")
                elif dif == 0:
                    avisos_criticos.append(f"🟠 **Vence Hoy**: '{ev['evento']}'")
                elif dif <= 3:
                    avisos_criticos.append(f"🟡 **Vence en {dif} días**: '{ev['evento']}' ({fecha_ev.strftime('%d/%m/%Y')})")
    except Exception:
        avisos_criticos = []
        
    bell_label = f"🔴 🔔 Notificaciones ({len(avisos_criticos)})" if avisos_criticos else "🔔 Notificaciones (0)"
    with st.popover(bell_label, use_container_width=True):
        st.markdown("##### 🔔 Alertas de Vencimiento")
        if avisos_criticos:
            for aviso in avisos_criticos:
                st.markdown(aviso)
        else:
            st.success("¡No tienes vencimientos pendientes! 🎉")
    st.markdown("<hr style='border-color: #1e293b; margin: 15px 0;' />", unsafe_allow_html=True)
    # Navegación interactiva por st.radio
    menu_options = ["📊 Finanzas del Hogar", "🛒 Lista de Compras", "🛍️ Asesor de Compras IA", "👨‍🍳 El Chef del Hogar", "🗓️ Calendario Familiar", "⚔️ Misiones del Hogar", "🤖 Asesor del Hogar IA", "⚙️ Mi Perfil"]
    if username == "dante":
        menu_options.append("🔑 Control de Usuarios")
    
    menu = st.radio(
        "Módulos del Sistema",
        menu_options,
        key="nav_menu"
    )
    st.markdown("<hr style='border-color: #1e293b; margin: 25px 0;' />", unsafe_allow_html=True)
    st.markdown("### 🔑 Conexión IA")
    api_key_input = st.text_input(
        "Gemini API Key",
        type="password",
        help="Clave de API segura de Google AI Studio.",
        value=st.session_state.get("gemini_api_key", "")
    )
    if api_key_input:
        if api_key_input != st.session_state.get("gemini_api_key", ""):
            st.session_state["gemini_api_key"] = api_key_input
            if db.guardar_variable(username, "gemini_api_key", api_key_input):
                st.toast("API Key guardada de forma segura para tu usuario.", icon="💾")
            else:
                st.error("Error al guardar la API Key en la base de datos.")
        st.success("API Key activa para tu sesión.")
    else:
        if st.session_state.get("gemini_api_key", ""):
            st.session_state["gemini_api_key"] = ""
            db.guardar_variable(username, "gemini_api_key", "")
            st.warning("API Key de tu usuario eliminada.")
        st.info("Ingresa tu API Key para activar el Asesor IA.")
    with st.expander("💡 ¿Cómo obtener tu API Key gratis?"):
        st.markdown("""
        1. Ve a [Google AI Studio](https://aistudio.google.com/).
        2. Inicia sesión con tu cuenta de Google.
        3. Haz clic en **"Get API key"** (Obtener clave).
        4. Haz clic en **"Create API key"** (Crear clave).
        5. Copia la clave (empieza con `AIzaSy...`) y pégala aquí arriba.
        """, unsafe_allow_html=True)
    if st.session_state.get("gemini_api_key", ""):
        st.markdown("---")
        usar_busqueda = st.checkbox(
            "🔍 Buscar en Google (Asesor)",
            value=db.obtener_variable(username, "usar_busqueda", "False") == "True",
            help="Permite al Asesor IA buscar en internet en tiempo real para recomendarte productos y precios reales de tiendas en Chile. NOTA: Requiere que tu API Key de Gemini tenga habilitada la facturación (billing) en Google AI Studio, de lo contrario dará error de cuota (exceeded quota)."
        )
        db.guardar_variable(username, "usar_busqueda", "True" if usar_busqueda else "False")
    else:
        usar_busqueda = False
    # Progreso de Nuestro Hogar en la Barra Lateral
    st.markdown("<hr style='border-color: #1e293b; margin: 20px 0;' />", unsafe_allow_html=True)
    st.markdown("### 🏡 Progreso de Nuestro Hogar")
    # Renderizar el Estado del Hogar (Etapa, LVL y XP)
    emoji, titulo = obtener_etapa_hogar(st.session_state.lvl)
    sidebar_progreso = textwrap.dedent(f"""
        <div style="text-align: center; padding: 15px; margin-bottom: 12px; border-radius: 12px; background: linear-gradient(135deg, rgba(251, 146, 60, 0.15), rgba(236, 72, 153, 0.15)); border: 1px solid rgba(251, 146, 60, 0.3); box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05); font-family: sans-serif;">
            <div style="font-size: 3.5rem; margin-bottom: 5px;">{emoji}</div>
            <div style="font-size: 1.1rem; font-weight: bold; color: #f97316; margin-bottom: 2px;">{titulo}</div>
            <div style="font-size: 0.85rem; color: #4b5563; margin-bottom: 10px; font-weight: 600;">Nivel {st.session_state.lvl} • {st.session_state.xp}/100 XP</div>
            <div style="background: rgba(226, 232, 240, 0.2); border-radius: 10px; height: 10px; overflow: hidden; border: 1px solid rgba(203, 213, 225, 0.3);">
                <div style="background: linear-gradient(90deg, #f97316, #ec4899); height: 100%; width: {st.session_state.xp}%; border-radius: 10px;"></div>
            </div>
        </div>
    """)
    render_html(sidebar_progreso)
    st.markdown("<p style='font-size: 0.8rem; color: #9ca3af; text-align: center; margin: 0;'>Completa las <strong>⚔️ Misiones del Hogar</strong> para hacer evolucionar tu casa.</p>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color: #1e293b; margin: 20px 0;' />", unsafe_allow_html=True)
    if st.button("🚪 Cerrar Sesión", use_container_width=True, key="btn_logout"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.last_loaded_user = None
        for k in ["xp", "lvl", "ahorro_vacaciones", "ahorro_emergencia"] + quest_keys:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

# --- RENDERING DE MÓDULOS ---
# Título de la sección principal
st.markdown(f"<div class='main-title'>{menu}</div>", unsafe_allow_html=True)
st.write("Gestión del hogar y decisiones inteligentes en un solo lugar.")

st.markdown("<br>", unsafe_allow_html=True)

# 1. MÓDULO: Finanzas del Hogar

if menu == "📊 Finanzas del Hogar":
    tab_resumen, tab_analisis = st.tabs(["📊 Resumen Financiero", "🔍 Análisis Mensual y Servicios"])
    with tab_resumen:
        # Obtener el resumen financiero desde SQLite
        resumen = db.obtener_resumen_financiero(username)
        # Grid de Tarjetas Métricas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
                <div class="metric-card-custom m-balance">
                    <div class="label">Saldo Disponible</div>
                    <div class="value">{format_clp(resumen['saldo'])}</div>
                    <div class="footer-info">Balance total neto actual</div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
                <div class="metric-card-custom m-income">
                    <div class="label">Ingresos Totales</div>
                    <div class="value">{format_clp(resumen['ingresos'])}</div>
                    <div class="footer-info">Suma de ingresos acumulados</div>
                </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
                <div class="metric-card-custom m-expense">
                    <div class="label">Gastos Totales</div>
                    <div class="value">{format_clp(resumen['gastos'])}</div>
                    <div class="footer-info">Suma de egresos acumulados</div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        # Gráfico Donut de Gastos por Categoría (Resiliente)
        transacciones_grafico = db.obtener_transacciones(username)
        gastos_grafico = [tx for tx in transacciones_grafico if tx["tipo"] == "Gasto"]
        if gastos_grafico:
            df_gastos = pd.DataFrame(gastos_grafico)
            df_grouped = df_gastos.groupby("categoria", as_index=False)["monto"].sum()
            if HAS_PLOTLY:
                fig = px.pie(
                    df_grouped,
                    values="monto",
                    names="categoria",
                    hole=0.6,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#f3f4f6", family="Outfit"),
                    showlegend=True,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=-0.25,
                        xanchor="center",
                        x=0.5
                    ),
                    margin=dict(t=20, b=20, l=20, r=20),
                    height=350,
                    separators=".,"
                )
                fig.update_traces(
                    textposition='inside',
                    textinfo='percent',
                    hovertemplate="<b>%{label}</b><br>Monto: $%{value:,.0f}<br>Porcentaje: %{percent}<extra></extra>"
                )
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("💡 **Soporte de Gráficos:** La librería `plotly` no está instalada en tu servidor. Mostrando gráfico alternativo nativo. Para activar el gráfico Donut, sube y confirma los cambios de `requirements.txt` en tu GitHub.")
                df_native = df_grouped.set_index("categoria")
                st.bar_chart(df_native["monto"])
        else:
            st.info("Registra transacciones de tipo 'Gasto' para visualizar el desglose por categorías.")
        st.markdown("<br>", unsafe_allow_html=True)
        # Contenedores de Formulario e Historial
        col_form, col_hist = st.columns([2, 3])
        with col_form:
            st.markdown("<div class='section-header'>📝 Registrar Transacción</div>", unsafe_allow_html=True)
            # Limpiar antes de instanciar los widgets si se solicitó
            if st.session_state.get("clear_tx_inputs"):
                st.session_state.tx_monto_input = 0
                st.session_state.tx_desc_input = ""
                st.session_state.tx_hormiga_chk = False
                st.session_state.clear_tx_inputs = False

            # Inicializar claves en session_state si no existen para poder limpiarlas
            if "tx_monto_input" not in st.session_state:
                st.session_state.tx_monto_input = 0
            if "tx_desc_input" not in st.session_state:
                st.session_state.tx_desc_input = ""
            if "tx_hormiga_chk" not in st.session_state:
                st.session_state.tx_hormiga_chk = False
                
            # Escáner Mágico de Boletas con IA
            with st.expander("📸 Escanear Boleta con IA", expanded=False):
                api_key = st.session_state.get("gemini_api_key", "")
                if not api_key:
                    st.info("Para usar el escáner de boletas con IA, ingresa tu Gemini API Key en la barra lateral.")
                else:
                    archivo_boleta = st.file_uploader("Sube una foto o imagen de tu boleta / ticket de compra", type=["png", "jpg", "jpeg"], key="uploader_boleta")
                    if archivo_boleta:
                        st.image(archivo_boleta, caption="Vista previa de la boleta", use_container_width=True)
                        if st.button("Analizar Boleta con IA", key="btn_analizar_boleta", use_container_width=True, type="secondary"):
                            with st.spinner("La IA está leyendo los números..."):
                                try:
                                    import json
                                    from PIL import Image
                                    
                                    # Abrir imagen con Pillow
                                    img = Image.open(archivo_boleta)
                                    
                                    # Prompt estricto para extraer JSON
                                    prompt_escaner = (
                                        "Analiza esta boleta de compra. Extrae el monto total exacto (solo el número entero), "
                                        "sugiere la mejor categoría (elige estrictamente entre: Alimentos / Súper, Luz, Agua, Gas, "
                                        "Internet, Plan Celular, Transporte / Gasolina, Salud / Farmacia, Entretenimiento / Ocio, Otros Gastos), "
                                        "y crea una breve descripción (ej. 'Compra Lider' o 'Farmacia'). "
                                        "Devuelve el resultado ÚNICAMENTE en formato JSON válido con las claves: "
                                        "'monto', 'categoria', 'descripcion'. No incluyas markdown, ni bloques de código "
                                        "como ```json o ```, solo el texto JSON puro y plano."
                                    )
                                    
                                    # Llamar a Gemini
                                    response_text = consultar_gemini(api_key, "Eres un asistente financiero experto.", [img, prompt_escaner])
                                    
                                    # Limpiar respuesta de marcas markdown
                                    clean_text = response_text.replace("```json", "").replace("```", "").strip()
                                    datos_boleta = json.loads(clean_text)
                                    
                                    # Guardar en variables de sesión para confirmación
                                    st.session_state.boleta_monto = int(datos_boleta.get("monto", 0))
                                    st.session_state.boleta_categoria = datos_boleta.get("categoria", "Otros Gastos")
                                    st.session_state.boleta_descripcion = datos_boleta.get("descripcion", "Compra Escaneada")
                                    st.session_state.boleta_analizada = True
                                    st.success("¡Boleta analizada correctamente!")
                                except Exception as e:
                                    st.error(f"No se pudo procesar la boleta: {str(e)}")
                                    
                    # Si ya está analizada, mostrar los resultados y el botón de guardar
                    if st.session_state.get("boleta_analizada"):
                        monto_esc = st.session_state.get("boleta_monto", 0)
                        cat_esc = st.session_state.get("boleta_categoria", "Otros Gastos")
                        desc_esc = st.session_state.get("boleta_descripcion", "Compra Escaneada")
                        
                        col_esc1, col_esc2, col_esc3 = st.columns(3)
                        with col_esc1:
                            st.metric("Monto sugerido", format_clp(monto_esc))
                        with col_esc2:
                            st.metric("Categoría sugerida", cat_esc)
                        with col_esc3:
                            st.metric("Descripción sugerida", desc_esc)
                            
                        # Campos editables en caso de que la IA se equivoque
                        st.markdown("<p style='font-size: 0.9rem; font-weight: bold;'>Editar datos si es necesario:</p>", unsafe_allow_html=True)
                        monto_esc_ed = st.number_input("Monto Final ($)", value=monto_esc, step=100, format="%d", key="ed_boleta_monto")
                        
                        # Mapear categorías del desplegable
                        categorias_gastos_disp = [
                            "Alimentos / Súper", "Sushi (Samagu, etc.)", "Hamburguesas (Wendy's / McDonald's)",
                            "Pizza (Little Caesars)", "Delivery General", "Luz", "Agua", "Gas",
                            "Internet", "Plan Celular", "Alquiler / Hipoteca", "Entretenimiento / Ocio",
                            "Salud / Farmacia", "Educación", "Transporte / Gasolina", "Hogar / Electrodomésticos",
                            "Otros Gastos"
                        ]
                        
                        default_cat_idx = 16 # Otros Gastos por defecto
                        for idx_c, cat_c in enumerate(categorias_gastos_disp):
                            if cat_esc.lower() in cat_c.lower():
                                default_cat_idx = idx_c
                                break
                                
                        cat_esc_ed = st.selectbox("Categoría Final", categorias_gastos_disp, index=default_cat_idx, key="ed_boleta_cat")
                        desc_esc_ed = st.text_input("Descripción Final", value=desc_esc, key="ed_boleta_desc")
                        
                        if st.button("Confirmar y Guardar Gasto Escaneado", key="btn_confirmar_guardar_boleta", use_container_width=True, type="primary"):
                            exito = db.agregar_transaccion(
                                usuario=username,
                                tipo="Gasto",
                                monto=monto_esc_ed,
                                categoria=cat_esc_ed,
                                descripcion=desc_esc_ed.strip(),
                                fecha=date.today().strftime('%Y-%m-%d'),
                                es_hormiga=0
                            )
                            if exito:
                                st.session_state.boleta_analizada = False
                                st.toast("Transacción escaneada guardada correctamente.", icon="✅")
                                st.rerun()
                            else:
                                st.error("No se pudo guardar la transacción en la base de datos.")
                                
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("🎯 Configurar Presupuestos Mensuales"):
                categorias_presupuesto = [
                    "Alimentos / Súper", 
                    "Sushi (Samagu, etc.)",
                    "Hamburguesas (Wendy's / McDonald's)",
                    "Pizza (Little Caesars)",
                    "Delivery General",
                    "Luz",
                    "Agua",
                    "Gas",
                    "Internet",
                    "Plan Celular",
                    "Alquiler / Hipoteca", 
                    "Entretenimiento / Ocio", 
                    "Salud / Farmacia", 
                    "Educación", 
                    "Transporte / Gasolina", 
                    "Hogar / Electrodomésticos", 
                    "Otros Gastos"
                ]
                with st.form("form_presupuesto", clear_on_submit=True):
                    cat_pres = st.selectbox("Categoría de Gasto", categorias_presupuesto, key="budget_cat_sel")
                    monto_pres = st.number_input("Monto Límite Mensual ($)", min_value=0.0, step=5000.0, format="%f", key="budget_amount_in")
                    btn_save_pres = st.form_submit_button("Establecer Límite")
                    if btn_save_pres:
                        if db.establecer_presupuesto(username, cat_pres, monto_pres):
                            st.toast(f"Presupuesto para {cat_pres} actualizado.", icon="🎯")
                            st.rerun()
                        else:
                            st.error("No se pudo guardar el presupuesto.")
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                tipo_tx = st.selectbox("Tipo de Operación", ["Ingreso", "Gasto", "Ahorro"], key="tx_tipo_input")
                monto_tx = st.number_input("Monto ($)", min_value=0, step=1000, format="%d", key="tx_monto_input")
                # Categorías contextualizadas al tipo de movimiento
                if tipo_tx == "Ingreso":
                    categorias = ["Sueldo / Salarios", "Inversiones", "Ventas", "Transferencias", "Otros Ingresos"]
                elif tipo_tx == "Ahorro":
                    # Cargar metas de ahorro dinámicas
                    metas_ahorro = db.obtener_metas_ahorro(username)
                    categorias = [f"{m['icono']} {m['nombre']}" for m in metas_ahorro]
                    if not categorias:
                        categorias = ["🎯 Ahorro General"]
                else:
                    categorias = [
                        "Alimentos / Súper", 
                        "Sushi (Samagu, etc.)",
                        "Hamburguesas (Wendy's / McDonald's)",
                        "Pizza (Little Caesars)",
                        "Delivery General",
                        "Luz",
                        "Agua",
                        "Gas",
                        "Internet",
                        "Plan Celular",
                        "Alquiler / Hipoteca", 
                        "Entretenimiento / Ocio", 
                        "Salud / Farmacia", 
                        "Educación", 
                        "Transporte / Gasolina", 
                        "Hogar / Electrodomésticos", 
                        "Otros Gastos"
                    ]
                categoria_tx = st.selectbox("Categoría", categorias, key="tx_cat_input")
                # Checkbox para Gasto Hormiga (solo si es Gasto)
                es_hormiga_val = 0
                if tipo_tx == "Gasto":
                    es_hormiga_chk = st.checkbox("¿Es Gasto Hormiga? (pequeño gasto cotidiano/impulso)", key="tx_hormiga_chk")
                    if es_hormiga_chk:
                        es_hormiga_val = 1
                descripcion_tx = st.text_input("Descripción (Opcional)", placeholder="Concepto o detalle del movimiento", key="tx_desc_input")
                fecha_tx = st.date_input("Fecha", value=date.today(), key="tx_fecha_input")
                btn_registrar = st.button("Registrar en Cuenta", use_container_width=True, type="primary", key="tx_btn_submit")
                if btn_registrar:
                    if monto_tx <= 0:
                        st.error("El monto debe ser superior a 0.")
                    else:
                        if tipo_tx == "Ahorro":
                            # Guardar en base de datos como Gasto para reflejarse en los reportes
                            exito = db.agregar_transaccion(
                                usuario=username,
                                tipo="Gasto",
                                monto=monto_tx,
                                categoria=categoria_tx,
                                descripcion=descripcion_tx.strip() if descripcion_tx.strip() else f"Aporte a meta: {categoria_tx}",
                                fecha=fecha_tx.strftime('%Y-%m-%d'),
                                es_hormiga=0
                            )
                            if exito:
                                # Aumentar el monto_actual de la meta de ahorro correspondiente
                                metas = db.obtener_metas_ahorro(username)
                                for m in metas:
                                    meta_str = f"{m['icono']} {m['nombre']}"
                                    if meta_str == categoria_tx:
                                        nuevo_monto_actual = m["monto_actual"] + float(monto_tx)
                                        db.actualizar_meta_ahorro(username, m["id"], m["nombre"], m["icono"], m["monto_meta"], nuevo_monto_actual)
                                        # Sincronizar variables de sesión de ahorro predeterminadas
                                        if m["nombre"] == "Vacaciones":
                                            st.session_state.ahorro_vacaciones = int(nuevo_monto_actual)
                                            db.guardar_variable(username, "ahorro_vacaciones", int(nuevo_monto_actual))
                                        elif m["nombre"] == "Fondo de Emergencia":
                                            st.session_state.ahorro_emergencia = int(nuevo_monto_actual)
                                            db.guardar_variable(username, "ahorro_emergencia", int(nuevo_monto_actual))
                                        break
                        else:
                            exito = db.agregar_transaccion(
                                usuario=username,
                                tipo=tipo_tx,
                                monto=monto_tx,
                                categoria=categoria_tx,
                                descripcion=descripcion_tx.strip(),
                                fecha=fecha_tx.strftime('%Y-%m-%d'),
                                es_hormiga=es_hormiga_val
                            )
                        if exito:
                            st.session_state.clear_tx_inputs = True
                            st.toast("Movimiento registrado correctamente.", icon="✅")
                            st.rerun()
                        else:
                            st.error("No se pudo registrar en la base de datos.")
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("🔧 Ajustar Saldo Actual (Manual)"):
                st.markdown("<p style='font-size: 0.9rem; color: #9ca3af; margin-bottom: 15px;'>Si el saldo disponible no coincide con tu saldo real (por ejemplo, por haber olvidado registrar un gasto), ingresa el monto real a continuación y el sistema creará un ajuste automático.</p>", unsafe_allow_html=True)
                saldo_real_input = st.number_input(
                    "Saldo Real Disponible ($)", 
                    value=int(resumen['saldo']), 
                    step=1000, 
                    format="%d", 
                    key="saldo_real_input"
                )
                descripcion_ajuste = st.text_input(
                    "Descripción del ajuste", 
                    value="Ajuste manual de saldo (olvido de registro)", 
                    key="desc_ajuste_input"
                )
                saldo_actual = resumen['saldo']
                diferencia = saldo_real_input - saldo_actual
                if diferencia != 0:
                    tipo_ajuste = "Ingreso" if diferencia > 0 else "Gasto"
                    monto_ajuste = abs(diferencia)
                    st.info(f"Se creará un **{tipo_ajuste}** automático de **{format_clp(monto_ajuste)}** para corregir el saldo.")
                    if st.button("Aplicar Ajuste de Saldo", use_container_width=True, key="btn_apply_ajuste"):
                        exito = db.agregar_transaccion(
                            usuario=username,
                            tipo=tipo_ajuste,
                            monto=monto_ajuste,
                            categoria="Ajuste de Saldo",
                            descripcion=descripcion_ajuste.strip(),
                            fecha=date.today().strftime('%Y-%m-%d')
                        )
                        if exito:
                            st.toast("Saldo ajustado correctamente.", icon="🔧")
                            st.rerun()
                        else:
                            st.error("No se pudo aplicar el ajuste.")
                else:
                    st.success("El saldo ingresado coincide con el saldo de la cuenta.")
        with col_hist:
            st.markdown("<div class='section-header'>📋 Últimos Movimientos</div>", unsafe_allow_html=True)
            transacciones = db.obtener_transacciones(username)
            if not transacciones:
                st.info("No hay transacciones registradas todavía.")
            else:
                # Mostrar los últimos 10 de manera dinámica
                for tx in transacciones[:10]:
                    clase_monto = "amount-ingreso" if tx["tipo"] == "Ingreso" else "amount-gasto"
                    signo = "+" if tx["tipo"] == "Ingreso" else "-"
                    # Conversión de fecha a formato local
                    fecha_obj = datetime.strptime(tx["fecha"], "%Y-%m-%d").date()
                    fecha_str = fecha_obj.strftime("%d/%m/%Y")
                    desc_html = f"<div class='tx-desc'>{tx['descripcion']}</div>" if tx['descripcion'] else ""
                    col_tx_data, col_tx_del = st.columns([9, 1])
                    with col_tx_data:
                        render_html(f"""
                            <div class="tx-row">
                                <div class="tx-date">{fecha_str}</div>
                                <div class="tx-info">
                                    <span class="tx-title">{tx['tipo']}</span>
                                    <span class="tx-category">{tx['categoria']}</span>
                                    {desc_html}
                                </div>
                                <div class="tx-amount {clase_monto}">{signo}{format_clp(tx['monto'])}</div>
                            </div>
                        """)
                    with col_tx_del:
                        # Botón eliminar con ID único
                        if st.button("🗑️", key=f"del_tx_{tx['id']}", help="Eliminar transacción"):
                            if db.eliminar_transaccion(username, tx['id']):
                                st.toast("Transacción eliminada.", icon="🗑️")
                                st.rerun()
                # Historial Completo en Expander si hay más de 10
                if len(transacciones) > 10:
                    with st.expander("🔍 Historial Completo y Filtrado"):
                        df = pd.DataFrame(transacciones)
                        df.columns = ["ID", "Tipo", "Monto", "Categoría", "Descripción", "Fecha"]
                        st.dataframe(df, use_container_width=True)
                        if HAS_OPENPYXL:
                            try:
                                output = BytesIO()
                                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                    df.to_excel(writer, index=False, sheet_name='Transacciones')
                                excel_data = output.getvalue()
                                st.download_button(
                                    label="📥 Descargar Historial en Excel (.xlsx)",
                                    data=excel_data,
                                    file_name=f"historial_finanzas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True,
                                    key="btn_download_excel"
                                )
                            except Exception as e:
                                st.error(f"Error al generar el archivo Excel: {e}")
                        else:
                            st.warning("💡 **Exportación:** La librería `openpyxl` no está instalada. Descarga en CSV habilitada como alternativa. Para descargar en formato Excel (.xlsx), sube y confirma los cambios de `requirements.txt` en tu GitHub.")
                            try:
                                csv_data = df.to_csv(index=False).encode('utf-8')
                                st.download_button(
                                    label="📥 Descargar Historial en CSV (.csv)",
                                    data=csv_data,
                                    file_name=f"historial_finanzas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv",
                                    use_container_width=True,
                                    key="btn_download_csv"
                                )
                            except Exception as e:
                                st.error(f"Error al generar el archivo CSV: {e}")
                        st.markdown("##### Eliminar Registro por ID")
                        del_id = st.number_input("ID de Transacción a Eliminar", min_value=1, step=1, key="input_del_id")
                        if st.button("Eliminar Registro", key="btn_del_id"):
                            if db.eliminar_transaccion(username, del_id):
                                st.success(f"Movimiento {del_id} eliminado.")
                                st.rerun()
                            else:
                                st.error("ID no encontrado o error de eliminación.")
        # Sub-sección de Metas de Ahorro (Estilo JRPG HP Bar Interactivo)
        st.markdown("<br><hr style='border-color: #1e293b; margin: 25px 0;' />", unsafe_allow_html=True)
        st.markdown("<div class='section-header'>🎯 Progreso de Metas de Ahorro</div>", unsafe_allow_html=True)
        # Obtener metas dinámicas del usuario
        metas_ahorro = db.obtener_metas_ahorro(username)
        with st.expander("⚙️ Ajustar Simulador de Ahorros"):
            conectar_saldo = st.toggle("Conectar con el Saldo Real de la cuenta", value=(db.obtener_variable(username, "toggle_saldo_real", "False") == "True"), key="toggle_saldo_real")
            db.guardar_variable(username, "toggle_saldo_real", "True" if conectar_saldo else "False")
            if conectar_saldo:
                saldo_real = max(0.0, resumen['saldo'])
                saldo_restante = saldo_real
                # Distribuir secuencialmente el saldo en tiempo real entre las metas
                for m in metas_ahorro:
                    m_meta = float(m["monto_meta"])
                    m_actual = min(saldo_restante, m_meta)
                    saldo_restante -= m_actual
                    if float(m["monto_actual"]) != m_actual:
                        db.actualizar_meta_ahorro(username, m["id"], m["nombre"], m["icono"], m_meta, m_actual)
                # Volver a cargar las metas actualizadas
                metas_ahorro = db.obtener_metas_ahorro(username)
                st.info(f"Conectado a la Base de Datos. Saldo Disponible Real: {format_clp(saldo_real)}. El saldo se distribuye secuencialmente entre tus metas de ahorro.")
            else:
                st.markdown("##### 🎚️ Ajustar Ahorro Acumulado")
                # Callback para guardar cambios en sliders de forma eficiente y evitar lags
                def guardar_monto_meta(meta_id, nombre, icono, monto_meta, key):
                    nuevo_monto = float(st.session_state[key])
                    db.actualizar_meta_ahorro(username, meta_id, nombre, icono, monto_meta, nuevo_monto)
                    st.toast("Ahorro acumulado actualizado.", icon="💾")
                for m in metas_ahorro:
                    st.slider(
                        f"{m['icono']} {m['nombre']} (Meta: {format_clp(m['monto_meta'])})",
                        min_value=0,
                        max_value=int(m['monto_meta']),
                        value=int(m['monto_actual']),
                        step=50000 if m['monto_meta'] >= 1000000 else 10000 if m['monto_meta'] >= 100000 else 1000,
                        key=f"slide_meta_{m['id']}",
                        on_change=guardar_monto_meta,
                        args=(m['id'], m['nombre'], m['icono'], m['monto_meta'], f"slide_meta_{m['id']}")
                    )
            st.markdown("<hr style='border-color: #1e293b; margin: 15px 0;' />", unsafe_allow_html=True)
            st.markdown("##### ➕ Agregar Nueva Meta de Ahorro")
            with st.form("form_add_meta", clear_on_submit=True):
                nueva_meta_nombre = st.text_input("Nombre de la Meta", placeholder="Ej. Comprar Auto, Enganche Casa")
                col_add_i, col_add_m = st.columns([2, 2])
                with col_add_i:
                    iconos_disponibles = [
                        "🎯 General", "🏠 Casa / Vivienda", "🚗 Auto / Vehículo", "🌴 Vacaciones / Viajes",
                        "🛡️ Fondo de Emergencia", "🏥 Salud / Bienestar", "🎓 Estudios / Educación",
                        "💍 Boda / Compromiso", "👶 Bebé / Hijos", "💻 Tecnología / Gadgets",
                        "🎄 Fiestas / Regalos", "🚲 Deporte / Pasatiempos", "🐶 Mascotas / Animales",
                        "💼 Inversiones / Negocio", "🛠️ Reparaciones / Mejoras", "🛋️ Muebles / Decoración",
                        "🍕 Comida / Salidas", "👕 Ropa / Vestimenta", "🎮 Consolas / Videojuegos",
                        "🎟️ Eventos / Conciertos", "👵 Jubilación / Retiro", "💳 Pago de Deudas",
                        "📚 Libros / Cursos", "🎸 Música / Instrumentos", "✈️ Viajes Largos / Vuelos",
                        "🛒 Compras Grandes / Despensa", "🏍️ Moto / Ciclomotor", "🪙 Monedas / Oro",
                        "🐷 Alcancía / Ahorro Hormiga", "🔨 Remodelación / Obras", "🔋 Energía / Paneles",
                        "🌱 Plantas / Jardín", "💧 Agua / Eco", "✨ Otros / Especial"
                    ]
                    nueva_meta_icono_sel = st.selectbox("Icono / Categoría", iconos_disponibles, index=0)
                    nueva_meta_icono = nueva_meta_icono_sel.split()[0]
                with col_add_m:
                    nueva_meta_monto = st.number_input("Monto Meta ($)", min_value=1.0, value=1000000.0, step=50000.0, format="%f")
                st.warning("⚠️ Verificación requerida:")
                confirmar_add = st.checkbox("¿Estás seguro de que deseas agregar esta meta de ahorro?", value=False, key="chk_conf_add_meta")
                btn_add_meta = st.form_submit_button("Crear Meta")
                if btn_add_meta:
                    if not nueva_meta_nombre.strip():
                        st.error("Por favor, escribe el nombre de la meta.")
                    elif not confirmar_add:
                        st.warning("Debes marcar la casilla verificadora para confirmar.")
                    else:
                        if db.agregar_meta_ahorro(username, nueva_meta_nombre.strip(), nueva_meta_icono.strip(), nueva_meta_monto):
                            st.toast("Meta de ahorro agregada con éxito.", icon="🎯")
                            st.rerun()
                        else:
                            st.error("No se pudo agregar la meta.")
            st.markdown("<hr style='border-color: #1e293b; margin: 15px 0;' />", unsafe_allow_html=True)
            st.markdown("##### 🔧 Modificar / Eliminar Metas Existentes")
            if not metas_ahorro:
                st.info("No tienes metas registradas.")
            else:
                for m in metas_ahorro:
                    col_meta_info, col_meta_actions = st.columns([5, 3])
                    with col_meta_info:
                        st.write(f"{m['icono']} **{m['nombre']}** (Meta: {format_clp(m['monto_meta'])})")
                    with col_meta_actions:
                        col_act_edit, col_act_del = st.columns(2)
                        with col_act_edit:
                            with st.popover("📝 Editar", use_container_width=True):
                                st.write(f"Editar: {m['nombre']}")
                                edit_nombre = st.text_input("Nombre", value=m['nombre'], key=f"edit_nombre_{m['id']}")
                                iconos_disponibles = [
                                    "🎯 General", "🏠 Casa / Vivienda", "🚗 Auto / Vehículo", "🌴 Vacaciones / Viajes",
                                    "🛡️ Fondo de Emergencia", "🏥 Salud / Bienestar", "🎓 Estudios / Educación",
                                    "💍 Boda / Compromiso", "👶 Bebé / Hijos", "💻 Tecnología / Gadgets",
                                    "🎄 Fiestas / Regalos", "🚲 Deporte / Pasatiempos", "🐶 Mascotas / Animales",
                                    "💼 Inversiones / Negocio", "🛠️ Reparaciones / Mejoras", "🛋️ Muebles / Decoración",
                                    "🍕 Comida / Salidas", "👕 Ropa / Vestimenta", "🎮 Consolas / Videojuegos",
                                    "🎟️ Eventos / Conciertos", "👵 Jubilación / Retiro", "💳 Pago de Deudas",
                                    "📚 Libros / Cursos", "🎸 Música / Instrumentos", "✈️ Viajes Largos / Vuelos",
                                    "🛒 Compras Grandes / Despensa", "🏍️ Moto / Ciclomotor", "🪙 Monedas / Oro",
                                    "🐷 Alcancía / Ahorro Hormiga", "🔨 Remodelación / Obras", "🔋 Energía / Paneles",
                                    "🌱 Plantas / Jardín", "💧 Agua / Eco", "✨ Otros / Especial"
                                ]
                                default_idx = 0
                                for idx, item in enumerate(iconos_disponibles):
                                    if item.startswith(m['icono']):
                                        default_idx = idx
                                        break
                                edit_icono_sel = st.selectbox("Icono / Categoría", iconos_disponibles, index=default_idx, key=f"edit_icono_sel_{m['id']}")
                                edit_icono = edit_icono_sel.split()[0]
                                edit_monto = st.number_input("Monto Meta ($)", min_value=1.0, value=float(m['monto_meta']), key=f"edit_monto_{m['id']}", format="%f")
                                confirmar_edit = st.checkbox("Confirmar cambios", value=False, key=f"chk_conf_edit_meta_{m['id']}")
                                if st.button("Guardar Cambios", key=f"btn_save_edit_meta_{m['id']}", use_container_width=True):
                                    if not edit_nombre.strip():
                                        st.error("Escribe un nombre.")
                                    elif not confirmar_edit:
                                        st.warning("Marca la casilla para confirmar.")
                                    else:
                                        # Ajustar monto actual si supera el nuevo monto meta
                                        edit_actual = min(float(m['monto_actual']), edit_monto)
                                        if db.actualizar_meta_ahorro(username, m['id'], edit_nombre.strip(), edit_icono.strip(), edit_monto, edit_actual):
                                            st.toast("Meta de ahorro actualizada.", icon="💾")
                                            st.rerun()
                        with col_act_del:
                            with st.popover("🗑️ Eliminar", use_container_width=True):
                                st.write(f"¿Eliminar {m['nombre']}?")
                                confirmar_del = st.checkbox("Confirmar eliminación", value=False, key=f"chk_conf_del_meta_{m['id']}")
                                if st.button("Sí, eliminar", key=f"btn_del_meta_{m['id']}", use_container_width=True):
                                    if confirmar_del:
                                        if db.eliminar_meta_ahorro(username, m['id']):
                                            st.toast("Meta de ahorro eliminada.", icon="🗑️")
                                            st.rerun()
                                    else:
                                        st.warning("Marca la casilla para confirmar.")
        # Generación dinámica del cuadro JRPG para las metas
        total_ahorrado = sum(float(m["monto_actual"]) for m in metas_ahorro)
        goals_rows_html = ""
        if not metas_ahorro:
            goals_rows_html = """
                <div style="text-align: center; color: #888; font-style: italic; padding: 20px 0;">
                    No hay metas de ahorro registradas. ¡Agrega metas en la configuración del simulador!
                </div>
            """
        else:
            for m in metas_ahorro:
                m_meta = float(m["monto_meta"])
                m_actual = float(m["monto_actual"])
                # Calcular porcentaje de progreso
                pct = int((m_actual / m_meta) * 100) if m_meta > 0 else 0
                pct = max(0, min(pct, 100))
                # Color JRPG dinámico (verde para alto, amarillo para medio, rojo para bajo)
                color = "#22c55e" if pct >= 50 else "#f59e0b" if pct >= 20 else "#ef4444"
                # Frase de estado dinámica
                if pct >= 100:
                    status = "¡Meta alcanzada! 🏆"
                elif pct >= 80:
                    status = "¡Casi listo! 🚀"
                elif pct >= 40:
                    status = "En marcha... ⛵"
                else:
                    status = "Ahorrando las primeras monedas... 🪙"
                goals_rows_html += f"""
                    <div style="margin-bottom: 25px;">
                        <div style="display: flex; justify-content: space-between; font-size: 1.05rem; font-weight: bold; margin-bottom: 6px; color: #1e293b;">
                            <span>{m['icono']} {m['nombre'].upper()} (Meta: {format_clp(m_meta)})</span>
                            <span style="color: #f97316;">{format_clp(m_actual)} / {format_clp(m_meta)}</span>
                        </div>
                        <div style="
                            background-color: rgba(226, 232, 240, 0.4);
                            border: 1px solid rgba(203, 213, 225, 0.5);
                            height: 18px;
                            width: 100%;
                            border-radius: 6px;
                            overflow: hidden;
                        ">
                            <div style="
                                background: linear-gradient(90deg, #f97316, #ec4899);
                                height: 100%;
                                width: {pct}%;
                                transition: width 0.3s ease;
                            "></div>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #64748b; margin-top: 4px; font-weight: 500;">
                            <span>Progreso: {pct}%</span>
                            <span>{status}</span>
                        </div>
                    </div>
                """
        goals_html = f"""
            <div style="
                background: linear-gradient(135deg, rgba(251, 146, 60, 0.05), rgba(236, 72, 153, 0.05));
                border: 1px solid rgba(251, 146, 60, 0.2);
                border-radius: 12px;
                padding: 20px;
                font-family: sans-serif;
                color: #1e293b;
                box-shadow: 0 4px 15px rgba(0,0,0,0.02);
                max-width: 800px;
                margin: 0 auto;
            ">
                <div style="font-size: 1.25rem; font-weight: bold; border-bottom: 2px dashed rgba(251, 146, 60, 0.3); padding-bottom: 8px; margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; color: #1e293b;">
                    <span>🎯 Progreso de Ahorros de {username_display}</span>
                    <span style="font-size: 0.95rem; color: #ec4899; font-weight: bold;">TOTAL AHORRADO: {format_clp(total_ahorrado)}</span>
                </div>
                {goals_rows_html}
            </div>
        """
        render_html(goals_html)
    
    with tab_analisis:
        st.markdown("<div class='section-header'>🔍 Análisis Mensual de Gastos y Servicios</div>", unsafe_allow_html=True)
        st.write("Analiza tus egresos mensuales, evalúa los gastos hormiga y realiza el seguimiento histórico de tus servicios básicos.")
        
        all_txs = db.obtener_transacciones(username)
        if not all_txs:
            st.info("No hay transacciones registradas para analizar. Comienza registrando algunos movimientos en el Resumen Financiero.")
        else:
            df_tx = pd.DataFrame(all_txs)
            df_tx['monto'] = df_tx['monto'].astype(float)
            df_tx['fecha'] = df_tx['fecha'].astype(str)
            df_tx['mes'] = df_tx['fecha'].apply(lambda x: x[:7])
            
            # Selector de Mes
            meses_disponibles = sorted(df_tx['mes'].unique(), reverse=True)
            mes_sel = st.selectbox("Seleccionar Mes para Análisis", meses_disponibles, key="select_analysis_month")
            
            # Filtrar por mes
            df_mes = df_tx[df_tx['mes'] == mes_sel]
            
            # Calcular métricas
            ingresos_mes = df_mes[df_mes['tipo'] == 'Ingreso']['monto'].sum()
            gastos_mes = df_mes[df_mes['tipo'] == 'Gasto']['monto'].sum()
            gastos_hormiga_mes = df_mes[(df_mes['tipo'] == 'Gasto') & (df_mes['es_hormiga'] == 1)]['monto'].sum()
            balance_mes = ingresos_mes - gastos_mes
            
            # Grid de métricas mensuales
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155; border-radius: 12px; padding: 15px; text-align: center;">
                        <div style="font-size: 0.8rem; color: #9ca3af; text-transform: uppercase; font-weight: 500;">Ingresos del Mes</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: #10b981; margin-top: 5px;">{format_clp(ingresos_mes)}</div>
                    </div>
                """, unsafe_allow_html=True)
            with col_m2:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155; border-radius: 12px; padding: 15px; text-align: center;">
                        <div style="font-size: 0.8rem; color: #9ca3af; text-transform: uppercase; font-weight: 500;">Gastos del Mes</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: #ef4444; margin-top: 5px;">{format_clp(gastos_mes)}</div>
                    </div>
                """, unsafe_allow_html=True)
            with col_m3:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155; border-radius: 12px; padding: 15px; text-align: center;">
                        <div style="font-size: 0.8rem; color: #9ca3af; text-transform: uppercase; font-weight: 500;">Gastos Hormiga</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: #fb923c; margin-top: 5px;">{format_clp(gastos_hormiga_mes)}</div>
                    </div>
                """, unsafe_allow_html=True)
            with col_m4:
                color_bal = "#10b981" if balance_mes >= 0 else "#ef4444"
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155; border-radius: 12px; padding: 15px; text-align: center;">
                        <div style="font-size: 0.8rem; color: #9ca3af; text-transform: uppercase; font-weight: 500;">Balance del Mes</div>
                        <div style="font-size: 1.4rem; font-weight: 700; color: {color_bal}; margin-top: 5px;">{format_clp(balance_mes)}</div>
                    </div>
                """, unsafe_allow_html=True)
            
            # --- SECCIÓN: Presupuestos Mensuales (Límites de Gastos) ---
            presupuestos = db.obtener_presupuestos(username)
            if presupuestos:
                st.markdown("#### 🎯 Presupuesto y Límites del Mes")
                df_gastos_mes = df_mes[df_mes['tipo'] == 'Gasto']
                gastos_por_cat = df_gastos_mes.groupby("categoria")["monto"].sum().to_dict() if not df_gastos_mes.empty else {}
                
                for cat, limite in presupuestos.items():
                    gasto_actual = gastos_por_cat.get(cat, 0.0)
                    porcentaje = (gasto_actual / limite) * 100 if limite > 0 else 0
                    porcentaje = max(0.0, min(porcentaje, 100.0))
                    
                    st.markdown(f"**{cat}**: {format_clp(gasto_actual)} / {format_clp(limite)}")
                    st.progress(int(porcentaje))
                st.markdown("<br>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- ANÁLISIS DE GASTOS HORMIGA ---
            st.markdown("#### 🐜 Análisis de Gastos Hormiga")
            pct_hormiga = (gastos_hormiga_mes / gastos_mes * 100) if gastos_mes > 0 else 0
            
            col_pct_text, col_pct_bar = st.columns([1, 2])
            with col_pct_text:
                st.markdown(f"Porcentaje del gasto mensual: **{pct_hormiga:.1f}%**")
                if pct_hormiga == 0:
                    st.success("¡Excelente! No tienes gastos hormiga registrados este mes. 🎉")
                elif pct_hormiga <= 10:
                    st.info("Tus gastos hormiga están bajo control. ¡Sigue así! 👍")
                elif pct_hormiga <= 20:
                    st.warning("Atención: Los pequeños gastos cotidianos están sumando una cifra considerable. ⚠️")
                else:
                    st.error("Alerta: Los gastos hormiga representan más del 20% de tus egresos. ¡Es hora de recortar suscripciones o compras impulsivas! 🚨")
            
            with col_pct_bar:
                st.progress(min(1.0, pct_hormiga / 100.0))
            
            df_hormiga_mes = df_mes[(df_mes['tipo'] == 'Gasto') & (df_mes['es_hormiga'] == 1)]
            if not df_hormiga_mes.empty:
                st.markdown("##### Detalle de Gastos Hormiga")
                df_hormiga_show = df_hormiga_mes[['fecha', 'categoria', 'descripcion', 'monto']].copy()
                df_hormiga_show['monto'] = df_hormiga_show['monto'].apply(lambda x: format_clp(x))
                df_hormiga_show.columns = ["Fecha", "Categoría", "Descripción", "Monto"]
                st.dataframe(df_hormiga_show, use_container_width=True, hide_index=True)
            
            # Auditoría Financiera IA
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 🤖 Auditoría Financiera IA con Gemini")
            st.write("Obtén un informe de auditoría personalizado sobre tus hábitos de consumo del mes seleccionado.")
            
            api_key = st.session_state.get("gemini_api_key", "")
            if not api_key:
                st.info("Para recibir auditorías de la IA, ingresa tu Gemini API Key en la barra lateral.")
            else:
                if st.button("🔍 Solicitar Auditoría Financiera a la IA", key="btn_solicitar_auditoria", use_container_width=True):
                    with st.spinner("Analizando tus movimientos del mes y redactando consejos..."):
                        try:
                            txs_texto = "\n".join([
                                f"- {tx['fecha']}: {tx['tipo']} de {format_clp(tx['monto'])} en '{tx['categoria']}' ({tx['descripcion'] or 'Sin descripción'})" + (" [GASTO HORMIGA]" if tx.get('es_hormiga') == 1 else "")
                                for _, tx in df_mes.iterrows()
                            ])
                            system_prompt_audit = f"""
                            Eres un auditor y asesor financiero experto para familias chilenas.
                            Tu tarea es auditar y aconsejar detalladamente sobre los gastos del usuario en base a los movimientos de un mes seleccionado.
                            Aquí tienes el resumen financiero del mes {mes_sel}:
                            - Ingresos Totales: {format_clp(ingresos_mes)}
                            - Gastos Totales: {format_clp(gastos_mes)}
                            - Gastos Hormiga: {format_clp(gastos_hormiga_mes)} ({pct_hormiga:.1f}% del total)
                            - Balance Neto: {format_clp(balance_mes)}
                            
                            Analiza los movimientos and proporciona:
                            1. Un diagnóstico de su salud financiera de este mes.
                            2. Análisis específico de los Gastos Hormiga (pequeños gastos cotidianos) y sugerencias para reducirlos.
                            3. Tres consejos concretos de ahorro adaptados a su patrón de consumo.
                            
                            Usa formato limpio en markdown, con tono empático y constructivo, pesos chilenos ($ sin decimales) y puntos como separador de miles.
                            """
                            resultado = consultar_gemini(api_key, system_prompt_audit, f"Estos son mis movimientos de {mes_sel}:\n{txs_texto}")
                            st.session_state.ia_audit_result = resultado
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al generar auditoría: {str(e)}")
            
            if "ia_audit_result" in st.session_state:
                with st.container(border=True):
                    st.markdown("##### 📋 Resultado de la Auditoría Financiera")
                    st.markdown(st.session_state.ia_audit_result)
                    if st.button("Limpiar Auditoría", key="btn_clear_ia_audit_tab"):
                        del st.session_state.ia_audit_result
                        st.rerun()
            
            # --- SECCIÓN: Análisis de Servicios del Hogar ---
            st.markdown("<br><hr style='border-color: #1e293b; margin: 25px 0;' />", unsafe_allow_html=True)
            st.markdown("### 🔌 Historial y Análisis de Servicios del Hogar")
            st.write("Registros mes a mes del agua, la luz, el gas, el internet y planes de celular para evaluar tus consumos específicos.")
            
            cat_servicios = ["Luz", "Agua", "Gas", "Internet", "Plan Celular", "Servicios (Luz, Agua, Gas)", "Internet / Teléfono"]
            df_tx_servicios = df_tx[(df_tx['tipo'] == 'Gasto') & (df_tx['categoria'].isin(cat_servicios))].copy() if not df_tx.empty else pd.DataFrame()
            
            if df_tx_servicios.empty:
                st.info("No hay registros de servicios para mostrar en el historial aún. Registra gastos en categorías como Luz, Agua, Gas, Internet o Plan Celular.")
            else:
                def normalizar_categoria_servicio(cat, desc):
                    cat_lower = cat.lower() if cat else ""
                    desc_lower = desc.lower() if desc else ""
                    
                    if "luz" in cat_lower or "luz" in desc_lower:
                        return "Luz"
                    elif "agua" in cat_lower or "agua" in desc_lower:
                        return "Agua"
                    elif "gas" in cat_lower or "gas" in desc_lower:
                        return "Gas"
                    elif "internet" in cat_lower or "net" in cat_lower or "internet" in desc_lower or "net" in desc_lower:
                        return "Internet"
                    elif "celular" in cat_lower or "teléfono" in cat_lower or "plan" in cat_lower or "celular" in desc_lower or "tel" in desc_lower or "plan" in desc_lower:
                        return "Plan Celular"
                    return "Otros Servicios"
                
                df_tx_servicios['Servicio'] = df_tx_servicios.apply(lambda r: normalizar_categoria_servicio(r['categoria'], r['descripcion']), axis=1)
                df_tx_servicios['mes'] = df_tx_servicios['fecha'].apply(lambda x: x[:7])
                
                df_pivot = df_tx_servicios.pivot_table(
                    index='mes',
                    columns='Servicio',
                    values='monto',
                    aggfunc='sum'
                ).fillna(0)
                
                for col in ["Luz", "Agua", "Gas", "Internet", "Plan Celular"]:
                    if col not in df_pivot.columns:
                        df_pivot[col] = 0.0
                
                df_pivot = df_pivot[["Luz", "Agua", "Gas", "Internet", "Plan Celular"]]
                df_pivot = df_pivot.sort_index(ascending=False)
                
                df_show = df_pivot.copy()
                for col in df_show.columns:
                    df_show[col] = df_show[col].apply(lambda val: format_clp(val))
                
                st.dataframe(df_show, use_container_width=True)
                
                st.markdown("##### 📈 Gráfico de Evolución de Gastos de Servicios")
                df_chart = df_pivot.sort_index(ascending=True)
                st.bar_chart(df_chart)

# 2. MÓDULO: Lista de Compras

elif menu == "🛒 Lista de Compras":
    # Presupuesto para salida de compras
    presupuesto_key = "presupuesto_compras"
    presupuesto_actual = int(db.obtener_variable(username, presupuesto_key, 0))
    # Grid superior para presupuesto y planificación
    col_p_title, col_p_btn = st.columns([3, 1])
    with col_p_title:
        st.markdown(f"#### 💰 Presupuesto Estimado para esta Salida: <span style='color: #10b981; font-weight: bold;'>{format_clp(presupuesto_actual)}</span>", unsafe_allow_html=True)
    with col_p_btn:
        with st.popover("⚙️ Ajustar Presupuesto", use_container_width=True):
            nuevo_presupuesto = st.number_input("Nuevo Presupuesto ($)", min_value=0, value=presupuesto_actual, step=5000, format="%d")
            if st.button("Guardar Presupuesto", use_container_width=True, key="btn_save_presupuesto"):
                db.guardar_variable(username, presupuesto_key, nuevo_presupuesto)
                st.toast("Presupuesto de compras actualizado.", icon="💾")
                st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)
    col_add_compra, col_lista_compra = st.columns([2, 3])
    with col_add_compra:
        st.markdown("<div class='section-header'>➕ Agregar Artículo</div>", unsafe_allow_html=True)
        with st.form("form_compra", clear_on_submit=True):
            producto = st.text_input("Producto / Artículo", placeholder="Ej. Leche entera, Cebollas, Jabón")
            cantidad = st.text_input("Cantidad / Formato", placeholder="Ej. 2 cajas, 1 kg, 3 unidades", value="1 unidad")
            tipo_lista = st.selectbox("Destino de Compra", ["Supermercado", "Feria (Frutas y Verduras)", "Otras Compras (Carne, Pescado)", "Pañalera (Bebé)", "Cuidado Personal"])
            btn_add = st.form_submit_button("Agregar a la Lista")
            if btn_add:
                if not producto.strip():
                    st.error("Escribe el nombre del artículo.")
                else:
                    if db.agregar_item_compra(username, producto.strip(), cantidad.strip(), tipo_lista):
                        st.toast("Artículo agregado.", icon="🛒")
                        st.rerun()
        # Definición de las 4 listas para renderizar sus opciones rápidas
        listas_definicion = [
            {"key": "super", "name": "Supermercado", "label_title": "⚡ Supermercado Rápido", "color": "#818cf8", "default_emoji": "📦"},
            {"key": "feria", "name": "Feria (Frutas y Verduras)", "label_title": "⚡ Feria Rápida", "color": "#22c55e", "default_emoji": "🥦"},
            {"key": "otras", "name": "Otras Compras (Carne, Pescado)", "label_title": "⚡ Otras Compras Rápido", "color": "#fb923c", "default_emoji": "🥩"},
            {"key": "panalera", "name": "Pañalera (Bebé)", "label_title": "⚡ Pañalera Rápida", "color": "#38bdf8", "default_emoji": "👶"},
            {"key": "cuidado", "name": "Cuidado Personal", "label_title": "⚡ Cuidado Personal Rápido", "color": "#ec4899", "default_emoji": "🧴"}
        ]
        for l_def in listas_definicion:
            st.markdown(f"<h5 style='color: {l_def['color']}; margin-top: 20px; margin-bottom: 10px;'>{l_def['label_title']}</h5>", unsafe_allow_html=True)
            items_rapidos = db.obtener_items_rapidos(username, l_def["name"])
            if not items_rapidos:
                st.info(f"No hay accesos rápidos de {l_def['name']}.")
            else:
                # Renderizar en columnas dinámicamente de a 3
                for chunk in [items_rapidos[i:i + 3] for i in range(0, len(items_rapidos), 3)]:
                    cols = st.columns(3)
                    for idx, r_item in enumerate(chunk):
                        with cols[idx]:
                            label = f"{r_item['icono']} {r_item['producto']}"
                            if st.button(label, use_container_width=True, key=f"btn_q_{l_def['key']}_{r_item['id']}"):
                                if db.agregar_item_compra(username, r_item['producto'], r_item['cantidad'], l_def["name"]):
                                    st.toast(f"{r_item['producto']} agregado.", icon=r_item['icono'])
                                    st.rerun()
            with st.expander(f"⚙️ Personalizar {l_def['name']} Rápido"):
                if items_rapidos:
                    for r_item in items_rapidos:
                        col_info, col_del = st.columns([4, 1])
                        with col_info:
                            st.write(f"{r_item['icono']} **{r_item['producto']}** ({r_item['cantidad']})")
                        with col_del:
                            if st.button("🗑️", key=f"del_qr_{l_def['key']}_{r_item['id']}", help="Eliminar de rápidos"):
                                if db.eliminar_item_rapido(username, r_item['id']):
                                    st.toast("Elemento rápido eliminado.", icon="🗑️")
                                    st.rerun()
                st.markdown(f"##### ➕ Agregar a {l_def['name']} Rápido")
                with st.form(f"form_add_qr_{l_def['key']}", clear_on_submit=True):
                    qr_producto = st.text_input("Producto", placeholder="Ej. Artículo", key=f"qr_prod_{l_def['key']}")
                    col_qr_c, col_qr_i = st.columns([2, 1])
                    with col_qr_c:
                        qr_cantidad = st.text_input("Cantidad/Formato", value="1 unit", key=f"qr_cant_{l_def['key']}")
                    with col_qr_i:
                        qr_icono = st.text_input("Icono (Emoji)", value=l_def["default_emoji"], key=f"qr_ico_{l_def['key']}")
                    btn_add_qr = st.form_submit_button("Agregar Opción Rápida")
                    if btn_add_qr:
                        if not qr_producto.strip():
                            st.error("Escribe el nombre del producto.")
                        else:
                            if db.agregar_item_rapido(username, qr_producto.strip(), qr_cantidad.strip(), l_def["name"], qr_icono.strip()):
                                st.toast("Opción rápida agregada.", icon="⚡")
                                st.rerun()
    with col_lista_compra:
        st.markdown("<div class='section-header'>📋 Hojas de Planificación de Compras</div>", unsafe_allow_html=True)
        items = db.obtener_items_compra(username)
        tab_super, tab_feria, tab_otras, tab_panalera, tab_cuidado = st.tabs([
            "🛒 Supermercado", 
            "🥦 Feria (Frutas y Vegetales)", 
            "🥩 Otras Compras (Carne, Pescado)", 
            "👶 Pañalera (Bebé)",
            "🧴 Cuidado Personal"
        ])
        # Definición del renderizador de pestañas
        def render_shopping_list_tab(list_name, list_color, default_expense_category, items_list, usr, bgt):
            items_this_list = [i for i in items_list if i.get("tipo_lista", "Supermercado") == list_name]
            # --- PLANIFICACIÓN DE TIENDA CONTEXTUAL ---
            if "Supermercado" in list_name:
                tiendas_def = ["Lider", "Jumbo", "Santa Isabel", "Tottus", "Acuenta", "Otro (Especificar)"]
                label_sel = "Supermercado al que irás"
            elif "Feria" in list_name:
                tiendas_def = ["Feria del Sábado", "Feria del Miércoles", "Feria Local", "Verdulería", "Otro (Especificar)"]
                label_sel = "Feria a la que irás"
            elif "Otras Compras" in list_name:
                tiendas_def = ["Carnicería Local", "Pescadería Local", "Lider", "Jumbo", "Otro (Especificar)"]
                label_sel = "Local/Supermercado al que irás"
            elif "Cuidado Personal" in list_name:
                tiendas_def = ["Preunic", "Maicao", "Farmacia Cruz Verde", "Farmacia Ahumada", "Farmacia Dr. Simi", "Supermercado", "Otro (Especificar)"]
                label_sel = "Perfumería/Farmacia a la que irás"
            else: # Pañalera
                tiendas_def = ["Pañalera del Barrio", "Supermercado", "Farmacia", "Otro (Especificar)"]
                label_sel = "Pañalera/Farmacia a la que irás"

            st.markdown(f"<div style='font-size: 0.95rem; font-weight: 600; color: {list_color}; margin-top: 5px; margin-bottom: 5px;'>📍 Planificación de Establecimiento</div>", unsafe_allow_html=True)
            col_sel_store, col_custom_store = st.columns(2)
            with col_sel_store:
                tienda_plan = st.selectbox(
                    label_sel,
                    tiendas_def,
                    key=f"plan_tienda_{l_def_tab_key(list_name)}",
                    label_visibility="collapsed"
                )
            with col_custom_store:
                if tienda_plan == "Otro (Especificar)":
                    tienda_plan_input = st.text_input(
                        "Especificar lugar",
                        placeholder="Ej: Minimarket Don Juan",
                        key=f"plan_tienda_input_{l_def_tab_key(list_name)}",
                        label_visibility="collapsed"
                    ).strip()
                else:
                    tienda_plan_input = tienda_plan
            
            st.markdown("<hr style='border-color: #1e293b; margin: 10px 0 15px 0;' />", unsafe_allow_html=True)
            if not items_this_list:
                st.info(f"No hay artículos en la lista de {list_name}.")
            else:
                pendientes = [i for i in items_this_list if i["comprado"] == 0]
                comprados = [i for i in items_this_list if i["comprado"] == 1]
                if pendientes:
                    st.markdown(f"<h5 style='color: {list_color}; margin-bottom: 12px;'>Pendientes por Comprar</h5>", unsafe_allow_html=True)
                    for item in pendientes:
                        col_chk, col_del = st.columns([9, 1])
                        with col_chk:
                            # Buscar mejor precio histórico del producto
                            mejor_precio = db.obtener_mejor_precio_historico(usr, item['producto'])
                            est_est = f" en {mejor_precio['establecimiento']}" if mejor_precio and mejor_precio.get('establecimiento') else ""
                            chk = st.checkbox(f"**{item['producto']}** ({item['cantidad']})", key=f"chk_p_{item['id']}", value=False)
                            # Mostrar precio estimado en la lista
                            if mejor_precio:
                                st.markdown(f"<div style='font-size: 0.82rem; color: #818cf8; margin-top: -12px; margin-left: 28px; margin-bottom: 8px;'>💡 Historial: {format_clp(mejor_precio['precio'])} {mejor_precio['marca'] or ''}{est_est}</div>", unsafe_allow_html=True)
                            if chk:
                                db.cambiar_estado_item_compra(usr, item['id'], True)
                                st.toast(f"Comprado: {item['producto']}", icon="✅")
                                st.rerun()
                        with col_del:
                            if st.button("🗑️", key=f"del_c_{item['id']}", help="Eliminar artículo"):
                                db.eliminar_item_compra(usr, item['id'])
                                st.toast("Artículo removido.", icon="🗑️")
                                st.rerun()
                if comprados:
                    st.markdown("<hr style='border-color: #1e293b; margin: 20px 0;' />", unsafe_allow_html=True)
                    st.markdown("<h5 style='color: #10b981; margin-bottom: 12px;'>Adquiridos</h5>", unsafe_allow_html=True)
                    st.markdown("<p style='font-size: 0.85rem; color: #9ca3af; margin-top: -5px;'>Ingresa la marca y precio pagado de cada artículo:</p>", unsafe_allow_html=True)
                    def on_change_details(item_id, k_brand, k_price):
                        new_brand = st.session_state[k_brand].strip()
                        try:
                            new_price = float(st.session_state[k_price])
                        except ValueError:
                            new_price = 0.0
                        db.actualizar_detalles_item_compra(usr, item_id, new_brand, new_price)
                    for item in comprados:
                        col_chk, col_brand, col_price, col_del = st.columns([4, 3, 2, 1])
                        with col_chk:
                            chk = st.checkbox(f"~~{item['producto']}~~", key=f"chk_c_active_{item['id']}", value=True)
                            if not chk:
                                db.cambiar_estado_item_compra(usr, item['id'], False)
                                st.toast(f"Devuelto: {item['producto']}", icon="🔄")
                                st.rerun()
                        with col_brand:
                            brand_val = item.get("marca", "")
                            st.text_input(
                                "Marca", 
                                value=brand_val, 
                                key=f"brand_val_{item['id']}", 
                                label_visibility="collapsed", 
                                placeholder="Marca (opcional)",
                                on_change=on_change_details,
                                args=(item['id'], f"brand_val_{item['id']}", f"price_val_{item['id']}")
                            )
                        with col_price:
                            price_val = float(item.get("precio", 0.0))
                            st.number_input(
                                "Precio ($)", 
                                min_value=0.0, 
                                value=price_val, 
                                key=f"price_val_{item['id']}", 
                                label_visibility="collapsed", 
                                step=500.0, 
                                format="%f",
                                on_change=on_change_details,
                                args=(item['id'], f"brand_val_{item['id']}", f"price_val_{item['id']}")
                            )
                        with col_del:
                            if st.button("🗑️", key=f"del_c_bought_{item['id']}", help="Eliminar artículo"):
                                db.eliminar_item_compra(usr, item['id'])
                                st.toast("Artículo removido.", icon="🗑️")
                                st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.container(border=True):
                        st.markdown(f"<h6 style='color: {list_color}; margin: 0;'>💸 Registrar Compra en Finanzas</h6>", unsafe_allow_html=True)
                        st.markdown("<p style='font-size: 0.8rem; color: #9ca3af; margin-bottom: 8px;'>Registra el costo de esta compra en tu historial de gastos.</p>", unsafe_allow_html=True)
                        suma_precios_ingresados = sum(float(i.get("precio", 0.0)) for i in comprados)
                        col_g_m, col_g_c = st.columns(2)
                        with col_g_m:
                            monto_gastado = st.number_input(
                                "Monto Gastado ($)", 
                                min_value=0, 
                                step=1000, 
                                value=int(suma_precios_ingresados), 
                                key=f"monto_g_{l_def_tab_key(list_name)}"
                            )
                        with col_g_c:
                            categoria_gasto = st.selectbox(
                                "Categoría de Finanzas",
                                ["Alimentos / Súper", "Sushi (Samagu, etc.)", "Hamburguesas (Wendy's / McDonald's)", "Pizza (Little Caesars)", "Delivery General", "Servicios (Luz, Agua, Gas)", "Otros Gastos"],
                                index=0 if default_expense_category == "Alimentos / Súper" else 6,
                                key=f"cat_g_{l_def_tab_key(list_name)}"
                            )
                        st.markdown(f"📍 **Registrando compra en**: `{tienda_plan_input}`")
                        tienda_input = tienda_plan_input
                        confirmar_limpieza = st.checkbox("Limpiar comprados al registrar", value=True, key=f"chk_clean_g_{l_def_tab_key(list_name)}")
                        if st.button("Registrar Gasto y Archivar", key=f"btn_reg_g_{l_def_tab_key(list_name)}", use_container_width=True):
                            if monto_gastado <= 0:
                                st.error("Ingresa un monto válido mayor a 0.")
                            else:
                                desc = f"Compra de {list_name} en {tienda_input}" if tienda_input else f"Compra de {list_name}"
                                if db.agregar_transaccion(usr, "Gasto", monto_gastado, categoria_gasto, desc, date.today().strftime('%Y-%m-%d'), es_hormiga=0):
                                    if confirmar_limpieza:
                                        db.limpiar_compras_completadas(usr, list_name, establecimiento=tienda_input)
                                    st.toast(f"Gasto de {format_clp(monto_gastado)} registrado en Finanzas.", icon="💸")
                                    st.rerun()
                                else:
                                    st.error("Error al guardar la transacción.")
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"🧹 Limpiar Comprados ({list_name.split()[0]})", use_container_width=True, key=f"btn_clean_{l_def_tab_key(list_name)}"):
                        db.limpiar_compras_completadas(usr, list_name, establecimiento=tienda_input if 'tienda_input' in locals() and tienda_input else None)
                        st.toast("Se limpiaron los productos comprados.", icon="🧹")
                        st.rerun()
        def l_def_tab_key(name):
            return name.split()[0].lower().replace("(", "").replace(")", "").replace(",", "")
        with tab_super:
            render_shopping_list_tab("Supermercado", "#818cf8", "Alimentos / Súper", items, username, presupuesto_actual)
        with tab_feria:
            render_shopping_list_tab("Feria (Frutas y Verduras)", "#22c55e", "Otros Gastos", items, username, presupuesto_actual)
        with tab_otras:
            render_shopping_list_tab("Otras Compras (Carne, Pescado)", "#fb923c", "Otros Gastos", items, username, presupuesto_actual)
        with tab_panalera:
            render_shopping_list_tab("Pañalera (Bebé)", "#38bdf8", "Otros Gastos", items, username, presupuesto_actual)
        with tab_cuidado:
            render_shopping_list_tab("Cuidado Personal", "#ec4899", "Otros Gastos", items, username, presupuesto_actual)


# 3. MÓDULO: Calendario Familiar

elif menu == "🗓️ Calendario Familiar":
    col_add_ev, col_lista_ev = st.columns([2, 3])
    with col_add_ev:
        st.markdown("<div class='section-header'>➕ Programar Evento</div>", unsafe_allow_html=True)
        with st.form("form_evento", clear_on_submit=True):
            nombre_evento = st.text_input("Concepto / Evento", placeholder="Ej. Pagar Electricidad, Cumpleaños Papá")
            tipo_evento = st.selectbox("Tipo de Recordatorio", ["Vencimiento", "Fecha Importante"])
            fecha_evento = st.date_input("Fecha Programada", value=date.today())
            btn_add_ev = st.form_submit_button("Guardar en Calendario")
            if btn_add_ev:
                if not nombre_evento.strip():
                    st.error("Escribe un nombre para el evento.")
                else:
                    if db.agregar_evento(username, nombre_evento.strip(), fecha_evento.strftime('%Y-%m-%d'), tipo_evento):
                        st.toast("Evento guardado.", icon="🗓️")
                        st.rerun()
    with col_lista_ev:
        st.markdown("<div class='section-header'>📅 Eventos y Recordatorios</div>", unsafe_allow_html=True)
        eventos = db.obtener_eventos(username)
        if not eventos:
            st.info("No hay eventos programados en el calendario.")
        else:
            tab_cuadros, tab_lista = st.tabs(["📅 Cuadros (Mes)", "📋 Lista de Eventos"])
            with tab_cuadros:
                # Inicializar variables de sesión para el mes y año del calendario
                if "cal_year" not in st.session_state:
                    st.session_state.cal_year = date.today().year
                if "cal_month" not in st.session_state:
                    st.session_state.cal_month = date.today().month

                # Botones de navegación de mes
                col_nav_prev, col_nav_month, col_nav_next = st.columns([1, 4, 1])
                with col_nav_prev:
                    if st.button("👈", key="btn_prev_month", use_container_width=True):
                        if st.session_state.cal_month == 1:
                            st.session_state.cal_month = 12
                            st.session_state.cal_year -= 1
                        else:
                            st.session_state.cal_month -= 1
                        st.rerun()
                with col_nav_month:
                    nombres_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                    nombre_mes = nombres_meses[st.session_state.cal_month - 1]
                    st.markdown(f"<h3 style='text-align: center; color: #818cf8; margin: 0;'>{nombre_mes} {st.session_state.cal_year}</h3>", unsafe_allow_html=True)
                with col_nav_next:
                    if st.button("👉", key="btn_next_month", use_container_width=True):
                        if st.session_state.cal_month == 12:
                            st.session_state.cal_month = 1
                            st.session_state.cal_year += 1
                        else:
                            st.session_state.cal_month += 1
                        st.rerun()
                
                # Renderizar la grilla del calendario mensual
                cal_html = render_month_calendar(st.session_state.cal_year, st.session_state.cal_month, eventos, username)
                st.markdown(cal_html, unsafe_allow_html=True)
                
            with tab_lista:
                hoy = date.today()

                # 1. Alertas de los Próximos 7 días
                eventos_proximos = []
                for ev in eventos:
                    fecha_ev = datetime.strptime(ev["fecha"], "%Y-%m-%d").date()
                    dif = (fecha_ev - hoy).days
                    if 0 <= dif <= 7 and ev["completado"] == 0:
                        eventos_proximos.append((ev, dif))
                if eventos_proximos:
                    st.markdown("<h5 style='color: #ef4444; margin-bottom: 12px;'>🔥 Crítico: Próximos 7 Días</h5>", unsafe_allow_html=True)
                    for ev, dif in eventos_proximos:
                        badge_style = "badge-vencimiento" if ev["tipo"] == "Vencimiento" else "badge-importante"
                        dias_str = "Hoy" if dif == 0 else "Mañana" if dif == 1 else f"En {dif} días"
                        col_ev, col_del = st.columns([9, 1])
                        with col_ev:
                            st.markdown(f"""
                                <div class="tx-row" style="border-left: 5px solid #ef4444;">
                                    <div class="tx-date" style="color: #ef4444; font-weight: bold;">{dias_str}</div>
                                    <div class="tx-info">
                                        <span class="tx-title">{ev['evento']}</span>
                                        <span class="badge {badge_style}">{ev['tipo']}</span>
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                        with col_del:
                            if st.button("🗑️", key=f"del_ev_p_{ev['id']}"):
                                db.eliminar_evento(username, ev['id'])
                                st.toast("Evento eliminado.", icon="🗑️")
                                st.rerun()
                    st.markdown("<hr style='border-color: #1e293b; margin: 20px 0;' />", unsafe_allow_html=True)
                
                # Pestañas para dividir Vencimientos y Fechas Importantes dentro de la lista
                tab_venc, tab_imp = st.tabs(["⚠️ Vencimientos y Cuentas", "🎉 Fechas Importantes"])
            with tab_venc:
                vencimientos = [e for e in eventos if e["tipo"] == "Vencimiento"]
                if not vencimientos:
                    st.info("No hay cuentas por pagar registradas.")
                else:
                    for ev in vencimientos:
                        fecha_ev = datetime.strptime(ev["fecha"], "%Y-%m-%d").date()
                        dif = (fecha_ev - hoy).days
                        if ev["completado"] == 1:
                            estado_txt = "Completado / Pagado"
                            color_style = "color: #10b981;"
                            border_style = "#10b981"
                        elif dif < 0:
                            estado_txt = f"Atrasado por {-dif} días"
                            color_style = "color: #ef4444; font-weight: bold;"
                            border_style = "#ef4444"
                        elif dif == 0:
                            estado_txt = "Vence Hoy"
                            color_style = "color: #f59e0b; font-weight: bold;"
                            border_style = "#f59e0b"
                        else:
                            estado_txt = f"Faltan {dif} días"
                            color_style = "color: #38bdf8;"
                            border_style = "#1e293b"
                        col_dat, col_act = st.columns([8, 2])
                        with col_dat:
                            linea_tachada = "~~" if ev["completado"] == 1 else ""
                            st.markdown(f"""
                                <div class="tx-row" style="border-color: {border_style};">
                                    <div class="tx-date">{fecha_ev.strftime('%d/%m/%Y')}</div>
                                    <div class="tx-info">
                                        <span class="tx-title">{linea_tachada}{ev['evento']}{linea_tachada}</span>
                                    </div>
                                    <div style="font-size: 0.85rem; {color_style}">{estado_txt}</div>
                                </div>
                            """, unsafe_allow_html=True)
                        with col_act:
                            col_chk, col_del = st.columns(2)
                            with col_chk:
                                icon = "🔄" if ev["completado"] == 1 else "✅"
                                help_t = "Marcar como pendiente" if ev["completado"] == 1 else "Marcar como pagado"
                                if st.button(icon, key=f"btn_chk_v_{ev['id']}", help=help_t):
                                    db.cambiar_estado_evento(username, ev['id'], not ev["completado"])
                                    st.toast("Estado de vencimiento modificado.", icon="✅")
                                    st.rerun()
                            with col_del:
                                if st.button("🗑️", key=f"btn_del_v_{ev['id']}", help="Eliminar recordatorio"):
                                    db.eliminar_evento(username, ev['id'])
                                    st.toast("Recordatorio eliminado.", icon="🗑️")
                                    st.rerun()
            with tab_imp:
                importantes = [e for e in eventos if e["tipo"] == "Fecha Importante"]
                if not importantes:
                    st.info("No hay fechas importantes registradas.")
                else:
                    for ev in importantes:
                        fecha_ev = datetime.strptime(ev["fecha"], "%Y-%m-%d").date()
                        dif = (fecha_ev - hoy).days
                        if dif < 0:
                            estado_txt = f"Pasó hace {-dif} días"
                            color_style = "color: #6b7280;"
                        elif dif == 0:
                            estado_txt = "¡Hoy! 🎉"
                            color_style = "color: #c084fc; font-weight: bold;"
                        else:
                            estado_txt = f"Faltan {dif} días"
                            color_style = "color: #a5b4fc;"
                        col_dat, col_del = st.columns([9, 1])
                        with col_dat:
                            st.markdown(f"""
                                <div class="tx-row">
                                    <div class="tx-date">{fecha_ev.strftime('%d/%m/%Y')}</div>
                                    <div class="tx-info">
                                        <span class="tx-title">{ev['evento']}</span>
                                    </div>
                                    <div style="font-size: 0.85rem; {color_style}">{estado_txt}</div>
                                </div>
                            """, unsafe_allow_html=True)
                        with col_del:
                            if st.button("🗑️", key=f"btn_del_i_{ev['id']}", help="Eliminar recordatorio"):
                                db.eliminar_evento(username, ev['id'])
                                st.toast("Recordatorio eliminado.", icon="🗑️")
                                st.rerun()

# 4. MÓDULO: Misiones del Hogar

elif menu == "⚔️ Misiones del Hogar":
    col_quests_left, col_quests_right = st.columns([3, 2])
    with col_quests_left:
        st.markdown("<div class='section-header'>📜 Tablero de Misiones del Gremio</div>", unsafe_allow_html=True)
        st.write("Completa estas misiones cotidianas para ganar experiencia y mantener tu hogar limpio y ordenado. Una vez completadas, se bloquearán y pasarán al registro de completadas.")
        # Cargar misiones dinámicas desde SQLite para el usuario
        misiones_definicion = db.obtener_misiones(username)
        # Leer el estado de completado de cada misión desde la base de datos
        misiones_estados = {}
        for m in misiones_definicion:
            misiones_estados[m["clave"]] = db.obtener_variable(username, m["clave"], "False") == "True"
        misiones_activas = [m for m in misiones_definicion if not misiones_estados[m["clave"]]]
        misiones_completadas = [m for m in misiones_definicion if misiones_estados[m["clave"]]]
        def reiniciar_misiones():
            for m in misiones_definicion:
                db.guardar_variable(username, m["clave"], "False")
            st.toast("Tablero de misiones reiniciado.", icon="🔄")
            st.rerun()
        def completar_mision(xp_ganada, quest_key):
            # Guardar en base de datos de manera persistente
            db.guardar_variable(username, quest_key, "True")
            # Sumar XP
            st.session_state.xp += xp_ganada
            st.toast(f"¡Tarea Completada! +{xp_ganada} XP", icon="🏡")
            if st.session_state.xp >= 100:
                st.session_state.xp = st.session_state.xp % 100
                st.session_state.lvl += 1
                st.balloons()
                st.toast("¡Felicitaciones! ¡Nuestro Hogar ha evolucionado de nivel! 🌟", icon="🏡")
            db.guardar_variable(username, "xp", st.session_state.xp)
            db.guardar_variable(username, "lvl", st.session_state.lvl)
            st.rerun()
        # Renderizar misiones activas
        st.markdown("#### 📋 Misiones y Tareas Disponibles")
        if misiones_activas:
            for m in misiones_activas:
                st.checkbox(
                    f"{m['label']} (+{m['xp']} XP)", 
                    key=f"chk_active_{m['clave']}", 
                    value=False,
                    on_change=completar_mision, 
                    args=(m["xp"], m["clave"])
                )
        else:
            st.markdown("""
                <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; border-radius: 8px; padding: 15px; color: #34d399; font-weight: bold; text-align: center; margin-bottom: 20px;">
                    🎉 ¡Felicidades! Has completado todas las misiones del gremio para hoy.
                </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### ✅ Misiones Completadas hoy")
        if misiones_completadas:
            for m in misiones_completadas:
                st.markdown(f"🏆 <span style='text-decoration: line-through; color: #6b7280; font-size: 1rem;'>{m['label']}</span> <span style='color: #10b981; font-weight: bold; font-size: 0.85rem;'>+{m['xp']} XP</span>", unsafe_allow_html=True)
        else:
            st.info("Aún no has completado ninguna misión hoy. ¡Manos a la obra, aventurero!")
        st.markdown("<br><hr style='border-color: #1e293b; margin: 20px 0;' />", unsafe_allow_html=True)
        st.button("🔄 Reiniciar Misiones Diarias", key="btn_reset_quests_main", on_click=reiniciar_misiones, use_container_width=True)
        # Expander para Administrar Misiones
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🔧 Administrar Tablero de Misiones"):
            st.markdown("##### ➕ Agregar Nueva Misión")
            with st.form("form_add_mision", clear_on_submit=True):
                nueva_mision_label = st.text_input("Nombre de la Misión", placeholder="Ej. Limpiar ventanas, Regar plantas")
                nueva_mision_xp = st.number_input("Recompensa de Experiencia (Máx: 40 XP)", min_value=1, max_value=40, value=15, step=1)
                # Verificador: checkbox de confirmación
                st.warning("⚠️ Verificación requerida:")
                confirmar_adicion = st.checkbox("¿Estás seguro de que deseas agregar esta misión?", value=False, key="chk_conf_add_mision")
                btn_add_mision = st.form_submit_button("Agregar Misión")
                if btn_add_mision:
                    if not nueva_mision_label.strip():
                        st.error("Por favor, escribe el nombre de la misión.")
                    elif not confirmar_adicion:
                        st.warning("Debes marcar la casilla verificadora para agregar la misión.")
                    else:
                        if db.agregar_mision(username, nueva_mision_label.strip(), nueva_mision_xp):
                            st.toast("Misión agregada al tablero.", icon="⚔️")
                            st.rerun()
                        else:
                            st.error("Error al guardar la misión.")
            st.markdown("<hr style='border-color: #1e293b; margin: 20px 0;' />", unsafe_allow_html=True)
            st.markdown("##### 🗑️ Eliminar Misiones Existentes")
            for m in misiones_definicion:
                col_m_name, col_m_action = st.columns([3, 2])
                with col_m_name:
                    st.write(f"{m['label']} ({m['xp']} XP)")
                with col_m_action:
                    # Popover de confirmación para eliminar
                    with st.popover("🗑️ Eliminar", use_container_width=True):
                        st.write("¿Estás seguro de que deseas eliminar esta misión?")
                        confirmar_eliminacion = st.checkbox("Confirmar eliminación", value=False, key=f"chk_conf_del_{m['id']}")
                        if st.button("Sí, eliminar", key=f"btn_del_q_{m['id']}", use_container_width=True):
                            if confirmar_eliminacion:
                                if db.eliminar_mision(username, m['id']):
                                    st.toast("Misión eliminada del tablero.", icon="🗑️")
                                    st.rerun()
                                else:
                                    st.error("No se pudo eliminar.")
                            else:
                                st.warning("Debes marcar la casilla verificadora para confirmar.")
    with col_quests_right:
        st.markdown("<div class='section-header'>🏡 Progreso de Nuestro Hogar</div>", unsafe_allow_html=True)
        st.write("Nivel y estado de evolución de la casa familiar:")
        emoji, titulo = obtener_etapa_hogar(st.session_state.lvl)
        gremio_status = f"""
            <div style="text-align: center; padding: 25px; border-radius: 12px; background: linear-gradient(135deg, rgba(251, 146, 60, 0.08), rgba(236, 72, 153, 0.08)); border: 2px solid rgba(251, 146, 60, 0.2); box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05); font-family: sans-serif;">
                <div style="font-size: 4.5rem; margin-bottom: 10px;">{emoji}</div>
                <h4 style="color: #f97316; font-weight: 700; margin: 0 0 5px 0; font-size: 1.4rem;">{titulo}</h4>
                <p style="color: #4b5563; margin: 0 0 15px 0; font-size: 0.95rem; font-weight: 500;">Etapa actual del desarrollo de nuestra casa</p>
                <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 0.95rem; color: #4b5563; margin-bottom: 5px;">
                    <span>Nivel {st.session_state.lvl}</span>
                    <span>{st.session_state.xp} / 100 XP</span>
                </div>
                <div style="background: rgba(226, 232, 240, 0.4); border-radius: 10px; height: 12px; overflow: hidden; border: 1px solid rgba(203, 213, 225, 0.3);">
                    <div style="background: linear-gradient(90deg, #f97316, #ec4899); height: 100%; width: {st.session_state.xp}%; border-radius: 10px;"></div>
                </div>
            </div>
        """
        render_html(gremio_status)
# 5. MÓDULO: Asesor de Compras IA
elif menu == "🛍️ Asesor de Compras IA":
    api_key = st.session_state.get("gemini_api_key", "")
    if not api_key:
        st.markdown("""
            <div class="premium-card" style="border-color: #f59e0b; background: rgba(245, 158, 11, 0.05); text-align: center; padding: 40px; margin-top: 20px;">
                <div style="font-size: 3rem; margin-bottom: 20px;">🔒</div>
                <h4 style="color: #f59e0b; font-weight: 600;">Asesor de Compras IA Desactivado</h4>
                <p style="color: #d1d5db; max-width: 550px; margin: 0 auto 20px auto; font-size: 0.95rem; line-height: 1.5;">
                    Para evaluar compras y recibir recomendaciones personalizadas basadas en tus finanzas actuales, introduce tu <strong>Gemini API Key</strong> en el panel lateral de configuración.
                </p>
                <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color: #818cf8; text-decoration: none; font-weight: 600; font-size: 0.95rem;">
                    👉 Obtén tu clave de API gratis aquí 👈
                </a>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("### 🛍️ Asesor de Compras e Inteligencia Artificial")
        st.write("Planificación inteligente, estimación de precios y rutas de ahorro para tus compras en Chile.")
        
        # Obtener presupuesto de compras (compartido con el módulo principal)
        presupuesto_key = "presupuesto_compras"
        presupuesto_actual = int(db.obtener_variable(username, presupuesto_key, 0))
        
        # Grid de presupuesto
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            st.markdown(f"#### 💰 Presupuesto de Salida: <span style='color: #10b981; font-weight: bold;'>{format_clp(presupuesto_actual)}</span>", unsafe_allow_html=True)
        with col_p2:
            with st.popover("⚙️ Ajustar Presupuesto", use_container_width=True):
                nuevo_presupuesto = st.number_input("Nuevo Presupuesto ($)", min_value=0, value=presupuesto_actual, step=5000, format="%d", key="btn_compras_ia_bgt")
                if st.button("Guardar Presupuesto", use_container_width=True, key="btn_save_presupuesto_compras_ia"):
                    db.guardar_variable(username, presupuesto_key, nuevo_presupuesto)
                    st.toast("Presupuesto de compras actualizado.", icon="💾")
                    st.rerun()

        # Obtener artículos
        items = db.obtener_items_compra(username)
        pendientes_todos = [i for i in items if i["comprado"] == 0]
        
        if not pendientes_todos:
            st.info("No hay artículos pendientes en tu lista de compras para analizar.")
        else:
            with st.container(border=True):
                st.markdown("##### 📋 Artículos Pendientes a Evaluar")
                # Agrupar por lista
                grouped = {}
                for item in pendientes_todos:
                    grouped.setdefault(item.get("tipo_lista", "Supermercado"), []).append(f"{item['producto']} ({item['cantidad']})")
                for t_list, p_items in grouped.items():
                    st.markdown(f"**{t_list}**: {', '.join(p_items)}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("🤖 Calcular Estimación de Precios IA", use_container_width=True, key="btn_estimar_precios_ia_new_page"):
                with st.spinner("Buscando precios de referencia y calculando estimación..."):
                    try:
                        # Lista formateada
                        lista_texto = "\n".join([f"- {item['producto']} (Cantidad: {item['cantidad']}) [Lista: {item.get('tipo_lista', 'Supermercado')}]" for item in pendientes_todos])
                        # Cargar historial de precios reales
                        historial_db = db.obtener_historial_precios(username)
                        historial_texto = ""
                        if historial_db:
                            historial_texto = "\nHistorial de precios reales pagados anteriormente por el usuario (Úsalos como tu primera fuente de referencia exacta):\n"
                            for h in historial_db[:20]:
                                historial_texto += f"- {h['producto']} (Marca: {h['marca'] if h['marca'] else 'Sin especificar'}): {format_clp(h['precio'])} (Fecha: {h['fecha']})\n"
                        
                        system_prompt_compras = f"""
                        Eres un asistente de compras experto en Chile. Tu tarea es estimar los precios de mercado aproximados (en pesos chilenos, CLP) de una lista de compras.
                        IMPORTANTE: Se te proporciona un historial de precios de compras anteriores realizadas por el usuario. Si un producto de la lista pendiente coincide con un producto del historial de precios, DEBES usar el precio histórico registrado (y mencionar la marca y que es un dato histórico suyo) como tu estimación de referencia.
                        Por favor, analiza la lista entregada y proporciona:
                        1. Un desglose estimado del valor de cada artículo.
                        2. El costo total estimado del carro.
                        3. Una comparación breve con el presupuesto de compras del usuario ({format_clp(presupuesto_actual)}). Indica si el costo supera el presupuesto o si está dentro de lo planeado.
                        4. Consejos útiles para ahorrar en esta lista (ej: marcas propias de supermercados como Lider, marcas de feria, etc.).
                        Usa formato limpio en markdown, con el símbolo "$" y sin decimales en los precios (separador de miles con puntos, ej: $1.500).
                        """
                        prompt_text = f"Esta es mi lista de compras pendiente:\n{lista_texto}\n{historial_texto}"
                        
                        resultado = ""
                        last_err = None
                        for candidate in AI_MODEL_CANDIDATES:
                            try:
                                model = genai.GenerativeModel(model_name=candidate, system_instruction=system_prompt_compras)
                                response = model.generate_content(prompt_text)
                                resultado = response.text
                                break
                            except Exception as e:
                                last_err = e
                                continue
                        if not resultado:
                            st.error("Los servidores de IA están saturados en este momento. Por favor, intenta de nuevo más tarde.")
                        else:
                            st.session_state["ultimo_analisis_compras_ia"] = resultado
                    except Exception as e:
                        st.error(f"Error al estimar precios: {str(e)}")
            
            if "ultimo_analisis_compras_ia" in st.session_state:
                st.markdown("---")
                st.markdown("##### 💡 Análisis y Recomendaciones Obtenidas")
                st.markdown(st.session_state["ultimo_analisis_compras_ia"])


elif menu == "👨‍🍳 El Chef del Hogar":
    api_key = st.session_state.get("gemini_api_key", "")
    if not api_key:
        st.markdown("""
            <div class="premium-card" style="border-color: #f59e0b; background: rgba(245, 158, 11, 0.05); text-align: center; padding: 40px; margin-top: 20px;">
                <div style="font-size: 3rem; margin-bottom: 20px;">🔒</div>
                <h4 style="color: #f59e0b; font-weight: 600;">Chef del Hogar Desactivado</h4>
                <p style="color: #d1d5db; max-width: 550px; margin: 0 auto 20px auto; font-size: 0.95rem; line-height: 1.5;">
                    Para recibir sugerencias de recetas basadas en los ingredientes que tienes, introduce tu <strong>Gemini API Key</strong> en el panel lateral de configuración.
                </p>
                <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color: #818cf8; text-decoration: none; font-weight: 600; font-size: 0.95rem;">
                    👉 Obtén tu clave de API gratis aquí 👈
                </a>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("### 👨‍🍳 El Chef del Hogar")
        st.write("Genera recetas creativas y deliciosas basadas en los ingredientes que tienes en tu refrigerador y despensa.")
        
        with st.container(border=True):
            st.markdown("##### 📝 ¿Qué tienes en casa?")
            ingredientes = st.text_input("Ingredientes (separados por comas)", placeholder="Ej: fideos, crema, champiñones, ajo, queso rallado")
            
            # Preferencias
            col1, col2 = st.columns(2)
            with col1:
                tipo_plato = st.selectbox("Tipo de Comida", ["Almuerzo / Cena", "Desayuno", "Postre / Dulce", "Picoteo / Entrada"])
            with col2:
                tiempo_disp = st.selectbox("Tiempo Disponible", ["Rápido (menos de 20 min)", "Normal (20-40 min)", "Elaborado (más de 40 min)"])
                
            btn_receta = st.button("🍳 ¡Cocinar con lo que tengo!", use_container_width=True, type="primary")
            
        if btn_receta:
            if not ingredientes.strip():
                st.warning("Por favor, ingresa al menos un ingrediente.")
            else:
                with st.spinner("El Chef de IA está ideando una receta deliciosa..."):
                    try:
                        system_prompt_chef = """
                        Eres un chef profesional chileno experto en optimizar ingredientes y cocina casera rápida.
                        Tu tarea es sugerir una o dos recetas deliciosas y fáciles de preparar con los ingredientes indicados por el usuario, pudiendo asumir condimentos básicos de cocina (sal, aceite, pimienta, agua).
                        Estructura tu respuesta en markdown con:
                        1. 📝 Nombre de la Receta (con emojis atractivos).
                        2. ⏱️ Tiempo estimado de preparación y dificultad.
                        3. 🛒 Ingredientes requeridos (resaltando los que el usuario tiene y listando opcionales si hicieran falta).
                        4. 🍳 Instrucciones paso a paso muy fáciles de seguir.
                        5. 💡 Tips del chef para mejorar el sabor, presentación o ahorrar gas/luz.
                        Mantén un tono alegre, inspiracional y chileno (ej: '¡A cocinar se ha dicho!', 'buen provecho').
                        """
                        prompt_text = f"Tengo los siguientes ingredientes: {ingredientes}. Tipo de plato deseado: {tipo_plato}. Tiempo disponible: {tiempo_disp}."
                        
                        resultado = ""
                        last_err = None
                        for candidate in AI_MODEL_CANDIDATES:
                            try:
                                model = genai.GenerativeModel(model_name=candidate, system_instruction=system_prompt_chef)
                                response = model.generate_content(prompt_text)
                                resultado = response.text
                                break
                            except Exception as e:
                                last_err = e
                                continue
                                
                        if not resultado:
                            st.error("Los servidores de IA están saturados en este momento. Por favor, intenta de nuevo más tarde.")
                        else:
                            st.session_state["ultima_receta_chef_ia"] = resultado
                            st.success("¡Receta generada con éxito!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error al generar receta: {str(e)}")
                        
        if "ultima_receta_chef_ia" in st.session_state:
            st.markdown("---")
            st.markdown("##### 🍽️ Receta Recomendada para Hoy")
            st.markdown(st.session_state["ultima_receta_chef_ia"])
            if st.button("🗑️ Limpiar Receta", use_container_width=True):
                del st.session_state["ultima_receta_chef_ia"]
                st.rerun()


# 6. MÓDULO: Asesor del Hogar IA
elif menu == "🤖 Asesor del Hogar IA":
    api_key = st.session_state.get("gemini_api_key", "")
    if not api_key:
        api_key = st.secrets.get("gemini_key") or st.secrets.get("api", {}).get("gemini_key")
        if api_key:
            st.session_state["gemini_api_key"] = api_key
    if not api_key:
        st.markdown("""
            <div class="premium-card" style="border-color: #f59e0b; background: rgba(245, 158, 11, 0.05); text-align: center; padding: 40px; margin-top: 20px;">
                <div style="font-size: 3rem; margin-bottom: 20px;">🔒</div>
                <h4 style="color: #f59e0b; font-weight: 600;">Asesor Financiero IA Desactivado</h4>
                <p style="color: #d1d5db; max-width: 550px; margin: 0 auto 20px auto; font-size: 0.95rem; line-height: 1.5;">
                    Para evaluar compras y recibir recomendaciones personalizadas basadas en tus finanzas actuales, introduce tu <strong>Gemini API Key</strong> en el panel lateral de configuración.
                </p>
                <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color: #818cf8; text-decoration: none; font-weight: 600; font-size: 0.95rem;">
                    👉 Obtén tu clave de API gratis aquí 👈
                </a>
            </div>
        """, unsafe_allow_html=True)
    else:
        resumen = db.obtener_resumen_financiero(username)
        saldo_disp = resumen["saldo"]
        # Definición de herramientas (Tools) locales para que la IA actúe en el hogar
        def crear_evento_calendario(evento: str, fecha: str, tipo_recordatorio: str, repetir_meses: int = 0, repetir_semanas: int = 0) -> str:
            """
            Crea un evento o recordatorio en el calendario familiar de la aplicación.
            Permite programar la repetición periódica automática (mensual o semanal) si se le solicita.
            Args:
                evento: Concepto o descripción del evento (ej. 'Pagar luz', 'Cumpleaños de Papá').
                fecha: Fecha programada o fecha del primer evento en formato exacto 'YYYY-MM-DD' (ej. '2026-06-15').
                tipo_recordatorio: Tipo de recordatorio, debe ser una de estas opciones exactas: 'Vencimiento' o 'Fecha Importante'.
                repetir_meses: Número de meses adicionales para repetir este evento mensualmente (ej. 11 para repetir el 10 de cada mes durante 1 año). Usa 0 para no repetir.
                repetir_semanas: Número de semanas adicionales para repetir este evento semanalmente. Usa 0 para no repetir.
            """
            try:
                start_date = datetime.strptime(fecha.strip(), "%Y-%m-%d").date()
            except ValueError:
                return "Error: Formato de fecha inválido. Debe ser YYYY-MM-DD."
            
            exito = db.agregar_evento(username, evento.strip(), start_date.strftime('%Y-%m-%d'), tipo_recordatorio.strip())
            if not exito:
                return "Error: No se pudo guardar el evento principal."
            
            try:
                repetir_meses = int(repetir_meses)
            except (ValueError, TypeError):
                repetir_meses = 0
            try:
                repetir_semanas = int(repetir_semanas)
            except (ValueError, TypeError):
                repetir_semanas = 0
            
            inserted = 1
            if repetir_meses > 0:
                import calendar
                for m in range(1, repetir_meses + 1):
                    year = start_date.year + (start_date.month + m - 1) // 12
                    month = (start_date.month + m - 1) % 12 + 1
                    day = start_date.day
                    last_day_of_month = calendar.monthrange(year, month)[1]
                    target_day = min(day, last_day_of_month)
                    next_date = date(year, month, target_day)
                    db.agregar_evento(username, evento.strip(), next_date.strftime('%Y-%m-%d'), tipo_recordatorio.strip())
                    inserted += 1
            elif repetir_semanas > 0:
                from datetime import timedelta
                for w in range(1, repetir_semanas + 1):
                    next_date = start_date + timedelta(weeks=w)
                    db.agregar_evento(username, evento.strip(), next_date.strftime('%Y-%m-%d'), tipo_recordatorio.strip())
                    inserted += 1
            
            return f"Éxito: Se crearon {inserted} eventos de '{evento}' en el calendario (inicio: {fecha})."
        def agregar_articulo_compra(producto: str, cantidad: str, destino_compra: str) -> str:
            """
            Agrega un nuevo artículo de compra a la lista especificada.
            Args:
                producto: Nombre del artículo (ej. 'Merluza', 'Pañales Pampers').
                cantidad: Cantidad o formato (ej. '2 kg', '1 paquete').
                destino_compra: Nombre exacto de la lista donde agregar. Debe ser una de estas opciones exactas: 
                                 'Supermercado', 'Feria (Frutas y Verduras)', 'Otras Compras (Carne, Pescado)'  'Pañalera (Bebé)' o 'Cuidado Personal'.
            """
            exito = db.agregar_item_compra(username, producto.strip(), cantidad.strip(), destino_compra.strip())
            if exito:
                return f"Éxito: Se agregó '{producto}' ({cantidad}) en la lista '{destino_compra}'."
            else:
                return f"Error: No se pudo agregar a la lista '{destino_compra}'."
        def agregar_tarea_aseo(nombre_tarea: str, xp_recompensa: int) -> str:
            """
            Agrega una nueva misión o tarea diaria de aseo/limpieza al Tablero de Misiones.
            Args:
                nombre_tarea: Descripción de la tarea (ej. 'Limpiar la estufa', 'Lavar el auto').
                xp_recompensa: Recompensa en puntos de experiencia (número entero entre 5 y 40).
            """
            xp_val = max(1, min(int(xp_recompensa), 40))
            exito = db.agregar_mision(username, nombre_tarea.strip(), xp_val)
            if exito:
                return f"Éxito: Se añadió la misión '{nombre_tarea}' (+{xp_val} XP) al Tablero."
            else:
                return "Error: No se pudo añadir la misión al tablero."
        def obtener_resumen_hogar() -> str:
            """
            Retorna un resumen de la información actual del hogar, incluyendo saldo financiero,
            misiones/tareas de aseo activas, eventos o cuentas por pagar del calendario,
            la lista de compras pendientes en todas las pestañas, y un resumen del historial
            de precios y tiendas para guiar las mejores decisiones de compra.
            """
            resumen_fin = db.obtener_resumen_financiero(username)
            saldo = resumen_fin["saldo"]
            ingresos = resumen_fin["ingresos"]
            gastos = resumen_fin["gastos"]
            # Análisis de Gastos Hormiga del mes en curso
            all_txs = db.obtener_transacciones(username)
            current_month = datetime.today().strftime('%Y-%m')
            gastos_mes = 0
            hormiga_mes = 0
            for tx in all_txs:
                if tx['fecha'].startswith(current_month):
                    if tx['tipo'] == 'Gasto':
                        gastos_mes += tx['monto']
                        if tx.get('es_hormiga') == 1:
                            hormiga_mes += tx['monto']
            eventos = db.obtener_eventos(username)
            eventos_pendientes = [ev for ev in eventos if ev.get("completado") == 0]
            misiones = db.obtener_misiones(username)
            compras = db.obtener_items_compra(username)
            compras_pendientes = [c for c in compras if c.get("comprado") == 0]
            # Historial de precios
            historial = db.obtener_historial_precios(username)
            best_prices = {}
            for h in historial:
                prod = h['producto'].lower().strip()
                price = h['precio']
                est = h.get('establecimiento') or "Sin local"
                brand = h.get('marca') or "Sin marca"
                if prod not in best_prices or price < best_prices[prod]['precio']:
                    best_prices[prod] = {'precio': price, 'marca': brand, 'establecimiento': est}
            res = []
            res.append(f"Resumen del Hogar de {username_display}:")
            res.append(f"- Finanzas Acumuladas: Saldo: {format_clp(saldo)}, Ingresos: {format_clp(ingresos)}, Gastos: {format_clp(gastos)}")
            res.append(f"- Finanzas de este mes ({current_month}): Gastos Totales: {format_clp(gastos_mes)}, de los cuales Gastos Hormiga: {format_clp(hormiga_mes)}")
            if eventos_pendientes:
                res.append("- Calendario (Eventos Pendientes):")
                for ev in eventos_pendientes:
                    res.append(f"  * [{ev['tipo']}] {ev['evento']} para el {ev['fecha']}")
            else:
                res.append("- Calendario: No hay eventos pendientes.")
            if misiones:
                res.append("- Misiones de Aseo Activas:")
                for m in misiones:
                    res.append(f"  * {m['label']} (+{m['xp']} XP)")
            else:
                res.append("- Misiones de Aseo: No hay misiones programadas.")
            if compras_pendientes:
                res.append("- Compras Pendientes:")
                por_lista = {}
                for c in compras_pendientes:
                    t_list = c.get("tipo_lista", "Otros")
                    por_lista.setdefault(t_list, []).append(f"{c['producto']} ({c['cantidad']})")
                for t_list, items in por_lista.items():
                    res.append(f"  * {t_list}: {', '.join(items)}")
            else:
                res.append("- Lista de Compras: No hay compras pendientes.")
            if best_prices:
                res.append("- Historial de Precios Más Convenientes en tu Base de Datos:")
                for prod, details in sorted(best_prices.items())[:20]:
                    res.append(f"  * {prod.title()}: {format_clp(details['precio'])} (Marca: {details['marca']} en {details['establecimiento']})")
            return "\n".join(res)
        st.markdown(f"""
            <div class="premium-card" style="border-left: 5px solid #6366f1;">
                <h5 style="margin-bottom: 8px; font-weight: 600; color: #f3f4f6;">💡 ¿Cómo consultarle al Asistente {username_display}?</h5>
                <p style="font-size: 0.9rem; color: #9ca3af; margin: 0; line-height: 1.5;">
                    El asistente lee tu <strong>Saldo Disponible actual ({format_clp(saldo_disp)})</strong> y te ayuda a planificar compras,
                    agendar eventos de calendario o asignar tareas de aseo en tu tablero mediante lenguaje natural.
                </p>
            </div>
        """, unsafe_allow_html=True)
        # Inicializar historial de chat
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        # Contenedor para el scroll del chat
        st.markdown(f"##### 💬 Conversación con Asistente {username_display}")
        # Mostrar historial existente
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        # Entrada de prompt de usuario
        if prompt := st.chat_input("Ej: Agenda pagar el agua el 15 de junio y agrega comprar carne en Otras Compras..."):
            # Mostrar mensaje del usuario
            with st.chat_message("user"):
                st.markdown(prompt)
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            # Procesar con Gemini
            with st.chat_message("assistant"):
                res_box = st.empty()
                with st.spinner("Procesando tu solicitud y coordinando tareas del hogar..."):
                    try:
                        genai.configure(api_key=api_key)
                        # Prompt del sistema dinámico con el saldo en tiempo real
                        system_prompt = f"""
                        Eres "{username_display} Asistente", el asistente inteligente oficial para la gestión del hogar.
                        FECHA Y HORA ACTUAL DEL SISTEMA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Día: {datetime.now().strftime('%A')})
                        IMPORTANTE: Usa siempre este año, mes y día de referencia para agendar o calcular fechas cuando el usuario hable de "hoy", "mañana", "el próximo mes", o de manera genérica.
                        Tu objetivo es ayudar a la familia en múltiples áreas: tomar decisiones financieras inteligentes, organizar tareas de aseo, programar recordatorios, analizar gastos mensuales (incluyendo gastos hormiga) y optimizar las compras del hogar.
                        SISTEMA DE NOTIFICACIONES (CAMPANA):
                        - El sistema cuenta con una campana de notificaciones persistente en el menú lateral.
                        - Para los recordatorios o eventos de tipo 'Vencimiento' creados, esta campana alertará AUTOMÁTICAMENTE al usuario cuando falten 3 días, 2 días, 1 día, y el mismo día del vencimiento (y si está atrasado).
                        - Por lo tanto, si el usuario te pide que le notifiques cuando falten 3, 2, 1 días o el mismo día, explícale que el sistema de notificaciones de la campana del hogar ya lo hace automáticamente para cualquier 'Vencimiento' que agendes.
                        IMPORTANTE: Tienes a tu disposición herramientas (functions) de control del hogar para interactuar con la base de datos real en tiempo real:
                        - Si el usuario te pide programar un recordatorio, cuenta, o evento, usa `crear_evento_calendario`.
                        - Si te pide agregar artículos a la lista de compras, usa `agregar_articulo_compra` (especificando la lista correcta: 'Supermercado', 'Feria (Frutas y Verduras)', 'Otras Compras (Carne, Pescado)' o 'Pañalera (Bebé)').
                        - Si te pide programar tareas de aseo/limpieza, usa `agregar_tarea_aseo`.
                        - Si te pide saber qué eventos hay, qué compras están pendientes, los mejores precios de tu historial, o el estado general del hogar, usa `obtener_resumen_hogar`.
                        RECOMENDACIÓN DE TIENDAS Y PRECIOS:
                        - Cuando te consulten dónde conviene comprar o te pregunten sobre la lista de compras, consulta los precios y locales históricos provistos en `obtener_resumen_hogar`.
                        - Compara y aconseja de manera inteligente al usuario en qué supermercado, feria o local específico le conviene comprar cada artículo de su lista para ahorrar al máximo.
                        - Analiza los gastos del mes (incluyendo los gastos hormiga) si te lo solicitan para brindar recomendaciones de ahorro y organización del presupuesto.
                        IMPORTANTE: Toda la contabilidad está expresada en pesos chilenos (CLP). El símbolo de la moneda es "$".
                        No utilices decimales en tus cálculos ni respuestas, y formatea las cifras con puntos como separador de miles (ej. $15.000, $350.000).
                        Contexto financiero actual de la familia en tiempo real (CLP):
                        - Saldo Disponible actual del hogar: {format_clp(saldo_disp)}
                        - Ingresos Totales registrados: {format_clp(resumen['ingresos'])}
                        - Gastos Totales registrados: {format_clp(resumen['gastos'])}
                        Sé constructivo, servicial, realista, empático y claro en español.
                        """
                        # Formatear el historial para Gemini API (limitando a los últimos 10 mensajes)
                        chat_history_sdk = []
                        for msg in st.session_state.chat_history[-10:-1]:
                            chat_history_sdk.append({
                                "role": "user" if msg["role"] == "user" else "model",
                                "parts": [msg["content"]]
                            })
                        current_prompt = st.session_state.chat_history[-1]["content"]
                        # Combinar herramientas locales de control del hogar y búsqueda en Google
                        tools_combined = [crear_evento_calendario, agregar_articulo_compra, agregar_tarea_aseo, obtener_resumen_hogar]
                        if usar_busqueda:
                            tools_combined.append({"google_search_retrieval": {}})
                        # Cascada de modelos (fallback)
                        assistant_res = ""
                        last_err = None
                        for candidate in AI_MODEL_CANDIDATES:
                            try:
                                model = genai.GenerativeModel(
                                    model_name=candidate,
                                    system_instruction=system_prompt,
                                    tools=tools_combined
                                )
                                # Crear sesión de chat con auto-ejecución de funciones activada
                                chat = model.start_chat(history=chat_history_sdk, enable_automatic_function_calling=True)
                                response = chat.send_message(current_prompt)
                                assistant_res = response.text
                                break
                            except Exception as e:
                                last_err = e
                                continue
                        if not assistant_res:
                            if last_err:
                                raise last_err
                            else:
                                raise Exception("Servidores de IA saturados.")
                        # Mostrar la respuesta
                        res_box.markdown(assistant_res)
                        # Agregar al historial en session_state
                        st.session_state.chat_history.append({"role": "assistant", "content": assistant_res})
                    except Exception as e:
                        err_str = str(e).lower()
                        if ("quota" in err_str or "429" in err_str or "limit" in err_str) and usar_busqueda:
                            err_text = (
                                "⚠️ **Error de Cuota / Plan Gratuito (429):** "
                                "Tu API Key está en el plan gratuito (Free Tier), el cual no permite la búsqueda en Google (Search Grounding). "
                                "Por favor, desmarca la opción 'Buscar en Google' en la barra lateral para continuar sin búsquedas web, "
                                "o habilita la facturación en tu consola de Google AI Studio."
                            )
                        else:
                            err_text = "Los servidores de IA están saturados en este momento. Por favor, intenta de nuevo más tarde."
                        res_box.error(err_text)
                        st.session_state.chat_history.append({"role": "assistant", "content": f"⚠️ Error de sistema: {str(e)}"})
            # Forzar actualización de pantalla para fijar historial
            st.rerun()
        # Botón para reiniciar chat
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Reiniciar Conversación", help="Borra el historial del chat"):
            st.session_state.chat_history = []
            st.rerun()

elif menu == "⚙️ Mi Perfil":
    st.markdown("### ⚙️ Mi Perfil de Usuario")
    st.write("Gestiona tu información de cuenta, correo electrónico y contraseña de acceso.")
    
    email_actual = db.obtener_email_usuario(username)
    
    col_perfil_mail, col_perfil_pass = st.columns(2)
    
    with col_perfil_mail:
        with st.container(border=True):
            st.markdown("##### 📧 Actualizar Correo Electrónico")
            with st.form("form_update_email"):
                email_input = st.text_input("Correo Electrónico", value=email_actual, placeholder="ejemplo@correo.com")
                btn_save_email = st.form_submit_button("Guardar Correo", use_container_width=True)
                if btn_save_email:
                    if db.actualizar_email_usuario(username, email_input.strip()):
                        st.toast("Correo electrónico actualizado correctamente.", icon="📧")
                        st.rerun()
                    else:
                        st.error("No se pudo actualizar el correo electrónico.")
        
    with col_perfil_pass:
        with st.container(border=True):
            st.markdown("##### 🔒 Cambiar Contraseña")
            with st.form("form_update_password", clear_on_submit=True):
                pass_actual = st.text_input("Contraseña Actual", type="password", placeholder="Ingresa tu contraseña actual")
                pass_nueva = st.text_input("Nueva Contraseña", type="password", placeholder="Mínimo 4 caracteres")
                pass_confirm = st.text_input("Confirmar Nueva Contraseña", type="password", placeholder="Repite la nueva contraseña")
                btn_save_pass = st.form_submit_button("Cambiar Contraseña", use_container_width=True)
                if btn_save_pass:
                    stored_hash = db.obtener_hash_usuario(username)
                    if not verify_password(pass_actual, stored_hash):
                        st.error("La contraseña actual es incorrecta.")
                    elif pass_nueva != pass_confirm:
                        st.error("Las nuevas contraseñas no coinciden.")
                    elif len(pass_nueva) < 4:
                        st.error("La nueva contraseña debe tener al menos 4 caracteres.")
                    else:
                        import hashlib
                        new_hash = hashlib.sha256(pass_nueva.encode()).hexdigest()
                        if db.actualizar_password_usuario(username, new_hash):
                            st.toast("Contraseña cambiada correctamente.", icon="🔒")
                            st.rerun()
                        else:
                            st.error("No se pudo cambiar la contraseña.")


elif menu == "🔑 Control de Usuarios" and username == "dante":
    st.markdown("### 👥 Control y Gestión de Usuarios del Hogar")
    st.write("Como administrador, puedes ver los usuarios creados en la aplicación y eliminarlos en caso de necesidad.")
    lista_usuarios = db.obtener_usuarios()
    with st.container(border=True):
        st.markdown("##### 📋 Usuarios Registrados")
        for u in lista_usuarios:
            col_u, col_actions = st.columns([3, 1])
            with col_u:
                st.markdown(f"**👤 {u.replace('_', ' ').title()}** (`{u}`)")
            with col_actions:
                if u == "dante":
                    st.markdown("<span style='color: #818cf8; font-weight: bold;'>Administrador (Tú)</span>", unsafe_allow_html=True)
                elif u == "prueba":
                    st.markdown("<span style='color: #9ca3af;'>Cuenta de Demostración</span>", unsafe_allow_html=True)
                else:
                    if st.button(f"Eliminar {u.title()}", key=f"del_{u}", type="secondary"):
                        st.session_state[f"confirm_delete_{u}"] = True
                        st.rerun()
                    if st.session_state.get(f"confirm_delete_{u}"):
                        st.warning(f"¿Estás seguro de que deseas eliminar permanentemente al usuario **{u.title()}** y todos sus datos relacionados (finanzas, compras, etc.)?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("Sí, eliminar", key=f"yes_del_{u}", type="primary"):
                                if db.eliminar_usuario(u):
                                    st.success(f"Usuario {u.title()} eliminado correctamente.")
                                    st.session_state[f"confirm_delete_{u}"] = False
                                    st.rerun()
                                else:
                                    st.error("No se pudo eliminar al usuario.")
                        with col_no:
                            if st.button("Cancelar", key=f"no_del_{u}"):
                                st.session_state[f"confirm_delete_{u}"] = False
                                st.rerun()
        st.markdown("<hr style='border-color: #1e293b; margin: 10px 0;' />", unsafe_allow_html=True)
