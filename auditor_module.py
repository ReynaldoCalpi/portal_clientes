import streamlit as st
import json
import os
from datetime import datetime

# Archivo donde guardaremos el registro de entregables enviados
LOG_FILE = "historial_entregas.json"

def auditor_deliverables_portal():
    st.header("🔍 Panel de Auditoría: Gestión de Entregables")
    
    # Selector de empresas integrado dentro del módulo de auditoría
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
    
    # --- Pestañas para organizar el flujo ---
    tab1, tab2 = st.tabs(["📤 Cargar y Enviar", "📜 Historial de Auditoría"])

    with tab1:
        st.subheader(f"Cargar nuevo entregable para: {cliente_seleccionado}")
        
        with st.form("form_auditor", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                periodo = st.text_input("Periodo Fiscal (ej. 2026)")
            with col2:
                tipo = st.selectbox(
                    "Tipo de Entregable", 
                    ["Libros de Ventas", "Libros de Compras", "Planillas", "Declaraciones", "Anexos Financieros", "Dictamen Fiscal"]
                )
                fecha = st.date_input("Fecha de emisión")
            
            archivos = st.file_uploader("Adjuntar archivos", accept_multiple_files=True)
            notas = st.text_area("Notas para el cliente")
            
            submitted = st.form_submit_button("🚀 Procesar y 'Enviar' Entregable")
            
            if submitted:
                if archivos:
                    registro = {
                        "cliente": cliente_seleccionado,
                        "tipo": tipo,
                        "periodo": periodo,
                        "fecha": str(fecha),
                        "archivos_procesados": [f.name for f in archivos],
                        "notas": notas
                    }
                    
                    data = []
                    if os.path.exists(LOG_FILE):
                        with open(LOG_FILE, "r") as f:
                            data = json.load(f)
                    
                    data.append(registro)
                    
                    with open(LOG_FILE, "w") as f:
                        json.dump(data, f, indent=4)
                    
                    st.success(f"¡Entregable de {tipo} registrado con éxito para {cliente_seleccionado}!")
                else:
                    st.error("Por favor adjunta al menos un archivo antes de procesar.")

    with tab2:
        st.subheader("Registros de Envíos")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                historial = json.load(f)
                st.table(historial)
        else:
            st.info("No hay entregables registrados aún.")
