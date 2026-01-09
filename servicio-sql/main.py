import os
import base64
import json
from datetime import datetime

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

# Nuevos imports (Fase 1)
from classifier import classify_document
from extractor import extract_fields
from config_loader import get_document_type

app = Flask(__name__)

# =========================
# Configuración Base de Datos (ENV)
# =========================
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")

if not DATABASE_URL:
    raise RuntimeError(
        "Falta variable de entorno DATABASE_URL (ej: postgresql://user:pass@host:5432/dbname)"
    )

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Documento(db.Model):
    __tablename__ = "documentos"
    id = db.Column(db.Integer, primary_key=True)
    nombre_archivo = db.Column(db.String)
    tipo_documento = db.Column(db.String)  # ej: LIQUIDACION / DESCONOCIDO / Pendiente
    url_almacenamiento = db.Column(db.String)
    contenido = db.Column(JSONB)  # aquí guardas el payload OCR (y luego extracción)
    fecha_proceso = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# Utilidades
# =========================
def _get_ocr_text_from_contenido(contenido: dict) -> str:
    """
    Intenta obtener el texto OCR desde distintas llaves comunes.
    Ajusta esto cuando confirmemos el formato real que te entrega servicio-ocr.
    """
    if not isinstance(contenido, dict):
        return ""

    # posibles llaves
    for k in ["ocr_text", "texto", "text", "ocr", "contenido_texto"]:
        val = contenido.get(k)
        if isinstance(val, str) and val.strip():
            return val

    # si viene como contenido["ocr"]["texto"]
    ocr = contenido.get("ocr")
    if isinstance(ocr, dict):
        texto = ocr.get("texto")
        if isinstance(texto, str) and texto.strip():
            return texto

    return ""


# =========================
# Endpoint Pub/Sub (se mantiene)
# =========================
@app.route("/", methods=["POST"])
def pubsub_push():
    envelope = request.get_json(silent=True)
    if not envelope:
        return "Bad Request: no Pub/Sub message received", 400

    pubsub_message = envelope.get("message")
    if not pubsub_message:
        return "Bad Request: invalid Pub/Sub message format", 400

    try:
        data = json.loads(base64.b64decode(pubsub_message["data"]).decode("utf-8"))
    except Exception as e:
        return f"Bad Request: error decoding message: {str(e)}", 400

    try:
        new_doc = Documento(
            nombre_archivo=data.get("archivo"),
            url_almacenamiento=data.get("url_storage"),
            contenido=data,  # payload OCR original (luego agregamos extracción aquí mismo)
            tipo_documento="Pendiente",
        )
        db.session.add(new_doc)
        db.session.commit()
        return "OK", 201
    except Exception as e:
        return f"Error: {str(e)}", 500


# =========================
# Paso 5 - Endpoint de prueba (sin DB)
# =========================
@app.route("/process-text", methods=["POST"])
def process_text():
    data = request.get_json(silent=True) or {}
    ocr_text = data.get("ocr_text", "")

    if not isinstance(ocr_text, str) or not ocr_text.strip():
        return jsonify({"error": "ocr_text es requerido"}), 400

    doc_type, confidence, method, details = classify_document(ocr_text)

    response = {
        "clasificacion": {
            "tipo_documento": doc_type,
            "confianza": confidence,
            "metodo": method,
            "detalles": details,
        },
        "extraccion": {"campos": {}, "campos_faltantes": [], "errores": []},
    }

    if doc_type != "DESCONOCIDO":
        config = get_document_type(doc_type)
        if not config:
            return jsonify({"error": f"No existe config para tipo {doc_type}"}), 500

        campos, faltantes, errores = extract_fields(ocr_text, config)
        response["extraccion"]["campos"] = campos
        response["extraccion"]["campos_faltantes"] = faltantes
        response["extraccion"]["errores"] = errores

    return jsonify(response), 200


# =========================
# Paso 6 - Procesar documento guardado en DB por ID
# =========================
@app.route("/process-doc/<int:doc_id>", methods=["POST"])
def process_doc(doc_id: int):
    doc = Documento.query.get(doc_id)
    if not doc:
        return jsonify({"error": "Documento no encontrado"}), 404

    contenido = doc.contenido or {}
    ocr_text = _get_ocr_text_from_contenido(contenido)

    if not ocr_text.strip():
        return jsonify(
            {
                "error": "No se encontró texto OCR en contenido del documento",
                "hint": "Revisa qué llave trae el servicio OCR (ej: ocr_text / texto / ocr.texto)",
            }
        ), 400

    # Clasificación
    doc_type, confidence, method, details = classify_document(ocr_text)
    doc.tipo_documento = doc_type  # actualiza la columna simple

    # Guardamos dentro del JSONB también (sin romper tu data original)
    contenido.setdefault("clasificacion", {})
    contenido["clasificacion"] = {
        "tipo_documento": doc_type,
        "confianza": confidence,
        "metodo": method,
        "detalles": details,
        "fecha": datetime.utcnow().isoformat() + "Z",
    }

    # Extracción (solo si tipo conocido)
    extraccion = {"campos": {}, "campos_faltantes": [], "errores": []}
    if doc_type != "DESCONOCIDO":
        config = get_document_type(doc_type)
        if not config:
            return jsonify({"error": f"No existe config para tipo {doc_type}"}), 500

        campos, faltantes, errores = extract_fields(ocr_text, config)
        extraccion = {
            "version_diccionario": config.get("version", "1.0"),
            "campos": campos,
            "campos_faltantes": faltantes,
            "errores": errores,
            "fecha": datetime.utcnow().isoformat() + "Z",
        }

    contenido["extraccion"] = extraccion

    # Estado pipeline mínimo (sin cambiar tu diseño actual más de la cuenta)
    contenido.setdefault("estado_pipeline", {})
    contenido["estado_pipeline"]["etapa_actual"] = "EXTRAIDO" if doc_type != "DESCONOCIDO" else "CLASIFICADO"
    contenido["estado_pipeline"].setdefault("historial", [])
    contenido["estado_pipeline"]["historial"].append(
        {
            "etapa": contenido["estado_pipeline"]["etapa_actual"],
            "fecha": datetime.utcnow().isoformat() + "Z",
            "detalle": "Procesado por servicio-sql (clasificación + extracción)",
        }
    )

    # Persistir
    doc.contenido = contenido
    doc.fecha_proceso = datetime.utcnow()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error guardando resultado: {str(e)}"}), 500

    return jsonify(
        {
            "id": doc.id,
            "tipo_documento": doc.tipo_documento,
            "clasificacion": contenido.get("clasificacion"),
            "extraccion": contenido.get("extraccion"),
        }
    ), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
