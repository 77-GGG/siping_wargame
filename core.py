"""
核心游戏引擎：资源系统、Debuff/Buff、角色、战斗逻辑
"""
import random
import copy

# ── 常量 ──
CRIT_PER_INITIATIVE = 5  # 每点战略主动权 = 5% 暴击率
CRIT_MULTIPLIER = 1.5


# ── Buff / Debuff ──
class StatusEffect:
    def __init__(self, name, duration, effect_fn, description="", stackable=False, stacks=1):
        self.name = name
        self.duration = duration  # -1 = 永久
        self.effect_fn = effect_fn
        self.description = description
        self.stackable = stackable
        self.stacks = stacks

    def tick(self):
        if self.duration > 0:
            self.duration -= 1
        return self.duration != 0

    def copy(self):
        s = StatusEffect(self.name, self.duration, self.effect_fn,
                         self.description, self.stackable, self.stacks)
        return s


# ── 三层血条 ──
class ThreeLayerHP:
    def __init__(self, position, troops, command):
        self.position_max = position
        self.troops_max = troops
        self.command_max = command
        self.position = position
        self.troops = troops
        self.command = command

    def take_damage(self, amount, layer=None):
        """返回 (实际伤害, 击穿的层级列表)"""
        breached = []
        remaining = amount
        if layer == "troops":
            old = self.troops
            self.troops = max(0, self.troops - remaining)
            if old > 0 and self.troops == 0:
                breached.append("troops")
            return amount - max(0, remaining - old), breached
        if layer == "position":
            old = self.position
            self.position = max(0, self.position - remaining)
            if old > 0 and self.position == 0:
                breached.append("position")
            return amount - max(0, remaining - old), breached

        # 默认：阵地 → 兵力 → 指挥
        if self.position > 0:
            taken = min(self.position, remaining)
            self.position -= taken
            remaining -= taken
            if self.position == 0:
                breached.append("position")
        if remaining > 0 and self.troops > 0:
            taken = min(self.troops, remaining)
            self.troops -= taken
            remaining -= taken
            if self.troops == 0:
                breached.append("troops")
        if remaining > 0:
            self.command = max(0, self.command - remaining)
            if self.command == 0:
                breached.append("command")
        return amount - remaining, breached

    def heal(self, amount, layer="position"):
        if layer == "position":
            self.position = min(self.position_max, self.position + amount)
        elif layer == "troops":
            self.troops = min(self.troops_max, self.troops + amount)

    def is_alive(self):
        return self.command > 0

    def total(self):
        return self.position + self.troops + self.command

    def total_max(self):
        return self.position_max + self.troops_max + self.command_max


# ── 玩家 ──
class Player:
    def __init__(self, name, hp_layers, energy_base, flexibility, initiative):
        self.name = name
        self.hp = hp_layers
        self.energy_base = energy_base
        self.energy_bonus = 0  # 永久加成(土地改革等)
        self.energy_temp = 0   # 临时加成(荫蔽集结等，单回合)
        self.energy_cap_penalty = 0  # 上限惩罚
        self.energy = 0
        self.block = 0
        self.flexibility = flexibility
        self.initiative = initiative
        self.buffs = []
        self.debuffs = []
        self.deck = []
        self.draw_pile = []
        self.hand = []
        self.discard_pile = []
        self.exhaust_pile = []
        self.draw_bonus = 0       # 永久抽牌加成
        self.draw_temp = 0        # 临时抽牌加成
        self.cards_played_this_turn = []
        self.attacks_played_this_turn = 0
        self.skills_played_this_turn = 0
        self.next_attack_multiplier = 1.0
        self.damage_reduction = 0.0  # 0~1
        self.frontline = 0           # 防线值
        self.frontline_max = 0
        self.tazishan = 0            # 塔子山HP
        self.tazishan_max = 0
        self.negotiation_chips = 0   # 谈判筹码
        self.phase = 1
        self.can_retreat = False
        self.abilities_active = []   # 已激活的能力牌名
        self.south_front_active = False
        self.south_invested = False
        self.turn_count = 0

    def get_energy(self):
        base = self.energy_base + self.energy_bonus + self.energy_temp
        cap = max(1, 5 - self.energy_cap_penalty)
        return min(base, cap)

    def start_turn(self):
        self.turn_count += 1
        self.block = 0
        self.energy = self.get_energy()
        self.energy_temp = 0
        self.cards_played_this_turn = []
        self.attacks_played_this_turn = 0
        self.skills_played_this_turn = 0
        self.damage_reduction = 0.0
        # 防线自然衰减
        if self.frontline > 0:
            self.frontline = max(0, self.frontline - 2)
        # debuff tick
        self.debuffs = [d for d in self.debuffs if d.tick()]
        self.buffs = [b for b in self.buffs if b.tick()]
        # 能力牌每回合效果
        self._apply_permanent_effects()

    def _apply_permanent_effects(self):
        if "土地改革" in self.abilities_active:
            pass  # 通过 energy_bonus 处理
        if "建立根据地" in self.abilities_active:
            self.hp.heal(2, "position")
            if self.turn_count % 3 == 0:
                self.flexibility += 1
        if "以战取和" in self.abilities_active:
            self.negotiation_chips += 1

    def draw_cards(self, n):
        drawn = []
        for _ in range(n):
            if not self.draw_pile:
                if not self.discard_pile:
                    break
                self.draw_pile = self.discard_pile[:]
                random.shuffle(self.draw_pile)
                self.discard_pile = []
            if self.draw_pile:
                drawn.append(self.draw_pile.pop(0))
        self.hand.extend(drawn)
        return drawn

    def init_combat(self):
        self.draw_pile = self.deck[:]
        random.shuffle(self.draw_pile)
        self.hand = []
        self.discard_pile = []
        self.exhaust_pile = []
        self.block = 0
        self.cards_played_this_turn = []

    def get_damage_mult(self):
        m = 1.0
        for d in self.debuffs:
            if d.name == "士气低落":
                m *= 0.8
        for b in self.buffs:
            if b.name == "士气高昂":
                m *= 1.2
            if b.name == "运动战加成":
                pass  # 通过 flat bonus 处理
        return m

    def get_block_mult(self):
        m = 1.0
        for d in self.debuffs:
            if d.name == "士气低落":
                m *= 0.8
        for b in self.buffs:
            if b.name == "士气高昂":
                m *= 1.2
        return m

    def get_flat_attack_bonus(self):
        bonus = 0
        for b in self.buffs:
            if b.name == "运动战加成":
                bonus += 2
            if b.name == "蓄力":
                bonus += b.stacks * 4
        if "四平精神" in self.abilities_active:
            if self.hp.position < self.hp.position_max * 0.5:
                bonus += 4
        return bonus

    def consume_蓄力(self):
        self.buffs = [b for b in self.buffs if b.name != "蓄力"]

    def get_crit_chance(self):
        return min(25, self.initiative * CRIT_PER_INITIATIVE) / 100.0

    def try_crit(self, damage):
        if random.random() < self.get_crit_chance():
            return int(damage * CRIT_MULTIPLIER), True
        return damage, False

    def has_debuff(self, name):
        return any(d.name == name for d in self.debuffs)

    def has_buff(self, name):
        return any(b.name == name for b in self.buffs)

    def add_buff(self, name, duration, desc="", stacks=1):
        for b in self.buffs:
            if b.name == name and b.stackable:
                b.stacks += stacks
                return
        self.buffs.append(StatusEffect(name, duration, None, desc, stacks=stacks))

    def add_debuff(self, name, duration, desc=""):
        for d in self.debuffs:
            if d.name == name:
                d.duration = max(d.duration, duration)
                return
        self.debuffs.append(StatusEffect(name, duration, None, desc))

    def remove_buff(self, name):
        self.buffs = [b for b in self.buffs if b.name != name]


# ── 敌人 ──
class Enemy:
    def __init__(self, name, hp, attack, traits=None, description=""):
        self.name = name
        self.hp_max = hp
        self.hp = hp
        self.attack = attack
        self.base_attack = attack
        self.traits = traits or []
        self.description = description
        self.debuffs = []
        self.intent = "attack"  # attack / defend / charge
        self.intent_value = attack
        self.first_hit = True
        self.turn_count = 0
        self.global_attack_bonus = 0

    def get_attack(self):
        a = self.attack + self.global_attack_bonus
        for d in self.debuffs:
            if d.name == "力量降低":
                a -= d.stacks
            if d.name == "补给中断":
                a -= 4
        return max(0, a)

    def take_damage(self, amount):
        vuln_mult = 1.0
        for d in self.debuffs:
            if d.name == "暴露侧翼":
                vuln_mult = 1.3
        actual = int(amount * vuln_mult)
        self.hp = max(0, self.hp - actual)
        if self.first_hit and "缅甸老兵" in self.traits:
            self.attack += 2
            self.first_hit = False
        return actual

    def is_alive(self):
        return self.hp > 0

    def tick_debuffs(self):
        damage = 0
        for d in self.debuffs:
            if d.name == "断粮":
                damage += d.stacks
        self.debuffs = [d for d in self.debuffs if d.tick()]
        if damage > 0:
            self.hp = max(0, self.hp - damage)
        return damage

    def add_debuff(self, name, duration=-1, stacks=1):
        for d in self.debuffs:
            if d.name == name and d.stackable:
                d.stacks += stacks
                return
        self.debuffs.append(StatusEffect(name, duration, None, stackable=(name in ["断粮", "力量降低"]), stacks=stacks))

    def has_debuff(self, name):
        return any(d.name == name for d in self.debuffs)

    def decide_intent(self, turn):
        self.turn_count = turn
        self.intent = "attack"
        self.intent_value = self.get_attack()


# ── 战斗管理器 ──
class BattleManager:
    def __init__(self, player, enemies):
        self.player = player
        self.enemies = enemies
        self.turn = 0
        self.log = []
        self.phase = 1
        self.battle_over = False
        self.battle_result = None  # "victory" / "defeat" / "retreat"
        self.pending_events = []

    def add_log(self, msg):
        self.log.append(msg)

    def alive_enemies(self):
        return [e for e in self.enemies if e.is_alive()]

    def start_turn(self):
        self.turn += 1
        self.player.start_turn()
        draw_count = 5 + self.player.draw_bonus + self.player.draw_temp
        self.player.draw_temp = 0
        self.player.draw_cards(draw_count)
        for e in self.alive_enemies():
            e.decide_intent(self.turn)
        self.add_log(f"\n{'='*50}")
        self.add_log(f"══ 回合 {self.turn} 开始 ══")

    def play_card(self, card_index_or_card, target_enemy=None):
        if isinstance(card_index_or_card, int):
            if card_index_or_card >= len(self.player.hand):
                return False, "无效的卡牌索引"
            card = self.player.hand[card_index_or_card]
        else:
            card = card_index_or_card
            if card not in self.player.hand:
                return False, "手牌中没有这张牌"

        if card.cost > self.player.energy:
            return False, "能量不足"

        self.player.energy -= card.cost
        self.player.hand.remove(card)
        result = card.play(self.player, self.alive_enemies(), target_enemy, self)
        self.player.cards_played_this_turn.append(card)
        if card.card_type == "攻击":
            self.player.attacks_played_this_turn += 1
        elif card.card_type == "技能":
            self.player.skills_played_this_turn += 1

        if card.card_type == "能力":
            self.player.exhaust_pile.append(card)
        elif card.exhaust:
            self.player.exhaust_pile.append(card)
        else:
            self.player.discard_pile.append(card)

        self.add_log(f"  打出【{card.name}】({card.card_type}/{card.cost}费) → {result}")

        # 拥政爱民检查
        if card.card_type == "技能" and "拥政爱民" in self.player.abilities_active:
            bonus_block = int(2 * self.player.get_block_mult())
            self.player.block += bonus_block
            self.add_log(f"    拥政爱民触发：+{bonus_block}格挡")

        # 人民战争检查
        if "人民战争" in self.player.abilities_active:
            threshold = 3
            if len(self.player.cards_played_this_turn) == threshold:
                dmg = int(3 * self.player.get_damage_mult())
                blk = int(4 * self.player.get_block_mult())
                self.player.block += blk
                enemies = self.alive_enemies()
                if enemies:
                    t = random.choice(enemies)
                    t.take_damage(dmg)
                    self.add_log(f"    人民战争触发：+{blk}格挡，{t.name}受{dmg}伤害")

        # 检查击杀
        for e in self.enemies:
            if not e.is_alive() and e.hp == 0:
                self.player.initiative = min(self.player.initiative + 1, 7)
                e.hp = -1  # 标记已处理
                self.add_log(f"    ☠ {e.name} 被消灭！战略主动权+1→{self.player.initiative}")

        return True, result

    def enemy_phase(self):
        self.add_log("  ─ 敌方行动 ─")
        for e in self.alive_enemies():
            atk = e.get_attack()
            if e.intent == "defend":
                self.add_log(f"  {e.name} 采取防御姿态")
                continue

            # 飞机坦克穿透
            if "飞机坦克" in e.traits:
                pen = 4
                _, breached = self.player.hp.take_damage(pen, layer="troops")
                self.add_log(f"  {e.name} 飞机坦克穿透：兵力-{pen}")

            # 判断攻击目标
            if self.player.tazishan > 0 and "五大主力" in e.traits:
                # 攻击塔子山
                actual = atk
                self.player.tazishan = max(0, self.player.tazishan - actual)
                self.add_log(f"  {e.name} 攻击塔子山：{actual}伤害 → 塔子山HP: {self.player.tazishan}")
                if self.player.tazishan == 0:
                    self.add_log("  ⚠⚠ 塔子山陷落！全体敌人攻+3，施加士气低落")
                    for ae in self.alive_enemies():
                        ae.global_attack_bonus += 3
                    self.player.add_debuff("士气低落", 3, "所有牌效果-20%")
                # 急行军：首回合攻击两次
                if "急行军" in e.traits and e.turn_count <= 1:
                    actual2 = atk
                    self.player.tazishan = max(0, self.player.tazishan - actual2)
                    self.add_log(f"  {e.name} 急行军二次攻击：{actual2}伤害 → 塔子山HP: {self.player.tazishan}")
                    if self.player.tazishan == 0:
                        self.add_log("  ⚠⚠ 塔子山陷落！")
                        for ae in self.alive_enemies():
                            ae.global_attack_bonus += 3
                        self.player.add_debuff("士气低落", 3)
            elif self.player.frontline > 0:
                # 攻击防线
                actual = atk
                if self.player.damage_reduction > 0:
                    actual = int(actual * (1 - self.player.damage_reduction))
                self.player.frontline = max(0, self.player.frontline - actual)
                self.add_log(f"  {e.name} 攻击防线：{actual}伤害 → 防线: {self.player.frontline}")
            else:
                # 攻击玩家HP
                actual = atk
                if self.player.damage_reduction > 0:
                    actual = int(actual * (1 - self.player.damage_reduction))
                if self.player.block > 0:
                    absorbed = min(self.player.block, actual)
                    self.player.block -= absorbed
                    actual -= absorbed
                if actual > 0:
                    _, breached = self.player.hp.take_damage(actual)
                    for layer in breached:
                        if layer == "position":
                            self.player.add_debuff("失去阵地", -1, "灵活度-1，能量-1/回合")
                        elif layer == "troops":
                            self.player.add_debuff("兵力枯竭", -1, "攻击伤害减半")
                self.add_log(f"  {e.name} 攻击：{atk}伤 → 格挡剩{self.player.block}，阵地{self.player.hp.position}，兵力{self.player.hp.troops}")

        # 断粮结算
        for e in self.alive_enemies():
            dmg = e.tick_debuffs()
            if dmg > 0:
                self.add_log(f"  {e.name} 断粮伤害：{dmg} → HP: {e.hp}")

    def check_battle_end(self):
        if not self.player.hp.is_alive():
            self.battle_over = True
            self.battle_result = "defeat"
            return True
        if self.battle_result == "retreat":
            self.battle_over = True
            return True
        return False

    def get_state_summary(self):
        p = self.player
        lines = []
        lines.append(f"阵地:{p.hp.position}/{p.hp.position_max} 兵力:{p.hp.troops}/{p.hp.troops_max} 指挥:{p.hp.command}/{p.hp.command_max}")
        lines.append(f"格挡:{p.block} 能量:{p.energy}/{p.get_energy()} 灵活度:{p.flexibility} 主动权:{p.initiative}")
        if p.frontline_max > 0:
            lines.append(f"防线:{p.frontline}/{p.frontline_max}")
        if p.tazishan_max > 0:
            lines.append(f"塔子山:{p.tazishan}/{p.tazishan_max}")
        if p.buffs:
            lines.append(f"Buff: {', '.join(b.name for b in p.buffs)}")
        if p.debuffs:
            lines.append(f"Debuff: {', '.join(d.name for d in p.debuffs)}")
        return '\n'.join(lines)
