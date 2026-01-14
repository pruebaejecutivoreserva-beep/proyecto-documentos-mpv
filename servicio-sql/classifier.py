import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

from unidecode import unidecode
from config_loader import get_all_document_types


# =========================
# Helpers de normalización
# =========================

def normalize_text(text: str) -> str:
    """
    Normaliza para comparación robusta contra OCR:
    - quita acentos
    - mayúsculas
    - colapsa espacios
    """
    if not text:
        return ""
    text = unidecode(text).upper()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def keyword_match(text_norm: str, kw_norm: str, mode: str = "word") -> bool:
    """
    mode:
      - "contains": substring simple (más permisivo)
      - "word": match por bordes (recomendado)
    """
    if not kw_norm:
        return False

    if mode == "contains":
        return kw_norm in text_norm

    # "word": bordes de palabra. Si kw tiene espacios, igual funciona.
    # Ej: "LIQUIDACION DE SUELDO" -> \bLIQUIDACION\ DE\ SUELDO\b
    pattern = r"\b" + re.escape(kw_norm) + r"\b"
    return re.search(pattern, text_norm) is not None


def safe_regex_search(pattern: str, text_norm: str) -> Tuple[bool, Optional[str]]:
    """
    Retorna (match, error). Nunca revienta.
    """
    if not pattern:
        return (False, None)
    try:
        return (re.search(pattern, text_norm, re.IGNORECASE) is not None, None)
    except re.error as e:
        return (False, str(e))


# =========================
# Scoring configurable
# =========================

@dataclass
class ScoringPolicy:
    # Pesos por defecto (muy razonables para OCR real)
    w_keyword: float = 0.20
    w_regex_title: float = 0.60

    # Umbral default si el JSON no lo trae
    default_min_conf: float = 0.60

    # Modo de matching de keywords
    keyword_mode: str = "word"  # "word" recomendado / "contains" más permisivo

    # Debug: cuántos candidatos devolver cuando no clasifica
    debug_top_k: int = 3


DEFAULT_POLICY = ScoringPolicy()


def _get_policy(cfg: Dict[str, Any]) -> ScoringPolicy:
    """
    Permite que el JSON overridee pesos/umbral/mode si lo deseas:
    Dentro de "clasificacion":
      - peso_keyword
      - peso_regex_titulo
      - confianza_minima
      - keyword_mode  ("word" | "contains")
    """
    clasif = cfg.get("clasificacion", {}) if isinstance(cfg, dict) else {}

    return ScoringPolicy(
        w_keyword=safe_float(clasif.get("peso_keyword"), DEFAULT_POLICY.w_keyword),
        w_regex_title=safe_float(clasif.get("peso_regex_titulo"), DEFAULT_POLICY.w_regex_title),
        default_min_conf=safe_float(clasif.get("confianza_minima"), DEFAULT_POLICY.default_min_conf),
        keyword_mode=str(clasif.get("keyword_mode") or DEFAULT_POLICY.keyword_mode).strip().lower(),
        debug_top_k=DEFAULT_POLICY.debug_top_k
    )


# =========================
# Clasificador principal
# =========================

def classify_document(ocr_text: str):
    """
    Devuelve (tipo_documento, confianza, metodo, detalles)

    - Usa reglas por tipo: keywords + regex_titulo.
    - Score configurable desde JSON.
    - Devuelve debug útil si no clasifica.
    """
    text_norm = normalize_text(ocr_text)
    doc_types = get_all_document_types() or {}

    best_type = "DESCONOCIDO"
    best_score = 0.0
    best_details: Dict[str, Any] = {"matches": []}

    ranking: List[Dict[str, Any]] = []

    for type_id, cfg in doc_types.items():
        if not isinstance(cfg, dict):
            continue
        if str(type_id).strip().upper() == "DESCONOCIDO":
            continue

        clasif = cfg.get("clasificacion", {})
        if not isinstance(clasif, dict):
            clasif = {}

        policy = _get_policy(cfg)

        keywords = clasif.get("palabras_clave", []) or []
        if not isinstance(keywords, list):
            keywords = []

        regex_title = str(clasif.get("regex_titulo") or "").strip()
        min_conf = policy.default_min_conf

        score = 0.0
        matches: List[Dict[str, Any]] = []

        # ---- Keywords ----
        for kw in keywords:
            kw_norm = normalize_text(str(kw))
            if keyword_match(text_norm, kw_norm, mode=policy.keyword_mode):
                score += policy.w_keyword
                matches.append({"tipo": "keyword", "valor": str(kw)})

        # ---- Regex título ----
        if regex_title:
            ok, err = safe_regex_search(regex_title, text_norm)
            if ok:
                score += policy.w_regex_title
                matches.append({"tipo": "regex_titulo", "valor": regex_title})
            elif err:
                matches.append({"tipo": "regex_error", "valor": f"{regex_title} | {err}"})

        confianza = min(1.0, score)

        ranking.append({
            "tipo_documento": str(type_id),
            "score": confianza,
            "confianza_minima": min_conf,
            "policy": {
                "w_keyword": policy.w_keyword,
                "w_regex_titulo": policy.w_regex_title,
                "keyword_mode": policy.keyword_mode
            },
            "matches": matches
        })

        if confianza >= min_conf and confianza > best_score:
            best_score = confianza
            best_type = str(type_id)
            best_details = {
                "matches": matches,
                "confianza_minima": min_conf,
                "policy": {
                    "w_keyword": policy.w_keyword,
                    "w_regex_titulo": policy.w_regex_title,
                    "keyword_mode": policy.keyword_mode
                }
            }

    # Si no clasificó: devolver debug con top candidatos
    if best_type == "DESCONOCIDO":
        top = sorted(ranking, key=lambda x: x["score"], reverse=True)[:DEFAULT_POLICY.debug_top_k]
        return ("DESCONOCIDO", 0.0, "REGLAS", {"top_candidatos": top})

    return (best_type, best_score, "REGLAS", best_details)
