"""
四平保卫战场景：三阶段Boss战 + 史实自动演示脚本
"""
import random
from core import Player, Enemy, ThreeLayerHP, BattleManager
from cards import create_siping_deck, create_all_cards, Card


# ── 敌人工厂 ──

def create_phase1_enemies():
    """阶段一：运动防御（回合1-4），两个敌人"""
    return [
        Enemy("新一军先头部队", 45, 7,
              traits=["缅甸老兵"],
              description="新一军先锋，首次被攻击后攻+2"),
        Enemy("七十一军侧翼", 30, 5,
              traits=[],
              description="从侧翼进攻的国军"),
    ]


def create_phase2_enemies():
    """阶段二：城防对峙（回合5-12），增兵时间轴"""
    return [
        Enemy("新一军主力", 60, 9,
              traits=["缅甸老兵", "飞机坦克"],
              description="孙立人新一军，精锐装备美械"),
        Enemy("七十一军主力", 40, 7,
              traits=[],
              description="陈明仁七十一军"),
    ]


def create_phase2_reinforcements():
    """阶段二增援时间轴"""
    return {
        6: Enemy("新六军前锋", 35, 8,
                 traits=["急行军"],
                 description="廖耀湘新六军先头团，急行军首回合攻两次"),
        8: Enemy("第52军", 30, 6,
                 traits=[],
                 description="赵公武第52军增援"),
    }


def create_phase3_boss():
    """阶段三：塔子山危机（回合10+）"""
    return Enemy("新六军(廖耀湘)", 60, 14,
                 traits=["五大主力", "急行军", "飞机坦克"],
                 description="国军五大主力之一，全力进攻塔子山")


# ── 政治事件 ──

POLITICAL_EVENTS = [
    {"turn": 3, "name": "马歇尔调停",
     "desc": "美国特使马歇尔要求双方停火",
     "effect": lambda p, enemies: _marshall_effect(p, enemies)},
    {"turn": 6, "name": "东北局紧急电报",
     "desc": "\"必须死守四平，寸土必争！\"",
     "effect": lambda p, enemies: _hq_order(p)},
    {"turn": 9, "name": "本溪失守",
     "desc": "南线本溪被攻占，敌军可抽调兵力北上",
     "effect": lambda p, enemies: _benxi_fall(p, enemies)},
]


def _marshall_effect(p, enemies):
    for e in enemies:
        e.attack = max(1, e.attack - 2)
    return "马歇尔调停：全体敌人攻-2本回合"


def _hq_order(p):
    p.add_buff("死守命令", 3, "攻+3格挡+3")
    p.block += 5
    return "东北局命令：获得3回合攻/格挡+3，立即+5格挡"


def _benxi_fall(p, enemies):
    reinforcement = Enemy("南线增援营", 25, 6, description="从本溪抽调的国军")
    enemies.append(reinforcement)
    return "本溪失守！敌军增援1个营(HP25/攻6)"


# ── 场景创建 ──

def create_player_leitong():
    """雷霆（先锋型）"""
    hp = ThreeLayerHP(40, 50, 20)
    p = Player("雷霆", hp, 3, flexibility=2, initiative=3)
    p.deck = create_siping_deck()
    return p


def create_player_panshi():
    """磐石（基石型）"""
    hp = ThreeLayerHP(60, 50, 25)
    p = Player("磐石", hp, 3, flexibility=1, initiative=1)
    p.deck = create_siping_deck()
    return p


class SipingBattle:
    """四平保卫战完整场景管理器"""

    def __init__(self, player):
        self.player = player
        self.phase = 1
        self.turn = 0
        self.enemies = create_phase1_enemies()
        self.reinforcements = create_phase2_reinforcements()
        self.phase3_triggered = False
        self.events_triggered = set()
        self.battle = BattleManager(player, self.enemies)
        self.all_logs = []
        self.game_over = False
        self.result = None

        # 四平特殊设置
        self.player.frontline = 0
        self.player.frontline_max = 0
        self.player.tazishan = 0
        self.player.tazishan_max = 0

    def setup_phase(self, phase_num):
        """切换阶段"""
        self.phase = phase_num
        if phase_num == 2:
            self.log("═" * 50)
            self.log("【第二阶段：城防对峙】")
            self.log("四平城防线建立，敌军持续增兵...")
            self.enemies = create_phase2_enemies()
            self.player.frontline = 40
            self.player.frontline_max = 40
            self.player.phase = 2
            self.battle = BattleManager(self.player, self.enemies)

        elif phase_num == 3:
            self.log("═" * 50)
            self.log("【第三阶段：塔子山危机】")
            self.log("新六军主力直扑塔子山！")
            boss = create_phase3_boss()
            self.enemies.append(boss)
            self.player.tazishan = 20
            self.player.tazishan_max = 20
            self.player.phase = 3
            self.player.can_retreat = True
            self.battle.enemies = self.enemies

    def log(self, msg):
        self.all_logs.append(msg)

    def check_phase_transition(self):
        """检查是否需要切换阶段"""
        if self.phase == 1 and self.turn >= 5:
            self.setup_phase(2)
            return True
        if self.phase == 2 and self.turn >= 10 and not self.phase3_triggered:
            self.phase3_triggered = True
            self.setup_phase(3)
            return True
        return False

    def check_reinforcements(self):
        """检查增援"""
        if self.turn in self.reinforcements and self.phase >= 2:
            r = self.reinforcements[self.turn]
            self.enemies.append(r)
            self.battle.enemies = self.enemies
            self.log(f"⚠ 增援抵达：{r.name}(HP{r.hp}/攻{r.attack}) — {r.description}")
            del self.reinforcements[self.turn]

    def check_events(self):
        """检查政治事件"""
        for evt in POLITICAL_EVENTS:
            if evt["turn"] == self.turn and evt["name"] not in self.events_triggered:
                self.events_triggered.add(evt["name"])
                result = evt["effect"](self.player, self.enemies)
                self.log(f"📜 政治事件：{evt['name']}")
                self.log(f"   {evt['desc']}")
                self.log(f"   效果：{result}")

    def start_turn(self):
        """开始新回合"""
        self.turn += 1
        self.check_phase_transition()
        self.check_reinforcements()
        self.check_events()
        self.battle.turn = self.turn
        self.battle.start_turn()
        # 合并日志
        self.all_logs.extend(self.battle.log)
        self.battle.log = []

    def play_card(self, card_idx_or_card, target=None):
        """打出卡牌"""
        ok, result = self.battle.play_card(card_idx_or_card, target)
        self.all_logs.extend(self.battle.log)
        self.battle.log = []
        return ok, result

    def end_turn(self):
        """结束回合（敌方行动）"""
        # 自力更生结算
        if "自力更生" in self.player.abilities_active:
            spare = self.player.energy
            if spare > 0:
                self.player.block += spare
                self.log(f"  自力更生：{spare}未用能量→{spare}格挡")

        self.battle.enemy_phase()
        self.all_logs.extend(self.battle.log)
        self.battle.log = []

        # 化四平为马德里回合末惩罚
        if self.player.has_buff("马德里精神"):
            self.player.hp.take_damage(10)
            self.player.remove_buff("马德里精神")
            self.log("  马德里精神消退：-10HP")

        # 弃牌
        self.player.discard_pile.extend(self.player.hand)
        self.player.hand = []

        # 检查结局
        if self.battle.check_battle_end():
            self.game_over = True
            self.result = self.battle.battle_result

        # 存活敌人清理
        self.enemies = [e for e in self.enemies if e.is_alive() or e.hp == -1]
        self.enemies = [e for e in self.enemies if e.hp != -1]
        self.battle.enemies = self.enemies

        if not self.enemies and self.phase >= 3:
            self.game_over = True
            self.result = "victory"
        elif not self.player.hp.is_alive():
            self.game_over = True
            self.result = "defeat"

    def get_recent_logs(self, n=20):
        return self.all_logs[-n:]

    def get_status(self):
        """获取当前状态文本"""
        p = self.player
        lines = [
            f"{'═' * 50}",
            f"  阶段{self.phase} | 回合{self.turn}",
            f"  阵地:{p.hp.position}/{p.hp.position_max}  兵力:{p.hp.troops}/{p.hp.troops_max}  指挥:{p.hp.command}/{p.hp.command_max}",
            f"  能量:{p.energy}/{p.get_energy()}  格挡:{p.block}  灵活度:{p.flexibility}  主动权:{p.initiative}",
        ]
        if p.frontline_max > 0:
            lines.append(f"  防线:{p.frontline}/{p.frontline_max}")
        if p.tazishan_max > 0:
            lines.append(f"  塔子山:{p.tazishan}/{p.tazishan_max}")
        if p.buffs:
            lines.append(f"  Buff: {', '.join(b.name for b in p.buffs)}")
        if p.debuffs:
            lines.append(f"  Debuff: {', '.join(d.name for d in p.debuffs)}")
        lines.append(f"  {'─' * 46}")
        for i, e in enumerate(self.enemies):
            if e.is_alive():
                debuffs = f" [{','.join(d.name for d in e.debuffs)}]" if e.debuffs else ""
                lines.append(f"  敌{i+1}. {e.name} HP:{e.hp}/{e.hp_max} 攻:{e.get_attack()}{debuffs}")
        return "\n".join(lines)


# ══════════════════════════════════════
#  自动演示脚本（史实模式）
# ══════════════════════════════════════

class AutoPlayScript:
    """按史实自动出牌的脚本"""

    def __init__(self, scenario):
        self.s = scenario

    def pick_cards(self):
        """AI选牌逻辑：根据阶段和局势自动选择"""
        p = self.s.player
        hand = p.hand[:]
        plays = []
        energy = p.energy

        # 阶段1：优先进攻
        if self.s.phase == 1:
            plays = self._aggressive_pick(hand, energy)
        # 阶段2：攻守平衡
        elif self.s.phase == 2:
            plays = self._balanced_pick(hand, energy)
        # 阶段3：防御优先
        else:
            plays = self._defensive_pick(hand, energy)

        return plays

    def _aggressive_pick(self, hand, energy):
        """进攻优先策略"""
        picks = []
        # 先出能力牌
        for c in hand[:]:
            if c.card_type == "能力" and c.cost <= energy:
                picks.append(c)
                energy -= c.cost
                hand.remove(c)
        # 出0费牌
        for c in hand[:]:
            if c.cost == 0 and energy >= 0:
                picks.append(c)
                hand.remove(c)
        # 出攻击牌
        for c in sorted([c for c in hand if c.card_type == "攻击"], key=lambda x: x.cost):
            if c.cost <= energy:
                picks.append(c)
                energy -= c.cost
                hand.remove(c)
        # 剩余能量出技能牌
        for c in sorted([c for c in hand if c.card_type == "技能"], key=lambda x: x.cost):
            if c.cost <= energy:
                picks.append(c)
                energy -= c.cost
                hand.remove(c)
        return picks

    def _balanced_pick(self, hand, energy):
        """攻守平衡策略"""
        picks = []
        # 能力牌
        for c in hand[:]:
            if c.card_type == "能力" and c.cost <= energy:
                picks.append(c)
                energy -= c.cost
                hand.remove(c)
        # 0费牌
        for c in hand[:]:
            if c.cost == 0:
                picks.append(c)
                hand.remove(c)
        # 交替出攻击和技能
        attacks = sorted([c for c in hand if c.card_type == "攻击"], key=lambda x: -x.cost)
        skills = sorted([c for c in hand if c.card_type == "技能"], key=lambda x: -x.cost)
        while energy > 0 and (attacks or skills):
            if skills and (not attacks or len(picks) % 2 == 0):
                c = skills.pop(0)
                if c.cost <= energy:
                    picks.append(c)
                    energy -= c.cost
                else:
                    skills.insert(0, c)
                    if attacks:
                        c = attacks.pop(0)
                        if c.cost <= energy:
                            picks.append(c)
                            energy -= c.cost
                    else:
                        break
            elif attacks:
                c = attacks.pop(0)
                if c.cost <= energy:
                    picks.append(c)
                    energy -= c.cost
                else:
                    attacks.insert(0, c)
                    break
            else:
                break
        return picks

    def _defensive_pick(self, hand, energy):
        """防御优先策略"""
        picks = []
        # 能力牌
        for c in hand[:]:
            if c.card_type == "能力" and c.cost <= energy:
                picks.append(c)
                energy -= c.cost
                hand.remove(c)
        # 0费牌
        for c in hand[:]:
            if c.cost == 0:
                picks.append(c)
                hand.remove(c)
        # 优先技能（防御）
        for c in sorted([c for c in hand if c.card_type == "技能"], key=lambda x: -x.cost):
            if c.cost <= energy:
                picks.append(c)
                energy -= c.cost
                hand.remove(c)
        # 剩余出攻击
        for c in sorted([c for c in hand if c.card_type == "攻击"], key=lambda x: x.cost):
            if c.cost <= energy:
                picks.append(c)
                energy -= c.cost
                hand.remove(c)
        return picks

    def pick_target(self, enemies):
        """选择目标：优先低HP"""
        alive = [e for e in enemies if e.is_alive()]
        if not alive:
            return None
        return min(alive, key=lambda e: e.hp)

    def should_retreat(self):
        """判断是否应该撤退"""
        p = self.s.player
        if not p.can_retreat:
            return False
        if self.s.turn >= 12:
            return True
        if p.hp.command <= 5:
            return True
        if p.hp.troops <= 10 and self.s.turn >= 10:
            return True
        return False
