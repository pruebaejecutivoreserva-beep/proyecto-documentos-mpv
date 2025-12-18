import os
import base64
import json
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

app = Flask(__name__)

# Configuración Base de Datos
db_uri = "postgresql://postgres:.|[M9L.d_qu8d7)7@34.176.211.158/documents_db"
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Documento(db.Model):
    __tablename__ = 'documentos'
    id = db.Column(db.Integer, primary_key=True)
    nombre_archivo = db.Column(db.String)
    tipo_documento = db.Column(db.String)
    url_almacenamiento = db.Column(db.String)
    contenido = db.Column(JSONB)
    fecha_proceso = db.Column(db.DateTime, default=datetime.utcnow)

@app.route("/", methods=["POST"])
def pubsub_push():
    # Pub/Sub envía los datos en un formato específico
    envelope = request.get_json()
    if not envelope:
        return "Bad Request: no Pub/Sub message received", 400

    pubsub_message = envelope.get("message")
    if not pubsub_message:
        return "Bad Request: invalid Pub/Sub message format", 400

    # Decodificar el mensaje que viene en Base64
    data = json.loads(base64.b64decode(pubsub_message["data"]).decode("utf-8"))

    try:
        new_doc = Documento(
            nombre_archivo=data.get('archivo'),
            url_almacenamiento=data.get('url_storage'),
            contenido=data, # Aquí va el texto del OCR
            tipo_documento="Pendiente"
        )
        db.session.add(new_doc)
        db.session.commit()
        print(f"Archivo guardado exitosamente: {data.get('archivo')}")
        return "OK", 201
    except Exception as e:
        print(f"Error al guardar: {str(e)}")
        return f"Error: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
