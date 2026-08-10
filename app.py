import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os
import io
import zipfile
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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
    """Extrae el Código de Generación, Número de Control (DTE-03), valor, iva y total con validación robusta y ecuaciones cruzadas."""
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
                        resumen.get("totalGravada") or 
                        resumen.get("subTotal") or 
                        resumen.get("subTotalVentas") or 
                        resumen.get("montoTotalOperacion") or 
                        item.get("totalGravada") or
                        item.get("subtotal") or 
                        item.get("valor") or 
                        0.0
                    )
                    
                    iva = (
                        resumen.get("totalIva") or 
                        resumen.get("iva") or 
                        resumen.get("ivaRenta") or 
                        resumen.get("ivaPerci1") or 
                        resumen.get("ivaRete1") or 
                        item.get("totalIva") or 
                        item.get("iva") or 
                        0.0
                    )
                    
                    if not iva and "tributos" in resumen and isinstance(resumen["tributos"], list):
                        iva_tributos = 0.0
                        for trib in resumen["tributos"]:
                            if isinstance(trib, dict):
                                val_trib = trib.get("valor") or trib.get("valTributo") or 0.0
                                try:
                                    iva_tributos += float(val_trib)
                                except:
                                    pass
                        if iva_tributos > 0:
                            iva = iva_tributos

                    total = (
                        resumen.get("totalPagar") or 
                        resumen.get("montoTotalOperacion") or 
                        resumen.get("total") or 
                        item.get("totalPagar") or 
                        item.get("total") or 
                        0.0
                    )
                    
                    try:
                        val_f = float(val) if val is not None else 0.0
                        iva_f = float(iva) if iva is not None else 0.0
                        total_f = float(total) if total is not None else 0.0
                        
                        if total_f == 0.0 and val_f > 0.0:
                            total_f = val_f + iva_f
                        elif val_f == 0.0 and total_f > 0.0 and iva_f > 0.0:
                            val_f = total_f - iva_f
                    except:
                        val_f, iva_f, total_f = 0.0, 0.0, 0.0
                        
                    summary_data.append({
                        "Código de Generación": str(gen_code),
                        "Número de Control": str(doc_num),
                        "Valor": val_f,
                        "IVA": iva_f,
                        "Total": total_f
                    })
            except Exception:
                summary_data.append({
                    "Código de Generación": "N/A",
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
if "user_id" not in st.session_state:
    st.session_state.user_id = ""

if "clients_db" not in st.session_state:
    st.session_state.clients_db = {}
if "employees_db" not in st.session_state:
    st.session_state.employees_db = {}
if "eventuales_db" not in st.session_state:
    st.session_state.eventuales_db = {}

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
                    if envio.get('notes'):
                        st.info(f"**📝 Notas / Aclaraciones del Cliente:**\n\n{envio['notes']}")
                    
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

# --- Panel del Cliente con las Pestañas Principales Solicitadas ---
def client_dashboard():
    st.title(f"📁 PORTAL DE CONTRIBUYENTE — {st.session_state.username}")
    st.markdown("Gestión documental, notas aclaratorias y generación de planillas fiscales.")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        mes = st.selectbox("MES FISCAL", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=5, key="client_mes")
    with col_p2:
        anio = st.selectbox("AÑO FISCAL", [2026, 2025], index=0, key="client_anio")
    with col_p3:
        quincena_op = st.selectbox("QUINCENA", ["Primera Quincena (Del 1 al 15)", "Segunda Quincena (Del 16 al Fin de Mes)"], key="client_quincena")
        
    periodo_str = f"{mes} {anio}"
    
    current_user_id = st.session_state.get("user_id", st.session_state.username)
    all_submissions = load_submissions()
    mis_envios = [s for s in all_submissions if s.get("user_id") == current_user_id or s.get("client") == st.session_state.username]
    envio_actual = next((s for s in mis_envios if s["periodo"] == periodo_str), None)
    
    st.markdown("### 📌 Estatus y Acciones Requeridas")
    if envio_actual:
        st.success(f"✔️ **Periodo {periodo_str} al día:** Tus documentos han sido recibidos correctamente y se encuentran en proceso de auditoría por RI Consultores.")
    else:
        st.warning(f"⚠️ **Acción requerida para {periodo_str}:** Aún no has enviado la información de tus documentos de Ventas y Compras. Por favor cárgalos en la pestaña correspondiente.")
        
    st.divider()
    
    # --- PESTAÑAS PRINCIPALES DEL PORTAL ---
    client_tab1, client_tab2, client_tab3, client_tab4 = st.tabs([
        "📁 CARGA DOCUMENTAL Y NOTAS", 
        "💼 GENERADOR DE PLANILLAS", 
        "📊 HISTORIAL Y RESUMEN",
        "🧾 CÁLCULOS MENSUALES PARA EVENTUALES 10%"
    ])
    
    with client_tab1:
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
                
            st.divider()
            st.subheader("📝 Notas Aclaratorias, Sugerencias y Observaciones por Documento o Mes")
            client_notes = st.text_area(
                "Usa este espacio para detallar aclaraciones sobre documentos específicos:",
                placeholder="Ej. El DTE-03 número... corresponde a una anulación extemporánea...",
                key="notes_input"
            )
                
            submit_files = st.form_submit_button("🚀 Validar y Enviar Documentación con Notas", use_container_width=True)
            
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
                        s_json_saved = save_files_to_folder(sales_json, st.session_state.username, periodo_str, "sales_json")
                        s_pdf_saved = save_files_to_folder(sales_pdf, st.session_state.username, periodo_str, "sales_pdf")
                        p_json_saved = save_files_to_folder(purch_json, st.session_state.username, periodo_str, "purch_json")
                        p_pdf_saved = save_files_to_folder(purch_pdf, st.session_state.username, periodo_str, "purch_pdf")
                        
                        submission_record = {
                            "user_id": current_user_id,
                            "client": st.session_state.username,
                            "periodo": periodo_str,
                            "sales_json_list": s_json_saved,
                            "sales_pdf_list": s_pdf_saved,
                            "purch_json_list": p_json_saved,
                            "purch_pdf_list": p_pdf_saved,
                            "notes": client_notes,
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
                        }
                        
                        save_submission_to_disk(submission_record)
                        st.success(f"¡Estructura validada! Documentos y notas del periodo {periodo_str} enviados correctamente a RI Consultores.")
                        st.rerun()
                    else:
                        st.error(f"❌ Error en el archivo '{archivo_fallido}': {error_detallado}")
                else:
                    st.warning("Adjunta al menos un archivo JSON principal antes de enviar.")

    with client_tab2:
        st.subheader("💼 MANTENIMIENTO DE PERSONAL Y PLANILLA QUINCENAL")
        
        if current_user_id not in st.session_state.employees_db:
            st.session_state.employees_db[current_user_id] = []
            
        emp_tab_add, emp_tab_manage, emp_tab_calc = st.tabs(["➕ Cargar Empleado", "✏️ Editar / Borrar Empleados", "🧮 Cálculo de Planilla"])
        
        with emp_tab_add:
            with st.form("form_add_employee"):
                new_emp_name = st.text_input("Nombre Completo del Empleado")
                new_emp_salario = st.number_input("Salario Base Mensual ($)", min_value=0.0, step=10.0, key="add_emp_sal")
                submit_add_emp = st.form_submit_button("Cargar Empleado al Sistema", use_container_width=True)
                
                if submit_add_emp:
                    if new_emp_name.strip():
                        st.session_state.employees_db[current_user_id].append({
                            "nombre": new_emp_name.strip(),
                            "salario": new_emp_salario
                        })
                        st.success(f"¡Empleado **{new_emp_name.strip()}** cargado al sistema exitosamente!")
                    else:
                        st.warning("Por favor ingresa el nombre del empleado.")
                        
        with emp_tab_manage:
            st.subheader("Listado de Personal Registrado")
            emps = st.session_state.employees_db.get(current_user_id, [])
            if emps:
                for idx, emp in enumerate(emps):
                    with st.expander(f"👤 {emp['nombre']} — Salario Base: ${emp['salario']:,.2f}"):
                        with st.form(f"edit_delete_emp_{idx}"):
                            ed_name = st.text_input("Editar Nombre", value=emp['nombre'], key=f"ed_name_{idx}")
                            ed_salario = st.number_input("Editar Salario Base Mensual ($)", min_value=0.0, step=10.0, value=float(emp['salario']), key=f"ed_sal_{idx}")
                            
                            col_btn1, col_btn2 = st.columns(2)
                            update_btn = col_btn1.form_submit_button("💾 Guardar Cambios", use_container_width=True)
                            delete_btn = col_btn2.form_submit_button("🗑️ Borrar Empleado", use_container_width=True)
                            
                            if update_btn:
                                st.session_state.employees_db[current_user_id][idx] = {
                                    "nombre": ed_name.strip(),
                                    "salario": ed_salario
                                }
                                st.success("¡Empleado actualizado correctamente!")
                                st.rerun()
                                
                            if delete_btn:
                                st.session_state.employees_db[current_user_id].pop(idx)
                                st.success("¡Empleado eliminado del sistema!")
                                st.rerun()
            else:
                st.info("No hay empleados cargados en el sistema todavía.")
                
        with emp_tab_calc:
            with st.form("form_planilla_quincenal"):
                emps = st.session_state.employees_db.get(current_user_id, [])
                emp_names = [e["nombre"] for e in emps] if emps else []
                
                if emp_names:
                    selected_emp_name = st.selectbox("Seleccionar Empleado Registrado", emp_names)
                    selected_emp_obj = next((e for e in emps if e["nombre"] == selected_emp_name), {"salario": 0.0})
                    default_sal = selected_emp_obj["salario"]
                else:
                    selected_emp_name = st.text_input("Nombre del Empleado Quincenal")
                    default_sal = 0.0
                    
                q_salario = st.number_input("Salario Base Mensual ($)", min_value=0.0, value=default_sal, step=10.0, key="q_sal")
                q_bono = st.number_input("Bonificaciones / Otros Ingresos ($)", min_value=0.0, step=5.0, key="q_bono")
                
                btn_q = st.form_submit_button("Calcular Quincena", use_container_width=True)
                if btn_q:
                    base_quincenal = (q_salario / 2.0) + q_bono
                    target_name = selected_emp_name if emp_names else (selected_emp_name or 'Empleado')
                    st.success(f"Resultado para {target_name} ({quincena_op}):")
                    st.metric("Total Devengado Quincenal", f"${base_quincenal:,.2f}")

    with client_tab3:
        st.subheader("📊 Historial de Declaraciones, Resumen Ejecutivo de IVA y Trazabilidad DTE")
        
        if mis_envios:
            st.info("Visualiza el detalle de tus declaraciones, las notas enviadas, el resumen de IVA y los códigos de generación correspondientes.")
            for envio in mis_envios:
                with st.expander(f"📅 Periodo: {envio['periodo']} — Entregado el {envio['fecha']}"):
                    if envio.get('notes'):
                        st.markdown("##### 📝 Tus Notas / Aclaraciones Enviadas")
                        st.info(envio['notes'])
                        st.markdown("---")
                    
                    df_sales = extract_invoice_summary(envio.get('sales_json_list'))
                    df_purch = extract_invoice_summary(envio.get('purch_json_list'))
                    
                    v_val = df_sales['Valor'].sum() if not df_sales.empty else 0.0
                    v_iva = df_sales['IVA'].sum() if not df_sales.empty else 0.0
                    v_tot = df_sales['Total'].sum() if not df_sales.empty else 0.0
                    
                    p_val = df_purch['Valor'].sum() if not df_purch.empty else 0.0
                    p_iva = df_purch['IVA'].sum() if not df_purch.empty else 0.0
                    p_tot = df_purch['Total'].sum() if not df_purch.empty else 0.0
                    
                    st.markdown("##### 💼 Resumen Ejecutivo de IVA")
                    col_re1, col_re2, col_re3 = st.columns(3)
                    col_re1.metric("Débito Fiscal (IVA Ventas)", f"${v_iva:,.2f}")
                    col_re2.metric("Crédito Fiscal (IVA Compras)", f"${p_iva:,.2f}")
                    
                    iva_neto = v_iva - p_iva
                    if iva_neto >= 0:
                        col_re3.metric("IVA a Pagar Estimado", f"${iva_neto:,.2f}", delta_color="inverse")
                    else:
                        col_re3.metric("Remanente de IVA a Favor", f"${abs(iva_neto):,.2f}", delta_color="normal")
                    
                    st.markdown("---")
                    st.markdown("##### 📈 Detalle de Ventas (Trazabilidad DTE)")
                    if not df_sales.empty:
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
                        
                    st.markdown("---")
                    st.markdown("##### 📉 Detalle de Compras y Gastos (Trazabilidad DTE)")
                    if not df_purch.empty:
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

    with client_tab4:
        st.subheader("🧾 MANTENIMIENTO DE EVENTUALES Y CÁLCULO DE 10%")
        
        if current_user_id not in st.session_state.eventuales_db:
            st.session_state.eventuales_db[current_user_id] = []
            
        ev_tab_add, ev_tab_manage, ev_tab_calc = st.tabs(["➕ Cargar Eventual", "✏️ Editar / Borrar Eventuales", "🧮 Calcular Todos y Crear Planilla"])
        
        with ev_tab_add:
            with st.form("form_add_eventual"):
                new_ev_name = st.text_input("Nombre Completo del Prestador de Servicios")
                new_ev_dui = st.text_input("DUI del Prestador de Servicios (ej. 00000000-0)")
                new_ev_monto = st.number_input("Monto Bruto Habitual ($)", min_value=0.0, step=10.0, key="add_ev_monto")
                submit_add_ev = st.form_submit_button("Cargar Eventual al Sistema", use_container_width=True)
                
                if submit_add_ev:
                    if new_ev_name.strip():
                        st.session_state.eventuales_db[current_user_id].append({
                            "nombre": new_ev_name.strip(),
                            "dui": new_ev_dui.strip(),
                            "monto": new_ev_monto
                        })
                        st.success(f"¡Prestador eventual **{new_ev_name.strip()}** cargado al sistema exitosamente!")
                    else:
                        st.warning("Por favor ingresa el nombre del prestador eventual.")
                        
        with ev_tab_manage:
            st.subheader("Listado de Personal Eventual Registrado")
            evs = st.session_state.eventuales_db.get(current_user_id, [])
            if evs:
                for idx, ev in enumerate(evs):
                    dui_str = f" - DUI: {ev['dui']}" if ev['dui'] else ""
                    with st.expander(f"👤 {ev['nombre']}{dui_str} — Monto Bruto Habitual: ${ev['monto']:,.2f}"):
                        with st.form(f"edit_delete_ev_{idx}"):
                            ed_ev_name = st.text_input("Editar Nombre", value=ev['nombre'], key=f"ed_ev_name_{idx}")
                            ed_ev_dui = st.text_input("Editar DUI", value=ev['dui'], key=f"ed_ev_dui_{idx}")
                            ed_ev_monto = st.number_input("Editar Monto Bruto Habitual ($)", min_value=0.0, step=10.0, value=float(ev['monto']), key=f"ed_ev_mon_{idx}")
                            
                            col_btn1, col_btn2 = st.columns(2)
                            update_ev_btn = col_btn1.form_submit_button("💾 Guardar Cambios", use_container_width=True)
                            delete_ev_btn = col_btn2.form_submit_button("🗑️ Borrar Eventual", use_container_width=True)
                            
                            if update_ev_btn:
                                st.session_state.eventuales_db[current_user_id][idx] = {
                                    "nombre": ed_ev_name.strip(),
                                    "dui": ed_ev_dui.strip(),
                                    "monto": ed_ev_monto
                                }
                                st.success("¡Prestador eventual actualizado correctamente!")
                                st.rerun()
                                
                            if delete_ev_btn:
                                st.session_state.eventuales_db[current_user_id].pop(idx)
                                st.success("¡Prestador eventual eliminado del sistema!")
                                st.rerun()
            else:
                st.info("No hay prestadores eventuales cargados en el sistema todavía.")
                
        with ev_tab_calc:
            st.subheader("🧮 Cálculo Masivo y Planilla de Retención (10% Eventuales)")
            st.info(f"ℹ️ Periodo fiscal en curso: **{periodo_str}**. Este módulo calcula la retención de renta del 10% para todos los prestadores eventuales y genera la planilla consolidada.")
            
            evs = st.session_state.eventuales_db.get(current_user_id, [])
            
            if evs:
                with st.form("form_calc_all_eventuales"):
                    st.markdown("##### Verifique o ajuste los montos brutos para la planilla actual:")
                    
                    updated_evs_data = []
                    for idx, ev in enumerate(evs):
                        col_n, col_d, col_m = st.columns([2, 1, 1])
                        with col_n:
                            st.text(ev['nombre'])
                        with col_d:
                            st.text(ev['dui'] or 'Sin DUI')
                        with col_m:
                            monto_val = st.number_input(
                                f"Monto ($) - {ev['nombre']}", 
                                min_value=0.0, 
                                value=float(ev['monto']), 
                                step=10.0, 
                                key=f"calc_all_monto_{idx}",
                                label_visibility="collapsed"
                            )
                        updated_evs_data.append({
                            "nombre": ev['nombre'],
                            "dui": ev['dui'],
                            "monto": monto_val
                        })
                    
                    btn_calc_all = st.form_submit_button("🚀 Calcular Todos y Crear Planilla", use_container_width=True)
                    
                if btn_calc_all:
                    planilla_data = []
                    total_bruto = 0.0
                    total_retencion = 0.0
                    total_liquido = 0.0
                    
                    for item in updated_evs_data:
                        bruto = item['monto']
                        retencion = bruto * 0.10
                        liquido = bruto - retencion
                        
                        total_bruto += bruto
                        total_retencion += retencion
                        total_liquido += liquido
                        
                        planilla_data.append({
                            "Prestador Eventual": item['nombre'],
                            "DUI": item['dui'] or "N/A",
                            "Monto Bruto": bruto,
                            "Retención 10%": retencion,
                            "Líquido a Pagar": liquido
                        })
                    
                    df_planilla = pd.DataFrame(planilla_data)
                    
                    st.success(f"¡Planilla de Eventuales para el periodo **{periodo_str}** calculada exitosamente!")
                    
                    st.markdown("##### 📊 Resumen Consolidado de la Planilla")
                    col_m1, col_m2, col_m3 = st.columns(3)
                    col_m1.metric("Total Bruto", f"${total_bruto:,.2f}")
                    col_m2.metric("Total Retención 10%", f"${total_retencion:,.2f}")
                    col_m3.metric("Total Líquido a Pagar", f"${total_liquido:,.2f}")
                    
                    st.markdown("##### 📋 Detalle de la Planilla")
                    st.dataframe(
                        df_planilla.style.format({
                            "Monto Bruto": "${:,.2f}",
                            "Retención 10%": "${:,.2f}",
                            "Líquido a Pagar": "${:,.2f}"
                        }),
                        use_container_width=True
                    )
                    
                    # Generación de Excel con formato profesional, periodo y totales generales
                    output = io.BytesIO()
                    
                    total_row_df = pd.DataFrame([{
                        "Prestador Eventual": "TOTALES GENERALES",
                        "DUI": "",
                        "Monto Bruto": total_bruto,
                        "Retención 10%": total_retencion,
                        "Líquido a Pagar": total_liquido
                    }])
                    df_export = pd.concat([df_planilla, total_row_df], ignore_index=True)
                    
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_export.to_excel(writer, index=False, sheet_name='Planilla Eventuales', startrow=4)
                        workbook = writer.book
                        worksheet = writer.sheets['Planilla Eventuales']
                        
                        # Metadatos superiores (Nombre de la planilla y periodo de referencia)
                        worksheet['A1'] = "RI CONSULTORES — PLANILLA DE RETENCIÓN DE RENTA (10% EVENTUALES)"
                        worksheet['A2'] = f"Periodo Fiscal / Mes de Referencia: {periodo_str}"
                        worksheet['A3'] = f"Cliente / Contribuyente: {st.session_state.username}"
                        
                        # Estilos profesionales
                        title_font = Font(name='Calibri', size=12, bold=True, color='1F4E78')
                        subtitle_font = Font(name='Calibri', size=10, bold=True, color='595959')
                        header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
                        header_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
                        
                        total_font = Font(name='Calibri', size=11, bold=True, color='000000')
                        total_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
                        
                        align_center = Alignment(horizontal='center', vertical='center')
                        align_right = Alignment(horizontal='right', vertical='center')
                        align_left = Alignment(horizontal='left', vertical='center')
                        
                        thin_border = Border(
                            left=Side(style='thin', color='D3D3D3'),
                            right=Side(style='thin', color='D3D3D3'),
                            top=Side(style='thin', color='D3D3D3'),
                            bottom=Side(style='thin', color='D3D3D3')
                        )
                        thick_bottom_border = Border(
                            left=Side(style='thin', color='D3D3D3'),
                            right=Side(style='thin', color='D3D3D3'),
                            top=Side(style='thin', color='D3D3D3'),
                            bottom=Side(style='double', color='000000')
                        )
                        
                        worksheet['A1'].font = title_font
                        worksheet['A2'].font = subtitle_font
                        worksheet['A3'].font = subtitle_font
                        
                        # Fila 5: Encabezados de la tabla (startrow=4)
                        header_row_idx = 5
                        for col_num in range(1, len(df_export.columns) + 1):
                            cell = worksheet.cell(row=header_row_idx, column=col_num)
                            cell.font = header_font
                            cell.fill = header_fill
                            cell.alignment = align_center
                            cell.border = thin_border
                            
                        # Aplicar formato a celdas de datos y fila de totales
                        total_row_idx = header_row_idx + len(df_export)
                        for row_idx in range(header_row_idx + 1, total_row_idx + 1):
                            is_total_row = (row_idx == total_row_idx)
                            for col_idx in range(1, len(df_export.columns) + 1):
                                cell = worksheet.cell(row=row_idx, column=col_idx)
                                if is_total_row:
                                    cell.font = total_font
                                    cell.fill = total_fill
                                    cell.border = thick_bottom_border
                                else:
                                    cell.border = thin_border
                                    
                                if col_idx in [3, 4, 5]: # Monto Bruto, Retención, Líquido
                                    cell.number_format = '$#,##0.00'
                                    cell.alignment = align_right
                                elif col_idx == 2: # DUI
                                    cell.alignment = align_center
                                else:
                                    cell.alignment = align_left
                                    
                        # Auto-ajuste de ancho de columnas
                        for col in worksheet.columns:
                            max_len = 0
                            for cell in col:
                                if cell.row >= 5:
                                    val_str = str(cell.value or '')
                                    if len(val_str) > max_len:
                                        max_len = len(val_str)
                            col_letter = get_column_letter(col[0].column)
                            worksheet.column_dimensions[col_letter].width = max(max_len + 4, 18)
                            
                    excel_data = output.getvalue()
                    
                    safe_client_name = st.session_state.username.replace(" ", "_").replace(".", "")
                    file_name_download = f"Planilla_Eventuales_10_{safe_client_name}_{periodo_str.replace(' ', '_')}.xlsx"
                    
                    st.download_button(
                        label="📥 Descargar Planilla de Eventuales en Excel (Formato Profesional)",
                        data=excel_data,
                        file_name=file_name_download,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            else:
                st.warning("⚠️ No hay prestadores eventuales registrados en el sistema. Por favor cargue al menos uno en la pestaña 'Cargar Eventual'.")

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
            st.session_state.user_id = ""
            st.rerun()
            
    if st.session_state.user_role == "admin":
        admin_dashboard()
    elif st.session_state.user_role == "client":
        client_dashboard()
