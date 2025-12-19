import os, json, psycopg2, fitz
from flask import Flask, request, jsonify
app = Flask(__name__)

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', '34.176.211.158'),
        database=os.environ.get('DB_NAME', 'postgres'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASS', 'TU_PASSWORD')
    )

@app.route('/', methods=['POST'])
def procesar():
    try:
        file = request.files['file']
        file_bytes = file.read()
        texto = ""
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for p in doc: texto += p.get_text()
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO documentos (nombre_archivo, contenido) VALUES (%s, %s) RETURNING id",
                    (file.filename, json.dumps({"contenido": texto, "archivo": file.filename})))
        nuevo_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"id": nuevo_id, "texto": texto})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
