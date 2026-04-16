# Build: 1
"""One-off script to merge new translation keys into en.json and ru.json.

Safe to re-run: uses dict.update() which overwrites matching keys but preserves
all other existing keys. Reads with UTF-8, writes with ensure_ascii=False to
preserve Cyrillic characters.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LANG_DIR = os.path.join(os.path.dirname(HERE), "data", "languages")

# (key, en_value, ru_value)
NEW_KEYS = [
    # --- Statistics section headers ---
    ("stat_hdr_current_run",    "CURRENT RUN",      "ТЕКУЩИЙ ЗАБЕГ"),
    ("stat_hdr_records",        "RECORDS",          "РЕКОРДЫ"),
    ("stat_hdr_combat",         "COMBAT",           "БОЙ"),
    ("stat_hdr_economy",        "ECONOMY",          "ЭКОНОМИКА"),
    ("stat_hdr_roster",         "ROSTER",           "ОТРЯД"),
    ("stat_hdr_progress",       "PROGRESS",         "ПРОГРЕСС"),
    # --- Statistics row labels ---
    ("stat_row_run_num",        "Run #",            "Забег №"),
    ("stat_row_arena_tier",     "Arena Tier",       "Уровень арены"),
    ("stat_row_kills",          "Kills",            "Убийств"),
    ("stat_row_max_tier",       "Max Tier",         "Макс. уровень"),
    ("stat_row_best_tier",      "Best Tier",        "Лучший уровень"),
    ("stat_row_best_kills",     "Best Kills",       "Лучшие убийства"),
    ("stat_row_total_runs",     "Total Runs",       "Всего забегов"),
    ("stat_row_wins",           "Wins",             "Побед"),
    ("stat_row_bosses_killed",  "Bosses Killed",    "Боссов убито"),
    ("stat_row_fighters_lost",  "Fighters Lost",    "Бойцов потеряно"),
    ("stat_row_graveyard",      "Graveyard",        "Могил"),
    ("stat_row_gold",           "Gold",             "Золото"),
    ("stat_row_total_gold",     "Total Gold Earned","Всего заработано"),
    ("stat_row_diamonds",       "Diamonds",         "Алмазов"),
    ("stat_row_fighters_alive", "Fighters Alive",   "Живых бойцов"),
    ("stat_row_total_kills",    "Total Kills",      "Всего убийств"),
    ("stat_row_highest_level",  "Highest Level",    "Высший уровень"),
    ("stat_row_total_injuries", "Total Injuries",   "Всего травм"),
    ("stat_row_achievements",   "Achievements",     "Достижения"),
    ("stat_row_story_chapter",  "Story Chapter",    "Глава истории"),
    ("stat_row_expeditions_done","Expeditions Done","Охот пройдено"),
    # --- Story chapter names ---
    ("chap_ch1",                "Chapter I: The Pit",         "Глава I: Яма"),
    ("chap_ch2",                "Chapter II: Blood & Iron",   "Глава II: Кровь и сталь"),
    ("chap_ch3",                "Chapter III: The Hunt",      "Глава III: Охота"),
    ("chap_ch4",                "Chapter IV: The Graveyard",  "Глава IV: Кладбище"),
    ("chap_ch5",                "Chapter V: Empire",          "Глава V: Империя"),
    ("chap_ch6",                "Chapter VI: The Void",       "Глава VI: Пустота"),
    # --- Chapter I quests ---
    ("qst_ch1_q1_name", "Into the Arena",      "На арене"),
    ("qst_ch1_q1_desc", "Reach arena tier 3",  "Достигни 3-го уровня арены"),
    ("qst_ch1_q2_name", "Brothers in Arms",    "Братья по оружию"),
    ("qst_ch1_q2_desc", "Have 2 fighters alive","Имей 2 живых бойцов"),
    ("qst_ch1_q3_name", "Armed",               "Вооружён"),
    ("qst_ch1_q3_desc", "Equip any weapon",    "Экипируй любое оружие"),
    ("qst_ch1_q4_name", "Blooded",             "Крещение"),
    ("qst_ch1_q4_desc", "Defeat 1 boss",       "Победи 1 босса"),
    # --- Chapter II quests ---
    ("qst_ch2_q1_name", "Climber",             "Восходящий"),
    ("qst_ch2_q1_desc", "Reach arena tier 7",  "Достигни 7-го уровня арены"),
    ("qst_ch2_q2_name", "Sharpened",           "Заточен"),
    ("qst_ch2_q2_desc", "Upgrade any item to +2","Улучши любой предмет до +2"),
    ("qst_ch2_q3_name", "War Band",            "Боевой отряд"),
    ("qst_ch2_q3_desc", "Have 4 fighters alive","Имей 4 живых бойцов"),
    ("qst_ch2_q4_name", "Armored",             "Бронирован"),
    ("qst_ch2_q4_desc", "Equip armor on any fighter","Экипируй броню на любого бойца"),
    # --- Chapter III quests ---
    ("qst_ch3_q1_name", "Scout",               "Разведчик"),
    ("qst_ch3_q1_desc", "Complete 3 expeditions","Заверши 3 охоты"),
    ("qst_ch3_q2_name", "Rising Power",        "Восходящая сила"),
    ("qst_ch3_q2_desc", "Reach arena tier 12", "Достигни 12-го уровня арены"),
    ("qst_ch3_q3_name", "Master",              "Мастер"),
    ("qst_ch3_q3_desc", "Train a fighter to Lv.10","Прокачай бойца до Ур.10"),
    ("qst_ch3_q4_name", "Relic Found",         "Реликвия найдена"),
    ("qst_ch3_q4_desc", "Own 1 relic",         "Завладей 1 реликвией"),
    # --- Chapter IV quests ---
    ("qst_ch4_q1_name", "Blood Price",         "Цена крови"),
    ("qst_ch4_q1_desc", "Lose 3 fighters to permadeath","Потеряй 3 бойцов навсегда"),
    ("qst_ch4_q2_name", "Unstoppable",         "Неудержимый"),
    ("qst_ch4_q2_desc", "Reach arena tier 18", "Достигни 18-го уровня арены"),
    ("qst_ch4_q3_name", "Titan Breaker",       "Сокрушитель титанов"),
    ("qst_ch4_q3_desc", "Defeat 5 bosses",     "Победи 5 боссов"),
    ("qst_ch4_q4_name", "Collector",           "Коллекционер"),
    ("qst_ch4_q4_desc", "Own 3 relics",        "Завладей 3 реликвиями"),
    # --- Chapter V quests ---
    ("qst_ch5_q1_name", "Legion",              "Легион"),
    ("qst_ch5_q1_desc", "Have 8 fighters alive","Имей 8 живых бойцов"),
    ("qst_ch5_q2_name", "Warlord",             "Полководец"),
    ("qst_ch5_q2_desc", "Reach arena tier 25", "Достигни 25-го уровня арены"),
    ("qst_ch5_q3_name", "Full Set",            "Полный набор"),
    ("qst_ch5_q3_desc", "Fighter with weapon + armor + accessory","Боец с оружием, бронёй и аксессуаром"),
    ("qst_ch5_q4_name", "Grand Master",        "Великий мастер"),
    ("qst_ch5_q4_desc", "Train a fighter to Lv.20","Прокачай бойца до Ур.20"),
    # --- Chapter VI quests ---
    ("qst_ch6_q1_name", "Ascendant",           "Вознесшийся"),
    ("qst_ch6_q1_desc", "Reach arena tier 35", "Достигни 35-го уровня арены"),
    ("qst_ch6_q2_name", "Legend",              "Легенда"),
    ("qst_ch6_q2_desc", "Defeat 20 bosses",    "Победи 20 боссов"),
    ("qst_ch6_q3_name", "Void Walker",         "Странник Пустоты"),
    ("qst_ch6_q3_desc", "Return from the Void Rift","Вернись из Разлома Пустоты"),
    ("qst_ch6_q4_name", "Immortal",            "Бессмертный"),
    ("qst_ch6_q4_desc", "Train a fighter to Lv.30","Прокачай бойца до Ур.30"),
    # --- Diamond Shop ---
    ("ds_revive_token_name",    "Soul Stone",                                                  "Камень души"),
    ("ds_revive_token_desc",    "Revive a dead fighter (full HP, clear injuries)",             "Воскреси погибшего бойца (полное здоровье, лечение травм)"),
    ("ds_heal_all_injuries_diamond_name", "Divine Surgeon",                                    "Божественный хирург"),
    ("ds_heal_all_injuries_diamond_desc", "Heal ALL injuries on ALL fighters (10 diamonds per injury, min 10)", "Вылечи ВСЕ травмы у ВСЕХ бойцов (10 алмазов за каждую травму, мин. 10)"),
    ("ds_extra_expedition_slot_name", "Scout Network",                                         "Разведсеть"),
    ("ds_extra_expedition_slot_desc", "Send +1 fighter on expeditions simultaneously",         "Отправляй +1 бойца в охоты одновременно"),
    ("ds_golden_armor_name",    "Golden War Set",                                              "Золотой боевой набор"),
    ("ds_golden_armor_desc",    "Blade of Ruin + Dragonscale Aegis + Crown of Ash",            "Клинок погибели + Драконья чешуя + Корона пепла"),
    ("ds_name_change_name",     "Identity Scroll",                                             "Свиток личности"),
    ("ds_name_change_desc",     "Rename any fighter",                                          "Переименуй любого бойца"),
    # --- Quest / reward helpers ---
    ("quest_status_done",       "[DONE]",     "[ГОТОВО]"),
    ("quest_status_locked",     "[LOCKED]",   "[ЗАКРЫТО]"),
    ("reward_diamonds",         "{n} diamonds","{n} алмазов"),
    ("reward_none",             "—",          "—"),
    # --- Item slot labels (uppercase, for forge subtitles) ---
    ("slot_weapon_upper",       "WEAPON",     "ОРУЖИЕ"),
    ("slot_armor_upper",        "ARMOR",      "БРОНЯ"),
    ("slot_accessory_upper",    "ACCESSORY",  "АКСЕССУАР"),
    ("slot_relic_upper",        "RELIC",      "РЕЛИКВИЯ"),
    # --- Rarity labels (uppercase, for forge subtitles) ---
    ("rarity_common_upper",     "COMMON",     "ОБЫЧНОЕ"),
    ("rarity_uncommon_upper",   "UNCOMMON",   "НЕОБЫЧНОЕ"),
    ("rarity_rare_upper",       "RARE",       "РЕДКОЕ"),
    ("rarity_epic_upper",       "EPIC",       "ЭПИЧЕСКОЕ"),
    ("rarity_legendary_upper",  "LEGENDARY",  "ЛЕГЕНДАРНОЕ"),
    # --- Max upgrade suffix ---
    ("item_max_upgrade",        "max +{n}",   "макс +{n}"),
    # --- Shard tier names (used in quest rewards + expedition cards) ---
    ("shard_tier_1_name",       "Metal Shard (I)",   "Осколок (I)"),
    ("shard_tier_2_name",       "Metal Shard (II)",  "Осколок (II)"),
    ("shard_tier_3_name",       "Metal Shard (III)", "Осколок (III)"),
    ("shard_tier_4_name",       "Metal Shard (IV)",  "Осколок (IV)"),
    ("shard_tier_5_name",       "Metal Shard (V)",   "Осколок (V)"),
    ("shard_name_fallback",     "Shard ({tier})",    "Осколок ({tier})"),
    # --- Shorten Russian diamond shop label so the tab fits (EN unchanged) ---
    ("diamond_shop_label",      "DIAMOND SHOP",      "АЛМАЗЫ"),
    # --- Toast / popup notifications (previously hardcoded English) ---
    ("bought_msg",              "Bought {name}",                              "Куплено: {name}"),
    ("expedition_returned",     "{fighter} returned from {exp}!",             "{fighter} вернулся из '{exp}'!"),
    ("expedition_returned_shard","{fighter} returned from {exp}! +{n} {shard}","{fighter} вернулся из '{exp}'! +{n} {shard}"),
    ("found_relic_msg",         "Found: {name} [{rarity}]",                   "Найдено: {name} [{rarity}]"),
    ("invalid_fighter_err",     "Invalid fighter",                            "Неверный боец"),
    ("not_found_err",           "Not found",                                  "Не найдено"),
    # --- Arena stats text labels ---
    ("arena_best_record",       "Best: T{tier} \u00b7 {kills} kills",         "Рекорд: T{tier} \u00b7 {kills} убийств"),
    ("arena_best_none",         "Best: ---",                                  "Рекорд: ---"),
    ("arena_run_stats",         "Run #{n} \u00b7 {kills} kills",              "Забег №{n} \u00b7 {kills} убийств"),
    ("arena_tier_top",          "TIER {n}",                                   "ТИР {n}"),
    ("arena_tier_enemy",        "Tier {n}",                                   "Тир {n}"),
    # --- Floating text (healing) ---
    ("healed_name",             "Healed {name}",                              "Исцелён: {name}"),
    ("healed_amount",           "Healed {n} (-{g}g)",                         "Восст. {n} HP (-{g}g)"),
]


def merge(lang_file, lang_idx):
    path = os.path.join(LANG_DIR, lang_file)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    orig_count = len(data)
    added = 0
    updated = 0
    for key, en_val, ru_val in NEW_KEYS:
        val = en_val if lang_idx == 0 else ru_val
        if key in data:
            if data[key] != val:
                data[key] = val
                updated += 1
        else:
            data[key] = val
            added += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"{lang_file}: {orig_count} -> {len(data)} keys (+{added} added, {updated} updated)")


if __name__ == "__main__":
    merge("en.json", 0)
    merge("ru.json", 1)
    print("OK")
