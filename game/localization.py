# Build: 28
"""Локализация — русский + английский (фоллбэк)."""

_current_lang = "ru"

STRINGS = {
    # ---- Навигация ----
    "nav_pit": {"ru": "АРЕНА", "en": "PIT"},
    "nav_squad": {"ru": "ОТРЯД", "en": "SQUAD"},
    "nav_anvil": {"ru": "КУЗНЯ", "en": "ANVIL"},
    "nav_hunts": {"ru": "ОХОТА", "en": "HUNTS"},
    "tab_missions": {"ru": "ЗАДАНИЯ", "en": "MISSIONS"},
    "tab_hunts": {"ru": "ОХОТА", "en": "HUNTS"},
    "nav_lore": {"ru": "ЗНАНИЯ", "en": "LORE"},
    "nav_more": {"ru": "ЕЩЁ", "en": "MORE"},

    # ---- Заголовки экранов ----
    "title_pit": {"ru": "А Р Е Н А", "en": "T H E   P I T"},
    "title_squad": {"ru": "О Т Р Я Д", "en": "S Q U A D"},
    "title_anvil": {"ru": "К У З Н Я", "en": "T H E   A N V I L"},
    "title_hunts": {"ru": "О Х О Т А", "en": "H U N T S"},
    "title_lore": {"ru": "З Н А Н И Я", "en": "L O R E"},
    "title_more": {"ru": "Н А С Т Р О Й К И", "en": "S E T T I N G S"},

    # ---- Арена / Бой ----
    "ready_to_fight": {"ru": "Готов к бою", "en": "Ready to fight"},
    "auto_battle": {"ru": "АВТО-БОЙ!", "en": "AUTO BATTLE!"},
    "boss_challenge": {"ru": "БОЙ С БОССОМ!", "en": "BOSS CHALLENGE!"},
    "boss_revenge": {"ru": "Босс выследил вашу группу и жаждет мести!", "en": "The boss tracked down your group and wants revenge!"},
    "boss_revenge_sub": {"ru": "Победите его или умрите с честью!", "en": "Defeat him or die with honor!"},
    "victory": {"ru": "ПОБЕДА!", "en": "VICTORY!"},
    "defeat": {"ru": "ПОРАЖЕНИЕ!", "en": "DEFEAT!"},
    "vs": {"ru": "ПРОТИВ", "en": "VS"},
    "fighters_ready": {"ru": "{n} бойцов готово", "en": "{n} fighters ready"},
    "fighters_alive": {"ru": "{n} бойцов в бою", "en": "{n} fighters alive"},
    "enemies_left": {"ru": "{n} врагов осталось", "en": "{n} enemies left"},
    "btn_auto": {"ru": "БОЙ", "en": "FIGHT"},
    "btn_boss": {"ru": "ОБЫЧН", "en": "COMMON"},
    "btn_next": {"ru": "ДАЛЕЕ", "en": "NEXT"},
    "btn_skip": {"ru": "ПРОПУСК", "en": "SKIP"},
    "btn_close": {"ru": "ЗАКРЫТЬ", "en": "CLOSE"},
    "ad_2x": {"ru": "2x РЕКЛАМА", "en": "2x AD"},
    "daily_ad_limit": {"ru": "Лимит рекламы (10/день)", "en": "Daily ad limit reached (10/day)"},

    # ---- Пермадес ----
    "permadeath": {"ru": "ГИБЕЛЬ", "en": "PERMADEATH"},
    "all_fighters_dead": {"ru": "ВСЕ БОЙЦЫ ПОГИБЛИ!", "en": "ALL FIGHTERS DEAD!"},
    "run_ended": {"ru": "Забег #{n} окончен.", "en": "Run #{n} ended."},
    "reached_tier_kills": {"ru": "Достигнут Тир {tier}  |  {kills} убийств", "en": "Reached Tier {tier}  |  {kills} kills"},
    "gold_equip_lost": {"ru": "Золото и снаряжение потеряны.\nАлмазы и достижения сохранены.", "en": "Gold and equipment are lost.\nDiamonds and achievements persist."},
    "new_run": {"ru": "НОВЫЙ ЗАБЕГ", "en": "NEW RUN"},

    # ---- Отряд / Набор ----
    "recruit_btn": {"ru": "+ НАНЯТЬ {cost}", "en": "+ RECRUIT {cost}"},
    "recruit_fighter_btn": {"ru": "+ НАНЯТЬ БОЙЦА", "en": "+ RECRUIT FIGHTER"},
    "choose_class": {"ru": "Выберите класс:", "en": "Choose a starter class:"},
    "recruit_fighter": {"ru": "Наём бойца", "en": "Recruit Fighter"},
    "btn_select": {"ru": "ВЫБРАТЬ", "en": "SELECT"},
    "dead_tag": {"ru": "МЁРТВ", "en": "DEAD"},
    "away_tag": {"ru": "В ПОХОДЕ", "en": "AWAY"},
    "active_tag": {"ru": "АКТИВЕН", "en": "ACTIVE"},
    "fallen": {"ru": "Павших: {n}", "en": "Fallen: {n}"},

    # ---- Кузня / Инвентарь ----
    "equip_btn": {"ru": "ЭКИПИРОВАТЬ", "en": "EQUIP"},
    "unequip_btn": {"ru": "СНЯТЬ", "en": "UNEQUIP"},
    "equipped_on": {"ru": "Надето на {name}", "en": "Equipped on {name}"},
    "improve_btn": {"ru": "УЛУЧШИТЬ", "en": "IMPROVE"},
    "upgrade_btn": {"ru": "УСИЛИТЬ", "en": "UPGRADE"},
    "level_label": {"ru": "Уровень", "en": "Level"},
    "bonus_label": {"ru": "Бонус", "en": "Bonus"},
    "total_atk": {"ru": "Итого ATK", "en": "Total ATK"},
    "cost_label": {"ru": "Цена", "en": "Cost"},
    "have_label": {"ru": "есть", "en": "have"},
    "weapon_base_atk": {"ru": "База оружия", "en": "Weapon base"},
    "armor_base_def": {"ru": "База брони", "en": "Armor base"},
    "accessory_base_hp": {"ru": "База аксессуара", "en": "Accessory base"},
    "total_label": {"ru": "Итого", "en": "Total"},
    "relic_base": {"ru": "База реликвии", "en": "Relic base"},
    "tab_shard": {"ru": "ОСКОЛКИ", "en": "SHARDS"},
    "enchant_label": {"ru": "ЗАЧАРОВАНИЕ", "en": "ENCHANTMENT"},
    "sell_btn": {"ru": "ПРОДАТЬ {price}", "en": "SELL {price}"},
    "buy_btn_price": {"ru": "КУПИТЬ {price}", "en": "BUY {price}"},
    "inventory_label": {"ru": "ИНВЕНТАРЬ", "en": "INVENTORY"},
    "inventory_count": {"ru": "ИНВЕНТАРЬ ({n})", "en": "INVENTORY ({n})"},
    "inventory_empty": {"ru": "Инвентарь пуст", "en": "Inventory is empty"},
    "empty_slot": {"ru": "--- пусто ---", "en": "--- empty ---"},
    "equipped_label": {"ru": "Надето: {name}", "en": "Equipped: {name}"},

    # ---- Экспедиции ----
    "danger_label": {"ru": "Опасность: {v}", "en": "Danger: {v}"},
    "relic_chance": {"ru": "Реликвия: {v}", "en": "Relic: {v}"},
    "send_name": {"ru": "Отправить {name}", "en": "Send {name}"},
    "send_btn": {"ru": "ОТПРАВИТЬ", "en": "SEND"},
    "no_eligible": {"ru": "Нет подходящих бойцов", "en": "No eligible fighters"},
    "no_expeditions_log": {"ru": "Пока нет экспедиций", "en": "No expeditions yet"},

    # ---- Лор ----
    "achievements_label": {"ru": "ДОСТИЖЕНИЯ", "en": "ACHIEVEMENTS"},
    "diamond_shop_label": {"ru": "МАГАЗИН АЛМАЗОВ", "en": "DIAMOND SHOP"},
    "stats_label": {"ru": "СТАТИСТИКА", "en": "STATISTICS"},
    "quests_label": {"ru": "КВЕСТЫ", "en": "QUESTS"},
    "done_label": {"ru": "ГОТОВО", "en": "DONE"},

    # ---- Настройки ----
    "restore_purchases": {"ru": "ВОССТАНОВИТЬ ПОКУПКИ", "en": "RESTORE PURCHASES"},
    "cloud_save": {"ru": "ОБЛАЧНОЕ СОХРАНЕНИЕ", "en": "CLOUD SAVE"},
    "sign_in_google": {"ru": "ВОЙТИ ЧЕРЕЗ GOOGLE", "en": "SIGN IN WITH GOOGLE"},
    "signed_in_as": {"ru": "ВХОД: {email}", "en": "SIGNED IN: {email}"},
    "sign_out_google": {"ru": "ВЫЙТИ", "en": "SIGN OUT"},
    "upload": {"ru": "ЗАГРУЗИТЬ", "en": "UPLOAD"},
    "download": {"ru": "СКАЧАТЬ", "en": "DOWNLOAD"},
    "sync": {"ru": "СИНХР.", "en": "SYNC"},
    "save_to_cloud": {"ru": "СОХРАНИТЬ В ОБЛАКО", "en": "SAVE TO CLOUD"},
    "load_from_cloud": {"ru": "ЗАГРУЗИТЬ ИЗ ОБЛАКА", "en": "LOAD FROM CLOUD"},
    "confirm_save_to_cloud": {"ru": "Облачное сохранение будет перезаписано локальным прогрессом. Продолжить?", "en": "This will overwrite your cloud save with local progress. Continue?"},
    "confirm_load_from_cloud": {"ru": "Локальный прогресс будет перезаписан облачным сохранением. Продолжить?", "en": "This will overwrite your local progress with cloud save. Continue?"},
    "confirm": {"ru": "ПОДТВЕРДИТЬ", "en": "CONFIRM"},
    "cancel": {"ru": "ОТМЕНА", "en": "CANCEL"},
    "remove_ads_label": {"ru": "Убрать рекламу", "en": "Remove Ads"},
    "remove_ads_buy": {"ru": "УБРАТЬ РЕКЛАМУ — $2", "en": "REMOVE ADS — $2"},
    "leaderboard_title": {"ru": "РЕЙТИНГ", "en": "LEADERBOARD"},
    "view_leaderboard": {"ru": "ПОКАЗАТЬ РЕЙТИНГ", "en": "VIEW LEADERBOARD"},
    "cloud_connected": {"ru": "Подключено!", "en": "Connected!"},
    "cloud_failed": {"ru": "Ошибка: {reason}", "en": "Failed: {reason}"},
    "cloud_uploaded": {"ru": "Сохранено в облако!", "en": "Saved to cloud!"},
    "cloud_loaded": {"ru": "Загружено из облака!", "en": "Loaded from cloud!"},

    # ---- Язык ----
    "language": {"ru": "ЯЗЫК", "en": "LANGUAGE"},
    "change_language": {"ru": "СМЕНИТЬ ЯЗЫК", "en": "CHANGE LANGUAGE"},

    # ---- Статусы ----
    "status_removed": {"ru": "Убрана", "en": "Removed"},
    "status_active": {"ru": "Активно", "en": "Active"},

    # ---- Туториал ----
    "got_it": {"ru": "ПОНЯТНО", "en": "GOT IT"},

    # ---- Сообщения движка ----
    "recruited_msg": {"ru": "Нанят {name} [{cls}]!", "en": "Recruited {name} [{cls}]!"},
    "need_gold": {"ru": "Нужно {cost}!", "en": "Need {cost}!"},
    "not_enough_gold": {"ru": "Не хватает {need} золота!", "en": "Need {need} more gold!"},
    "not_in_battle": {"ru": "Нельзя менять снаряжение в бою!", "en": "Cannot change equipment during battle!"},
    "not_enough_diamonds": {"ru": "Недостаточно алмазов", "en": "Not enough diamonds"},
    "fighter_dead": {"ru": "{name} мёртв", "en": "{name} is dead"},
    "dismiss_btn": {"ru": "Выгнать", "en": "Dismiss"},
    "dismiss_confirm_title": {"ru": "Выгнать бойца?", "en": "Dismiss fighter?"},
    "dismiss_confirm_msg": {"ru": "Выгнать {name} навсегда?\nСнаряжение вернётся в инвентарь.", "en": "Dismiss {name} permanently?\nEquipment will be returned to inventory."},
    "dismiss_confirm_btn": {"ru": "Да, выгнать", "en": "Yes, dismiss"},
    "fighter_dismissed": {"ru": "{name} выгнан", "en": "{name} dismissed"},
    "no_fighters": {"ru": "Нет бойцов!", "en": "No fighters!"},
    "reached_level": {"ru": "{name} достиг Ур.{lv} (+{pts} очк.)", "en": "{name} reached Lv.{lv} (+{pts} pts)"},
    "no_unused_points": {"ru": "Нет свободных очков", "en": "No unused points"},
    "stat_distributed": {"ru": "{name}: {stat} +1 (осталось {pts})", "en": "{name}: {stat} +1 ({pts} left)"},
    "item_not_found": {"ru": "Предмет не найден", "en": "Item not found"},
    "bought_msg": {"ru": "Куплено: {name}", "en": "Bought {name}"},
    "equipped_msg": {"ru": "{item} экипирован на {name}", "en": "{item} equipped on {name}"},
    "already_on_expedition": {"ru": "{name} уже в походе", "en": "{name} is already on expedition"},
    "max_expeditions": {"ru": "Макс. походов: {n}", "en": "Max expeditions: {n}"},
    "need_level": {"ru": "Нужен Ур.{lv}", "en": "Need Lv.{lv}"},
    "departed_msg": {"ru": "{name} ушёл: {exp}", "en": "{name} departed: {exp}"},
    "healed_all": {"ru": "Все исцелены!", "en": "All healed!"},
    "no_active_fighter": {"ru": "Нет активного бойца", "en": "No active fighter"},
    "revived_msg": {"ru": "{name} воскрешён!", "en": "Revived {name}!"},
    "no_dead_fighters": {"ru": "Нет погибших бойцов для воскрешения", "en": "No dead fighters to revive"},
    "war_drums": {"ru": "Барабаны войны на 1 час!", "en": "War Drums active for 1 hour!"},
    "expedition_slots": {"ru": "Слоты походов: {n}!", "en": "Expedition slots: {n}!"},
    "golden_set_equipped": {"ru": "Золотой боевой набор на {name}!", "en": "Golden War Set equipped on {name}!"},
    "golden_set_bought": {"ru": "Золотой набор добавлен в инвентарь!", "en": "Golden War Set added to inventory!"},
    "all_injuries_healed": {"ru": "Вылечено {n} травм!", "en": "{n} injuries healed!"},
    "no_injuries": {"ru": "Нет травм для лечения", "en": "No injuries to heal"},
    "no_healable_injuries": {"ru": "Нет излечимых травм", "en": "No healable injuries"},
    "permanent_injury_tag": {"ru": "(НАВСЕГДА)", "en": "(PERMANENT)"},
    "fallen_forever": {"ru": "{name} ПОГИБ НАВСЕГДА!", "en": "{name} has FALLEN FOREVER!"},
    "knocked_out_injury": {"ru": "{name} нокаут! {injury}", "en": "{name} knocked out! {injury}"},
    "suffered_injury": {"ru": "Получена травма: {injury}", "en": "Suffered: {injury}"},
    "injured_expedition": {"ru": "Травма: {injury}", "en": "Injured: {injury}"},
    "healed_injury_msg": {"ru": "Вылечен {name}: {injury} ({cost}з)", "en": "Healed {name}: {injury} ({cost}g)"},
    "healed_all_injuries_msg": {"ru": "Вылечено {n} травм за {cost}з", "en": "Healed {n} injuries for {cost}g"},
    "heal_cost_mult": {"ru": "Стоимость лечения: x{mult}", "en": "Heal cost: x{mult}"},
    "battle_log_btn": {"ru": "ЖУРНАЛ БОЁВ", "en": "BATTLE LOG"},
    "event_log_btn": {"ru": "ЖУРНАЛ СОБЫТИЙ", "en": "EVENT LOG"},
    "event_log_title": {"ru": "Журнал событий", "en": "Event Log"},
    "event_log_empty": {"ru": "Нет событий", "en": "No events"},
    "evt_battle": {"ru": "Бой", "en": "Battle"},
    "evt_hire": {"ru": "Найм", "en": "Hire"},
    "evt_dismiss": {"ru": "Увольнение", "en": "Dismiss"},
    "evt_level_up": {"ru": "Уровень", "en": "Level Up"},
    "evt_perk": {"ru": "Перк", "en": "Perk"},
    "evt_buy": {"ru": "Покупка", "en": "Buy"},
    "evt_sell": {"ru": "Продажа", "en": "Sell"},
    "evt_equip": {"ru": "Экипировка", "en": "Equip"},
    "evt_upgrade": {"ru": "Улучшение", "en": "Upgrade"},
    "evt_enchant": {"ru": "Зачарование", "en": "Enchant"},
    "evt_heal": {"ru": "Лечение", "en": "Heal"},
    "evt_expedition_send": {"ru": "Экспедиция", "en": "Expedition"},
    "battle_log_title": {"ru": "Журнал боёв", "en": "Battle Log"},
    "battle_log_empty": {"ru": "Нет записей", "en": "No battles yet"},
    "battle_log_victory": {"ru": "ПОБЕДА", "en": "VICTORY"},
    "battle_log_defeat": {"ru": "ПОРАЖЕНИЕ", "en": "DEFEAT"},
    "battle_log_boss": {"ru": "БОСС", "en": "BOSS"},
    "battle_log_knocked": {"ru": "Нокаут: {names}", "en": "Knocked out: {names}"},
    "battle_log_injuries": {"ru": "Травмы: {names}", "en": "Injuries: {names}"},
    "revived_all_msg": {"ru": "Воскрешено {n} бойцов!", "en": "{n} fighters revived!"},
    "renamed_msg": {"ru": "{old} теперь {new}!", "en": "{old} is now {new}!"},
    "rename_title": {"ru": "Переименовать бойца", "en": "Rename Fighter"},
    "confirm_btn": {"ru": "ПОДТВЕРДИТЬ", "en": "CONFIRM"},
    "level_n": {"ru": "Ур.{n}", "en": "Lv.{n}"},
    "btn_common": {"ru": "БОСС", "en": "BOSS"},
    "back_btn": {"ru": "НАЗАД", "en": "BACK"},
    "tab_weapon": {"ru": "ОРУЖИЕ", "en": "WEAPONS"},
    "tab_armor": {"ru": "БРОНЯ", "en": "ARMOR"},
    "tab_accessory": {"ru": "АКСЕССУАРЫ", "en": "ACCESSORIES"},
    "tier_advanced": {"ru": "Продвижение до уровня {tier}!", "en": "Advanced to tier {tier}!"},
    "2x_gold_reward": {"ru": "2x золото на 60 секунд!", "en": "2x gold for 60 seconds!"},
    "2x_gold_active": {"ru": "2x ЗОЛОТО: {t}с", "en": "2x GOLD: {t}s"},
    "diamonds_earned": {"ru": "+{n} алмазов!", "en": "+{n} diamonds!"},

    # ---- Магазин ----
    "blood_salve": {"ru": "Кровяная мазь", "en": "Blood Salve"},
    "blood_salve_desc": {"ru": "Полностью исцелить активного бойца", "en": "Fully heal active fighter"},
    "fury_tonic": {"ru": "Тоник ярости", "en": "Fury Tonic"},
    "fury_tonic_desc": {"ru": "+2 СИЛ активному бойцу", "en": "+2 base STR to active fighter"},
    "stone_brew": {"ru": "Каменное зелье", "en": "Stone Brew"},
    "stone_brew_desc": {"ru": "+2 ЖИВ активному бойцу", "en": "+2 base VIT to active fighter"},
    "surgeon_kit": {"ru": "Набор хирурга", "en": "Surgeon's Kit"},
    "surgeon_kit_desc": {"ru": "Вылечить 1 ранение (исп. {n}x)", "en": "Remove 1 injury (used {n}x)"},

    # ---- UI кнопки ----
    "heal_all_injuries": {"ru": "ВЫЛЕЧИТЬ ВСЕ ТРАВМЫ", "en": "HEAL ALL INJURIES"},
    "heal_all_injuries_cost": {"ru": "ВЫЛЕЧИТЬ ВСЕ ТРАВМЫ {cost}", "en": "HEAL ALL INJURIES {cost}"},
    "heal_all": {"ru": "ВЫЛЕЧИТЬ ВСЕХ", "en": "HEAL ALL"},
    "heal_all_cost": {"ru": "ВЫЛЕЧИТЬ ВСЕХ {cost}", "en": "HEAL ALL {cost}"},
    "heal_btn": {"ru": "ЛЕЧИТЬ", "en": "HEAL"},
    "train_btn": {"ru": "ТРЕН. {cost}", "en": "TRAIN {cost}"},
    "injuries_label": {"ru": "Травмы: {n}   Риск смерти: {risk}", "en": "Injuries: {n}   Death Risk: {risk}"},
    "injuries_tab": {"ru": "Травмы", "en": "Injuries"},
    "death_risk": {"ru": "Риск смерти", "en": "Death risk"},
    "heal_all_injuries_btn": {"ru": "ВЫЛЕЧИТЬ ВСЕ", "en": "HEAL ALL"},
    "kills_label": {"ru": "Убийств: {n}", "en": "Kills: {n}"},
    # ---- Perks ----
    "perks_btn": {"ru": "ПЕРКИ", "en": "PERKS"},
    "perk_points_label": {"ru": "Очки перков: {n}", "en": "Perk Points: {n}"},
    "perk_tier_label": {"ru": "Уровень {n}", "en": "Tier {n}"},
    "perk_unlocked": {"ru": "Открыт", "en": "Unlocked"},
    "perk_unlock_btn": {"ru": "Открыть ({cost})", "en": "Unlock ({cost})"},
    "perk_passive_label": {"ru": "ПАССИВНАЯ", "en": "PASSIVE"},
    "class_modifiers_label": {"ru": "МОДИФИКАТОРЫ", "en": "MODIFIERS"},
    "class_perks_label": {"ru": "ДРЕВО ПЕРКОВ", "en": "PERK TREE"},
    "class_points_per_level": {"ru": "+{n} очков за уровень", "en": "+{n} points per level"},
    "perk_cross_class": {"ru": "Кросс-класс: x{mult}", "en": "Cross-class: x{mult}"},
    "perk_already_unlocked": {"ru": "Перк уже открыт", "en": "Perk already unlocked"},
    "invalid_perk": {"ru": "Неверный перк", "en": "Invalid perk"},
    "not_enough_perk_points": {"ru": "Недостаточно очков перков", "en": "Not enough perk points"},
    "perk_unlocked_msg": {"ru": "{name}: перк {perk} открыт!", "en": "{name}: {perk} unlocked!"},
    "relics_label": {"ru": "Реликвий: {n}", "en": "Relics: {n}"},
    "pts_label": {"ru": "{n} очк.", "en": "{n} pts"},
    "total_wins": {"ru": "Всего побед", "en": "Total Wins"},
    "current_tier": {"ru": "Текущий уровень", "en": "Current Tier"},
    "best_tier": {"ru": "Лучший уровень", "en": "Best Tier Reached"},
    # ---- Shards & Upgrades ----
    "tab_enchant": {"ru": "ЗАЧАРОВАНИЕ", "en": "ENCHANT"},
    "shard_name_1": {"ru": "Осколок (I)", "en": "Shard (I)"},
    "shard_name_2": {"ru": "Осколок (II)", "en": "Shard (II)"},
    "shard_name_3": {"ru": "Осколок (III)", "en": "Shard (III)"},
    "shard_name_4": {"ru": "Осколок (IV)", "en": "Shard (IV)"},
    "shard_name_5": {"ru": "Осколок (V)", "en": "Shard (V)"},
    "max_upgrade_reached": {"ru": "Максимальный уровень!", "en": "Max upgrade!"},
    "not_enough_shards": {"ru": "Нужно {need}x Осколок({tier}), есть {have}", "en": "Need {need}x Shard({tier}), have {have}"},
    "weapon_upgraded": {"ru": "{name} улучшен до +{level}!", "en": "{name} upgraded to +{level}!"},
    "weapon_enchanted": {"ru": "{name}: {ench}!", "en": "{name}: {ench}!"},
    "invalid_enchantment": {"ru": "Неверное зачарование", "en": "Invalid enchantment"},
    "only_weapons": {"ru": "Только оружие", "en": "Weapons only"},
    "enchant_bleeding": {"ru": "Кровотечение", "en": "Bleeding"},
    "enchant_frostbite": {"ru": "Обморожение", "en": "Frostbite"},
    "enchant_poison": {"ru": "Отравление", "en": "Poison"},
    "enchant_burn": {"ru": "Ожог", "en": "Burn"},
    "enchant_paralyze": {"ru": "Паралич", "en": "Paralyze"},
    "enchant_corruption": {"ru": "Порча", "en": "Corruption"},
    "enchant_lightning": {"ru": "Молния", "en": "Lightning"},
    "enchant_weaken": {"ru": "Ослабление", "en": "Weaken"},
    "enchant_drain": {"ru": "Вытягивание", "en": "Drain"},
    "enchant_holy_fire": {"ru": "Священный огонь", "en": "Holy Fire"},
    "shard_label": {"ru": "ОСКОЛКИ", "en": "SHARDS"},
    "enchant_cost_label": {"ru": "{gold}g + {count}x Оск.({tier})", "en": "{gold}g + {count}x Shard({tier})"},
    "upgrade_cost_label": {"ru": "{count}x Оск.({tier})", "en": "{count}x Shard({tier})"},
    "current_enchant": {"ru": "Зачар: {name}", "en": "Ench: {name}"},
    "no_enchant": {"ru": "Без зачарования", "en": "No enchantment"},
    "enchant_names": {"ru": {"bleeding": "Кровотечение", "frostbite": "Обморожение", "poison": "Отравление", "burn": "Ожог", "paralyze": "Паралич", "corruption": "Порча", "lightning": "Молния", "weaken": "Ослабление", "drain": "Вытягивание", "holy_fire": "Священный огонь"}, "en": {"bleeding": "Bleeding", "frostbite": "Frostbite", "poison": "Poison", "burn": "Burn", "paralyze": "Paralyze", "corruption": "Corruption", "lightning": "Lightning", "weaken": "Weaken", "drain": "Drain", "holy_fire": "Holy Fire"}},
    # ---- Inventory tabs ----
    "tab_weapon": {"ru": "ОРУЖИЕ", "en": "WEAPON"},
    "tab_armor": {"ru": "БРОНЯ", "en": "ARMOR"},
    "tab_accessory": {"ru": "АКСЕССУАР", "en": "ACCESSORY"},
    "tab_relic": {"ru": "РЕЛИКВИЯ", "en": "RELIC"},
    "sort_best": {"ru": "Лучшее", "en": "Best"},
    "sort_worst": {"ru": "Худшее", "en": "Worst"},
    "filter_all": {"ru": "Все", "en": "All"},
    "filter_common": {"ru": "Обычн.", "en": "Common"},
    "filter_uncommon": {"ru": "Необ.", "en": "Uncommon"},
    "filter_rare": {"ru": "Редк.", "en": "Rare"},
    "filter_epic": {"ru": "Эпич.", "en": "Epic"},
    "filter_legendary": {"ru": "Легенд.", "en": "Legend."},
    "filter_free": {"ru": "Свободн.", "en": "Free"},
    "filter_equipped": {"ru": "Надето", "en": "Equipped"},
    "relic_slot": {"ru": "Реликвия", "en": "Relic"},
    "exp_shard_reward": {"ru": "Награда: {name}", "en": "Reward: {name}"},
    # ---- Help ----
    "buy_diamonds_label": {"ru": "КУПИТЬ АЛМАЗЫ", "en": "BUY DIAMONDS"},
    "help_title": {"ru": "ПОМОЩЬ", "en": "HELP"},
    "help_sections": {
        "ru": [
            ("АРЕНА (ПИТ)", "Бойцы сражаются с волнами врагов.\n"
             "- Авто-бой: все бойцы vs все враги\n"
             "- Босс: усиленный враг (x10 HP), победа повышает тир арены\n"
             "- Золото получаете только за победы на арене\n"
             "- Лечение: 1 золото = 10 HP (округление вверх)"),
            ("БОЙЦЫ (ОТРЯД)", "Каждый боец имеет 3 стата:\n"
             "- STR (Сила): базовый урон = STR x 2\n"
             "- AGI (Ловкость): шанс крита и уклонения\n"
             "- VIT (Живучесть): макс. HP = VIT x 10\n\n"
             "Тренировка повышает уровень и даёт очки статов.\n"
             "Экипировка: оружие, броня, аксессуар, реликвия."),
            ("ТРАВМЫ И СМЕРТЬ", "Когда боец падает в бою:\n"
             "- Проверка permadeath (шанс зависит от травм)\n"
             "- Если выжил — получает травму (+1)\n"
             "- Каждая травма увеличивает шанс гибели\n"
             "- Лечение травм за золото в деталях бойца\n"
             "- Гибель навсегда — экипировка возвращается в инвентарь"),
            ("КУЗНЯ И ИНВЕНТАРЬ", "Кузня: покупка оружия, брони, аксессуаров за золото.\n"
             "Инвентарь: 5 вкладок (оружие/броня/аксессуар/реликвия/осколки).\n"
             "- Тап на предмет: детали + продать/надеть/улучшить\n"
             "- Продажа: 50% от стоимости\n"
             "- Показывает и надетые предметы (можно снять)\n"
             "- Вкладка Осколки: количество осколков по тирам"),
            ("ПРОКАЧКА ЭКИПИРОВКИ", "Любую экипировку (кроме реликвий) можно улучшить за осколки.\n\n"
             "Макс. уровень зависит от редкости:\n"
             "- Common: +5, Uncommon: +10, Rare: +15\n"
             "- Epic: +20, Legendary: +25\n\n"
             "Стоимость осколков:\n"
             "- +1..+5: Осколок (I), от 1 до 5 штук\n"
             "- +6..+10: Осколок (II), от 1 до 5 штук\n"
             "- +11..+15: Осколок (III)\n"
             "- +16..+20: Осколок (IV)\n"
             "- +21..+25: Осколок (V)\n\n"
             "Бонусы от прокачки:\n"
             "- Оружие ATK: (STR + AGI) x (уровень x 20%)\n"
             "- Броня DEF: (STR + VIT) x (уровень x 20%)\n"
             "- Аксессуар HP: (AGI + VIT) x (уровень x 20%) x 10\n\n"
             "Реликвии: бонус делится на ATK/DEF/HP поровну.\n"
             "Формула: (STR+AGI+VIT) x (уровень x 20%) / 3\n"
             "HP бонус реликвии x10. Стоимость осколков x10."),
            ("ЗАЧАРОВАНИЕ", "Оружие можно зачаровать.\n"
             "Каждый удар копит buildup на враге:\n\n"
             "- Кровотечение: 20/удар, порог 100\n"
             "  Срабатывание: -15% макс. HP врага\n"
             "  Цена: 50K золота + 100x Осколок (V)\n\n"
             "- Обморожение: 15/удар, порог 100\n"
             "  Срабатывание: -10% HP + ATK -20% на 3 хода\n"
             "  Цена: 80K золота + 100x Осколок (V)\n\n"
             "- Отравление: 25/удар, порог 80\n"
             "  Срабатывание: -5% HP/ход на 4 хода\n"
             "  Цена: 60K золота + 100x Осколок (V)"),
            ("ОХОТА (ЭКСПЕДИЦИИ)", "Отправляйте бойцов на экспедиции.\n"
             "- Награда: 1-10 осколков металла (тир зависит от экспедиции)\n"
             "- Шанс найти реликвию (15%-55%)\n"
             "- Опасность: шанс проверки permadeath\n"
             "- Опасность x 0.5: шанс травмы\n"
             "- Чем выше уровень экспедиции — больше опасность"),
            ("МАГАЗИН АЛМАЗОВ", "Алмазы — премиум валюта.\n"
             "- Получаете за достижения\n"
             "- Можно купить за реальные деньги\n"
             "- Тратятся в магазине алмазов (вкладка Знания)\n"
             "- Сохраняются после roguelike сброса"),
            ("ROGUELIKE СБРОС", "Когда все бойцы погибли — забег заканчивается.\n"
             "- Сбрасывается: золото, бойцы, тир арены, осколки, инвентарь\n"
             "- Сохраняется: алмазы, достижения, рекорды, покупки"),
        ],
        "en": [
            ("ARENA (THE PIT)", "Fighters battle waves of enemies.\n"
             "- Auto-battle: all fighters vs all enemies\n"
             "- Boss: enhanced enemy (x10 HP), winning increases arena tier\n"
             "- Gold is earned only from arena victories\n"
             "- Healing: 1 gold = 10 HP (rounded up)"),
            ("FIGHTERS (SQUAD)", "Each fighter has 3 stats:\n"
             "- STR (Strength): base damage = STR x 2\n"
             "- AGI (Agility): crit chance and dodge chance\n"
             "- VIT (Vitality): max HP = VIT x 10\n\n"
             "Training levels up and gives stat points.\n"
             "Equipment: weapon, armor, accessory, relic."),
            ("INJURIES & DEATH", "When a fighter falls in battle:\n"
             "- Permadeath check (chance depends on injuries)\n"
             "- If survived — gains an injury (+1)\n"
             "- Each injury increases death chance\n"
             "- Heal injuries with gold in fighter details\n"
             "- Permadeath — equipment returns to inventory"),
            ("FORGE & INVENTORY", "Forge: buy weapons, armor, accessories for gold.\n"
             "Inventory: 5 tabs (weapon/armor/accessory/relic/shards).\n"
             "- Tap item: details + sell/equip/upgrade\n"
             "- Sell price: 50% of cost\n"
             "- Shows equipped items too (can unequip)\n"
             "- Shards tab: shard counts by tier"),
            ("EQUIPMENT UPGRADE", "Any equipment can be upgraded with metal shards.\n\n"
             "Max level depends on rarity:\n"
             "- Common: +5, Uncommon: +10, Rare: +15\n"
             "- Epic: +20, Legendary: +25\n\n"
             "Shard cost:\n"
             "- +1..+5: Shard (I), 1 to 5 pieces\n"
             "- +6..+10: Shard (II), 1 to 5 pieces\n"
             "- +11..+15: Shard (III)\n"
             "- +16..+20: Shard (IV)\n"
             "- +21..+25: Shard (V)\n\n"
             "Upgrade bonuses:\n"
             "- Weapon ATK: (STR + AGI) x (level x 20%)\n"
             "- Armor DEF: (STR + VIT) x (level x 20%)\n"
             "- Accessory HP: (AGI + VIT) x (level x 20%) x 10\n\n"
             "Relics: bonus split equally to ATK/DEF/HP.\n"
             "Formula: (STR+AGI+VIT) x (level x 20%) / 3\n"
             "Relic HP bonus x10. Shard cost x10."),
            ("ENCHANTMENT", "Weapons can be enchanted.\n"
             "Each hit builds up status on enemy:\n\n"
             "- Bleeding: 20/hit, threshold 100\n"
             "  Trigger: -15% enemy max HP\n"
             "  Cost: 50K gold + 100x Shard (V)\n\n"
             "- Frostbite: 15/hit, threshold 100\n"
             "  Trigger: -10% HP + ATK -20% for 3 turns\n"
             "  Cost: 80K gold + 100x Shard (V)\n\n"
             "- Poison: 25/hit, threshold 80\n"
             "  Trigger: -5% HP/turn for 4 turns\n"
             "  Cost: 60K gold + 100x Shard (V)"),
            ("EXPEDITIONS (HUNTS)", "Send fighters on expeditions.\n"
             "- Reward: 1-10 metal shards (tier depends on expedition)\n"
             "- Chance to find a relic (15%-55%)\n"
             "- Danger: chance of permadeath check\n"
             "- Danger x 0.5: chance of injury\n"
             "- Higher expedition level = more danger"),
            ("DIAMOND SHOP", "Diamonds are premium currency.\n"
             "- Earned from achievements\n"
             "- Can be purchased with real money\n"
             "- Spent in diamond shop (Lore tab)\n"
             "- Kept after roguelike reset"),
            ("ROGUELIKE RESET", "When all fighters die — the run ends.\n"
             "- Reset: gold, fighters, arena tier, shards, inventory\n"
             "- Kept: diamonds, achievements, records, purchases"),
        ],
    },
    # ---- Notifications ----
    "achievement_unlocked": {
        "ru": "{name}! +{diamonds} alm.",
        "en": "{name}! +{diamonds} dia.",
    },
    "quest_completed": {
        "ru": "{name} +{diamonds} alm.",
        "en": "{name} +{diamonds} dia.",
    },
}


def t(key, **kwargs):
    """Получить строку по ключу с подстановкой аргументов."""
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(_current_lang, entry.get("en", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def set_language(lang_code):
    """Установить язык (ru или en)."""
    global _current_lang
    _current_lang = lang_code if lang_code in ("ru", "en") else "ru"


def get_language():
    return _current_lang


def init_language():
    """Set default language to English. User choice is restored from save."""
    global _current_lang
    lang = "en"
    _current_lang = lang if lang in ("ru", "en") else "ru"
    return _current_lang
