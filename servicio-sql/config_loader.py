import json
import os

BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# Ruta al directorio config/document_types del repo
CONFIG_PATH = os.path.join(BASE_PATH, "config", "document_types")

def load_document_types():
    """
    Carga todos los JSON de config/document_types
    y los devuelve como dict { ID_TIPO: config }
    """
    types = {}

    if not os.path.exists(CONFIG_PATH):
        raise RuntimeError(f"No existe el directorio de configuraciones: {CONFIG_PATH}")

    for filename in os.listdir(CONFIG_PATH):
        if not filename.endswith(".json"):
            continue

        full_path = os.path.join(CONFIG_PATH, filename)

        with open(full_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if "id" not in config:
            raise ValueError(f"{filename} no tiene campo 'id'")

        types[config["id"]] = config

    return types


# Cache en memoria (se carga una vez por proceso)
DOCUMENT_TYPES = load_document_types()


def get_document_type(type_id):
    return DOCUMENT_TYPES.get(type_id)


def get_all_document_types():
    return DOCUMENT_TYPES
