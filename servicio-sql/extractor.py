import re
from unidecode import unidecode


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unidecode(text).upper()
    return text


def normalize_money(value: str, config):
    """
    Convierte '1.234.567' o '$ 1,234,567' en 1234567
    """
    if not value:
        return None

    value = value.strip()

    symbols = config.get("normalizacion", {}).get("montos", {}).get("remover_simbolos", [])
    for s in symbols:
        value = value.replace(s, "")

    separators = config.get("normalizacion", {}).get("montos", {}).get("separadores_miles", [])
    for sep in separators:
        value = value.replace(sep, "")

    try:
        return int(value)
    except:
        return None


def normalize_period(value: str, config):
    """
    Convierte:
      '01/2025' -> 'ENERO 2025'
      'Octubre del 2025' -> 'OCTUBRE 2025'
    """
    if not value:
        return None

    value = unidecode(value).upper()

    # Caso 01/2025
    m = re.search(r"(\d{2})/(20\d{2})", value)
    if m:
        month_num = m.group(1)
        year = m.group(2)
        map_months = config.get("normalizacion", {}).get("periodo", {}).get("map_mes_numero_a_nombre", {})
        month_name = map_months.get(month_num)
        if month_name:
            return f"{month_name} {year}"

    # Caso OCTUBRE 2025
    m = re.search(r"(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\s+(?:DEL\s+)?(20\d{2})", value)
    if m:
        return f"{m.group(1)} {m.group(2)}"

    return None


def extract_fields(ocr_text: str, doc_config: dict):
    text = normalize_text(ocr_text)

    campos_config = doc_config.get("campos", {})
    results = {}
    missing = []
    errors = []

    for field_name, cfg in campos_config.items():
        value = None

        # Buscar por claves
        keys = cfg.get("claves_busqueda", [])
        for key in keys:
            key_norm = normalize_text(key)
            idx = text.find(key_norm)
            if idx != -1:
                # Tomamos una ventana de texto luego de la clave
                window = text[idx: idx + 200]
                numbers = re.findall(r"[\d\.,]+", window)
                if numbers:
                    value = numbers[0]
                    break

        # Buscar por regex
        if not value:
            regex = cfg.get("regex")
            if regex:
                m = re.search(regex, text)
                if m:
                    value = m.group(0)

            regex_opts = cfg.get("regex_opciones", [])
            for r in regex_opts:
                m = re.search(r, text)
                if m:
                    value = m.group(0)
                    break

        # Normalizaciones especiales
        if value:
            if cfg.get("tipo") == "number":
                value = normalize_money(value, doc_config)
            if field_name == "periodo_remuneracion":
                value = normalize_period(value, doc_config)

        if value is None:
            if cfg.get("obligatorio"):
                missing.append(field_name)
        else:
            results[field_name] = value

    return results, missing, errors
