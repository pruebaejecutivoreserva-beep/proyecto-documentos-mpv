import json
import os
from typing import Dict, Any, Optional


BASE_PATH = os.path.dirname(os.path.abspath(__file__))


def _normalize_env_path(env_path: str) -> Optional[str]:
    """
    Acepta:
    - /app/config/document_types   (directo)
    - /app/config                 (se normaliza a /app/config/document_types)
    - ./config, config, etc.      (se resuelve absoluto y se normaliza)
    """
    if not env_path:
        return None

    env_path = env_path.strip()
    if not env_path:
        return None

    # Si viene relativo, lo hacemos absoluto respecto a BASE_PATH
    if not os.path.isabs(env_path):
        env_path = os.path.abspath(os.path.join(BASE_PATH, env_path))

    # Si env_path es un dir y NO termina en document_types, intentamos agregarlo
    if os.path.isdir(env_path) and os.path.basename(env_path) != "document_types":
        candidate = os.path.join(env_path, "document_types")
        if os.path.isdir(candidate):
            return candidate

    # Si env_path es directo a document_types
    if os.path.isdir(env_path) and os.path.basename(env_path) == "document_types":
        return env_path

    # Si env_path existe como archivo o no existe, no sirve
    return None


def _resolve_document_types_path() -> str:
    """
    Resuelve la ruta donde están los JSON de tipos de documento.

    Prioridad:
    1) ENV DOCUMENT_TYPES_PATH (recomendado) o ENV CONFIG_PATH (compatibilidad)
       - puede apuntar directo a .../document_types o a .../config
    2) Ruta local dentro del servicio (si Dockerfile copia config a /app/config):
       - BASE_PATH/config/document_types  => normalmente /app/config/document_types
    3) Ruta alternativa si el build se hizo desde raíz del repo y el servicio vive en /app/servicio-sql:
       - /app/servicio-sql/config/document_types
    4) Ruta legacy:
       - /config/document_types
    """
    env_primary = os.getenv("DOCUMENT_TYPES_PATH")
    env_compat = os.getenv("CONFIG_PATH")

    # 1) ENV
    for raw in (env_primary, env_compat):
        normalized = _normalize_env_path(raw) if raw else None
        if normalized:
            return normalized

    # 2) Local esperado si el contenedor hace WORKDIR /app y copiamos config a /app/config
    local_path = os.path.join(BASE_PATH, "config", "document_types")
    if os.path.isdir(local_path):
        return local_path

    # 3) Alternativa típica si la app corre desde /app/servicio-sql
    alt_path = os.path.join("/app", "servicio-sql", "config", "document_types")
    if os.path.isdir(alt_path):
        return alt_path

    # 4) Legacy
    legacy_path = "/config/document_types"
    if os.path.isdir(legacy_path):
        return legacy_path

    # Si nada existe, devolvemos la ruta local esperada para que el error sea claro
    return local_path


DOCUMENT_TYPES_PATH = _resolve_document_types_path()


def load_document_types() -> Dict[str, Dict[str, Any]]:
    """
    Carga todos los JSON de DOCUMENT_TYPES_PATH y los devuelve como dict { ID_TIPO: config }
    """
    types: Dict[str, Dict[str, Any]] = {}

    if not os.path.isdir(DOCUMENT_TYPES_PATH):
        searched = {
            "DOCUMENT_TYPES_PATH_resuelto": DOCUMENT_TYPES_PATH,
            "ENV_DOCUMENT_TYPES_PATH": os.getenv("DOCUMENT_TYPES_PATH"),
            "ENV_CONFIG_PATH": os.getenv("CONFIG_PATH"),
            "BASE_PATH": BASE_PATH,
            "local_esperado": os.path.join(BASE_PATH, "config", "document_types"),
            "alt_esperado": "/app/servicio-sql/config/document_types",
            "legacy": "/config/document_types",
        }
        raise RuntimeError(
            "No existe el directorio de configuraciones para document_types.\n"
            f"Detalles: {json.dumps(searched, ensure_ascii=False)}"
        )

    filenames = [f for f in os.listdir(DOCUMENT_TYPES_PATH) if f.endswith(".json")]
    if not filenames:
        raise RuntimeError(f"El directorio existe pero no hay JSON en: {DOCUMENT_TYPES_PATH}")

    for filename in filenames:
        full_path = os.path.join(DOCUMENT_TYPES_PATH, filename)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Error leyendo JSON {full_path}: {e}")

        doc_id = str(config.get("id", "")).strip()
        if not doc_id:
            raise ValueError(f"{filename} no tiene campo 'id' válido")

        types[doc_id] = config

    return types


# Cache en memoria (se carga una vez por proceso)
DOCUMENT_TYPES = load_document_types()


def get_document_type(type_id: str):
    if type_id is None:
        return None
    return DOCUMENT_TYPES.get(str(type_id).strip())


def get_all_document_types():
    return DOCUMENT_TYPES
