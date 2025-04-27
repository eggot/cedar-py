import re

def detect_casing(identifiers):
    casing_patterns = [
        ("snake_case_t", r"^[a-z]+(_[a-z0-9]+)*_t$"),
        ("snake_case", r"^[a-z]+(_[a-z0-9]+)*$"),
        ("TPascalCase", r"^T[A-Z][a-z0-9]*([A-Z][a-z0-9]*)*$"),
        ("PascalCase", r"^[A-Z][a-z0-9]+([A-Z][a-z0-9]*)*$"),
        ("camelCase", r"^[a-z]+([A-Z][a-z0-9]*)*$"),
        ("kebab-case", r"^[a-z0-9]+(-[a-z0-9]+)*$"),
    ]

    for name in identifiers:
        detected = None
        for casing, pattern in casing_patterns:
            if re.match(pattern, name):
                detected = casing
                break
        if not detected:
            return None  # If one identifier doesn't match any known pattern, return None

    return detected  # All identifiers follow the same casing

def translate_to_casing(identifiers, target_casing):
    def to_snake_case(name):
        if detected_casing == 'TPascalCase':
            name = name[1:]
        name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
        name = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', name)
        return name.replace("-", "_").lower().lstrip('t').rstrip('_t')

    def to_camel_case(name):
        name = to_snake_case(name)
        return re.sub(r'_([a-z])', lambda x: x.group(1).upper(), name)

    def to_pascal_case(name):
        name = to_camel_case(name)
        return name[0].upper() + name[1:]

    def to_kebab_case(name):
        return to_snake_case(name).replace("_", "-")

    def to_tpascal_case(name):
        return "T" + to_pascal_case(name)

    def to_snake_case_t(name):
        return to_snake_case(name) + "_t"

    casing_transformers = {
        "snake_case": to_snake_case,
        "camelCase": to_camel_case,
        "PascalCase": to_pascal_case,
        "kebab-case": to_kebab_case,
        "TPascalCase": to_tpascal_case,
        "snake_case_t": to_snake_case_t,
    }

    if target_casing not in casing_transformers:
        raise ValueError(f"Target casing '{target_casing}' is not supported.")

    detected_casing = detect_casing(identifiers)
    if not detected_casing:
        raise ValueError("Identifiers do not follow a consistent naming convention.")
    print(detected_casing)
    transformer = casing_transformers[target_casing]
    return {identifier: transformer(identifier) for identifier in identifiers}

if __name__ == '__main__':
    # Example usage
    identifiers = {"my_thing_t", "my_thing2_t"}
    target_casing = "TPascalCase"
    translated_identifiers = translate_to_casing(identifiers, target_casing)
    for original, translated in translated_identifiers.items():
        print(f"{original}: {translated}")
