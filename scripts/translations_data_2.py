# Build: 1
"""Part 2 of (key, en, ru) triples."""
NEW_KEYS = [
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
