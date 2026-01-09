import re
from unidecode import unidecode
from config_loader import get_all_document_types


def normalize_text(text: str) -> str:
    """
    Normaliza para comparación:
    - mayúsculas
    - sin acentos
    - espacios colapsados
    """
    if not text:
        return ""
    text = unidecode(text).upper()
    text = re.sub(r"\s+", " ", text)
    return text


def classify_document(ocr_text: str):
    """
    Devuelve (tipo_documento, confianza, metodo, detalles)

    Regla:
    - suma puntos por palabras_clave encontradas
    - suma puntos si regex_titulo matchea
    - elige el tipo con mayor score, siempre que supere confianza_minima
    """
    text = normalize_text(ocr_text)
    doc_types = get_all_document_types()

    best_type = "DESCONOCIDO"
    best_score = 0.0
    best_details = {"matches": []}

    for type_id, cfg in doc_types.items():
        # Evitar clasificar con "DESCONOCIDO" si existiera en config
        if type_id == "DESCONOCIDO":
            continue

        clasif = cfg.get("clasificacion", {})
        keywords = clasif.get("palabras_clave", [])
        regex_title = clasif.get("regex_titulo", "")
        min_conf = float(clasif.get("confianza_minima", 0.8))

        score = 0.0
        matches = []

        # Palabras clave
        for kw in keywords:
            kw_norm = normalize_text(kw)
            if kw_norm and kw_norm in text:
                score += 0.15
                matches.append({"tipo": "keyword", "valor": kw})

        # Regex (si existe)
        if regex_title:
            try:
                if re.search(regex_title, text, re.IGNORECASE):
                    score += 0.4
                    matches.append({"tipo": "regex_titulo", "valor": regex_title})
            except re.error:
                # regex inválida en config: no rompe el sistema
                matches.append({"tipo": "regex_error", "valor": regex_title})

        # Convertir score a "confianza" simple
        confianza = min(1.0, score)

        if confianza >= min_conf and confianza > best_score:
            best_score = confianza
            best_type = type_id
            best_details = {"matches": matches, "confianza_minima": min_conf}

    if best_type == "DESCONOCIDO":
        return ("DESCONOCIDO", 0.0, "REGLAS", {"matches": []})

    return (best_type, best_score, "REGLAS", best_details)
