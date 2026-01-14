import re
from unidecode import unidecode
from config_loader import get_all_document_types


def normalize_text(text: str) -> str:
    """
    Normaliza para comparación:
    - sin acentos
    - mayúsculas
    - colapsa espacios
    """
    if not text:
        return ""
    text = unidecode(text)
    text = text.upper()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_regex_search(pattern: str, text: str) -> bool:
    if not pattern:
        return False
    try:
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    except re.error:
        return False


def classify_document(ocr_text: str):
    """
    Devuelve: (tipo_documento, confianza, metodo, detalles)

    Mejoras:
    - Confianza basada en:
      * proporción de keywords encontradas (no solo suma fija)
      * bonus por regex de título
      * (opcional) bonus por "señales" extra si las agregas en config
    - Si no alcanza confianza_minima, aún puede devolver el "mejor candidato"
      como BAJA_CONFIANZA (útil para debug y para no quedar siempre en DESCONOCIDO).
    """
    text = normalize_text(ocr_text)
    doc_types = get_all_document_types()

    best_type = "DESCONOCIDO"
    best_score = 0.0
    best_details = {"matches": [], "confianza_minima": None}

    for type_id, cfg in doc_types.items():
        if type_id == "DESCONOCIDO":
            continue

        clasif = cfg.get("clasificacion", {})
        keywords = clasif.get("palabras_clave", []) or []
        regex_title = clasif.get("regex_titulo", "") or ""
        min_conf = float(clasif.get("confianza_minima", 0.8))

        # Pesos configurables (si no vienen, usamos defaults buenos)
        pesos = clasif.get("pesos", {}) or {}
        w_keywords = float(pesos.get("keywords", 0.55))   # peso total máximo por keywords
        w_regex = float(pesos.get("regex_titulo", 0.45))  # bonus por regex

        matches = []
        score = 0.0

        # 1) Keywords: usamos proporción (en vez de +0.15 por cada una)
        kw_norms = []
        for kw in keywords:
            kwn = normalize_text(str(kw))
            if kwn:
                kw_norms.append((kw, kwn))

        found = 0
        for raw_kw, kw_n in kw_norms:
            if kw_n in text:
                found += 1
                matches.append({"tipo": "keyword", "valor": raw_kw})

        if kw_norms:
            ratio = found / max(1, len(kw_norms))
            score += w_keywords * ratio  # 0..w_keywords

        # 2) Regex título
        if regex_title:
            if safe_regex_search(regex_title, text):
                score += w_regex
                matches.append({"tipo": "regex_titulo", "valor": regex_title})
            else:
                # si el regex viene malo, lo marcamos (sin romper)
                try:
                    re.compile(regex_title)
                except re.error:
                    matches.append({"tipo": "regex_error", "valor": regex_title})

        confianza = max(0.0, min(1.0, score))

        # Nos quedamos con el mejor SIEMPRE (para debug)
        if confianza > best_score:
            best_score = confianza
            best_type = type_id
            best_details = {
                "matches": matches,
                "confianza_minima": min_conf,
                "score": round(confianza, 4),
                "keywords_found": found,
                "keywords_total": len(kw_norms),
            }

    # --- Política de salida ---
    # Si no hay nada, DESCONOCIDO
    if best_score <= 0.0:
        return ("DESCONOCIDO", 0.0, "REGLAS", {"matches": []})

    # Si el mejor candidato no alcanza su umbral, devolvemos BAJA_CONFIANZA
    # (Si prefieres la lógica antigua, cambia esto por DESCONOCIDO)
    min_conf_best = best_details.get("confianza_minima") or 0.8
    if best_score < float(min_conf_best):
        return (best_type, best_score, "REGLAS_BAJA_CONFIANZA", best_details)

    return (best_type, best_score, "REGLAS", best_details)
