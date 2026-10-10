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

# --- Importación de Módulos Externos ---
from auditor_module import auditor_deliverables_portal
from admin_uploader_module import admin_file_uploader

# --- Configuración Inicial de la Página (Debe ser la primera orden de Streamlit) ---
st.set_page_config(
    page_title="Portal de Contribuyente - RI Consultores",
    page_icon="📊",
    layout="wide"
)

# --- Configuración de Persistencia en Disco (Soporte local y Render /data) ---
DATA_DIR = "/data" if os.path.exists("/data") else "."

DB_FILE = os.path.join(DATA_DIR, "submissions_db.json")
EMPLOYEES_FILE = os.path.join(DATA_DIR, "employees_db.json")
EVENTUALES_FILE = os.path.join(DATA_DIR, "eventuales_db.json")
CLIENTS_FILE = os.path.join(DATA_DIR, "clients_db.json")  # <-- NUEVO: Archivo persistente para clientes
UPLOAD_DIR = os.path.join(DATA_DIR, "uploaded_files")
LOG_FILE = os.path.join(DATA_DIR, "historial_entregas.json")
CARPETA_ENTREGABLES = os.path.join(DATA_DIR, "entregables_guardados")

# Asegurar que las carpetas existan en el entorno actual
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CARPETA_ENTREGABLES, exist_ok=True)

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

def load_json_db(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_db(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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

# --- Funciones de Cálculo de Ley (El Salvador) ---
def calcular_isss_quincenal(sueldo_base_q):
    base = min(sueldo_base_q, 500.0)
    return round(base * 0.03, 2)

def calcular_afp_quincenal(sueldo_base_q):
    return round(sueldo_base_q * 0.0725, 2)

def calcular_renta_quincenal(sueldo_neto_isss_afp):
    b = sueldo_neto_isss_afp
    if b <= 275.00:
        return 0.0
    elif b <= 447.62:
        return round((b - 275.00) * 0.10 + 8.83, 2)
    elif b <= 1019.05:
        return round((b - 447.62) * 0.20 + 30.00, 2)
    else:
        return round((b - 1019.05) * 0.30 + 144.28, 2)

def extract_invoice_summary(file_list):
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

# --- Inicialización de Estados de Sesión y Bases Persistentes ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = ""

if "employees_db" not in st.session_state:
    st.session_state.employees_db = load_json_db(EMPLOYEES_FILE)
if "eventuales_db" not in st.session_state:
    st.session_state.eventuales_db = load_json_db(EVENTUALES_FILE)

# --- Sincronización de Clientes Oficiales y Persistentes ---
official_clients = {
    "admin": {"password": "admin123", "role": "admin", "name": "Administrador General"},
    "soluciones_503": {"password": "sol503_2026", "role": "client", "name": "Soluciones 503 S.A.S. de C.V"},
    "distribuidora_libertad": {"password": "libertad_2026", "role": "client", "name": "Distribuidora Libertad"},
    "leftech": {"password": "leftech_2026", "role": "client", "name": "Leftech"},
    "cedillo": {"password": "cedillo_2026", "role": "client", "name": "Cedillo"},
    "mercadito_rosa": {"password": "rosa_2026", "role": "client", "name": "Mercadito Rosa de Saron AC"},
    "heavens_coffe": {"password": "heavens2026", "role": "client", "name": "Heavens Coffe SAS"}
}

if "clients_db" not in st.session_state:
    saved_clients = load_json_db(CLIENTS_FILE)
    if not saved_clients:
        saved_clients = official_clients
        save_json_db(CLIENTS_FILE, saved_clients)
    else:
        # Asegurar que los oficiales siempre estén presentes
        for k, v in official_clients.items():
            if k not in saved_clients:
                saved_clients[k] = v
        save_json_db(CLIENTS_FILE, saved_clients)
    st.session_state.clients_db = saved_clients

# --- Pantalla de Login ---
def login_screen():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 RI Consultores")
        st.markdown("### Portal de Gestión Documental y Auditoría")
        
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
        
        # ENLACES A SITIO WEB Y WHATSAPP EN PANTALLA DE LOGIN
        st.divider()
        st.markdown("🌐 **Sitio Web Oficial:** [Visítanos aquí](https://throbbing-sky-ca37.riconsultoressv2021.workers.dev/)")
        st.markdown("💬 **Soporte WhatsApp:** [Escríbenos (+503 7824 9071)](https://wa.me/50378249071)")

# --- Panel de Administración ---
def admin_dashboard():
    st.title("🎛️ Panel de Control - Administrador")
    st.markdown("Supervisa el cumplimiento fiscal, administra cuentas, revisa los documentos cargados y gestiona entregables de auditoría.")
    
    # Diagnóstico rápido de disco para tu tranquilidad
    with st.expander("🛠️ Diagnóstico de Disco Persistente"):
        st.write(f"Ruta actual de almacenamiento (`DATA_DIR`): `{DATA_DIR}`")
        st.write(f"¿Existe la carpeta de datos?: {os.path.exists(DATA_DIR)}")
        st.write(f"¿Disco Render activo (`/data`)?: {os.path.exists('/data')}")

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Estatus y Archivos Recibidos", "📤 Cargar Entregables de Auditoría", "➕ Crear Nuevo Usuario", "👥 Listado de Cuentas"])
    
    with tab1:
        st.subheader("Control de Recepción y Descarga de Documentos y Planillas")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_mes = st.selectbox("Filtrar por Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=5)
        with col_f2:
            filtro_anio = st.selectbox("Filtrar por Año", [2026, 2025], index=0)
            
        periodo_seleccionado = f"{filtro_mes} {filtro_anio}"
        all_submissions = load_submissions()
        envios_periodo = [s for s in all_submissions if s["periodo"] == periodo_seleccionado]
        
        if envios_periodo:
            st.success(f"Se encontraron {len(envios_periodo)} registros/entregas para el periodo {periodo_seleccionado}.")
            for idx, envio in enumerate(envios_periodo):
                if envio.get("type") == "planilla_quincenal_empleados":
                    with st.expander(f"💼 [PLANILLA QUINCENAL SUELDOS] {envio['client']} — ({envio.get('quincena', 'Quincena')}) — Entregado el {envio['fecha']}"):
                        st.markdown(f"**Periodo Fiscal:** {envio['periodo']} | **Quincena:** {envio.get('quincena', 'N/A')}")
                        st.markdown(f"**Resumen Consolidado:** Total Devengado: **${envio['total_devengado']:,.2f}** | ISSS: **${envio['total_isss']:,.2f}** | AFP: **${envio['total_afp']:,.2f}** | RENTA: **${envio['total_renta']:,.2f}** | Líquido a Pagar: **${envio['total_liquido']:,.2f}**")
                        
                        df_pq_admin = pd.DataFrame(envio['data'])
                        output_pq_adm = io.BytesIO()
                        total_row_pq_adm = pd.DataFrame([{
                            "Empleado": "TOTALES GENERALES",
                            "DUI": "",
                            "Código Renta": "",
                            "Salario Base M.": 0.0,
                            "Días Trab.": "",
                            "Bonif. / Ingresos": 0.0,
                            "Total Devengado Q.": envio['total_devengado'],
                            "ISSS": envio['total_isss'],
                            "AFP": envio['total_afp'],
                            "RENTA": envio['total_renta'],
                            "Líquido a Pagar": envio['total_liquido']
                        }])
                        df_exp_pq_adm = pd.concat([df_pq_admin, total_row_pq_adm], ignore_index=True)
                        
                        with pd.ExcelWriter(output_pq_adm, engine='openpyxl') as writer:
                            df_exp_pq_adm.to_excel(writer, index=False, sheet_name='Planilla Quincenal', startrow=4)
                            workbook = writer.book
                            worksheet = writer.sheets['Planilla Quincenal']
                            
                            worksheet['A1'] = f"RI CONSULTORES — PLANILLA DE SUELDOS QUINCENAL ({envio.get('quincena', '').upper()})"
                            worksheet['A2'] = f"Periodo Fiscal: {envio['periodo']}"
                            worksheet['A3'] = f"Cliente / Contribuyente: {envio['client']}"
                            
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
                                left=Side(style='thin', color='D3D3D3'), right=Side(style='thin', color='D3D3D3'),
                                top=Side(style='thin', color='D3D3D3'), bottom=Side(style='thin', color='D3D3D3')
                            )
                            thick_bottom_border = Border(
                                left=Side(style='thin', color='D3D3D3'), right=Side(style='thin', color='D3D3D3'),
                                top=Side(style='thin', color='D3D3D3'), bottom=Side(style='double', color='000000')
                            )
                            
                            worksheet['A1'].font = title_font
                            worksheet['A2'].font = subtitle_font
                            worksheet['A3'].font = subtitle_font
                            
                            header_row_idx = 5
                            for col_num in range(1, len(df_exp_pq_adm.columns) + 1):
                                cell = worksheet.cell(row=header_row_idx, column=col_num)
                                cell.font = header_font
                                cell.fill = header_fill
                                cell.alignment = align_center
                                cell.border = thin_border
                                
                            total_row_idx = header_row_idx + len(df_exp_pq_adm)
                            for row_idx in range(header_row_idx + 1, total_row_idx + 1):
                                is_total_row = (row_idx == total_row_idx)
                                for col_idx in range(1, len(df_exp_pq_adm.columns) + 1):
                                    cell = worksheet.cell(row=row_idx, column=col_idx)
                                    if is_total_row:
                                        cell.font = total_font
                                        cell.fill = total_fill
                                        cell.border = thick_bottom_border
                                    else:
                                        cell.border = thin_border
                                        
                                    if col_idx >= 6:
                                        cell.number_format = '$#,##0.00'
                                        cell.alignment = align_right
                                    elif col_idx == 5:
                                        cell.alignment = align_center
                                        cell.number_format = '0.0'
                                    elif col_idx in [2, 3]:
                                        cell.alignment = align_center
                                    else:
                                        cell.alignment = align_left
                                        
                            for col in worksheet.columns:
                                max_len = 0
                                for cell in col:
                                    if cell.row >= 5:
                                        val_str = str(cell.value or '')
                                        if len(val_str) > max_len:
                                            max_len = len(val_str)
                                col_letter = get_column_letter(col[0].column)
                                worksheet.column_dimensions[col_letter].width = max(max_len + 4, 18)
                                
                        excel_pq_adm_data = output_pq_adm.getvalue()
                        safe_c_name = envio['client'].replace(" ", "_").replace(".", "")
                        
                        st.download_button(
                            label="📥 Descargar Planilla Quincenal del Cliente (Excel)",
                            data=excel_pq_adm_data,
                            file_name=f"Planilla_Quincenal_{safe_c_name}_{envio['periodo'].replace(' ', '_')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_adm_pq_{idx}"
                        )

                elif envio.get("type") == "planilla_eventuales":
                    with st.expander(f"🧾 [PLANILLA EVENTUALES] {envio['client']} — Entregado el {envio['fecha']}"):
                        st.markdown(f"**Periodo Fiscal:** {envio['periodo']}")
                        st.markdown(f"**Resumen Consolidado:** Total Bruto: **${envio['total_bruto']:,.2f}** | Retención 10%: **${envio['total_retencion']:,.2f}** | Líquido a Pagar: **${envio['total_liquido']:,.2f}**")
                        
                        df_ev_admin = pd.DataFrame(envio['data'])
                        output_adm = io.BytesIO()
                        total_row_adm = pd.DataFrame([{
                            "Prestador Eventual": "TOTALES GENERALES",
                            "DUI": "",
                            "Monto Bruto": envio['total_bruto'],
                            "Retención 10%": envio['total_retencion'],
                            "Líquido a Pagar": envio['total_liquido']
                        }])
                        df_exp_adm = pd.concat([df_ev_admin, total_row_adm], ignore_index=True)
                        
                        with pd.ExcelWriter(output_adm, engine='openpyxl') as writer:
                            df_exp_adm.to_excel(writer, index=False, sheet_name='Planilla Eventuales', startrow=4)
                            workbook = writer.book
                            worksheet = writer.sheets['Planilla Eventuales']
                            
                            worksheet['A1'] = "RI CONSULTORES — PLANILLA DE RETENCIÓN DE RENTA (10% EVENTUALES)"
                            worksheet['A2'] = f"Periodo Fiscal / Mes de Referencia: {envio['periodo']}"
                            worksheet['A3'] = f"Cliente / Contribuyente: {envio['client']}"
                            
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
                                left=Side(style='thin', color='D3D3D3'), right=Side(style='thin', color='D3D3D3'),
                                top=Side(style='thin', color='D3D3D3'), bottom=Side(style='thin', color='D3D3D3')
                            )
                            thick_bottom_border = Border(
                                left=Side(style='thin', color='D3D3D3'), right=Side(style='thin', color='D3D3D3'),
                                top=Side(style='thin', color='D3D3D3'), bottom=Side(style='double', color='000000')
                            )
                            
                            worksheet['A1'].font = title_font
                            worksheet['A2'].font = subtitle_font
                            worksheet['A3'].font = subtitle_font
                            
                            header_row_idx = 5
                            for col_num in range(1, len(df_exp_adm.columns) + 1):
                                cell = worksheet.cell(row=header_row_idx, column=col_num)
                                cell.font = header_font
                                cell.fill = header_fill
                                cell.alignment = align_center
                                cell.border = thin_border
                                
                            total_row_idx = header_row_idx + len(df_exp_adm)
                            for row_idx in range(header_row_idx + 1, total_row_idx + 1):
                                is_total_row = (row_idx == total_row_idx)
                                for col_idx in range(1, len(df_exp_adm.columns) + 1):
                                    cell = worksheet.cell(row=row_idx, column=col_idx)
                                    if is_total_row:
                                        cell.font = total_font
                                        cell.fill = total_fill
                                        cell.border = thick_bottom_border
                                    else:
                                        cell.border = thin_border
                                        
                                    if col_idx in [3, 4, 5]:
                                        cell.number_format = '$#,##0.00'
                                        cell.alignment = align_right
                                    elif col_idx == 2:
                                        cell.alignment = align_center
                                    else:
                                        cell.alignment = align_left
                                        
                            for col in worksheet.columns:
                                max_len = 0
                                for cell in col:
                                    if cell.row >= 5:
                                        val_str = str(cell.value or '')
                                        if len(val_str) > max_len:
                                            max_len = len(val_str)
                                col_letter = get_column_letter(col[0].column)
                                worksheet.column_dimensions[col_letter].width = max(max_len + 4, 18)
                                
                        excel_adm_data = output_adm.getvalue()
                        safe_c_name = envio['client'].replace(" ", "_").replace(".", "")
                        
                        st.download_button(
                            label="📥 Descargar Planilla de Eventuales del Cliente (Excel)",
                            data=excel_adm_data,
                            file_name=f"Planilla_Eventuales_10_{safe_c_name}_{envio['periodo'].replace(' ', '_')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_adm_ev_{idx}"
                        )
                else:
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
            st.info(f"No hay documentos ni planillas registrados para el periodo {periodo_seleccionado} todavía.")

    with tab2:
        admin_file_uploader()

    with tab3:
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
                        # --- GUARDAR EN DISCO PERSISTENTE ---
                        save_json_db(CLIENTS_FILE, st.session_state.clients_db)
                        st.success(f"¡Cliente **{company_name}** registrado con éxito en el disco persistente!")
                else:
                    st.warning("Completa todos los campos.")

    with tab4:
        st.subheader("Cuentas de Clientes Activas")
        client_accounts = [{"Usuario ID": k, "Nombre": v["name"]} for k, v in st.session_state.clients_db.items() if v["role"] == "client"]
        if client_accounts:
            st.dataframe(pd.DataFrame(client_accounts), use_container_width=True)
        else:
            st.warning("No hay clientes registrados.")

# --- Panel del Cliente con Pestañas y Portal de Auditoría ---
def client_dashboard():
    st.title(f"📁 PORTAL DE CONTRIBUYENTE — {st.session_state.username}")
    st.markdown("Gestión documental, notas aclaratorias, generación de planillas fiscales y portal de auditoría.")
    
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
    envio_actual = next((s for s in mis_envios if s["periodo"] == periodo_str and s.get("type") not in ["planilla_eventuales", "planilla_quincenal_empleados"]), None)
    
    st.markdown("### 📌 Estatus y Acciones Requeridas")
    if envio_actual:
        st.success(f"✔️ **Periodo {periodo_str} al día:** Tus documentos han sido recibidos correctamente y se encuentran en proceso de auditoría por RI Consultores.")
    else:
        st.warning(f"⚠️ **Acción requerida para {periodo_str}:** Aún no has enviado la información de tus documentos de Ventas y Compras. Por favor cárgalos en la pestaña correspondiente.")
        
    st.divider()
    
    # --- PESTAÑAS PRINCIPALES DEL CLIENTE ---
    client_tab1, client_tab2, client_tab3, client_tab4, client_tab5 = st.tabs([
        "📁 CARGA DOCUMENTAL Y NOTAS", 
        "💼 GENERADOR DE PLANILLAS", 
        "📊 HISTORIAL Y RESUMEN",
        "🧾 BASE Y PLANILLA DE EVENTUALES (10%)",
        "🔍 ENTREGABLES DE AUDITORÍA"
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
            
        emp_tab_add, emp_tab_manage, emp_tab_calc = st.tabs(["➕ Cargar Empleado", "✏️ Editar / Borrar Empleados", "🧮 Cálculo Masivo de Planilla"])
        
        with emp_tab_add:
            with st.form("form_add_employee"):
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    new_emp_name = st.text_input("Nombre Completo del Empleado")
                    new_emp_dui = st.text_input("DUI del Empleado (ej. 00000000-0)")
                with col_e2:
                    new_emp_salario = st.number_input("Salario Base Mensual ($)", min_value=0.0, step=10.0, key="add_emp_sal")
                    new_emp_codigo = st.selectbox("Clasificación / Código de Renta", ["Código 01 (Sueldos y Salarios / Tabla)", "Código 60 (Otras Retenciones / Servicios)"], key="add_emp_cod")
                
                submit_add_emp = st.form_submit_button("Cargar Empleado al Sistema", use_container_width=True)
                
                if submit_add_emp:
                    if new_emp_name.strip():
                        if current_user_id not in st.session_state.employees_db:
                            st.session_state.employees_db[current_user_id] = []
                        st.session_state.employees_db[current_user_id].append({
                            "nombre": new_emp_name.strip(),
                            "dui": new_emp_dui.strip(),
                            "codigo": new_emp_codigo,
                            "salario": new_emp_salario
                        })
                        save_json_db(EMPLOYEES_FILE, st.session_state.employees_db)
                        st.success(f"¡Empleado **{new_emp_name.strip()}** cargado al sistema exitosamente con su DUI y código de renta!")
                        st.rerun()
                    else:
                        st.warning("Por favor ingresa el nombre del empleado.")
                        
        with emp_tab_manage:
            st.subheader("Listado de Personal Registrado")
            emps = st.session_state.employees_db.get(current_user_id, [])
            if emps:
                for idx, emp in enumerate(emps):
                    dui_txt = f" — DUI: {emp.get('dui', 'N/A')}" if emp.get('dui') else ""
                    cod_txt = f" | {emp.get('codigo', 'Código 01')}"
                    with st.expander(f"👤 {emp['nombre']}{dui_txt}{cod_txt} — Salario: ${emp['salario']:,.2f}"):
                        with st.form(f"edit_delete_emp_{idx}"):
                            ed_name = st.text_input("Editar Nombre", value=emp['nombre'], key=f"ed_name_{idx}")
                            ed_dui = st.text_input("Editar DUI", value=emp.get('dui', ''), key=f"ed_dui_{idx}")
                            ed_codigo = st.selectbox("Editar Código de Renta", ["Código 01 (Sueldos y Salarios / Tabla)", "Código 60 (Otras Retenciones / Servicios)"], index=0 if "01" in emp.get('codigo', '') else 1, key=f"ed_cod_{idx}")
                            ed_salario = st.number_input("Editar Salario Base Mensual ($)", min_value=0.0, step=10.0, value=float(emp['salario']), key=f"ed_sal_{idx}")
                            
                            col_btn1, col_btn2 = st.columns(2)
                            update_btn = col_btn1.form_submit_button("💾 Guardar Cambios", use_container_width=True)
                            delete_btn = col_btn2.form_submit_button("🗑️ Borrar Empleado", use_container_width=True)
                            
                            if update_btn:
                                st.session_state.employees_db[current_user_id][idx] = {
                                    "nombre": ed_name.strip(),
                                    "dui": ed_dui.strip(),
                                    "codigo": ed_codigo,
                                    "salario": ed_salario
                                }
                                save_json_db(EMPLOYEES_FILE, st.session_state.employees_db)
                                st.success("¡Empleado actualizado y guardado correctamente!")
                                st.rerun()
                                
                            if delete_btn:
                                st.session_state.employees_db[current_user_id].pop(idx)
                                save_json_db(EMPLOYEES_FILE, st.session_state.employees_db)
                                st.success("¡Empleado eliminado del sistema permanentemente!")
                                st.rerun()
            else:
                st.info("No hay empleados cargados en el sistema todavía.")
                
        with emp_tab_calc:
            st.markdown(f"##### 🧮 Cálculo Masivo de Planilla Quincenal — **{periodo_str}** ({quincena_op})")
            st.info("ℹ️ Indica los días trabajados en la quincena (máximo 15) y bonificaciones para cada empleado. El salario base se calculará de forma proporcional a los días laborados.")
            
            emps_calc = st.session_state.employees_db.get
