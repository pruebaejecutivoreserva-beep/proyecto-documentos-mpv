import os
import requests
from flask import Flask, request, jsonify
from google.cloud import vision

app = Flask(__name__)
client = vision.ImageAnnotatorClient()

# Endpoint del Servicio 2
SQL_SERVICE_URL = "https://servicio-2-sql-v2-22596087784.europe-west1.run.app"

@app.route("/", methods=["POST"])
def process_ocr():
    if 'file' not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400
    
    file = request.files['file']
    filename = file.filename
    content = file.read()
    mime_type = file.content_type
    
    try:
        # --- LÓGICA DE EXTRACCIÓN INTELIGENTE ---
        if filename.lower().endswith('.pdf') or mime_type == 'application/pdf':
            # Configuración para PDFs (Certificados, F30, Contratos largos)
            input_config = vision.InputConfig(content=content, mime_type='application/pdf')
            feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            request_vision = vision.AnnotateFileRequest(input_config=input_config, features=[feature])
            
            response = client.batch_annotate_files(requests=[request_vision])
            
            # Consolidamos todas las páginas
            full_text = ""
            for page_response in response.responses[0].responses:
                if page_response.full_text_annotation:
                    full_text += page_response.full_text_annotation.text + "\n"
        else:
            # Configuración para Imágenes (Liquidaciones, EPP, Cursos, ODI)
            image = vision.Image(content=content)
            response = client.document_text_detection(image=image)
            full_text = response.full_text_annotation.text if response.full_text_annotation else ""

        if not full_text.strip():
            return jsonify({"error": "El motor no pudo extraer texto legible del archivo"}), 422

        # --- PREPARACIÓN Y PERSISTENCIA ---
        # Limpiamos el texto para evitar errores de inserción SQL
        clean_text = full_text.replace("'", '"')
        
        payload = {
            "contenido": clean_text,
            "archivo": filename
        }
        
        # Guardar en base de datos
        requests.post(SQL_SERVICE_URL, json=payload, timeout=60)
        
        return jsonify({
            "status": "Procesado",
            "metadatos": {
                "archivo": filename,
                "paginas_o_tipo": "Multi-página PDF" if filename.lower().endswith('.pdf') else "Imagen Única"
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
