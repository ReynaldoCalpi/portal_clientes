import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os
import io
import zipfile

# Configuración de la página
st.set_page_config(
    page_title="Portal de Contribuyente - RI Consultores",
    page_icon="📊",
    layout="wide"
)

# --- Configuración de Persistencia en Disco ---
DB_FILE = "submissions_db.json"
EMPLOYEES_DB = "employees_db.json"
UPLOAD_DIR = "uploaded_files"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Funciones de utilería para Datos
def load_json_db(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_json_db(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def save_submission_to_disk(submission_data):
    submissions = load_json_db(DB_FILE)
    submissions.append(submission_data)
    save_json_db(DB_FILE, submissions)

def save_employee_record(employee_data):
    employees = load_json_db(EMPLOYEES_DB)
    employees.append(employee_data)
    save_json_db(EMPLOYEES_DB, employees)

def save_files_to_folder(file_list, client_name, periodo_str, category):
    saved_files_info = []
    if not file_list: return saved_files_info
    safe_client = client_name.replace(" ", "_").replace(".", "")
    safe_periodo = periodo_str.replace(" ", "_")
    folder_path = os.path.join(UPLOAD_DIR, safe_client, safe_periodo, category)
    os.makedirs(folder_path, exist_ok=True)
    for file_obj in file_list:
        file_path = os.path.join(folder_path, file_obj.name)
        file_obj.seek(0)
        with open(file_path, "wb") as f:
            f.write(file_obj.getbuffer())
        saved_files_info.append({"name": file_obj.name, "path": file_path})
    return saved_files_info

def create_zip_buffer(json_list, pdf_list):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_info in (json_list or []):
            if os.path.exists(file_info['path']): zip_file.write(file_info['path'], arcname=file_info['name'])
        for file_info in (pdf_list or []):
            if os.path.exists(file_info['path']): zip_file.write(file_info['path'], arcname=file_info['name'])
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def calcular_empleado_quincenal(salario_mensual, comisiones, h_diurnas, h_nocturnas, otras_deducciones):
    tarifa_hora = (salario_mensual / 30.0) / 8.0
    pago_diurnas = h_diurnas * tarifa_hora * 2.0
    pago_nocturnas = h_nocturnas * tarifa_hora * 2.25
    total_gravable = (salario_mensual / 2.0) + comisiones + pago_diurnas + pago_nocturnas
    
    isss = min(total_gravable * 0.03, 15.00)
    afp = min(total_gravable * 0.0725, 3522.53)
    base_renta = max(total_gravable - isss - afp, 0.0)
    
    if base_renta <= 275.00: renta = 0.0
    elif base_renta <= 447.62: renta = ((base_renta - 275.00) * 0.10) + 8.83
    elif base_renta <= 1019.05: renta = ((base_renta - 447.62) * 0.20) + 30.00
    else: renta = ((base_renta - 1019.05) * 0.30) + 144.28
        
    liquido = total_gravable - isss - afp - renta - otras_deducciones
    return total_gravable, isss, afp, renta, liquido

# --- Inicialización de Estados ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_role" not in st.session_state: st.session_state.user_role = None
if "username" not in st.session_state: st.session_state.username = ""
if "user_id" not in st.session_state: st.session_state.user_id = ""
if "calc_result" not in st.session_state: st.session_state.calc_result = None

# --- Pantalla de Login ---
def login_screen():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 RI Consultores")
        clients_db = {
            "admin": {"password": "admin123", "role": "admin", "name": "Administrador General"},
            "soluciones_503": {"password": "sol503_2026", "role": "client", "name": "Soluciones 503 S.A.S. de C.V"},
            "leftech": {"password": "leftech_2026", "role": "client", "name": "Leftech"}
        }
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Iniciar Sesión"):
                if username in clients_db and clients_db[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.user_role = clients_db[username]["role"]
                    st.session_state.username = clients_db[username]["name"]
                    st.session_state.user_id = username
                    st.rerun()

# --- Panel del Cliente ---
def client_dashboard():
    st.title(f"📁 PORTAL — {st.session_state.username}")
    tab1, tab2 = st.tabs(["CARGA DOCUMENTAL", "GENERADOR PLANILLAS"])
    
    with tab1:
        st.write("Panel de Carga") # Simplificado para espacio
    
    with tab2:
        st.subheader("💼 GENERADOR DE PLANILLAS")
        with st.form("form_planilla"):
            es_eventual = st.checkbox("Marcar como Eventual (10% fijo)")
            q_empleado = st.text_input("Nombre del Empleado")
            q_dui = st.text_input("Número de DUI")
            q_salario = st.number_input("Salario Base ($)", value=600.0)
            q_com = st.number_input("Comisiones ($)", value=0.0)
            h_d = st.number_input("Horas Extras Diurnas", value=0.0)
            h_n = st.number_input("Horas Extras Nocturnas", value=0.0)
            
            if st.form_submit_button("Calcular"):
                if es_eventual:
                    tot_grav = q_salario + q_com
                    renta = tot_grav * 0.10
                    st.session_state.calc_result = {"Nombre": q_empleado, "DUI": q_dui, "Total": tot_grav, "Renta": renta, "Liquido": tot_grav - renta}
                else:
                    t, i, a, r, l = calcular_empleado_quincenal(q_salario, q_com, h_d, h_n, 0.0)
                    st.session_state.calc_result = {"Nombre": q_empleado, "DUI": q_dui, "Total": t, "Renta": r, "Liquido": l}
        
        if st.session_state.calc_result:
            res = st.session_state.calc_result
            st.success(f"Resultado: **{res['Nombre']}** (DUI: {res['DUI']})")
            if st.button("💾 Guardar Registro en Base de Datos"):
                res["Fecha"] = datetime.now().strftime("%Y-%m-%d")
                save_employee_record(res)
                st.success("¡Registro guardado con éxito!")
                st.session_state.calc_result = None # Limpiar
                st.rerun()

        st.divider()
        st.subheader("📋 Historial de Empleados Guardados")
        emp_records = load_json_db(EMPLOYEES_DB)
        if emp_records:
            st.dataframe(pd.DataFrame(emp_records), use_container_width=True)

# --- Ejecución ---
if not st.session_state.logged_in: login_screen()
else:
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()
    client_dashboard()
