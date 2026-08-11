import streamlit as st

# Tus funciones existentes
def client_dashboard():
    # ... todo tu código actual del portal del cliente ...
    st.write("Vista del Cliente")

def auditor_deliverables_portal():
    # ... el código que generamos en el paso anterior ...
    st.write("Vista del Auditor")

def main():
    st.sidebar.title("🔐 Acceso al Sistema")
    
    # Selector de Rol para decidir qué portal cargar
    rol = st.sidebar.radio(
        "Seleccionar Portal:", 
        ["Portal del Contribuyente", "Portal de Auditoría (RI Consultores)"]
    )
    
    st.sidebar.divider()
    
    # Lógica de enrutamiento
    if rol == "Portal del Contribuyente":
        client_dashboard()
    else:
        auditor_deliverables_portal()

if __name__ == "__main__":
    main()