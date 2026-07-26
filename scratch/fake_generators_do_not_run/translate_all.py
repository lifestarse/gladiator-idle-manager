import json
import os
import re
import time
from deep_translator import GoogleTranslator

LANG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "languages")
if not os.path.exists(LANG_DIR):
    LANG_DIR = r"c:\Users\user\gladiator-idle-manager\data\languages"

print(f"Target language directory: {LANG_DIR}")

TARGET_LANGUAGES = ["uk", "de", "es", "fr", "it", "pt", "pl"]

def should_translate(s):
    if not isinstance(s, str):
        return False
    s_strip = s.strip()
    if not s_strip:
        return False
    if all(c.isdigit() or c in '.,+-*/%()[]{}<>=$#@!?:; "_\'' for c in s_strip):
        return False
    return True

def translate_batch_with_retry(translator, batch, retries=5, delay=2.0):
    joined_text = " ||| ".join(batch)
    for i in range(3):
        try:
            translated_joined = translator.translate(joined_text)
            parts = re.split(r'\s*\|\|\|\s*', translated_joined)
            if len(parts) == len(batch):
                return parts
            else:
                print(f"  Fast translation split mismatch: expected {len(batch)} items, got {len(parts)}. Retrying fast method...")
        except Exception as e:
            print(f"  Fast translation attempt {i+1} failed: {e}. Retrying...")
        time.sleep(delay)
        
    print("  Fast translation failed. Falling back to slow element-by-element translation...")
    results = []
    for idx, text in enumerate(batch):
        item_translated = None
        for k in range(retries):
            try:
                if not text.strip():
                    item_translated = text
                    break
                item_translated = translator.translate(text)
                break
            except Exception as item_err:
                print(f"    Item '{text}' failed (attempt {k+1}/{retries}): {item_err}")
                if k == retries - 1:
                    item_translated = text
                time.sleep(delay)
        results.append(item_translated)
    return results

def protect_placeholders(text):
    placeholders = re.findall(r'\{[a-zA-Z0-9_]+\}', text)
    protected = text
    for i, p in enumerate(placeholders):
        protected = protected.replace(p, f"[{i}]")
    return protected, placeholders

def restore_placeholders(text, placeholders):
    restored = text
    for i, p in enumerate(placeholders):
        restored = re.sub(rf'\[\s*{i}\s*\]', p, restored)
    return restored

def extract_strings(data, path=None):
    if path is None:
        path = []
    results = []
    if isinstance(data, dict):
        for k, v in data.items():
            results.extend(extract_strings(v, path + [k]))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            results.extend(extract_strings(v, path + [i]))
    elif isinstance(data, str):
        results.append((path, data))
    return results

def rebuild_structure(extracted):
    result = None
    for path, val in extracted:
        if result is None:
            result = [] if isinstance(path[0], int) else {}
        curr = result
        for i, p in enumerate(path[:-1]):
            nxt_p = path[i+1]
            if isinstance(curr, list):
                while len(curr) <= p:
                    curr.append(None)
                if curr[p] is None:
                    curr[p] = [] if isinstance(nxt_p, int) else {}
                curr = curr[p]
            else:
                if p not in curr:
                    curr[p] = [] if isinstance(nxt_p, int) else {}
                curr = curr[p]
        p_last = path[-1]
        if isinstance(curr, list):
            while len(curr) <= p_last:
                curr.append(None)
            curr[p_last] = val
        else:
            curr[p_last] = val
    return result

def build_data_en():
    workspace = r"c:\Users\user\gladiator-idle-manager"
    achievements = {a['id']: a for a in json.load(open(os.path.join(workspace, 'data', 'achievements.json'), 'r', encoding='utf-8'))['achievements']}
    expeditions = {e['id']: e for e in json.load(open(os.path.join(workspace, 'data', 'expeditions.json'), 'r', encoding='utf-8'))['expeditions']}
    weapons = {w['id']: w for w in json.load(open(os.path.join(workspace, 'data', 'weapons.json'), 'r', encoding='utf-8'))['items']}
    armor = {a['id']: a for a in json.load(open(os.path.join(workspace, 'data', 'armor.json'), 'r', encoding='utf-8'))['items']}
    accessories = {a['id']: a for a in json.load(open(os.path.join(workspace, 'data', 'accessories.json'), 'r', encoding='utf-8'))['items']}
    relics = {r['id']: r for r in json.load(open(os.path.join(workspace, 'data', 'relics.json'), 'r', encoding='utf-8'))['items']}
    classes = json.load(open(os.path.join(workspace, 'data', 'fighter_classes.json'), 'r', encoding='utf-8'))['classes']

    data_ru_path = os.path.join(LANG_DIR, 'data_ru.json')
    data_ru = json.load(open(data_ru_path, 'r', encoding='utf-8'))

    data_en = {}

    # achievements
    data_en['achievements'] = {}
    for aid, ach in data_ru['achievements'].items():
        data_en['achievements'][aid] = {
            'name': achievements[aid]['name'],
            'desc': achievements[aid]['desc']
        }

    # expeditions
    data_en['expeditions'] = {}
    for eid, exp in data_ru['expeditions'].items():
        data_en['expeditions'][eid] = {
            'name': expeditions[eid]['name'],
            'desc': expeditions[eid]['desc']
        }

    # weapons
    data_en['weapons'] = {}
    for wid, weap in data_ru['weapons'].items():
        data_en['weapons'][wid] = {
            'name': weapons[wid]['name'],
            'description': weapons[wid]['description']
        }

    # armor
    data_en['armor'] = {}
    for aid, arm in data_ru['armor'].items():
        data_en['armor'][aid] = {
            'name': armor[aid]['name'],
            'description': armor[aid]['description']
        }

    # accessories
    data_en['accessories'] = {}
    for acid, acc in data_ru['accessories'].items():
        data_en['accessories'][acid] = {
            'name': accessories[acid]['name'],
            'description': accessories[acid]['description']
        }

    # relics
    data_en['relics'] = {}
    for rid, rel in data_ru['relics'].items():
        data_en['relics'][rid] = {
            'name': relics[rid]['name'],
            'description': relics[rid]['description'],
            'special_effect': relics[rid]['special_effect']
        }

    # classes
    data_en['classes'] = {}
    for cid, cls in data_ru['classes'].items():
        data_en['classes'][cid] = {
            'desc': classes[cid]['description'],
            'passive_ability': {
                'name': classes[cid]['passive_ability']['name'],
                'description': classes[cid]['passive_ability']['description']
            },
            'active_skill': {
                'name': classes[cid]['active_skill']['name'],
                'description': classes[cid]['active_skill']['description']
            },
            'perks': {}
        }
        for pid in cls['perks'].keys():
            perk_data = next(p for p in classes[cid]['perk_tree'] if p['id'] == pid)
            data_en['classes'][cid]['perks'][pid] = {
                'name': perk_data['name'],
                'description': perk_data['description']
            }

    return data_en

def chunk_by_chars_and_count(items, max_count=50, max_chars=4000):
    chunks = []
    current_chunk = []
    current_len = 0
    for item in items:
        text_len = len(item[0])
        added_len = text_len + (5 if current_chunk else 0)
        if len(current_chunk) >= max_count or current_len + added_len > max_chars:
            chunks.append(current_chunk)
            current_chunk = [item]
            current_len = text_len
        else:
            current_chunk.append(item)
            current_len += added_len
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def translate_structured_data(source_dict, target_lang, batch_size=50):
    print(f"Translating to {target_lang}...")
    translator = GoogleTranslator(source='en', target=target_lang)
    
    extracted = extract_strings(source_dict)
    print(f"  Extracted {len(extracted)} strings.")
    
    to_translate_indices = []
    to_translate_texts = []
    
    for idx, (path, val) in enumerate(extracted):
        if should_translate(val):
            to_translate_indices.append(idx)
            prot, placeholders = protect_placeholders(val)
            to_translate_texts.append((prot, placeholders))
    
    print(f"  {len(to_translate_texts)} strings require translation.")
    
    translated_texts = []
    batches = chunk_by_chars_and_count(to_translate_texts, max_count=batch_size, max_chars=4000)
    for i, batch in enumerate(batches):
        batch_raw = [item[0] for item in batch]
        print(f"    Batch {i+1}/{len(batches)} ({len(batch)} items, {sum(len(x) for x in batch_raw)} chars)...")
        
        batch_translated = translate_batch_with_retry(translator, batch_raw)
        
        for idx, trans_val in enumerate(batch_translated):
            orig_placeholders = batch[idx][1]
            restored = restore_placeholders(trans_val, orig_placeholders)
            translated_texts.append(restored)
            
        time.sleep(0.5)
        
    rebuild_extracted = []
    for idx, (path, val) in enumerate(extracted):
        if idx in to_translate_indices:
            t_idx = to_translate_indices.index(idx)
            rebuild_extracted.append((path, translated_texts[t_idx]))
        else:
            rebuild_extracted.append((path, val))
            
    return rebuild_structure(rebuild_extracted)

def main():
    en_json_path = os.path.join(LANG_DIR, "en.json")
    en_json = json.load(open(en_json_path, "r", encoding="utf-8"))
    
    data_en = build_data_en()
    
    for lang in TARGET_LANGUAGES:
        lang_json_path = os.path.join(LANG_DIR, f"{lang}.json")
        data_lang_json_path = os.path.join(LANG_DIR, f"data_{lang}.json")
        
        print(f"=== Starting {lang} UI strings ===")
        ui_translated = translate_structured_data(en_json, lang)
        with open(lang_json_path, "w", encoding="utf-8") as f:
            json.dump(ui_translated, f, ensure_ascii=False, indent=2)
        print(f"Saved {lang_json_path}")
        
        print(f"=== Starting {lang} Game database ===")
        db_translated = translate_structured_data(data_en, lang)
        with open(data_lang_json_path, "w", encoding="utf-8") as f:
            json.dump(db_translated, f, ensure_ascii=False, indent=2)
        print(f"Saved {data_lang_json_path}")
        print("-" * 40)

if __name__ == "__main__":
    main()
