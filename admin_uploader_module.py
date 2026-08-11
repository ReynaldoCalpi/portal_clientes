import streamlit as st
import json
import os
from datetime import datetime

def admin_file_uploader():
    st.header("📤 Portal de Carga: Entregables de Auditoría")
    
    # Lista de clientes (puedes cargar esto desde una DB o archivo de configuración)
    clientes = ["Empresa_A", "Empresa_B", "Transportes_Calpi"] # Ejemplo
    cliente_seleccionado = st.selectbox("Seleccionar Cliente:", clientes)
    
    with st.form("uploader_form", clear_on_submit=True):
        tipo_doc = st.text_input("Tipo de Documento (ej. Dictamen, Anexo, Declaración):")
        periodo = st.text_input("Periodo (ej. Agosto 2026):")
        notas = st.text_area("Notas para el cliente:")
        uploaded_files = st.file_uploader("Seleccionar archivos:", accept_multiple_files=True)
        
        submit = st.form_submit_button("Cargar y Notificar")
        
    if submit and uploaded_files and cliente_seleccionado:
        # 1. Crear directorio del cliente si no existe
        ruta_cliente = os.path.join("entregables_guardados", cliente_seleccionado)
        os.makedirs(ruta_cliente, exist_ok=True)
        
        nombres_archivos = []
        
        # 2. Guardar archivos físicamente
        for file in uploaded_files:
            ruta_guardado = os.path.join(ruta_cliente, file.name)
            with open(ruta_guardado, "wb") as f:
                f.write(file.getbuffer())
            nombres_archivos.append(file.name)
            
        # 3. Actualizar el JSON de historial
        LOG_FILE = "historial_entregas.json"
        nuevo_registro = {
            "cliente": cliente_seleccionado,
            "tipo": tipo_doc,
            "periodo": periodo,
            "notas": notas,
            "archivos": nombres_archivos,
            "fecha_emision": datetime.now().strftime("%Y-%m-%d")
        }
        
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                try:
                    historial = json.load(f)
                except json.JSONDecodeError:
                    historial = []
        else:
            historial = []
            
        historial.append(nuevo_registro)
        
        with open(LOG_FILE, "w") as f:
            json.dump(historial, f, indent=4)
            
        st.success(f"Archivos cargados correctamente para {cliente_seleccionado}.")