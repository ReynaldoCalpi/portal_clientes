import streamlit as st
import os
import json
import io
import zipfile

AUDITOR_DB = "auditor_deliverables_db.json"

def load_auditor_db():
    if os.path.exists(AUDITOR_DB):
        try:
            with open(AUDITOR_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def create_zip_from_files(files_list):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_info in files_list:
            if os.path.exists(file_info['path']):
                zip_file.write(file_info['path'], arcname=file_info['name'])
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def auditor_deliverables_portal(current_username):
    st.subheader("🔍 Entregables y Reportes de Auditoría")
    st.markdown("Aquí encontrarás los documentos, declaraciones procesadas y reportes oficiales enviados por RI Consultores para ti.")
    
    db = load_auditor_db()
    current_user_id = st.session_state.get("user_id", "")
    
    # Filtro robusto que compara tanto el ID de usuario como el nombre comercial
    mis_entregables = [
        r for r in db 
        if r.get("client_id") == current_user_id or 
           r.get("client_name") == current_username or 
           r.get("client_id") == current_username
    ]
    
    if mis_entregables:
        st.success(f"Se encontraron {len(mis_entregables)} entregables o reportes disponibles.")
        for idx, item in enumerate(mis_entregables):
            with st.expander(f"📁 [{item['periodo']}] {item['title']} — (Enviado el {item['fecha']})"):
                if item.get("notes"):
                    st.info(f"**📝 Notas del Auditor:**\n\n{item['notes']}")
                    
                files = item.get("files", [])
                if files:
                    st.markdown("**📂 Archivos Disponibles para Descarga:**")
                    
                    if len(files) > 1:
                        zip_bytes = create_zip_from_files(files)
                        st.download_button(
                            label="📦 Descargar todos los archivos (ZIP)",
                            data=zip_bytes,
                            file_name=f"Entregables_{item['periodo'].replace(' ', '_')}.zip",
                            mime="application/zip",
                            key=f"dl_aud_zip_{idx}"
                        )
                        st.divider()
                        
                    for f_idx, file_info in enumerate(files):
                        if os.path.exists(file_info['path']):
                            with open(file_info['path'], "rb") as f_in:
                                file_bytes = f_in.read()
                            st.download_button(
                                label=f"📥 Descargar: {file_info['name']}",
                                data=file_bytes,
                                file_name=file_info['name'],
                                mime="application/octet-stream",
                                key=f"dl_ind_{idx}_{f_idx}"
                            )
                else:
                    st.warning("Este registro no contiene archivos adjuntos.")
    else:
        st.info("No tienes entregables de auditoría pendientes ni archivos nuevos en este momento.")
