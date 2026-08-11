import streamlit as st
import os
import json
from datetime import datetime

AUDITOR_DB = "auditor_deliverables_db.json"
AUDITOR_DIR = "auditor_uploaded_files"

if not os.path.exists(AUDITOR_DIR):
    os.makedirs(AUDITOR_DIR)

def load_auditor_db():
    if os.path.exists(AUDITOR_DB):
        try:
            with open(AUDITOR_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_auditor_db(data):
    with open(AUDITOR_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def admin_file_uploader():
    st.subheader("📤 Carga de Entregables de Auditoría para Clientes")
    st.markdown("Sube reportes, declaraciones procesadas, dictámenes o archivos anexos para que el cliente pueda descargarlos desde su portal.")
    
    clients = st.session_state.get("clients_db", {})
    client_options = {k: v["name"] for k, v in clients.items() if v["role"] == "client"}
    
    if not client_options:
        st.warning("No hay clientes registrados para enviar archivos.")
        return
        
    with st.form("admin_upload_deliverable_form"):
        selected_client_id = st.selectbox(
            "Seleccionar Cliente Destino",
            options=list(client_options.keys()),
            format_func=lambda x: client_options[x]
        )
        
        periodo_aud = st.selectbox(
            "Periodo Fiscal del Entregable",
            ["Enero 2026", "Febrero 2026", "Marzo 2026", "Abril 2026", "Mayo 2026", "Junio 2026", "Julio 2026", "Agosto 2026", "Septiembre 2026", "Octubre 2026", "Noviembre 2026", "Diciembre 2026"],
            index=5
        )
        
        doc_title = st.text_input("Título / Descripción del Archivo (ej. Declaración IVA Procesada, Dictamen Fiscal)")
        
        uploaded_files = st.file_uploader(
            "Archivos Anexos (PDF, Excel, ZIP, etc.)", 
            type=["pdf", "xlsx", "xls", "zip", "json", "docx"], 
            accept_multiple_files=True
        )
        
        admin_notes = st.text_area("Notas o indicaciones del auditor para el cliente", placeholder="Ej. Adjunto la declaración validada...")
        
        submit_audit_file = st.form_submit_button("🚀 Enviar Entregable al Portal del Cliente", use_container_width=True)
        
        if submit_audit_file:
            if uploaded_files and doc_title.strip():
                client_name = client_options[selected_client_id]
                safe_client = selected_client_id.replace(" ", "_")
                safe_periodo = periodo_aud.replace(" ", "_")
                folder_path = os.path.join(AUDITOR_DIR, safe_client, safe_periodo)
                os.makedirs(folder_path, exist_ok=True)
                
                saved_files = []
                for file_obj in uploaded_files:
                    file_path = os.path.join(folder_path, file_obj.name)
                    file_obj.seek(0)
                    with open(file_path, "wb") as f:
                        f.write(file_obj.getbuffer())
                    saved_files.append({
                        "name": file_obj.name,
                        "path": file_path
                    })
                    
                record = {
                    "client_id": selected_client_id,
                    "client_name": client_name,
                    "periodo": periodo_aud,
                    "title": doc_title.strip(),
                    "files": saved_files,
                    "notes": admin_notes,
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                
                db = load_auditor_db()
                db.append(record)
                save_auditor_db(db)
                
                st.success(f"¡Entregable enviado con éxito para **{client_name}**!")
            else:
                st.warning("Debes ingresar un título y adjuntar al menos un archivo.")
