import streamlit as st
import requests

st.set_page_config(page_title="APS - Extractor Integral", layout="wide")

st.image("logo-aps.png", width=150)
st.title("Extractor de Datos para Análisis SQL")
st.markdown("---")

archivo = st.file_uploader("Cargar PDF o Imagen", type=['pdf', 'jpg', 'png', 'jpeg'])

if archivo:
    if st.button("EJECUTAR EXTRACCIÓN COMPLETA"):
        with st.spinner("El motor está discriminando el tipo de archivo y realizando OCR..."):
            try:
                # URL de tu motor potente con 2GB RAM
                url = "https://servicio-1-ocr-v2-22596087784.europe-west1.run.app"
                files = {"file": (archivo.name, archivo.getvalue(), archivo.type)}
                
                r = requests.post(url, files=files, timeout=300)
                
                if r.status_code == 200:
                    res = r.json()
                    st.success("✅ Datos persistidos en PostgreSQL")
                    
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.subheader("Metadatos de Control")
                        st.write(f"**Archivo:** {archivo.name}")
                        st.write(f"**Tipo detectado:** {res.get('tipo_archivo', 'Auto')}")
                    
                    with col2:
                        st.subheader("Contenido Almacenado (para SQL)")
                        # Aquí mostramos el texto completo que se guardó en la columna 'contenido'
                        texto_final = res.get('texto', res.get('data_extraida', 'No se recuperó texto'))
                        st.text_area("Texto Bruto Extraído", texto_final, height=400)
                else:
                    st.error(f"Error del motor: {r.status_code}")
            except Exception as e:
                st.error(f"Error de conexión: {e}")

st.sidebar.warning("Foco: Extracción completa para análisis posterior mediante consultas JSONB.")
