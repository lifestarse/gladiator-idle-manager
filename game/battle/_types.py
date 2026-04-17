# Build: 1
"""Battle type definitions (enums, state dataclasses)."""
from ._shared import *  # noqa: F401,F403


class BattlePhase(Enum):
    IDLE = auto()
    STARTING = auto()
    TURN_PLAYER = auto()
    TURN_ENEMY = auto()
    TURN_RESOLVE = auto()
    VICTORY = auto()
    DEFEAT = auto()
    BOSS_INTRO = auto()


class BattleEvent:
    """Single event in the battle log (for animation)."""
    def __init__(self, event_type, attacker="", defender="", damage=0,
                 message="", is_kill=False, is_crit=False, is_boss=False,
                 is_dodge=False, skill_type=""):
        self.event_type = event_type
        self.attacker = attacker
        self.defender = defender
        self.damage = damage
        self.message = message
        self.is_kill = is_kill
        self.is_crit = is_crit
        self.is_boss = is_boss
        self.is_dodge = is_dodge
        # For event_type=="skill" only: which skill type fired. Used by
        # _skill_activation_phase to collapse identical skill activations
        # from many fighters in one turn into a single summary event —
        # otherwise 1000 fighters all rallying on turn 1 emits 1000
        # near-identical lines and buries actual combat events under them.
        self.skill_type = skill_type


class EnemyStatusTracker:
    """Tracks status effect state for a single enemy during battle."""
    def __init__(self, original_attack, original_defense=0):
        self.status_buildup = {}  # dynamic: populated on first hit per enchantment
        self.active_effects = []  # list of active status effect dicts
        self.original_attack = original_attack
        self.original_defense = original_defense
        self.skip_next_turn = False  # paralyze flag
        self.modifier_state = {}    # boss modifier per-fight state


class SkillState:
    """Tracks per-fighter active skill cooldown and transient flags for one battle."""
    def __init__(self, skill_def):
        self.skill_def = skill_def
        self.cooldown_remaining = 0       # 0 = ready to fire
        self.guaranteed_crit = False      # Shadowstep: force next crit
        self.dodge_next_attack = False    # Shadowstep: auto-dodge next hit
        self.extra_attacks = 0            # Frenzy: remaining bonus swings this turn
        self.extra_attack_mult = 1.0      # Frenzy: damage multiplier for bonus swings


class BattleState:
    """Tracks state of an ongoing battle."""

    def __init__(self):
        self.phase = BattlePhase.IDLE
        self.turn_number = 0
        self.player_fighters = []
        self.current_fighter_idx = 0
        self.enemies = []
        self.current_enemy_idx = 0
        self.events = []
        self.is_boss_fight = False
        self.boss_defeated = False
        self.all_defeated = False
        self.gold_earned = 0
        self.skip_mode = False
        self.enemy_status: dict = {}
        # Active skill system
        self.skill_states: dict = {}    # id(fighter) -> SkillState
        self.team_buffs: list = []      # active team-wide buffs [{type, value, turns_left}]
        # Lazy snapshot of fighter combat stats (attack/defense/max_hp/crit/
        # dodge/crit_mult/damage_reduction) keyed by id(fighter). Fighter
        # stats are the result of heavy property chains (equipment loops +
        # perk lookups); they're invariant during a battle except when an
        # injury is added via handle_fighter_death, which invalidates the
        # entry. Biggest win is in boss fights: same 1000 fighters attack
        # the same boss for 40+ turns, previously recomputing stats every
        # single attack.
        self.fighter_stat_cache: dict = {}
        # Scalar running total of team atk_bonus_pct. Previously recomputed
        # via sum(genexpr) on every single player attack — in a 1000-fighter
        # battle where every merc rallies, that's 1M iterations/turn burning
        # ~50% of battle CPU. Maintained incrementally by _execute_skill
        # (buff add) and _tick_skill_buffs (expiry).
        self.team_atk_bonus_pct: float = 0.0
        self.team_shield = None         # Shield Wall: {reduction_pct, turns_left} or None
        self.enemy_stuns: dict = {}     # id(enemy) -> stun_turns_remaining

    @property
    def current_fighter(self):
        if 0 <= self.current_fighter_idx < len(self.player_fighters):
            f = self.player_fighters[self.current_fighter_idx]
            if f.alive and f.hp > 0:
                return f
        return None

    @property
    def current_enemy(self):
        if 0 <= self.current_enemy_idx < len(self.enemies):
            e = self.enemies[self.current_enemy_idx]
            if e.hp > 0:
                return e
        return None

    def next_alive_fighter(self):
        for i in range(len(self.player_fighters)):
            idx = (self.current_fighter_idx + 1 + i) % len(self.player_fighters)
            f = self.player_fighters[idx]
            if f.alive and f.hp > 0:
                self.current_fighter_idx = idx
                return True
        return False

    def next_alive_enemy(self):
        for i in range(len(self.enemies)):
            idx = (self.current_enemy_idx + 1 + i) % len(self.enemies)
            if self.enemies[idx].hp > 0:
                self.current_enemy_idx = idx
                return True
        return False

    def any_fighters_alive(self):
        return any(f.alive and f.hp > 0 for f in self.player_fighters)

    def any_enemies_alive(self):
        return any(e.hp > 0 for e in self.enemies)
