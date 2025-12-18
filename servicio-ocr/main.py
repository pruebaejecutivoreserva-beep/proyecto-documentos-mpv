import os
import json
from flask import Flask, request, jsonify
from google.cloud import vision
from google.cloud import storage
from google.cloud import pubsub_v1

app = Flask(__name__)

# Configuración de Clientes
vision_client = vision.ImageAnnotatorClient()
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()

# Configuración de entorno
BUCKET_NAME = "documentos-mpv-storage"
PROJECT_ID = "documentos-mpv"
TOPIC_PATH = publisher.topic_path(PROJECT_ID, "ocr-results")

@app.route("/", methods=["POST"])
def process_ocr():
    if 'file' not in request.files:
        return jsonify({"error": "No se recibió archivo"}), 400
    
    file = request.files['file']
    filename = file.filename
    
    try:
        # 1. SUBIR AL BUCKET (Persistencia)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"entradas/{filename}")
        
        content = file.read()
        blob.upload_from_string(content, content_type=file.content_type)
        gcs_uri = f"gs://{BUCKET_NAME}/entradas/{filename}"

        # 2. PROCESAR OCR
        if filename.lower().endswith('.pdf'):
            input_config = vision.InputConfig(content=content, mime_type='application/pdf')
            feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            request_vision = vision.AnnotateFileRequest(input_config=input_config, features=[feature])
            response = vision_client.batch_annotate_files(requests=[request_vision])
            full_text = "\n".join([p.full_text_annotation.text for p in response.responses[0].responses if p.full_text_annotation])
        else:
            image = vision.Image(content=content)
            response = vision_client.document_text_detection(image=image)
            full_text = response.full_text_annotation.text if response.full_text_annotation else ""

        # 3. PUBLICAR A PUB/SUB (Asíncrono)
        payload = {
            "archivo": filename,
            "url_storage": gcs_uri,
            "contenido": full_text.replace("'", '"')
        }
        
        publisher.publish(TOPIC_PATH, data=json.dumps(payload).encode("utf-8"))

        return jsonify({
            "status": "Exito: Archivo guardado y procesando",
            "bucket_path": gcs_uri
        }), 202

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
