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
UPLOAD_DIR = "uploaded_files"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def load_submissions():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_submission_to_disk(submission_data):
    submissions = load_submissions()
    submissions.append(submission_data)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(submissions, f, ensure_ascii=False, indent=4)

def save_files_to_folder(file_list, client_name, periodo_str, category):
    saved_files_info = []
    if not file_list:
        return saved_files_info
        
    safe_client = client_name.replace(" ", "_").replace(".", "")
    safe_periodo = periodo_str.replace(" ", "_")
    folder_path = os.path.join(UPLOAD_DIR, safe_client, safe_periodo, category)
    os.makedirs(folder_path, exist_ok=True)
    
    for file_obj in file_list:
        file_path = os.path.join(folder_path, file_obj.name)
        file_obj.seek(0)
        with open(file_path, "wb") as f:
            f.write(file_obj.getbuffer())
        saved_files_info.append({
            "name": file_obj.name,
            "path": file_path
        })
    return saved_files_info

def create_zip_buffer(json_list, pdf_list):
    """Crea un archivo ZIP en memoria con los JSONs y PDFs proporcionados."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_info in (json_list or []):
            if os.path.exists(file_info['path']):
                zip_file.write(file_info['path'], arcname=file_info['name'])
        for file_info in (pdf_list or []):
            if os.path.exists(file_info['path']):
                zip_file.write(file_info['path'], arcname=file_info['name'])
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def extract_invoice_summary(file_list):
    """Extrae datos de facturación con validación robusta."""
    summary_data = []
    if not file_list:
        return pd.DataFrame()
    
    for file_info in file_list:
        path = file_info.get("path")
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    content = json.load(f)
                
                items = content if isinstance(content, list) else [content]
                for item in items:
                    doc_num = None
                    nc_root = item.get("numeroControl")
                    if nc_root and str(nc_root).startswith("DTE-03"):
                        doc_num = nc_root
                        
                    ident = item.get("identificacion", {})
                    if not doc_num and isinstance(ident, dict):
                        nc_ident = ident.get("numeroControl")
                        if nc_ident and str(nc_ident).startswith("DTE-03"):
                            doc_num = nc_ident
                                
                    if not doc_num:
                        doc_num = (
                            nc_root or 
                            (ident.get("numeroControl") if isinstance(ident, dict) else None) or
                            item.get("codigoGeneracion") or 
                            item.get("numDocumento") or 
                            file_info["name"]
                        )
                    
                    gen_code = None
                    if isinstance(ident, dict):
                        gen_code = ident.get("codigoGeneracion")
                    if not gen_code:
                        gen_code = item.get("codigoGeneracion") or item.get("selloRecibido") or "N/A"
                    
                    resumen = item.get("resumen", {})
                    if not isinstance(resumen, dict):
                        resumen = {}
                    
                    val = (
                        resumen.get("totalGravada") or resumen.get("subTotal") or resumen.get("subTotalVentas") or 
                        resumen.get("montoTotalOperacion") or item.get("totalGravada") or item.get("subtotal") or 
                        item.get("valor") or 0.0
                    )
                    
                    iva = (
                        resumen.get("totalIva") or resumen.get("iva") or resumen.get("ivaRenta") or 
                        resumen.get("ivaPerci1") or resumen.get("ivaRete1") or item.get("totalIva") or 
                        item.get("iva") or 0.0
                    )
                    
                    if not iva and "tributos" in resumen and isinstance(resumen["tributos"], list):
                        iva_tributos = 0.0
                        for trib in resumen["tributos"]:
                            if isinstance(trib, dict):
                                val_trib = trib.get("valor") or trib.get("valTributo") or 0.0
                                try:
                                    iva_tributos += float(val_trib)
                                except: pass
                        if iva_tributos > 0:
                            iva = iva_tributos

                    total = (
                        resumen.get("totalPagar") or resumen.get("montoTotalOperacion") or resumen.get("total") or 
                        item.get("totalPagar") or item.get("total") or 0.0
                    )
                    
                    try:
                        val_f, iva_f, total_f = float(val), float(iva), float(total)
                        if total_f == 0.0 and val_f > 0.0: total_f = val_f + iva_f
                        elif val_f == 0.0 and total_f > 0.0 and iva_f > 0.0: val_f = total_f - iva_f
                    except:
                        val_f, iva_f, total_f = 0.0, 0.0, 0.0
                        
                    summary_data.append({"Código de Generación": str(gen_code), "Número de Control": str(doc_num), "Valor": val_f, "IVA": iva_f, "Total": total_f})
            except Exception:
                summary_data.append({"Código de Generación": "N/A", "Número de Control": file_info["name"], "Valor": 0.0, "IVA": 0.0, "Total": 0.0})
    return pd.DataFrame(summary_data)

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
if "clients_db" not in st.session_state: st.session_state.clients_db = {
    "admin": {"password": "admin123", "role": "admin", "name": "Administrador General"},
    "soluciones_503": {"password": "sol503_2026", "role": "client", "name": "Soluciones 503 S.A.S. de C.V"},
    "distribuidora_libertad": {"password": "libertad_2026", "role": "client", "name": "Distribuidora Libertad"},
    "leftech": {"password": "leftech_2026", "role": "client", "name": "Leftech"},
    "cedillo": {"password": "cedillo_2026", "role": "client", "name": "Cedillo"},
    "mercadito_rosa": {"password": "rosa_2026", "role": "client", "name": "Mercadito Rosa de Saron AC"}
}

# --- Pantalla de Login ---
def login_screen():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 RI Consultores")
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Iniciar Sesión", use_container_width=True):
                user_key = username.strip().lower()
                if user_key in st.session_state.clients_db and st.session_state.clients_db[user_key]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.user_role = st.session_state.clients_db[user_key]["role"]
                    st.session_state.username = st.session_state.clients_db[user_key]["name"]
                    st.session_state.user_id = user_key
                    st.rerun()
                else: st.error("Usuario o contraseña incorrectos.")

# --- Panel de Administración ---
def admin_dashboard():
    st.title("🎛️ Panel de Control - Administrador")
    tab1, tab2, tab3 = st.tabs(["📋 Estatus", "➕ Nuevo Usuario", "👥 Cuentas"])
    
    with tab1:
        filtro_mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=5)
        filtro_anio = st.selectbox("Año", [2026, 2025], index=0)
        periodo_sel = f"{filtro_mes} {filtro_anio}"
        
        all_subs = load_submissions()
        envios_periodo = [s for s in all_subs if periodo_sel in s["periodo"]]
        
        for idx, envio in enumerate(envios_periodo):
            with st.expander(f"📁 {envio['client']} ({envio['periodo']})"):
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    if envio.get('sales_json_list') or envio.get('sales_pdf_list'):
                        st.download_button("📦 Descargar Ventas (ZIP)", data=create_zip_buffer(envio.get('sales_json_list'), envio.get('sales_pdf_list')), file_name=f"Ventas_{envio['client'].replace(' ', '_')}.zip", key=f"v_{idx}")
                with col_d2:
                    if envio.get('purch_json_list') or envio.get('purch_pdf_list'):
                        st.download_button("📦 Descargar Compras (ZIP)", data=create_zip_buffer(envio.get('purch_json_list'), envio.get('purch_pdf_list')), file_name=f"Compras_{envio['client'].replace(' ', '_')}.zip", key=f"p_{idx}")

    with tab2:
        with st.form("new_client_form"):
            new_id = st.text_input("Usuario ID").lower()
            name = st.text_input("Nombre Razón Social")
            pwd = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Registrar"):
                st.session_state.clients_db[new_id] = {"password": pwd, "role": "client", "name": name}
                st.success("¡Cliente registrado!")

    with tab3:
        st.dataframe(pd.DataFrame([{"Usuario ID": k, "Nombre": v["name"]} for k, v in st.session_state.clients_db.items() if v["role"] == "client"]))

# --- Panel del Cliente ---
def client_dashboard():
    st.title(f"📁 PORTAL DE CONTRIBUYENTE — {st.session_state.username}")
    mes = st.selectbox("MES FISCAL", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=5)
    anio = st.selectbox("AÑO FISCAL", [2026, 2025], index=0)
    periodo_str = f"{mes} {anio}"
    
    current_user_id = st.session_state.get("user_id", st.session_state.username)
    all_submissions = load_submissions()
    mis_envios = [s for s in all_submissions if s.get("user_id") == current_user_id or s.get("client") == st.session_state.username]
    
    client_tab1, client_tab2, client_tab3 = st.tabs(["CARGA DOCUMENTAL", "GENERADOR PLANILLAS", "HISTORIAL"])
    
    with client_tab1:
        with st.form("upload_form"):
            col_v, col_c = st.columns(2)
            with col_v:
                sales_json = st.file_uploader("JSON Ventas", type=["json"], accept_multiple_files=True)
                sales_pdf = st.file_uploader("PDFs Ventas", type=["pdf", "zip"], accept_multiple_files=True)
            with col_c:
                purch_json = st.file_uploader("JSON Compras", type=["json"], accept_multiple_files=True)
                purch_pdf = st.file_uploader("PDFs Compras", type=["pdf", "zip"], accept_multiple_files=True)
            
            notes = st.text_area("Notas Aclaratorias")
            if st.form_submit_button("🚀 Enviar"):
                s_json_s = save_files_to_folder(sales_json, st.session_state.username, periodo_str, "sales_json")
                s_pdf_s = save_files_to_folder(sales_pdf, st.session_state.username, periodo_str, "sales_pdf")
                p_json_s = save_files_to_folder(purch_json, st.session_state.username, periodo_str, "purch_json")
                p_pdf_s = save_files_to_folder(purch_pdf, st.session_state.username, periodo_str, "purch_pdf")
                
                submission_record = {
                    "user_id": current_user_id, "client": st.session_state.username, "periodo": periodo_str,
                    "sales_json_list": s_json_s, "sales_pdf_list": s_pdf_s, "purch_json_list": p_json_s,
                    "purch_pdf_list": p_pdf_s, "notes": notes, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                save_submission_to_disk(submission_record)
                st.success("Documentos enviados.")
                st.rerun()

    with client_tab2:
        st.subheader("💼 GENERADOR DE PLANILLAS Y RETENCIONES")
        with st.form("form_planilla"):
            es_eventual = st.checkbox("👤 Marcar como Empleado Eventual (10% fijo)")
            q_empleado = st.text_input("Nombre del Empleado / Prestador")
            q_dui = st.text_input("Número de DUI", placeholder="00000000-0")
            q_salario = st.number_input("Salario Base ($)", min_value=0.0, value=600.0)
            q_comisiones = st.number_input("Comisiones ($)", min_value=0.0)
            h_diurnas = st.number_input("Horas Extras Diurnas", min_value=0.0)
            h_nocturnas = st.number_input("Horas Extras Nocturnas", min_value=0.0)
            otras_ded = st.number_input("Otras Deducciones ($)", min_value=0.0)
            
            if st.form_submit_button("Calcular"):
                dui_display = f" (DUI: {q_dui})" if q_dui else ""
                if es_eventual:
                    tot_grav = q_salario + q_comisiones + (h_diurnas * (q_salario/30/8 * 2)) + (h_nocturnas * (q_salario/30/8 * 2.25))
                    renta = tot_grav * 0.10
                    liquido = tot_grav - renta - otras_ded
                    st.success(f"Resultado Eventual: **{q_empleado}**{dui_display}")
                    st.metric("Líquido", f"${liquido:,.2f}")
                else:
                    tot_grav, isss, afp, renta, liq = calcular_empleado_quincenal(q_salario, q_comisiones, h_diurnas, h_nocturnas, otras_ded)
                    st.success(f"Resultado Quincenal: **{q_empleado}**{dui_display}")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Devengado", f"${tot_grav:,.2f}")
                    c2.metric("Renta", f"${renta:,.2f}")
                    c3.metric("Líquido", f"${liq:,.2f}")

    with client_tab3:
        st.subheader("📊 Historial")
        for envio in mis_envios:
            with st.expander(f"Periodo: {envio['periodo']}"):
                st.write(f"Entregado el: {envio['fecha']}")
                if envio.get('notes'): st.info(envio['notes'])

# --- Control de Flujo ---
if not st.session_state.logged_in:
    login_screen()
else:
    with st.sidebar:
        st.write(f"Conectado: **{st.session_state.username}**")
        if st.button("Cerrar Sesión"):
            st.session_state.logged_in = False
            st.rerun()
            
    if st.session_state.user_role == "admin": admin_dashboard()
    elif st.session_state.user_role == "client": client_dashboard()
