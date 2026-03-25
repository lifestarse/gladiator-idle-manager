# Build: 1
"""Localization system — supports EN, RU, ES, DE, FR, PT, JA, KO, ZH."""

import locale
import os

_current_lang = "en"

STRINGS = {
    # ---- Navigation ----
    "nav_pit": {
        "en": "PIT", "ru": "АРЕНА", "es": "FOSO", "de": "GRUBE",
        "fr": "FOSSE", "pt": "ARENA", "ja": "闘技場", "ko": "투기장", "zh": "竞技场",
    },
    "nav_squad": {
        "en": "SQUAD", "ru": "ОТРЯД", "es": "EQUIPO", "de": "TRUPP",
        "fr": "ÉQUIPE", "pt": "EQUIPE", "ja": "部隊", "ko": "부대", "zh": "小队",
    },
    "nav_anvil": {
        "en": "ANVIL", "ru": "КУЗНЯ", "es": "YUNQUE", "de": "AMBOSS",
        "fr": "ENCLUME", "pt": "BIGORNA", "ja": "鍛冶", "ko": "대장간", "zh": "铁砧",
    },
    "nav_hunts": {
        "en": "HUNTS", "ru": "ОХОТА", "es": "CAZAR", "de": "JAGD",
        "fr": "CHASSES", "pt": "CAÇADAS", "ja": "狩猟", "ko": "사냥", "zh": "狩猎",
    },
    "nav_lore": {
        "en": "LORE", "ru": "ЗНАНИЯ", "es": "SABER", "de": "KUNDE",
        "fr": "SAVOIR", "pt": "SABER", "ja": "伝承", "ko": "전승", "zh": "传说",
    },
    "nav_more": {
        "en": "MORE", "ru": "ЕЩЁ", "es": "M\u00c1S", "de": "MEHR",
        "fr": "PLUS", "pt": "MAIS", "ja": "その他", "ko": "더보기", "zh": "更多",
    },

    # ---- Screen titles ----
    "title_pit": {
        "en": "T H E   P I T", "ru": "А Р Е Н А", "es": "E L   F O S O",
        "de": "D I E   G R U B E", "fr": "L A   F O S S E", "pt": "A   A R E N A",
        "ja": "闘 技 場", "ko": "투 기 장", "zh": "竞 技 场",
    },
    "title_squad": {
        "en": "S Q U A D", "ru": "О Т Р Я Д", "es": "E Q U I P O",
        "de": "T R U P P", "fr": "É Q U I P E", "pt": "E Q U I P E",
        "ja": "部 隊", "ko": "부 대", "zh": "小 队",
    },
    "title_anvil": {
        "en": "T H E   A N V I L", "ru": "К У З Н Я", "es": "E L   Y U N Q U E",
        "de": "D E R   A M B O S S", "fr": "L ' E N C L U M E", "pt": "A   B I G O R N A",
        "ja": "鍛 冶 場", "ko": "대 장 간", "zh": "铁 砧",
    },
    "title_hunts": {
        "en": "H U N T S", "ru": "О Х О Т А", "es": "C A Z A R",
        "de": "J A G D", "fr": "C H A S S E S", "pt": "C A Ç A D A S",
        "ja": "狩 猟", "ko": "사 냥", "zh": "狩 猎",
    },
    "title_lore": {
        "en": "L O R E", "ru": "З Н А Н И Я", "es": "S A B E R",
        "de": "K U N D E", "fr": "S A V O I R", "pt": "S A B E R",
        "ja": "伝 承", "ko": "전 승", "zh": "传 说",
    },
    "title_more": {
        "en": "M A R K E T  &  S E T T I N G S", "ru": "М А Г А З И Н  &  Н А С Т Р О Й К И",
        "es": "T I E N D A  &  A J U S T E S", "de": "M A R K T  &  E I N S T E L L U N G E N",
        "fr": "M A R C H É  &  P A R A M È T R E S", "pt": "L O J A  &  C O N F I G U R A Ç Õ E S",
        "ja": "マーケット & 設定", "ko": "상점 & 설정", "zh": "市场 & 设置",
    },

    # ---- Arena / Battle ----
    "ready_to_fight": {
        "en": "Ready to fight", "ru": "Готов к бою", "es": "Listo para luchar",
        "de": "Kampfbereit", "fr": "Prêt au combat", "pt": "Pronto para lutar",
        "ja": "戦闘準備完了", "ko": "전투 준비 완료", "zh": "准备战斗",
    },
    "auto_battle": {
        "en": "AUTO BATTLE!", "ru": "АВТО-БОЙ!", "es": "¡BATALLA AUTO!",
        "de": "AUTO-KAMPF!", "fr": "COMBAT AUTO!", "pt": "BATALHA AUTO!",
        "ja": "オートバトル！", "ko": "자동 전투!", "zh": "自动战斗！",
    },
    "boss_challenge": {
        "en": "BOSS CHALLENGE!", "ru": "БОЙ С БОССОМ!", "es": "¡DESAFÍO JEFE!",
        "de": "BOSS-HERAUSFORDERUNG!", "fr": "DÉFI DU BOSS!", "pt": "DESAFIO DO CHEFE!",
        "ja": "ボスチャレンジ！", "ko": "보스 도전!", "zh": "BOSS挑战！",
    },
    "victory": {
        "en": "VICTORY!", "ru": "ПОБЕДА!", "es": "¡VICTORIA!",
        "de": "SIEG!", "fr": "VICTOIRE!", "pt": "VITÓRIA!",
        "ja": "勝利！", "ko": "승리!", "zh": "胜利！",
    },
    "defeat": {
        "en": "DEFEAT!", "ru": "ПОРАЖЕНИЕ!", "es": "¡DERROTA!",
        "de": "NIEDERLAGE!", "fr": "DÉFAITE!", "pt": "DERROTA!",
        "ja": "敗北！", "ko": "패배!", "zh": "战败！",
    },
    "vs": {
        "en": "VS", "ru": "ПРОТИВ", "es": "VS", "de": "VS",
        "fr": "VS", "pt": "VS", "ja": "VS", "ko": "VS", "zh": "VS",
    },
    "fighters_ready": {
        "en": "{n} fighters ready", "ru": "{n} бойцов готово", "es": "{n} luchadores listos",
        "de": "{n} Kämpfer bereit", "fr": "{n} combattants prêts", "pt": "{n} lutadores prontos",
        "ja": "{n}人の戦士準備完了", "ko": "{n}명의 전사 준비됨", "zh": "{n}名战士就绪",
    },
    "btn_auto": {
        "en": "FIGHT", "ru": "БОЙ", "es": "PELEA", "de": "KAMPF",
        "fr": "COMBAT", "pt": "LUTA", "ja": "戦闘", "ko": "전투", "zh": "战斗",
    },
    "btn_boss": {
        "en": "BOSS", "ru": "БОСС", "es": "JEFE", "de": "BOSS",
        "fr": "BOSS", "pt": "CHEFE", "ja": "ボス", "ko": "보스", "zh": "首领",
    },
    "btn_next": {
        "en": "NEXT", "ru": "ДАЛЕЕ", "es": "SIG.", "de": "WEITER",
        "fr": "SUIV.", "pt": "PRÓX.", "ja": "次へ", "ko": "다음", "zh": "下一个",
    },
    "btn_skip": {
        "en": "SKIP", "ru": "ПРОПУСК", "es": "SALTAR", "de": "\u00dcBER.",
        "fr": "PASSER", "pt": "PULAR", "ja": "スキップ", "ko": "건너뛰기", "zh": "跳过",
    },
    "ad_2x": {
        "en": "2x AD", "ru": "2x РЕКЛАМА", "es": "2x ANUNCIO", "de": "2x WERBUNG",
        "fr": "2x PUB", "pt": "2x ANÚNCIO", "ja": "2x 広告", "ko": "2x 광고", "zh": "2x 广告",
    },
    "daily_ad_limit": {
        "en": "Daily ad limit reached (10/day)", "ru": "Лимит рекламы (10/день)",
        "es": "Límite diario de anuncios (10/día)", "de": "Tägliches Werbelimit (10/Tag)",
        "fr": "Limite pub atteinte (10/jour)", "pt": "Limite diário de anúncios (10/dia)",
        "ja": "広告の日次制限に達しました(10/日)", "ko": "일일 광고 한도 (10/일)", "zh": "每日广告上限(10/天)",
    },

    # ---- Permadeath popup ----
    "permadeath": {
        "en": "PERMADEATH", "ru": "ГИБЕЛЬ", "es": "MUERTE PERMANENTE",
        "de": "PERMANENTER TOD", "fr": "MORT DÉFINITIVE", "pt": "MORTE PERMANENTE",
        "ja": "永久死亡", "ko": "영구 사망", "zh": "永久死亡",
    },
    "all_fighters_dead": {
        "en": "ALL FIGHTERS DEAD!", "ru": "ВСЕ БОЙЦЫ ПОГИБЛИ!",
        "es": "¡TODOS LOS LUCHADORES MUERTOS!", "de": "ALLE KÄMPFER TOT!",
        "fr": "TOUS LES COMBATTANTS MORTS!", "pt": "TODOS OS LUTADORES MORTOS!",
        "ja": "全戦士死亡！", "ko": "모든 전사 사망!", "zh": "全部战士阵亡！",
    },
    "run_ended": {
        "en": "Run #{n} ended.", "ru": "Забег #{n} окончен.", "es": "Ronda #{n} terminada.",
        "de": "Lauf #{n} beendet.", "fr": "Série #{n} terminée.", "pt": "Rodada #{n} encerrada.",
        "ja": "ラン #{n} 終了。", "ko": "런 #{n} 종료.", "zh": "第{n}轮结束。",
    },
    "reached_tier_kills": {
        "en": "Reached Tier {tier}  |  {kills} kills",
        "ru": "Достигнут Тир {tier}  |  {kills} убийств",
        "es": "Nivel {tier} alcanzado  |  {kills} muertes",
        "de": "Stufe {tier} erreicht  |  {kills} Siege",
        "fr": "Rang {tier} atteint  |  {kills} victimes",
        "pt": "Nível {tier} alcançado  |  {kills} mortes",
        "ja": "ティア{tier}到達  |  {kills}キル",
        "ko": "티어 {tier} 도달  |  {kills} 처치",
        "zh": "达到阶级{tier}  |  {kills}次击杀",
    },
    "gold_equip_lost": {
        "en": "Gold and equipment are lost.\nDiamonds and achievements persist.",
        "ru": "Золото и снаряжение потеряны.\nАлмазы и достижения сохранены.",
        "es": "Oro y equipo perdidos.\nDiamantes y logros se conservan.",
        "de": "Gold und Ausrüstung verloren.\nDiamanten und Erfolge bleiben.",
        "fr": "Or et équipement perdus.\nDiamants et succès conservés.",
        "pt": "Ouro e equipamento perdidos.\nDiamantes e conquistas permanecem.",
        "ja": "ゴールドと装備は失われます。\nダイヤと実績は保持されます。",
        "ko": "골드와 장비를 잃습니다.\n다이아몬드와 업적은 유지됩니다.",
        "zh": "金币和装备将丢失。\n钻石和成就将保留。",
    },
    "new_run": {
        "en": "NEW RUN", "ru": "НОВЫЙ ЗАБЕГ", "es": "NUEVA RONDA",
        "de": "NEUER LAUF", "fr": "NOUVELLE SÉRIE", "pt": "NOVA RODADA",
        "ja": "ニューラン", "ko": "새 런", "zh": "新一轮",
    },

    # ---- Squad / Roster ----
    "recruit_btn": {
        "en": "+ RECRUIT ({cost})", "ru": "+ НАНЯТЬ ({cost})",
        "es": "+ RECLUTAR ({cost})", "de": "+ REKRUT ({cost})",
        "fr": "+ RECRUTER ({cost})", "pt": "+ RECRUTAR ({cost})",
        "ja": "+ 雇用 ({cost})", "ko": "+ 고용 ({cost})", "zh": "+ 招募 ({cost})",
    },
    "choose_class": {
        "en": "Choose a starter class:", "ru": "Выберите класс:",
        "es": "Elige una clase inicial:", "de": "Wähle eine Starterklasse:",
        "fr": "Choisissez une classe:", "pt": "Escolha uma classe inicial:",
        "ja": "初期クラスを選択:", "ko": "시작 클래스 선택:", "zh": "选择初始职业:",
    },
    "recruit_fighter": {
        "en": "Recruit Fighter", "ru": "Наём бойца", "es": "Reclutar Luchador",
        "de": "Kämpfer rekrutieren", "fr": "Recruter Combattant", "pt": "Recrutar Lutador",
        "ja": "戦士を雇用", "ko": "전사 고용", "zh": "招募战士",
    },
    "btn_select": {
        "en": "SELECT", "ru": "ВЫБРАТЬ", "es": "ELEGIR", "de": "WÄHLEN",
        "fr": "CHOISIR", "pt": "ESCOLHER", "ja": "選択", "ko": "선택", "zh": "选择",
    },
    "dead_tag": {
        "en": "DEAD", "ru": "МЁРТВ", "es": "MUERTO", "de": "TOT",
        "fr": "MORT", "pt": "MORTO", "ja": "死亡", "ko": "사망", "zh": "死亡",
    },
    "away_tag": {
        "en": "AWAY", "ru": "В ПОХОДЕ", "es": "AUSENTE", "de": "UNTERWEGS",
        "fr": "ABSENT", "pt": "AUSENTE", "ja": "遠征中", "ko": "원정 중", "zh": "远征中",
    },
    "active_tag": {
        "en": "ACTIVE", "ru": "АКТИВЕН", "es": "ACTIVO", "de": "AKTIV",
        "fr": "ACTIF", "pt": "ATIVO", "ja": "出撃中", "ko": "활성", "zh": "出战中",
    },
    "fallen": {
        "en": "Fallen: {n}", "ru": "Павших: {n}", "es": "Caídos: {n}",
        "de": "Gefallen: {n}", "fr": "Tombés: {n}", "pt": "Caídos: {n}",
        "ja": "戦死: {n}", "ko": "전사: {n}", "zh": "阵亡: {n}",
    },

    # ---- Forge / Anvil ----

    # ---- Expeditions / Hunts ----
    "danger_label": {
        "en": "Danger: {v}", "ru": "Опасность: {v}", "es": "Peligro: {v}",
        "de": "Gefahr: {v}", "fr": "Danger: {v}", "pt": "Perigo: {v}",
        "ja": "危険度: {v}", "ko": "위험도: {v}", "zh": "危险: {v}",
    },
    "relic_chance": {
        "en": "Relic: {v}", "ru": "Реликвия: {v}", "es": "Reliquia: {v}",
        "de": "Relikt: {v}", "fr": "Relique: {v}", "pt": "Relíquia: {v}",
        "ja": "遺物: {v}", "ko": "유물: {v}", "zh": "遗物: {v}",
    },
    "send_name": {
        "en": "Send {name}", "ru": "Отправить {name}", "es": "Enviar {name}",
        "de": "Senden {name}", "fr": "Envoyer {name}", "pt": "Enviar {name}",
        "ja": "{name}を派遣", "ko": "{name} 파견", "zh": "派遣{name}",
    },
    "no_eligible": {
        "en": "No eligible fighters", "ru": "Нет подходящих бойцов",
        "es": "Sin luchadores aptos", "de": "Keine geeigneten Kämpfer",
        "fr": "Aucun combattant éligible", "pt": "Sem lutadores aptos",
        "ja": "対象の戦士なし", "ko": "적격 전사 없음", "zh": "无合适战士",
    },

    # ---- Lore screen sections ----
    "achievements_label": {
        "en": "ACHIEVEMENTS", "ru": "ДОСТИЖЕНИЯ", "es": "LOGROS",
        "de": "ERFOLGE", "fr": "SUCC\u00c8S", "pt": "CONQUISTAS",
        "ja": "実績", "ko": "업적", "zh": "成就",
    },
    "diamond_shop_label": {
        "en": "DIAMOND SHOP", "ru": "МАГАЗИН АЛМАЗОВ", "es": "TIENDA DE DIAMANTES",
        "de": "DIAMANTENSHOP", "fr": "BOUTIQUE DIAMANTS", "pt": "LOJA DE DIAMANTES",
        "ja": "ダイヤショップ", "ko": "다이아 상점", "zh": "钻石商店",
    },
    "done_label": {
        "en": "DONE", "ru": "ГОТОВО", "es": "HECHO", "de": "FERTIG",
        "fr": "FAIT", "pt": "FEITO", "ja": "完了", "ko": "완료", "zh": "完成",
    },

    # ---- More / Market screen ----
    "restore_purchases": {
        "en": "RESTORE PURCHASES", "ru": "ВОССТАНОВИТЬ ПОКУПКИ",
        "es": "RESTAURAR COMPRAS", "de": "KÄUFE WIEDERHERSTELLEN",
        "fr": "RESTAURER LES ACHATS", "pt": "RESTAURAR COMPRAS",
        "ja": "購入を復元", "ko": "구매 복원", "zh": "恢复购买",
    },
    "cloud_save": {
        "en": "CLOUD SAVE", "ru": "ОБЛАЧНОЕ СОХРАНЕНИЕ",
        "es": "GUARDADO EN NUBE", "de": "CLOUD-SPEICHER",
        "fr": "SAUVEGARDE CLOUD", "pt": "SALVAR NA NUVEM",
        "ja": "クラウドセーブ", "ko": "클라우드 저장", "zh": "云存档",
    },
    "sign_in_google": {
        "en": "SIGN IN WITH GOOGLE", "ru": "ВОЙТИ ЧЕРЕЗ GOOGLE",
        "es": "INICIAR SESIÓN CON GOOGLE", "de": "MIT GOOGLE ANMELDEN",
        "fr": "SE CONNECTER AVEC GOOGLE", "pt": "ENTRAR COM GOOGLE",
        "ja": "Googleでサインイン", "ko": "Google 로그인", "zh": "Google登录",
    },
    "signed_in_as": {
        "en": "SIGNED IN: {email}", "ru": "ВХОД: {email}",
        "es": "CONECTADO: {email}", "de": "ANGEMELDET: {email}",
        "fr": "CONNECTÉ: {email}", "pt": "CONECTADO: {email}",
        "ja": "ログイン中: {email}", "ko": "로그인: {email}", "zh": "已登录: {email}",
    },
    "sign_out_google": {
        "en": "SIGN OUT", "ru": "ВЫЙТИ",
        "es": "CERRAR SESIÓN", "de": "ABMELDEN",
        "fr": "SE DÉCONNECTER", "pt": "SAIR",
        "ja": "サインアウト", "ko": "로그아웃", "zh": "退出登录",
    },
    "language": {
        "en": "LANGUAGE", "ru": "ЯЗЫК",
        "es": "IDIOMA", "de": "SPRACHE",
        "fr": "LANGUE", "pt": "IDIOMA",
        "ja": "言語", "ko": "언어", "zh": "语言",
    },
    "change_language": {
        "en": "CHANGE LANGUAGE", "ru": "СМЕНИТЬ ЯЗЫК",
        "es": "CAMBIAR IDIOMA", "de": "SPRACHE ÄNDERN",
        "fr": "CHANGER LA LANGUE", "pt": "MUDAR IDIOMA",
        "ja": "言語を変更", "ko": "언어 변경", "zh": "更改语言",
    },
    "upload": {
        "en": "UPLOAD", "ru": "ЗАГРУЗИТЬ", "es": "SUBIR", "de": "HOCHLADEN",
        "fr": "ENVOYER", "pt": "ENVIAR", "ja": "アップロード", "ko": "업로드", "zh": "上传",
    },
    "download": {
        "en": "DOWNLOAD", "ru": "СКАЧАТЬ", "es": "DESCARGAR", "de": "HERUNTERLADEN",
        "fr": "TÉLÉCHARGER", "pt": "BAIXAR", "ja": "ダウンロード", "ko": "다운로드", "zh": "下载",
    },
    "sync": {
        "en": "SYNC", "ru": "СИНХР.", "es": "SINCR.", "de": "SYNC",
        "fr": "SYNC", "pt": "SINCR.", "ja": "同期", "ko": "동기化", "zh": "同步",
    },
    "save_to_cloud": {
        "en": "SAVE TO CLOUD", "ru": "СОХРАНИТЬ В ОБЛАКО",
        "es": "GUARDAR EN LA NUBE", "de": "IN CLOUD SPEICHERN",
        "fr": "SAUVEGARDER DANS LE CLOUD", "pt": "SALVAR NA NUVEM",
        "ja": "クラウドに保存", "ko": "클라우드에 저장", "zh": "保存到云端",
    },
    "load_from_cloud": {
        "en": "LOAD FROM CLOUD", "ru": "ЗАГРУЗИТЬ ИЗ ОБЛАКА",
        "es": "CARGAR DESDE LA NUBE", "de": "AUS CLOUD LADEN",
        "fr": "CHARGER DEPUIS LE CLOUD", "pt": "CARREGAR DA NUVEM",
        "ja": "クラウドから読込", "ko": "클라우드에서 불러오기", "zh": "从云端加载",
    },
    "confirm_save_to_cloud": {
        "en": "This will overwrite your cloud save with local progress. Continue?",
        "ru": "Облачное сохранение будет перезаписано локальным прогрессом. Продолжить?",
        "es": "Esto sobrescribirá tu guardado en la nube. ¿Continuar?",
        "de": "Der Cloud-Speicherstand wird überschrieben. Fortfahren?",
        "fr": "La sauvegarde cloud sera écrasée. Continuer ?",
        "pt": "O salvamento na nuvem será substituído. Continuar?",
        "ja": "クラウドのセーブデータが上書きされます。続行しますか？",
        "ko": "클라우드 저장 데이터가 덮어씌워집니다. 계속하시겠습니까?",
        "zh": "这将覆盖您的云端存档。是否继续？",
    },
    "confirm_load_from_cloud": {
        "en": "This will overwrite your local progress with cloud save. Continue?",
        "ru": "Локальный прогресс будет перезаписан облачным сохранением. Продолжить?",
        "es": "Esto sobrescribirá tu progreso local. ¿Continuar?",
        "de": "Der lokale Fortschritt wird überschrieben. Fortfahren?",
        "fr": "La progression locale sera écrasée. Continuer ?",
        "pt": "O progresso local será substituído. Continuar?",
        "ja": "ローカルの進行状況が上書きされます。続行しますか？",
        "ko": "로컬 진행 상황이 덮어씌워집니다. 계속하시겠습니까?",
        "zh": "这将覆盖您的本地进度。是否继续？",
    },
    "confirm": {
        "en": "CONFIRM", "ru": "ПОДТВЕРДИТЬ",
        "es": "CONFIRMAR", "de": "BESTÄTIGEN",
        "fr": "CONFIRMER", "pt": "CONFIRMAR",
        "ja": "確認", "ko": "확인", "zh": "确认",
    },
    "cancel": {
        "en": "CANCEL", "ru": "ОТМЕНА",
        "es": "CANCELAR", "de": "ABBRECHEN",
        "fr": "ANNULER", "pt": "CANCELAR",
        "ja": "キャンセル", "ko": "취소", "zh": "取消",
    },

    # ---- Tutorial / popups ----
    "got_it": {
        "en": "GOT IT", "ru": "ПОНЯТНО", "es": "ENTENDIDO", "de": "VERSTANDEN",
        "fr": "COMPRIS", "pt": "ENTENDI", "ja": "了解", "ko": "확인", "zh": "明白了",
    },

    # ---- Engine messages ----
    "recruited_msg": {
        "en": "Recruited {name} [{cls}]!", "ru": "Нанят {name} [{cls}]!",
        "es": "¡Reclutado {name} [{cls}]!", "de": "{name} [{cls}] rekrutiert!",
        "fr": "{name} [{cls}] recruté!", "pt": "{name} [{cls}] recrutado!",
        "ja": "{name}【{cls}】を雇用！", "ko": "{name} [{cls}] 고용!", "zh": "招募了{name}【{cls}】！",
    },
    "need_gold": {
        "en": "Need {cost}!", "ru": "Нужно {cost}!", "es": "¡Necesitas {cost}!",
        "de": "{cost} benötigt!", "fr": "Il faut {cost}!", "pt": "Precisa de {cost}!",
        "ja": "{cost}必要！", "ko": "{cost} 필요!", "zh": "需要{cost}！",
    },
    "not_enough_gold": {
        "en": "Not enough gold!", "ru": "Недостаточно золота!", "es": "¡Oro insuficiente!",
        "de": "Nicht genug Gold!", "fr": "Pas assez d'or!", "pt": "Ouro insuficiente!",
        "ja": "ゴールドが足りません！", "ko": "골드가 부족합니다!", "zh": "金币不足！",
    },
    "not_enough_diamonds": {
        "en": "Not enough diamonds", "ru": "Недостаточно алмазов",
        "es": "Diamantes insuficientes", "de": "Nicht genug Diamanten",
        "fr": "Pas assez de diamants", "pt": "Diamantes insuficientes",
        "ja": "ダイヤ不足", "ko": "다이아 부족", "zh": "钻石不足",
    },
    "2x_gold_active": {
        "en": "2x GOLD: {t}s", "ru": "2x ЗОЛОТО: {t}с", "es": "2x ORO: {t}s",
        "de": "2x GOLD: {t}s", "fr": "2x OR: {t}s", "pt": "2x OURO: {t}s",
        "ja": "2xゴールド: {t}秒", "ko": "2x 골드: {t}초", "zh": "2倍金币: {t}秒",
    },

    # ---- Status strings ----
    "status_removed": {
        "en": "Removed", "ru": "Убрана", "es": "Eliminado", "de": "Entfernt",
        "fr": "Supprimé", "pt": "Removido", "ja": "削除済み", "ko": "제거됨", "zh": "已移除",
    },
    "status_active": {
        "en": "Active", "ru": "Активно", "es": "Activo", "de": "Aktiv",
        "fr": "Actif", "pt": "Ativo", "ja": "有効", "ko": "활성", "zh": "活跃",
    },

    # ---- Forge / Anvil detail ----
    "equipped_msg": {
        "en": "Equipped {item} on {name}!", "ru": "{item} экипирован на {name}!",
        "es": "¡{item} equipado en {name}!", "de": "{item} auf {name} ausgerüstet!",
        "fr": "{item} équipé sur {name}!", "pt": "{item} equipado em {name}!",
        "ja": "{name}に{item}を装備！", "ko": "{name}에 {item} 장착!", "zh": "{name}装备了{item}！",
    },
    "no_active_fighter": {
        "en": "No active fighter", "ru": "Нет активного бойца",
        "es": "Sin luchador activo", "de": "Kein aktiver Kämpfer",
        "fr": "Aucun combattant actif", "pt": "Sem lutador ativo",
        "ja": "アクティブ戦士なし", "ko": "활성 전사 없음", "zh": "无出战战士",
    },
    "item_not_found": {
        "en": "Item not found", "ru": "Предмет не найден", "es": "Objeto no encontrado",
        "de": "Gegenstand nicht gefunden", "fr": "Objet non trouvé", "pt": "Item não encontrado",
        "ja": "アイテムなし", "ko": "아이템 없음", "zh": "物品未找到",
    },

    # ---- Expeditions ----
    "departed_msg": {
        "en": "{name} departed for {exp}!", "ru": "{name} отправился в {exp}!",
        "es": "¡{name} partió a {exp}!", "de": "{name} ging auf {exp}!",
        "fr": "{name} parti pour {exp}!", "pt": "{name} partiu para {exp}!",
        "ja": "{name}は{exp}に出発！", "ko": "{name}이(가) {exp}로 출발!", "zh": "{name}出发前往{exp}！",
    },
    "already_on_expedition": {
        "en": "{name} already on expedition", "ru": "{name} уже в походе",
        "es": "{name} ya en expedición", "de": "{name} bereits auf Expedition",
        "fr": "{name} déjà en expédition", "pt": "{name} já em expedição",
        "ja": "{name}は遠征中", "ko": "{name} 원정 중", "zh": "{name}已在远征中",
    },
    "max_expeditions": {
        "en": "Max {n} expedition(s) at once!", "ru": "Макс. {n} походов одновременно!",
        "es": "¡Máx. {n} expedición(es) a la vez!", "de": "Max. {n} Expedition(en) gleichzeitig!",
        "fr": "Max {n} expédition(s) à la fois!", "pt": "Máx. {n} expedição(ões) ao mesmo tempo!",
        "ja": "最大{n}件の遠征！", "ko": "최대 {n}개 원정!", "zh": "最多{n}次远征！",
    },
    "need_level": {
        "en": "Need Lv.{lv}+", "ru": "Нужен Ур.{lv}+", "es": "Necesita Nv.{lv}+",
        "de": "Lv.{lv}+ benötigt", "fr": "Nv.{lv}+ requis", "pt": "Precisa Nv.{lv}+",
        "ja": "Lv.{lv}以上必要", "ko": "Lv.{lv}+ 필요", "zh": "需要Lv.{lv}+",
    },

    # ---- Fighter messages ----
    "fighter_dead": {
        "en": "{name} is dead", "ru": "{name} мёртв", "es": "{name} está muerto",
        "de": "{name} ist tot", "fr": "{name} est mort", "pt": "{name} está morto",
        "ja": "{name}は死亡", "ko": "{name} 사망", "zh": "{name}已死亡",
    },
    "reached_level": {
        "en": "{name} reached Lv.{lv}! +{pts} stat points",
        "ru": "{name} достиг Ур.{lv}! +{pts} очков характеристик",
        "es": "¡{name} alcanzó Nv.{lv}! +{pts} puntos de atributo",
        "de": "{name} erreichte Lv.{lv}! +{pts} Statuspunkte",
        "fr": "{name} a atteint Nv.{lv}! +{pts} pts de stats",
        "pt": "{name} alcançou Nv.{lv}! +{pts} pontos de atributo",
        "ja": "{name}がLv.{lv}到達！+{pts}ステータスポイント",
        "ko": "{name} Lv.{lv} 달성! +{pts} 스탯 포인트",
        "zh": "{name}达到Lv.{lv}！+{pts}属性点",
    },
    "no_unused_points": {
        "en": "No unused points!", "ru": "Нет свободных очков!",
        "es": "¡Sin puntos disponibles!", "de": "Keine freien Punkte!",
        "fr": "Aucun point disponible!", "pt": "Sem pontos disponíveis!",
        "ja": "未使用ポイントなし！", "ko": "미사용 포인트 없음!", "zh": "没有未分配的点数！",
    },
    "stat_distributed": {
        "en": "{name}: {stat} +1 ({pts} pts left)",
        "ru": "{name}: {stat} +1 ({pts} очк. осталось)",
        "es": "{name}: {stat} +1 ({pts} pts rest.)",
        "de": "{name}: {stat} +1 ({pts} Pkt. übrig)",
        "fr": "{name}: {stat} +1 ({pts} pts rest.)",
        "pt": "{name}: {stat} +1 ({pts} pts rest.)",
        "ja": "{name}: {stat} +1 (残り{pts}ポイント)",
        "ko": "{name}: {stat} +1 ({pts}포인트 남음)",
        "zh": "{name}: {stat} +1 (剩余{pts}点)",
    },
    "no_fighters": {
        "en": "No fighters available!", "ru": "Нет доступных бойцов!",
        "es": "¡Sin luchadores disponibles!", "de": "Keine Kämpfer verfügbar!",
        "fr": "Aucun combattant disponible!", "pt": "Sem lutadores disponíveis!",
        "ja": "戦士がいません！", "ko": "전사가 없습니다!", "zh": "没有可用战士！",
    },

    # ---- Shop / consumable messages ----
    "bought_msg": {
        "en": "Bought {name}!", "ru": "Куплено: {name}!", "es": "¡{name} comprado!",
        "de": "{name} gekauft!", "fr": "{name} acheté!", "pt": "{name} comprado!",
        "ja": "{name}を購入！", "ko": "{name} 구매!", "zh": "购买了{name}！",
    },
    "healed_all": {
        "en": "All fighters healed!", "ru": "Все бойцы исцелены!",
        "es": "¡Todos los luchadores curados!", "de": "Alle Kämpfer geheilt!",
        "fr": "Tous les combattants soignés!", "pt": "Todos os lutadores curados!",
        "ja": "全戦士回復！", "ko": "모든 전사 회복!", "zh": "全部战士已治疗！",
    },
    "revived_msg": {
        "en": "Revived {name}!", "ru": "{name} воскрешён!", "es": "¡{name} resucitado!",
        "de": "{name} wiederbelebt!", "fr": "{name} ressuscité!", "pt": "{name} revivido!",
        "ja": "{name}を復活！", "ko": "{name} 부활!", "zh": "{name}已复活！",
    },
    "no_dead_fighters": {
        "en": "No dead fighters to revive", "ru": "Нет погибших бойцов для воскрешения",
        "es": "Sin luchadores muertos para resucitar", "de": "Keine toten Kämpfer zum Wiederbeleben",
        "fr": "Aucun combattant mort à ressusciter", "pt": "Sem lutadores mortos para reviver",
        "ja": "復活対象の戦士なし", "ko": "부활할 전사 없음", "zh": "没有死亡战士可复活",
    },
    "war_drums": {
        "en": "War Drums active for 1 hour!", "ru": "Барабаны войны на 1 час!",
        "es": "¡Tambores de guerra activos 1 hora!", "de": "Kriegstrommeln aktiv für 1 Stunde!",
        "fr": "Tambours de guerre actifs 1 heure!", "pt": "Tambores de guerra ativos por 1 hora!",
        "ja": "ウォードラム1時間有効！", "ko": "전쟁 북 1시간 활성!", "zh": "战鼓激活1小时！",
    },
    "expedition_slots": {
        "en": "Expedition slots: {n}!", "ru": "Слоты походов: {n}!",
        "es": "¡Espacios de expedición: {n}!", "de": "Expedition-Slots: {n}!",
        "fr": "Places d'expédition: {n}!", "pt": "Vagas de expedição: {n}!",
        "ja": "遠征スロット: {n}！", "ko": "원정 슬롯: {n}!", "zh": "远征位: {n}！",
    },
    "golden_set_equipped": {
        "en": "Golden War Set equipped on {name}!", "ru": "Золотой боевой набор на {name}!",
        "es": "¡Set de Guerra Dorado equipado en {name}!", "de": "Goldenes Kriegsset auf {name} ausgerüstet!",
        "fr": "Set de Guerre Doré équipé sur {name}!", "pt": "Set de Guerra Dourado equipado em {name}!",
        "ja": "{name}に黄金戦セット装備！", "ko": "{name}에 황금 전쟁 세트 장착!", "zh": "{name}装备了黄金战争套装！",
    },
    "tier_advanced": {
        "en": "Advanced to tier {tier}!", "ru": "Продвижение до уровня {tier}!",
        "es": "¡Avanzado al nivel {tier}!", "de": "Zu Stufe {tier} aufgestiegen!",
        "fr": "Avancé au rang {tier}!", "pt": "Avançou para o nível {tier}!",
        "ja": "ティア{tier}に到達！", "ko": "티어 {tier}로 진급!", "zh": "升至阶级{tier}！",
    },
    "2x_gold_reward": {
        "en": "2x gold for 60 seconds!", "ru": "2x золото на 60 секунд!",
        "es": "¡2x oro por 60 segundos!", "de": "2x Gold für 60 Sekunden!",
        "fr": "2x or pendant 60 secondes!", "pt": "2x ouro por 60 segundos!",
        "ja": "60秒間ゴールド2倍！", "ko": "60초간 골드 2배!", "zh": "60秒双倍金币！",
    },
    "diamonds_earned": {
        "en": "+{n} diamonds!", "ru": "+{n} алмазов!", "es": "+{n} diamantes!",
        "de": "+{n} Diamanten!", "fr": "+{n} diamants!", "pt": "+{n} diamantes!",
        "ja": "+{n}ダイヤ！", "ko": "+{n} 다이아!", "zh": "+{n}钻石！",
    },

    # ---- Anvil / Forge active fighter info ----

    # ---- Shop consumable names/descriptions ----
    "blood_salve": {
        "en": "Blood Salve", "ru": "Кровяная мазь", "es": "Bálsamo de Sangre",
        "de": "Blutsalbe", "fr": "Baume de Sang", "pt": "Bálsamo de Sangue",
        "ja": "血の軟膏", "ko": "피의 연고", "zh": "血膏",
    },
    "blood_salve_desc": {
        "en": "Fully heal active fighter", "ru": "Полностью исцелить активного бойца",
        "es": "Cura completa del luchador activo", "de": "Aktiven Kämpfer voll heilen",
        "fr": "Soigne complètement le combattant actif", "pt": "Cura total do lutador ativo",
        "ja": "出撃中の戦士を全回復", "ko": "활성 전사 완전 회복", "zh": "完全治疗出战战士",
    },
    "fury_tonic": {
        "en": "Fury Tonic", "ru": "Тоник ярости", "es": "Tónico de Furia",
        "de": "Wuttrank", "fr": "Tonique de Fureur", "pt": "Tônico de Fúria",
        "ja": "憤怒の薬", "ko": "분노의 물약", "zh": "狂怒药剂",
    },
    "fury_tonic_desc": {
        "en": "+2 base STR to active fighter", "ru": "+2 СИЛ активному бойцу",
        "es": "+2 FUE base al luchador activo", "de": "+2 Basis-STR für aktiven Kämpfer",
        "fr": "+2 FOR de base au combattant actif", "pt": "+2 FOR base ao lutador ativo",
        "ja": "出撃中の戦士にSTR+2", "ko": "활성 전사 기본 STR +2", "zh": "出战战士基础力量+2",
    },
    "stone_brew": {
        "en": "Stone Brew", "ru": "Каменное зелье", "es": "Brebaje de Piedra",
        "de": "Steingebräu", "fr": "Breuvage de Pierre", "pt": "Poção de Pedra",
        "ja": "石の薬", "ko": "바위의 물약", "zh": "石酿药剂",
    },
    "stone_brew_desc": {
        "en": "+2 base VIT to active fighter", "ru": "+2 ЖИВ активному бойцу",
        "es": "+2 VIT base al luchador activo", "de": "+2 Basis-VIT für aktiven Kämpfer",
        "fr": "+2 VIT de base au combattant actif", "pt": "+2 VIT base ao lutador ativo",
        "ja": "出撃中の戦士にVIT+2", "ko": "활성 전사 기본 VIT +2", "zh": "出战战士基础体力+2",
    },
    "surgeon_kit": {
        "en": "Surgeon's Kit", "ru": "Набор хирурга", "es": "Kit de Cirujano",
        "de": "Chirurgenset", "fr": "Kit Chirurgical", "pt": "Kit Cirúrgico",
        "ja": "外科キット", "ko": "외과 도구", "zh": "外科工具包",
    },
    "surgeon_kit_desc": {
        "en": "Remove 1 injury (used {n}x)", "ru": "Вылечить 1 ранение (исп. {n}x)",
        "es": "Eliminar 1 herida (usado {n}x)", "de": "1 Verletzung heilen (benutzt {n}x)",
        "fr": "Soigner 1 blessure (utilisé {n}x)", "pt": "Curar 1 ferimento (usado {n}x)",
        "ja": "負傷1回復(使用{n}回)", "ko": "부상 1 치료 (사용 {n}회)", "zh": "治疗1次伤痕(已用{n}次)",
    },

    # ---- Misc ----
    "fighters_alive": {
        "en": "{n} fighters alive", "ru": "{n} бойцов в бою",
        "es": "{n} luchadores vivos", "de": "{n} Kämpfer leben",
        "fr": "{n} combattants en vie", "pt": "{n} lutadores vivos",
        "ja": "{n}人の戦士生存", "ko": "{n}명 전사 생존", "zh": "{n}名战士存活",
    },
    "enemies_left": {
        "en": "{n} enemies left", "ru": "{n} врагов осталось",
        "es": "{n} enemigos restantes", "de": "{n} Feinde übrig",
        "fr": "{n} ennemis restants", "pt": "{n} inimigos restantes",
        "ja": "残り{n}体の敵", "ko": "적 {n}명 남음", "zh": "剩余{n}个敌人",
    },

    # ---- UI buttons & labels (was hardcoded) ----
    "heal_all_injuries": {
        "en": "HEAL ALL INJURIES", "ru": "ВЫЛЕЧИТЬ ВСЕ ТРАВМЫ",
        "es": "CURAR TODAS LAS HERIDAS", "de": "ALLE VERLETZUNGEN HEILEN",
        "fr": "SOIGNER TOUTES LES BLESSURES", "pt": "CURAR TODOS OS FERIMENTOS",
        "ja": "全負傷を回復", "ko": "모든 부상 치료", "zh": "治疗所有伤痕",
    },
    "heal_all_injuries_cost": {
        "en": "HEAL ALL INJURIES ({cost})", "ru": "ВЫЛЕЧИТЬ ВСЕ ТРАВМЫ ({cost})",
        "es": "CURAR HERIDAS ({cost})", "de": "VERLETZUNGEN HEILEN ({cost})",
        "fr": "SOIGNER BLESSURES ({cost})", "pt": "CURAR FERIMENTOS ({cost})",
        "ja": "全負傷を回復 ({cost})", "ko": "모든 부상 치료 ({cost})", "zh": "治疗所有伤痕 ({cost})",
    },
    "heal_all": {
        "en": "HEAL ALL", "ru": "ВЫЛЕЧИТЬ ВСЕХ",
        "es": "CURAR TODOS", "de": "ALLE HEILEN",
        "fr": "TOUT SOIGNER", "pt": "CURAR TODOS",
        "ja": "全員回復", "ko": "모두 치료", "zh": "全部治疗",
    },
    "heal_all_cost": {
        "en": "HEAL ALL ({cost})", "ru": "ВЫЛЕЧИТЬ ВСЕХ ({cost})",
        "es": "CURAR TODOS ({cost})", "de": "ALLE HEILEN ({cost})",
        "fr": "TOUT SOIGNER ({cost})", "pt": "CURAR TODOS ({cost})",
        "ja": "全員回復 ({cost})", "ko": "모두 치료 ({cost})", "zh": "全部治疗 ({cost})",
    },
    "heal_btn": {
        "en": "HEAL", "ru": "ЛЕЧИТЬ",
        "es": "CURAR", "de": "HEILEN",
        "fr": "SOIGNER", "pt": "CURAR",
        "ja": "回復", "ko": "치료", "zh": "治疗",
    },
    "equip_btn": {
        "en": "EQUIP", "ru": "ЭКИПИРОВАТЬ",
        "es": "EQUIPAR", "de": "AUSRÜSTEN",
        "fr": "ÉQUIPER", "pt": "EQUIPAR",
        "ja": "装備", "ko": "장착", "zh": "装备",
    },
    "sell_btn": {
        "en": "SELL", "ru": "ПРОДАТЬ",
        "es": "VENDER", "de": "VERKAUFEN",
        "fr": "VENDRE", "pt": "VENDER",
        "ja": "売却", "ko": "판매", "zh": "出售",
    },
    "inventory_label": {
        "en": "INVENTORY", "ru": "ИНВЕНТАРЬ",
        "es": "INVENTARIO", "de": "INVENTAR",
        "fr": "INVENTAIRE", "pt": "INVENTÁRIO",
        "ja": "インベントリ", "ko": "인벤토리", "zh": "背包",
    },
    "inventory_count": {
        "en": "INVENTORY ({n})", "ru": "ИНВЕНТАРЬ ({n})",
        "es": "INVENTARIO ({n})", "de": "INVENTAR ({n})",
        "fr": "INVENTAIRE ({n})", "pt": "INVENTÁRIO ({n})",
        "ja": "インベントリ ({n})", "ko": "인벤토리 ({n})", "zh": "背包 ({n})",
    },
    "leaderboard_title": {
        "en": "LEADERBOARD", "ru": "РЕЙТИНГ",
        "es": "CLASIFICACIÓN", "de": "BESTENLISTE",
        "fr": "CLASSEMENT", "pt": "CLASSIFICAÇÃO",
        "ja": "リーダーボード", "ko": "리더보드", "zh": "排行榜",
    },
    "view_leaderboard": {
        "en": "VIEW LEADERBOARD", "ru": "ПОКАЗАТЬ РЕЙТИНГ",
        "es": "VER CLASIFICACIÓN", "de": "BESTENLISTE ANZEIGEN",
        "fr": "VOIR CLASSEMENT", "pt": "VER CLASSIFICAÇÃO",
        "ja": "リーダーボード表示", "ko": "리더보드 보기", "zh": "查看排行榜",
    },
    "total_wins": {
        "en": "Total Wins", "ru": "Всего побед",
        "es": "Victorias Totales", "de": "Siege Gesamt",
        "fr": "Victoires Totales", "pt": "Vitórias Totais",
        "ja": "総勝利数", "ko": "총 승리", "zh": "总胜利",
    },
    "current_tier": {
        "en": "Current Tier", "ru": "Текущий уровень",
        "es": "Nivel Actual", "de": "Aktuelle Stufe",
        "fr": "Niveau Actuel", "pt": "Nível Atual",
        "ja": "現在のティア", "ko": "현재 티어", "zh": "当前层级",
    },
    "best_tier": {
        "en": "Best Tier Reached", "ru": "Лучший уровень",
        "es": "Mejor Nivel", "de": "Beste Stufe",
        "fr": "Meilleur Niveau", "pt": "Melhor Nível",
        "ja": "最高ティア", "ko": "최고 티어", "zh": "最高层级",
    },
    "remove_ads_label": {
        "en": "Remove Ads", "ru": "Убрать рекламу",
        "es": "Quitar Anuncios", "de": "Werbung Entfernen",
        "fr": "Supprimer les Pubs", "pt": "Remover Anúncios",
        "ja": "広告を削除", "ko": "광고 제거", "zh": "移除广告",
    },
    "remove_ads_buy": {
        "en": "REMOVE ADS — $2", "ru": "УБРАТЬ РЕКЛАМУ — $2",
        "es": "QUITAR ANUNCIOS — $2", "de": "WERBUNG WEG — $2",
        "fr": "SUPPRIMER PUBS — $2", "pt": "REMOVER ANÚNCIOS — $2",
        "ja": "広告削除 — $2", "ko": "광고 제거 — $2", "zh": "移除广告 — $2",
    },
    "cloud_connected": {
        "en": "Connected!", "ru": "Подключено!",
        "es": "¡Conectado!", "de": "Verbunden!",
        "fr": "Connecté!", "pt": "Conectado!",
        "ja": "接続済み！", "ko": "연결됨!", "zh": "已连接！",
    },
    "cloud_failed": {
        "en": "Failed: {reason}", "ru": "Ошибка: {reason}",
        "es": "Error: {reason}", "de": "Fehler: {reason}",
        "fr": "Échec: {reason}", "pt": "Falha: {reason}",
        "ja": "失敗: {reason}", "ko": "실패: {reason}", "zh": "失败: {reason}",
    },
    "cloud_uploaded": {
        "en": "Saved to cloud!", "ru": "Сохранено в облако!",
        "es": "¡Guardado en la nube!", "de": "In Cloud gespeichert!",
        "fr": "Sauvegardé dans le cloud!", "pt": "Salvo na nuvem!",
        "ja": "クラウドに保存！", "ko": "클라우드에 저장!", "zh": "已保存到云端！",
    },
    "cloud_loaded": {
        "en": "Loaded from cloud!", "ru": "Загружено из облака!",
        "es": "¡Cargado desde la nube!", "de": "Aus Cloud geladen!",
        "fr": "Chargé depuis le cloud!", "pt": "Carregado da nuvem!",
        "ja": "クラウドから読込！", "ko": "클라우드에서 불러옴!", "zh": "已从云端加载！",
    },
    "no_expeditions_log": {
        "en": "No expeditions yet", "ru": "Пока нет экспедиций",
        "es": "Aún no hay expediciones", "de": "Noch keine Expeditionen",
        "fr": "Pas encore d'expéditions", "pt": "Sem expedições ainda",
        "ja": "遠征なし", "ko": "원정 없음", "zh": "暂无远征",
    },
    "recruit_fighter_btn": {
        "en": "+ RECRUIT FIGHTER", "ru": "+ НАНЯТЬ БОЙЦА",
        "es": "+ RECLUTAR LUCHADOR", "de": "+ KÄMPFER REKRUTIEREN",
        "fr": "+ RECRUTER COMBATTANT", "pt": "+ RECRUTAR LUTADOR",
        "ja": "+ 戦士を雇用", "ko": "+ 전사 고용", "zh": "+ 招募战士",
    },
    "train_btn": {
        "en": "TRAIN Lv.{lv} ({cost})", "ru": "ТРЕН. Ур.{lv} ({cost})",
        "es": "ENTRENAR Nv.{lv} ({cost})", "de": "TRAINING Lv.{lv} ({cost})",
        "fr": "ENTRAÎNER Nv.{lv} ({cost})", "pt": "TREINAR Nv.{lv} ({cost})",
        "ja": "訓練 Lv.{lv} ({cost})", "ko": "훈련 Lv.{lv} ({cost})", "zh": "训练 Lv.{lv} ({cost})",
    },
}


def set_language(lang_code):
    """Set current language. Falls back to 'en' if not supported."""
    global _current_lang
    _current_lang = lang_code if lang_code in ("en", "ru", "es", "de", "fr", "pt", "ja", "ko", "zh") else "en"


def get_language():
    return _current_lang


def t(key, **kwargs):
    """Get translated string by key, with optional format args."""
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


def detect_system_language():
    """Detect language from system locale."""
    # Android: try jnius first
    try:
        from kivy.utils import platform
        if platform == "android":
            try:
                from jnius import autoclass
                Locale = autoclass("java.util.Locale")
                lang = Locale.getDefault().getLanguage()
                if lang:
                    return lang
            except Exception:
                pass
            # Fallback: read system property
            try:
                import subprocess
                result = subprocess.check_output(
                    ["getprop", "persist.sys.locale"], timeout=2
                ).decode().strip()
                if result:
                    return result[:2]
            except Exception:
                pass
    except Exception:
        pass
    # Desktop
    try:
        lang = locale.getdefaultlocale()[0]
        if lang:
            return lang[:2]
    except Exception:
        pass
    return "en"


def init_language():
    """Auto-detect and set language."""
    lang = detect_system_language()
    print(f"[LOCALE] Detected language: {lang}")
    set_language(lang)
    return lang
    return lang
