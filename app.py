import streamlit as st
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Portal de Clientes - RI Consultores",
    page_icon="📊",
    layout="wide"
)

# --- Inicialización de Estados (Base Intacta) ---
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

# --- Panel de Administración (Fase 1 y 2 Intactas) ---
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
                        st.markdown("**Ventas:**")
                        if envio['sales_json']:
                            st.download_button(f"Descargar JSON Ventas", envio['sales_json'].getvalue(), file_name=envio['sales_name'], key=f"s_json_{idx}")
                        else:
                            st.text("Sin JSON de ventas")
                            
                        if envio['sales_pdf']:
                            st.download_button(f"Descargar PDF/Resguardo Ventas", envio['sales_pdf'].getvalue(), file_name=envio['sales_pdf_name'], key=f"s_pdf_{idx}")
                    with col_d2:
                        st.markdown("**Compras:**")
                        if envio['purch_json']:
                            st.download_button(f"Descargar JSON Compras", envio['purch_json'].getvalue(), file_name=envio['purch_name'], key=f"p_json_{idx}")
                        else:
                            st.text("Sin JSON de compras")
                            
                        if envio['purch_pdf']:
                            st.download_button(f"Descargar PDF Compras", envio['purch_pdf'].getvalue(), file_name=envio['purch_pdf_name'], key=f"p_pdf_{idx}")
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

# --- Panel del Cliente (Fase 3: Carga + Historial del Contribuyente) ---
def client_dashboard():
    st.title(f"📁 Portal de Contribuyente — {st.session_state.username}")
    st.markdown("Sube tus archivos JSON y PDFs correspondientes al periodo fiscal en curso de forma segura.")
    
    # Pestañas para el cliente
    client_tab1, client_tab2 = st.tabs(["📤 Cargar Documentos del Periodo", "📜 Mi Historial de Envíos"])
    
    with client_tab1:
        col1, col2 = st.columns(2)
        with col1:
            mes = st.selectbox("Mes Fiscal", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=6)
        with col2:
            anio = st.selectbox("Año Fiscal", [2026, 2025], index=0)
            
        st.divider()
        
        with st.form("upload_form"):
            col_v, col_c = st.columns(2)
            
            with col_v:
                st.subheader("📈 Ventas")
                sales_json = st.file_uploader("Archivo JSON de Ventas (DTEs)", type=["json"], key="s_json")
                sales_pdf = st.file_uploader("PDFs de Resguardo / Ventas", type=["pdf", "zip"], key="s_pdf")

            with col_c:
                st.subheader("📉 Compras y Gastos")
                purch_json = st.file_uploader("Archivo JSON de Compras", type=["json"], key="p_json")
                purch_pdf = st.file_uploader("PDFs de Compras y Gastos", type=["pdf", "zip"], key="p_pdf")
                
            submit_files = st.form_submit_button("🚀 Enviar Documentación a RI Consultores", use_container_width=True)
            
            if submit_files:
                if sales_json or purch_json:
                    periodo_str = f"{mes} {anio}"
                    st.session_state.submissions.append({
                        "client": st.session_state.username,
                        "periodo": periodo_str,
                        "sales_json": sales_json,
                        "sales_name": sales_json.name if sales_json else None,
                        "sales_pdf": sales_pdf,
                        "sales_pdf_name": sales_pdf.name if sales_pdf else None,
                        "purch_json": purch_json,
                        "purch_name": purch_json.name if purch_json else None,
                        "purch_pdf": purch_pdf,
                        "purch_pdf_name": purch_pdf.name if purch_pdf else None,
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    st.success(f"¡Documentos para el periodo {periodo_str} enviados correctamente a RI Consultores!")
                else:
                    st.warning("Adjunta al menos un archivo JSON principal.")

    with client_tab2:
        st.subheader("Historial de Declaraciones y Envíos Realizados")
        # Filtrar solo los envíos de este cliente logueado
        mis_envios = [s for s in st.session_state.submissions if s["client"] == st.session_state.username]
        
        if mis_envios:
            st.info("Aquí puedes verificar los comprobantes que ya has entregado en periodos anteriores.")
            for envio in mis_envios:
                with st.expander(f"📅 Periodo: {envio['periodo']} (Enviado el {envio['fecha']})"):
                    st.markdown(f"- **Ventas (JSON):** {envio['sales_name'] if envio['sales_json'] else 'No adjunto'}")
                    st.markdown(f"- **Ventas (PDF):** {envio['sales_pdf_name'] if envio['sales_pdf'] else 'No adjunto'}")
                    st.markdown(f"- **Compras (JSON):** {envio['purch_name'] if envio['purch_json'] else 'No adjunto'}")
                    st.markdown(f"- **Compras (PDF):** {envio['purch_pdf_name'] if envio['purch_pdf'] else 'No adjunto'}")
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
