import streamlit as st
import json
import os
from datetime import datetime

# Archivo donde guardaremos el registro de entregables enviados
LOG_FILE = "historial_entregas.json"

import streamlit as st

# Selector de empresas creadas para la gestión de auditoría y entregables
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

st.write(f"Trabajando actualmente con: **{cliente_seleccionado}**")

def auditor_deliverables_portal():
    st.header("🔍 Panel de Auditoría: Gestión de Entregables")
    
    # --- Pestañas para organizar el flujo ---
    tab1, tab2 = st.tabs(["📤 Cargar y Enviar", "📜 Historial de Auditoría"])

    with tab1:
        st.subheader("Cargar nuevo entregable")
        
        with st.form("form_auditor", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                cliente = st.text_input("Nombre del Cliente/Empresa")
                periodo = st.text_input("Periodo Fiscal (ej. 2026)")
            with col2:
                tipo = st.selectbox("Tipo de Entregable", 
                                    ["Aenxos de Declaraciones"])
                fecha = st.date_input("Fecha de emisión")
            
            archivos = st.file_uploader("Adjuntar archivos", accept_multiple_files=True)
            notas = st.text_area("Notas para el cliente")
            
            submitted = st.form_submit_button("🚀 Procesar y 'Enviar' Entregable")
            
            if submitted:
                if archivos and cliente:
                    # 1. Aquí guardarías los archivos en una carpeta (ej: /entregables)
                    # Por ahora simulamos el registro del envío
                    registro = {
                        "cliente": cliente,
                        "tipo": tipo,
                        "periodo": periodo,
                        "fecha": str(fecha),
                        "archivos_procesados": [f.name for f in archivos]
                    }
                    
                    # 2. Guardar en JSON (Base de datos simple)
                    data = []
                    if os.path.exists(LOG_FILE):
                        with open(LOG_FILE, "r") as f:
                            data = json.load(f)
                    
                    data.append(registro)
                    
                    with open(LOG_FILE, "w") as f:
                        json.dump(data, f, indent=4)
                    
                    st.success(f"¡Entregable de {tipo} registrado y listo para el cliente {cliente}!")
                else:
                    st.error("Por favor completa los campos obligatorios y sube al menos un archivo.")

    with tab2:
        st.subheader("Registros de Envíos")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                historial = json.load(f)
                st.table(historial)
        else:
            st.info("No hay entregables registrados aún.")
