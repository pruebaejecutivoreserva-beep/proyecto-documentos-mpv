import json
import os
from typing import Dict, Any


BASE_PATH = os.path.dirname(os.path.abspath(__file__))


def _resolve_config_path() -> str:
    """
    Resuelve la ruta donde están los JSON de tipos de documento.

    Prioridad:
    1) ENV CONFIG_PATH (si lo defines en Cloud Run)
       - puede apuntar directo a .../document_types o a .../config
    2) Ruta local dentro del servicio: /app/config/document_types
       - equivalente a BASE_PATH/config/document_types
    3) Ruta legacy: /config/document_types (compatibilidad con builds viejos)
    """

    env_path = os.getenv("CONFIG_PATH")
    if env_path:
        env_path = env_path.strip()

        # Si te pasan CONFIG_PATH=/app/config, lo normalizamos a /app/config/document_types
        if os.path.isdir(env_path) and os.path.basename(env_path) != "document_types":
            candidate = os.path.join(env_path, "document_types")
            if os.path.isdir(candidate):
                return candidate

        # Si te pasan directo CONFIG_PATH=/app/config/document_types
        if os.path.isdir(env_path):
            return env_path

    local_path = os.path.join(BASE_PATH, "config", "document_types")
    if os.path.isdir(local_path):
        return local_path

    legacy_path = "/config/document_types"
    if os.path.isdir(legacy_path):
        return legacy_path

    # Si nada existe, devolvemos la ruta "local esperada" para que el error sea claro
    return local_path


CONFIG_PATH = _resolve_config_path()


def load_document_types() -> Dict[str, Dict[str, Any]]:
    """
    Carga todos los JSON de CONFIG_PATH y los devuelve como dict { ID_TIPO: config }
    """
    types: Dict[str, Dict[str, Any]] = {}

    if not os.path.isdir(CONFIG_PATH):
        searched = {
            "CONFIG_PATH_resuelto": CONFIG_PATH,
            "ENV_CONFIG_PATH": os.getenv("CONFIG_PATH"),
            "local_path_esperado": os.path.join(BASE_PATH, "config", "document_types"),
            "legacy_path": "/config/document_types",
        }
        raise RuntimeError(
            "No existe el directorio de configuraciones.\n"
            f"Detalles: {json.dumps(searched, ensure_ascii=False)}"
        )

    filenames = [f for f in os.listdir(CONFIG_PATH) if f.endswith(".json")]
    if not filenames:
        raise RuntimeError(
            f"El directorio existe pero no hay JSON en: {CONFIG_PATH}"
        )

    for filename in filenames:
        full_path = os.path.join(CONFIG_PATH, filename)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Error leyendo JSON {full_path}: {e}")

        if "id" not in config or not str(config["id"]).strip():
            raise ValueError(f"{filename} no tiene campo 'id' válido")

        types[str(config["id"]).strip()] = config

    return types


# Cache en memoria (se carga una vez por proceso)
DOCUMENT_TYPES = load_document_types()


def get_document_type(type_id: str):
    if type_id is None:
        return None
    return DOCUMENT_TYPES.get(str(type_id).strip())


def get_all_document_types():
    return DOCUMENT_TYPES
