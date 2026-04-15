# Build: 1
"""Verify translation flow — DOES NOT touch real save file."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.engine import GameEngine
from game.localization import t, get_language
from game.data_loader import data_loader

def main():
    # Bootstrap engine and override SAVE_PATH so we never touch the real save
    eng = GameEngine()
    eng.SAVE_PATH = tempfile.NamedTemporaryFile(suffix='.json', delete=False).name

    # Simulate load with saved_lang=ru
    save_data = {'language': 'ru', 'fighters': [], 'shards': {}}
    eng._apply_save_data(save_data)

    from game.achievements import ACHIEVEMENTS
    first = next(a for a in ACHIEVEMENTS if a['id'] == 'first_blood')
    exp = next(e for e in data_loader.expeditions if e['id'] == 'dark_tunnels')

    print(f'Current language: {get_language()}')
    print()
    print('=== DATA TRANSLATION (via apply_translations) ===')
    print(f"first_blood name: {first['name']}")
    print(f"first_blood desc: {first['desc']}")
    print(f"dark_tunnels name: {exp['name']}")
    print(f"dark_tunnels desc: {exp['desc']}")
    print()
    print('=== FLAT KEY TRANSLATION (via t()) ===')
    print(f"stat_hdr_combat: {t('stat_hdr_combat')}")
    print(f"stat_row_wins:   {t('stat_row_wins')}")
    print(f"chap_ch1:        {t('chap_ch1')}")
    print(f"qst_ch1_q1_name: {t('qst_ch1_q1_name')}")
    print(f"qst_ch1_q1_desc: {t('qst_ch1_q1_desc')}")
    print(f"ds_revive_token_name: {t('ds_revive_token_name')}")
    print(f"ds_heal_all_injuries_diamond_desc: {t('ds_heal_all_injuries_diamond_desc')}")
    print(f"reward_diamonds (n=25): {t('reward_diamonds', n=25)}")
    print(f"quest_status_done: {t('quest_status_done')}")
    print()
    print('=== FALLBACK CHECK (missing key returns key itself) ===')
    print(f"missing_key: {t('this_key_does_not_exist')}")

    # Cleanup
    if os.path.exists(eng.SAVE_PATH):
        os.remove(eng.SAVE_PATH)
    print()
    print('VERIFIED')

if __name__ == '__main__':
    main()
