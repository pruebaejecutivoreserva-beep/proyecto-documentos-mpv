import os
from flask import Flask, request
import sqlalchemy
from google.cloud.sql.connector import Connector

app = Flask(__name__)

# Configuración de conexión
def getconn():
    connector = Connector()
    conn = connector.connect(
        os.environ["DB_INSTANCE_CONNECTION_NAME"],
        "pymysql",
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        db=os.environ["DB_NAME"]
    )
    return conn

# Crear el motor de base de datos
pool = sqlalchemy.create_engine(
    "mysql+pymysql://",
    creator=getconn,
)

@app.route("/", methods=["POST"])
def store_data():
    data = request.get_json()
    
    # SQL para insertar los datos extraídos
    insert_stmt = sqlalchemy.text(
        "INSERT INTO document_data (file_name, document_type, raw_text) VALUES (:file_name, :document_type, :raw_text)"
    )
    
    with pool.connect() as db_conn:
        db_conn.execute(insert_stmt, parameters={
            "file_name": data.get("file_name"),
            "document_type": data.get("document_type"),
            "raw_text": data.get("raw_text")
        })
        db_conn.commit()
    
    return "Datos guardados en SQL correctamente", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))