import streamlit as st
import json
import os
from datetime import datetime

# Archivos y carpetas de control
LOG_FILE = "historial_entregas.json"
CARPETA_ENTREGABLES = "entregables_guardados"

def auditor_deliverables_portal():
    st.header("🔍 Panel de Auditoría: Gestión de Entregables")

    # --- LÓGICA DE AUTENTICACIÓN ---
    if 'admin_autenticado' not in st.session_state:
        st.session_state.admin_autenticado = False

    if not st.session_state.admin_autenticado:
        password = st.text_input("Ingrese contraseña de Administrador:", type="password")
        if st.button("Acceder al Portal"):
            try:
                clave_correcta = st.secrets["ADMIN_PASSWORD"]
            except:
                clave_correcta = "admin123" # Clave temporal por defecto si no está en secrets
            
            if password == clave_correcta:
                st.session_state.admin_autenticado = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta. Acceso denegado.")
        return

    # Botón de salida del panel de administración
    if st.sidebar.button("🔒 Cerrar Sesión"):
        st.session_state.admin_autenticado = False
        st.rerun()

    # --- SELECTOR DE EMPRESAS ---
    cliente_seleccionado = st.selectbox(
        "Seleccionar Empresa / Contribuyente:",
        [
            "soluciones_503",
            "distribuidora_libertad",
            "leftech",
            "cedillo",
            "mercadito_rosa"
        ]
    )
    
    st.info(f"Trabajando actualmente con: **{cliente_seleccionado}**")
    st.divider()
    
    # --- PESTAÑAS DE FLUJO ---
    tab1, tab2 = st.tabs(["📤 Cargar y Enviar", "📜 Historial de Auditoría"])

    with tab1:
        st.subheader(f"Cargar nuevo entregable para: {cliente_seleccionado}")
        
        # Campos de captura fuera del form para garantizar la carga fluida de archivos
        col1, col2 = st.columns(2)
        with col1:
            periodo = st.text_input("Periodo Fiscal (ej. 2026)")
        with col2:
            tipo = st.selectbox(
                "Tipo de Entregable", 
                ["Anexos de Declaraciones"]
            )
            fecha = st.date_input("Fecha de emisión")
        
        # Selector múltiple de archivos habilitado
        archivos = st.file_uploader(
            "Adjuntar archivos (PDF, Excel, ZIP, etc.)", 
            accept_multiple_files=True,
            type=["pdf", "xlsx", "xls", "zip", "rar", "txt", "docx"]
        )
        
        notas = st.text_area("Notas u observaciones para el contribuyente")
        
        if st.button("🚀 Procesar y Guardar Entregable"):
            if archivos:
                # 1. Crear estructura de carpetas física si no existe
                if not os.path.exists(CARPETA_ENTREGABLES):
                    os.makedirs(CARPETA_ENTREGABLES)
                
                cliente_dir = os.path.join(CARPETA_ENTREGABLES, cliente_seleccionado)
                if not os.path.exists(cliente_dir):
                    os.makedirs(cliente_dir)
                
                # 2. Guardar físicamente cada archivo adjunto
                nombres_guardados = []
                for archivo in archivos:
                    ruta_destino = os.path.join(cliente_dir, archivo.name)
                    with open(ruta_destino, "wb") as f:
                        f.write(archivo.getbuffer())
                    nombres_guardados.append(archivo.name)
                
                # 3. Registrar la operación en el archivo JSON de control
                registro = {
                    "cliente": cliente_seleccionado,
                    "tipo": tipo,
                    "periodo": periodo,
                    "fecha_emision": str(fecha),
                    "archivos": nombres_guardados,
                    "notas": notas,
                    "fecha_registro": str(datetime.now())
                }
                
                data = []
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, "r") as f:
                        data = json.load(f)
                
                data.append(registro)
                
                with open(LOG_FILE, "w") as f:
                    json.dump(data, f, indent=4)
                
                st.success(f"¡Se han guardado y enviado {len(archivos)} archivo(s) correctamente para {cliente_seleccionado}!")
            else:
                st.error("Por favor adjunta al menos un archivo antes de procesar el envío.")

    with tab2:
        st.subheader("Registros de Envíos Realizados")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                historial = json.load(f)
                st.table(historial)
        else:
            st.info("No hay entregables registrados aún.")
