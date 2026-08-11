import streamlit as st
import json
import os

def auditor_deliverables_portal(nombre_empresa_actual):
    st.subheader("📥 Documentos y Entregables Recibidos de Auditoría")
    
    LOG_FILE = "historial_entregas.json"
    
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            try:
                historial = json.load(f)
            except json.JSONDecodeError:
                historial = []
            
        # Filtramos únicamente los registros que coincidan con la empresa actual del cliente
        entregables_cliente = [
            item for item in historial if item.get("cliente") == nombre_empresa_actual
        ]
        
        if entregables_cliente:
            for idx, entrega in enumerate(entregables_cliente):
                with st.expander(f"📁 {entrega.get('tipo', 'Documento')} — Periodo: {entrega.get('periodo', 'N/A')} (Fecha: {entrega.get('fecha_emision', 'N/A')})"):
                    st.write(f"**Notas del auditor:** {entrega.get('notas', 'Sin observaciones')}")
                    st.markdown("**Archivos adjuntos disponibles:**")
                    
                    # Mostrar enlaces de descarga
                    for archivo in entrega.get("archivos", []):
                        ruta_archivo = os.path.join("entregables_guardados", nombre_empresa_actual, archivo)
                        if os.path.exists(ruta_archivo):
                            with open(ruta_archivo, "rb") as file_to_download:
                                st.download_button(
                                    label=f"⬇️ Descargar {archivo}",
                                    data=file_to_download,
                                    file_name=archivo,
                                    key=f"download_{nombre_empresa_actual}_{idx}_{archivo}"
                                )
                        else:
                            st.warning(f"El archivo {archivo} no se encuentra disponible temporalmente en el servidor.")
        else:
            st.info("No tienes entregables o anexos de auditoría pendientes de descarga.")
    else:
        st.info("No hay registros de entregas en el sistema.")
