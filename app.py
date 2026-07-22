import streamlit as st
import pandas as pd
from datetime import datetime
import json

# Configuración de la página
st.set_page_config(
    page_title="Portal de Clientes - RI Consultores",
    page_icon="📊",
    layout="wide"
)

# --- Inicialización de Estados ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "username" not in st.session_state:
    st.session_state.username = ""

if "clients_db" not in st.session_state:
    st.session_state.clients_db = {
        "admin": {"password": "admin123", "role": "admin", "name": "Administrador General"},
        "comercial_alfa": {"password": "123", "role": "client", "name": "Comercial Alfa S.A. de C.V."},
        "distribuidora_beta": {"password": "123", "role": "client", "name": "Distribuidora Beta"}
    }

if "submissions" not in st.session_state:
    st.session_state.submissions = []

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
    st.markdown("Supervisa el cumplimiento fiscal, administra cuentas y revisa los documentos cargados.")
    
    tab1, tab2, tab3 = st.tabs(["📋 Estatus y Archivos Recibidos", "➕ Crear Nuevo Usuario", "👥 Listado de Cuentas"])
    
    with tab1:
        st.subheader("Control de Recepción y Descarga de Documentos")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_mes = st.selectbox("Filtrar por Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=6)
        with col_f2:
            filtro_anio = st.selectbox("Filtrar por Año", [2026, 2025], index=0)
            
        periodo_seleccionado = f"{filtro_mes} {filtro_anio}"
        envios_periodo = [s for s in st.session_state.submissions if s["periodo"] == periodo_seleccionado]
        
        if envios_periodo:
            st.success(f"Se encontraron {len(envios_periodo)} entregas para el periodo {periodo_seleccionado}.")
            for idx, envio in enumerate(envios_periodo):
                with st.expander(f"📁 {envio['client']} — Entregado el {envio['fecha']}"):
                    col_d1, col_d2 = st.columns(2)
                    
                    with col_d1:
                        st.markdown("**📈 Ventas:**")
                        if envio.get('sales_json_list'):
                            st.text(f"JSONs de Ventas ({len(envio['sales_json_list'])} archivos):")
                            for f_idx, file_obj in enumerate(envio['sales_json_list']):
                                file_obj.seek(0)
                                st.download_button(f"📥 {file_obj.name}", file_obj.getvalue(), file_name=file_obj.name, key=f"s_j_{idx}_{f_idx}")
                        else:
                            st.text("Sin JSON de ventas")
                            
                        if envio.get('sales_pdf_list'):
                            st.text(f"PDFs/Resguardos Ventas ({len(envio['sales_pdf_list'])} archivos):")
                            for f_idx, file_obj in enumerate(envio['sales_pdf_list']):
                                file_obj.seek(0)
                                st.download_button(f"📥 {file_obj.name}", file_obj.getvalue(), file_name=file_obj.name, key=f"s_p_{idx}_{f_idx}")
                                
                    with col_d2:
                        st.markdown("**📉 Compras:**")
                        if envio.get('purch_json_list'):
                            st.text(f"JSONs de Compras ({len(envio['purch_json_list'])} archivos):")
                            for f_idx, file_obj in enumerate(envio['purch_json_list']):
                                file_obj.seek(0)
                                st.download_button(f"📥 {file_obj.name}", file_obj.getvalue(), file_name=file_obj.name, key=f"p_j_{idx}_{f_idx}")
                        else:
                            st.text("Sin JSON de compras")
                            
                        if envio.get('purch_pdf_list'):
                            st.text(f"PDFs de Compras ({len(envio['purch_pdf_list'])} archivos):")
                            for f_idx, file_obj in enumerate(envio['purch_pdf_list']):
                                file_obj.seek(0)
                                st.download_button(f"📥 {file_obj.name}", file_obj.getvalue(), file_name=file_obj.name, key=f"p_p_{idx}_{f_idx}")
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

# --- Panel del Cliente (Validación con Diagnóstico Detallado) ---
def client_dashboard():
    st.title(f"📁 Portal de Contribuyente — {st.session_state.username}")
    st.markdown("Arrastra y suelta múltiples archivos JSON y PDFs correspondientes al periodo en curso.")
    
    client_tab1, client_tab2 = st.tabs(["📤 Cargar Documentos (Múltiples)", "📜 Mi Historial de Envíos"])
    
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
                    
                    # Validar cada archivo JSON cargado con reporte de errores específico
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
                        st.session_state.submissions.append({
                            "client": st.session_state.username,
                            "periodo": periodo_str,
                            "sales_json_list": sales_json,
                            "sales_pdf_list": sales_pdf,
                            "purch_json_list": purch_json,
                            "purch_pdf_list": purch_pdf,
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        st.success(f"¡Estructura validada! Documentos del periodo {periodo_str} enviados correctamente a RI Consultores.")
                    else:
                        st.error(f"❌ Error en el archivo '{archivo_fallido}': {error_detallado}")
                else:
                    st.warning("Adjunta al menos un archivo JSON principal antes de enviar.")

    with client_tab2:
        st.subheader("Historial de Declaraciones y Envíos Realizados")
        mis_envios = [s for s in st.session_state.submissions if s["client"] == st.session_state.username]
        
        if mis_envios:
            st.info("Aquí puedes verificar los comprobantes que ya has entregado en periodos anteriores.")
            for envio in mis_envios:
                s_count = len(envio.get('sales_json_list', [])) + len(envio.get('sales_pdf_list', []))
                p_count = len(envio.get('purch_json_list', [])) + len(envio.get('purch_pdf_list', []))
                with st.expander(f"📅 Periodo: {envio['periodo']} (Enviado el {envio['fecha']})"):
                    st.markdown(f"- **Archivos de Ventas cargados:** {s_count} archivo(s)")
                    st.markdown(f"- **Archivos de Compras cargados:** {p_count} archivo(s)")
                    st.success("Estatus: Entregado y registrado con éxito.")
        else:
            st.warning("Aún no has registrado envíos de documentos en el portal.")

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
