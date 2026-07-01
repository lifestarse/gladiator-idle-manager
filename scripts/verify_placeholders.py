import json
import os
import re

LANG_DIR = r"c:\Users\user\gladiator-idle-manager\data\languages"
TARGET_LANGUAGES = ["uk", "de", "es", "fr", "it", "pt", "pl", "ru"]

def get_placeholders(text):
    if not isinstance(text, str):
        return set()
    return set(re.findall(r'\{[a-zA-Z0-9_]+\}', text))

def extract_all_placeholders(data, path=None):
    if path is None:
        path = []
    results = {}
    if isinstance(data, dict):
        for k, v in data.items():
            results.update(extract_all_placeholders(v, path + [k]))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            results.update(extract_all_placeholders(v, path + [i]))
    elif isinstance(data, str):
        p = get_placeholders(data)
        if p:
            results[tuple(path)] = p
    return results

def main():
    print("Verifying formatting placeholder integrity...")
    
    # UI translation files
    en_path = os.path.join(LANG_DIR, "en.json")
    en_data = json.load(open(en_path, "r", encoding="utf-8"))
    en_ui_placeholders = extract_all_placeholders(en_data)
    
    errors = 0
    for lang in TARGET_LANGUAGES:
        lang_path = os.path.join(LANG_DIR, f"{lang}.json")
        if not os.path.exists(lang_path):
            print(f"File missing: {lang_path}")
            errors += 1
            continue
            
        lang_data = json.load(open(lang_path, "r", encoding="utf-8"))
        lang_ui_placeholders = extract_all_placeholders(lang_data)
        
        for path, expected in en_ui_placeholders.items():
            path_str = " -> ".join(map(str, path))
            actual = lang_ui_placeholders.get(path, set())
            if expected != actual:
                print(f"[{lang}.json] Mismatch at '{path_str}': Expected {expected}, got {actual}")
                errors += 1
                
    # Database translation files
    # Let's verify each data_{lang}.json vs data_ru.json structure, and verify placeholders are correct
    # Wait, we can construct data_en.json in memory to get correct English placeholder expectations
    from translate_all import build_data_en
    data_en = build_data_en()
    en_db_placeholders = extract_all_placeholders(data_en)
    
    for lang in TARGET_LANGUAGES:
        db_path = os.path.join(LANG_DIR, f"data_{lang}.json")
        if not os.path.exists(db_path):
            print(f"File missing: {db_path}")
            errors += 1
            continue
            
        db_data = json.load(open(db_path, "r", encoding="utf-8"))
        db_placeholders = extract_all_placeholders(db_data)
        
        for path, expected in en_db_placeholders.items():
            path_str = " -> ".join(map(str, path))
            actual = db_placeholders.get(path, set())
            if expected != actual:
                print(f"[data_{lang}.json] Mismatch at '{path_str}': Expected {expected}, got {actual}")
                errors += 1
                
    if errors == 0:
        print("SUCCESS: All placeholders are perfectly preserved across all languages!")
    else:
        print(f"FAILURE: Found {errors} mismatching placeholder errors.")

if __name__ == "__main__":
    main()
