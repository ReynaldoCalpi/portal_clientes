import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os
import io
import zipfile

# Configuración de la página
st.set_page_config(
    page_title="Portal de Clientes - RI Consultores",
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
    """Extrae el número de control (priorizando DTE-03), valor, iva y total desde el JSON."""
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
                    # Búsqueda estructurada del número de control comenzando con DTE-03
                    doc_num = None
                    nc_root = item.get("numeroControl")
                    if nc_root and str(nc_root).startswith("DTE-03"):
                        doc_num = nc_root
                        
                    if not doc_num:
                        ident = item.get("identificacion", {})
                        if isinstance(ident, dict):
                            nc_ident = ident.get("numeroControl")
                            if nc_ident and str(nc_ident).startswith("DTE-03"):
                                doc_num = nc_ident
                                
                    # Fallback general si no encuentra el DTE-03 exacto
                    if not doc_num:
                        doc_num = (
                            nc_root or 
                            (ident.get("numeroControl") if isinstance(ident, dict) else None) or
                            item.get("codigoGeneracion") or 
                            item.get("numDocumento") or 
                            file_info["name"]
                        )
                    
                    resumen = item.get("resumen", {})
                    if isinstance(resumen, dict):
                        val = resumen.get("totalGravada") or resumen.get("subTotal") or resumen.get("montoTotalOperacion") or 0.0
                        iva = resumen.get("totalIva") or resumen.get("ivaRenta") or 0.0
                        total = resumen.get("totalPagar") or resumen.get("montoTotalOperacion") or 0.0
                    else:
                        val = item.get("valor") or item.get("subtotal") or 0.0
                        iva = item.get("iva") or 0.0
                        total = item.get("total") or 0.0
                        
                    summary_data.append({
                        "Número de Control": doc_num,
                        "Valor": float(val) if val else 0.0,
                        "IVA": float(iva) if iva else 0.0,
                        "Total": float(total) if total else 0.0
                    })
            except Exception:
                summary_data.append({
                    "Número de Control": file_info["name"],
                    "Valor": 0.0,
                    "IVA": 0.0,
                    "Total": 0.0
                })
    return pd.DataFrame(summary_data)

# --- Inicialización de Estados de Sesión ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "username" not in st.session_state:
    st.session_state.username = ""

if "clients_db" not in st.session_state:
    st.session_state.clients_db = {}

# --- Sincronización de Clientes Oficiales ---
official_clients = {
    "admin": {"password": "admin123", "role": "admin", "name": "Administrador General"},
    "soluciones_503": {"password": "sol503_2026", "role": "client", "name": "Soluciones 503 S.A.S. de C.V"},
    "distribuidora_libertad": {"password": "libertad_2026", "role": "client", "name": "Distribuidora Libertad"},
    "leftech": {"password": "leftech_2026", "role": "client", "name": "Leftech"},
    "cedillo": {"password": "cedillo_2026", "role": "client", "name": "Cedillo"},
    "mercadito_rosa": {"password": "rosa_2026", "role": "client", "name": "Mercadito Rosa de Saron AC"}
}

for k, v in official_clients.items():
    st.session_state.clients_db[k] = v

# --- Pantalla de Login ---
def login_screen():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 RI Consultores")
        st.markdown("### Portal de Gestión Documental")
        
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Iniciar Sesión", use_container_width=True)
            
            if submit:
                user_key = username.strip().lower()
                if user_key in st.session_state.clients_db and st.session_state.clients_db[user_key]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.user_role = st.session_state.clients_db[user_key]["role"]
                    st.session_state.username = st.session_state.clients_db[user_key]["name"]
                    st.session_state.user_id = user_key
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

# --- Panel de Administración ---
def admin_dashboard():
    st.title("🎛️ Panel de Control - Administrador")
    st.markdown("Supervisa el cumplimiento fiscal, administra cuentas y revisa los documentos cargados en tiempo real.")
    
    tab1, tab2, tab3 = st.tabs(["📋 Estatus y Archivos Recibidos", "➕ Crear Nuevo Usuario", "👥 Listado de Cuentas"])
    
    with tab1:
        st.subheader("Control de Recepción y Descarga de Documentos")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_mes = st.selectbox("Filtrar por Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=5)
        with col_f2:
            filtro_anio = st.selectbox("Filtrar por Año", [2026, 2025], index=0)
            
        periodo_seleccionado = f"{filtro_mes} {filtro_anio}"
        all_submissions = load_submissions()
        envios_periodo = [s for s in all_submissions if s["periodo"] == periodo_seleccionado]
        
        if envios_periodo:
            st.success(f"Se encontraron {len(envios_periodo)} entregas para el periodo {periodo_seleccionado}.")
            for idx, envio in enumerate(envios_periodo):
                with st.expander(f"📁 {envio['client']} — Entregado el {envio['fecha']}"):
                    col_d1, col_d2 = st.columns(2)
                    
                    with col_d1:
                        st.markdown("**📈 Ventas:**")
                        has_sales = envio.get('sales_json_list') or envio.get('sales_pdf_list')
                        if has_sales:
                            zip_sales_bytes = create_zip_buffer(envio.get('sales_json_list'), envio.get('sales_pdf_list'))
                            safe_client_name = envio['client'].replace(" ", "_").replace(".", "")
                            st.download_button(
                                label="📦 Descargar todas las Ventas (ZIP)",
                                data=zip_sales_bytes,
                                file_name=f"Ventas_{safe_client_name}_{envio['periodo'].replace(' ', '_')}.zip",
                                mime="application/zip",
                                key=f"zip_sales_{idx}"
                            )
                        else:
                            st.text("Sin archivos de ventas")
                            
                    with col_d2:
                        st.markdown("**📉 Compras y Gastos:**")
                        has_purch = envio.get('purch_json_list') or envio.get('purch_pdf_list')
                        if has_purch:
                            zip_purch_bytes = create_zip_buffer(envio.get('purch_json_list'), envio.get('purch_pdf_list'))
                            safe_client_name = envio['client'].replace(" ", "_").replace(".", "")
                            st.download_button(
                                label="📦 Descargar todas las Compras (ZIP)",
                                data=zip_purch_bytes,
                                file_name=f"Compras_{safe_client_name}_{envio['periodo'].replace(' ', '_')}.zip",
                                mime="application/zip",
                                key=f"zip_purch_{idx}"
                            )
                        else:
                            st.text("Sin archivos de compras")
        else:
            st.info(f"No hay documentos registrados para el periodo {periodo_seleccionado} todavía.")

    with tab2:
        st.subheader("Dar de alta a un nuevo cliente")
        with st.form("new_client_form"):
            new_user_id = st.text_input("Identificador único de usuario (ej. empresa_abc)").strip().lower()
            company_name = st.text_input("Nombre Comercial / Razón Social")
            temp_pass = st.text_input("Contraseña Temporal", type="password")
            create_btn = st.form_submit_button("Registrar Cliente en el Sistema")
            
            if create_btn:
                if new_user_id and company_name and temp_pass:
                    if new_user_id in st.session_state.clients_db:
                        st.error("Ese identificador ya existe.")
                    else:
                        st.session_state.clients_db[new_user_id] = {
                            "password": temp_pass,
                            "role": "client",
                            "name": company_name
                        }
                        st.success(f"¡Cliente **{company_name}** registrado con éxito!")
                else:
                    st.warning("Completa todos los campos.")

    with tab3:
        st.subheader("Cuentas de Clientes Activas")
        client_accounts = [{"Usuario ID": k, "Nombre": v["name"]} for k, v in st.session_state.clients_db.items() if v["role"] == "client"]
        if client_accounts:
            st.dataframe(pd.DataFrame(client_accounts), use_container_width=True)
        else:
            st.warning("No hay clientes registrados.")

# --- Panel del Cliente ---
def client_dashboard():
    st.title(f"📁 Portal de Contribuyente — {st.session_state.username}")
    st.markdown("Arrastra y suelta múltiples archivos JSON y PDFs correspondientes al periodo en curso.")
    
    client_tab1, client_tab2 = st.tabs(["📤 Cargar Documentos (Múltiples)", "📊 Historial y Resumen Financiero"])
    
    with client_tab1:
        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes Fiscal", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=5)
        with col2:
            anio = st.selectbox("Año Fiscal", [2026, 2025], index=0)
            
        st.divider()
        
        with st.form("upload_form"):
            col_v, col_c = st.columns(2)
            
            with col_v:
                st.subheader("📈 Ventas")
                sales_json = st.file_uploader("Arrastra tus JSON de Ventas (Múltiples)", type=["json"], accept_multiple_files=True, key="s_json")
                sales_pdf = st.file_uploader("Arrastra tus PDFs/ZIP de Ventas (Múltiples)", type=["pdf", "zip"], accept_multiple_files=True, key="s_pdf")

            with col_c:
                st.subheader("📉 Compras y Gastos")
                purch_json = st.file_uploader("Arrastra tus JSON de Compras (Múltiples)", type=["json"], accept_multiple_files=True, key="p_json")
                purch_pdf = st.file_uploader("Arrastra tus PDFs de Compras (Múltiples)", type=["pdf", "zip"], accept_multiple_files=True, key="p_pdf")
                
            submit_files = st.form_submit_button("🚀 Validar y Enviar Documentación", use_container_width=True)
            
            if submit_files:
                if sales_json or purch_json:
                    json_valido = True
                    archivo_fallido = ""
                    error_detallado = ""
                    
                    for j_file in (sales_json or []) + (purch_json or []):
                        try:
                            j_file.seek(0)
                            content = j_file.read()
                            if isinstance(content, bytes):
                                text_content = content.decode('utf-8-sig', errors='replace')
                            else:
                                text_content = content
                            json.loads(text_content)
                        except Exception as e:
                            json_valido = False
                            archivo_fallido = j_file.name
                            error_detallado = str(e)
                            break
                            
                    if json_valido:
                        periodo_str = f"{mes} {anio}"
                        
                        s_json_saved = save_files_to_folder(sales_json, st.session_state.username, periodo_str, "sales_json")
                        s_pdf_saved = save_files_to_folder(sales_pdf, st.session_state.username, periodo_str, "sales_pdf")
                        p_json_saved = save_files_to_folder(purch_json, st.session_state.username, periodo_str, "purch_json")
                        p_pdf_saved = save_files_to_folder(purch_pdf, st.session_state.username, periodo_str, "purch_pdf")
                        
                        submission_record = {
                            "client": st.session_state.username,
                            "periodo": periodo_str,
                            "sales_json_list": s_json_saved,
                            "sales_pdf_list": s_pdf_saved,
                            "purch_json_list": p_json_saved,
                            "purch_pdf_list": p_pdf_saved,
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
                        }
                        
                        save_submission_to_disk(submission_record)
                        st.success(f"¡Estructura validada! Documentos del periodo {periodo_str} enviados correctamente a RI Consultores.")
                    else:
                        st.error(f"❌ Error en el archivo '{archivo_fallido}': {error_detallado}")
                else:
                    st.warning("Adjunta al menos un archivo JSON principal antes de enviar.")

    with client_tab2:
        st.subheader("📊 Historial de Declaraciones y Reporte Detallado")
        all_submissions = load_submissions()
        mis_envios = [s for s in all_submissions if s["client"] == st.session_state.username]
        
        if mis_envios:
            st.info("Visualiza el detalle de tus documentos fiscales, números de control (DTE-03) e importes correspondientes por cada periodo.")
            for envio in mis_envios:
                with st.expander(f"📅 Periodo: {envio['periodo']} — Entregado el {envio['fecha']}"):
                    
                    # --- Sección de Ventas ---
                    st.markdown("---")
                    st.markdown("##### 📈 Reporte Detallado de Ventas")
                    df_sales = extract_invoice_summary(envio.get('sales_json_list'))
                    if not df_sales.empty:
                        v_val = df_sales['Valor'].sum()
                        v_iva = df_sales['IVA'].sum()
                        v_tot = df_sales['Total'].sum()
                        
                        col_m1, col_m2, col_m3 = st.columns(3)
                        col_m1.metric("Subtotal Ventas", f"${v_val:,.2f}")
                        col_m2.metric("IVA Ventas", f"${v_iva:,.2f}")
                        col_m3.metric("Total Ventas", f"${v_tot:,.2f}")
                        
                        st.dataframe(
                            df_sales.style.format({
                                "Valor": "${:,.2f}",
                                "IVA": "${:,.2f}",
                                "Total": "${:,.2f}"
                            }),
                            use_container_width=True
                        )
                    else:
                        st.text("Sin registros de ventas detallados para este periodo.")
                        
                    # --- Sección de Compras ---
                    st.markdown("---")
                    st.markdown("##### 📉 Reporte Detallado de Compras y Gastos")
                    df_purch = extract_invoice_summary(envio.get('purch_json_list'))
                    if not df_purch.empty:
                        p_val = df_purch['Valor'].sum()
                        p_iva = df_purch['IVA'].sum()
                        p_tot = df_purch['Total'].sum()
                        
                        col_pm1, col_pm2, col_pm3 = st.columns(3)
                        col_pm1.metric("Subtotal Compras", f"${p_val:,.2f}")
                        col_pm2.metric("IVA Compras", f"${p_iva:,.2f}")
                        col_pm3.metric("Total Compras", f"${p_tot:,.2f}")
                        
                        st.dataframe(
                            df_purch.style.format({
                                "Valor": "${:,.2f}",
                                "IVA": "${:,.2f}",
                                "Total": "${:,.2f}"
                            }),
                            use_container_width=True
                        )
                    else:
                        st.text("Sin registros de compras detallados para este periodo.")
        else:
            st.warning("⚠️ Aún no has registrado envíos de documentos en el portal.")

# --- Control de Sesión ---
if not st.session_state.logged_in:
    login_screen()
else:
    with st.sidebar:
        st.write(f"Conectado como:\n**{st.session_state.username}**")
        st.divider()
        if st.button("Cerrar Sesión", type="primary"):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.session_state.username = ""
            st.rerun()
            
    if st.session_state.user_role == "admin":
        admin_dashboard()
    elif st.session_state.user_role == "client":
        client_dashboard()
