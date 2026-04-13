"""
卡牌定义：攻击牌11张 + 技能牌11张 + 能力牌8张 + 战役专属10张
"""
import random


class Card:
    def __init__(self, name, cost, card_type, description, play_fn, exhaust=False, tags=None):
        self.name = name
        self.cost = cost
        self.card_type = card_type  # "攻击" / "技能" / "能力"
        self.description = description
        self.play_fn = play_fn
        self.exhaust = exhaust
        self.tags = tags or []

    def play(self, player, enemies, target, battle):
        return self.play_fn(player, enemies, target, battle)

    def copy(self):
        return Card(self.name, self.cost, self.card_type, self.description,
                    self.play_fn, self.exhaust, self.tags[:])

    def __repr__(self):
        return f"[{self.name}|{self.card_type}{self.cost}费] {self.description}"

    def short(self):
        return f"{self.name}({self.cost}费)"


# ══════════════════════════════════════
#  攻击牌 (11张)
# ══════════════════════════════════════

def _集中兵力(p, enemies, target, battle):
    base = 8
    bonus = 5 if p.attacks_played_this_turn > 0 else 0
    dmg = int((base + bonus + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    t = target or (enemies[0] if enemies else None)
    if t:
        actual = t.take_damage(dmg)
        return f"{'暴击！' if crit else ''}{t.name}受{actual}伤害" + (f"(连击+{bonus})" if bonus else "")
    return "无目标"

def _各个击破(p, enemies, target, battle):
    if not enemies:
        return "无目标"
    weakest = min(enemies, key=lambda e: e.hp)
    main_dmg = int((18 + p.get_flat_attack_bonus()) * p.get_damage_mult())
    main_dmg, crit = p.try_crit(main_dmg)
    actual_main = weakest.take_damage(main_dmg)
    splash = int(6 * p.get_damage_mult())
    splash_total = 0
    for e in enemies:
        if e is not weakest and e.is_alive():
            splash_total += e.take_damage(splash)
    return f"{'暴击！' if crit else ''}{weakest.name}受{actual_main}，其余共{splash_total}"

def _反复肉搏(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    hits = 4
    total = 0
    for _ in range(hits):
        dmg = int((5 + p.get_flat_attack_bonus()) * p.get_damage_mult())
        actual = t.take_damage(dmg)
        total += actual
    return f"{t.name}受{hits}×伤害，共{total}"

def _夜战突袭(p, enemies, target, battle):
    base = 9
    double = p.attacks_played_this_turn == 0 and p.turn_count > 1
    if double:
        base *= 2
    dmg = int((base + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    t = target or (enemies[0] if enemies else None)
    if t:
        actual = t.take_damage(dmg)
        return f"{'暴击！' if crit else ''}{'夜袭翻倍！' if double else ''}{t.name}受{actual}伤害"
    return "无目标"

def _侧翼包抄(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    dmg = int((7 + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    actual = t.take_damage(dmg)
    t.add_debuff("暴露侧翼", 2)
    return f"{'暴击！' if crit else ''}{t.name}受{actual}伤害+暴露侧翼(受伤+30%)"

def _奇袭夺城(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    dmg = int((6 + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    actual = t.take_damage(dmg)
    drawn = ""
    if len(p.cards_played_this_turn) == 0:
        cards = p.draw_cards(2)
        drawn = f"，抽{len(cards)}牌"
    return f"{'暴击！' if crit else ''}{t.name}受{actual}伤害{drawn}"

def _围点打援(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    dmg = int((10 + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    actual = t.take_damage(dmg)
    t.add_debuff("围困", 2)
    aid_dmg = 0
    for e in enemies:
        if e is not t and e.is_alive():
            ad = int(8 * p.get_damage_mult())
            aid_dmg += e.take_damage(ad)
    return f"{'暴击！' if crit else ''}{t.name}受{actual}+围困，援敌共{aid_dmg}"

def _南线牵制(p, enemies, target, battle):
    total = 0
    for e in enemies:
        if e.is_alive():
            dmg = int(5 * p.get_damage_mult())
            total += e.take_damage(dmg)
    if enemies:
        stunned = random.choice([e for e in enemies if e.is_alive()] or [None])
        if stunned:
            stunned.add_debuff("牵制", 1)
    return f"全体共{total}伤害+随机1敌被牵制"

def _破袭游击(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    dmg = int((5 + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    actual = t.take_damage(dmg)
    t.add_debuff("力量降低", -1, stacks=2)
    return f"{'暴击！' if crit else ''}{t.name}受{actual}伤害+永久攻-2"

def _力战不退(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    dmg = int((13 + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    actual = t.take_damage(dmg)
    p.block += 8
    return f"{'暴击！' if crit else ''}{t.name}受{actual}伤害+获得8格挡"

def _全军出击(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    dmg = int((28 + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    actual = t.take_damage(dmg)
    # 本回合不能再出牌：将能量清零
    p.energy = 0
    return f"{'暴击！' if crit else ''}全军出击！{t.name}受{actual}伤害！本回合结束"


# ══════════════════════════════════════
#  技能牌 (11张)
# ══════════════════════════════════════

def _战略后撤(p, enemies, target, battle):
    blk = int(11 * p.get_block_mult())
    p.block += blk
    drawn = p.draw_cards(2)
    return f"+{blk}格挡，抽{len(drawn)}牌"

def _破敌交通(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    t.add_debuff("补给中断", 2)
    t.add_debuff("断粮", -1, stacks=3)
    return f"{t.name}攻-4持续2回合+3层断粮(每层1伤/回合)"

def _诱敌深入(p, enemies, target, battle):
    p.damage_reduction = 0.75
    p.next_attack_multiplier = 2.0
    return "本回合受伤-75%，下回合首攻翻倍"

def _整军经武(p, enemies, target, battle):
    blk = int(6 * p.get_block_mult())
    p.block += blk
    p.add_buff("整军经武", 1, "每出攻击牌+3格挡")
    return f"+{blk}格挡+每出攻击牌额外+3格挡"

def _坚守阵地(p, enemies, target, battle):
    blk = int(20 * p.get_block_mult())
    p.block += blk
    return f"+{blk}格挡(保留至下回合)"

def _运动防御(p, enemies, target, battle):
    hp_ratio = p.hp.total() / p.hp.total_max()
    base = 16 if hp_ratio < 0.5 else 7
    blk = int(base * p.get_block_mult())
    p.block += blk
    return f"+{blk}格挡" + ("(低血触发!)" if hp_ratio < 0.5 else "")

def _构筑工事(p, enemies, target, battle):
    blk = int(9 * p.get_block_mult())
    p.block += blk
    p.add_buff("工事加固", 1, "下回合+6格挡")
    return f"+{blk}格挡+下回合+6格挡"

def _荫蔽集结(p, enemies, target, battle):
    drawn = p.draw_cards(3)
    p.energy_temp += 1
    return f"抽{len(drawn)}牌+下回合+1能量"

def _养精蓄锐(p, enemies, target, battle):
    p.add_buff("蓄力", -1, "每层下次攻击+5", stacks=3)
    return "获得3层蓄力(每层下次攻击+5)"

def _战场侦察(p, enemies, target, battle):
    # 简化：抽2牌 + 显示敌意图
    drawn = p.draw_cards(2)
    intents = ", ".join(f"{e.name}意图:{e.intent}({e.intent_value})" for e in enemies if e.is_alive())
    return f"抽{len(drawn)}牌，侦察: {intents}"

def _统筹全局(p, enemies, target, battle):
    p.energy += 3
    if p.hand:
        cheapest = min(p.hand, key=lambda c: c.cost)
        cheapest.cost = 0
    return f"能量+3，最低费手牌费用归0"


# ══════════════════════════════════════
#  能力牌 (8张) — 打出后永久生效，消耗
# ══════════════════════════════════════

def _土地改革(p, enemies, target, battle):
    p.energy_bonus += 1
    p.abilities_active.append("土地改革")
    return "永久每回合+1能量"

def _人民战争(p, enemies, target, battle):
    p.abilities_active.append("人民战争")
    return "永久：每回合出≥3牌→+4格挡+3伤害"

def _灵活应变(p, enemies, target, battle):
    p.abilities_active.append("灵活应变")
    return "永久：每回合可转换1手牌"

def _建立根据地(p, enemies, target, battle):
    p.abilities_active.append("建立根据地")
    return "永久：每回合+2阵地HP，每3回合+1灵活度"

def _高树勋运动(p, enemies, target, battle):
    p.abilities_active.append("高树勋运动")
    return "永久：击杀时30%使另一敌起义1回合"

def _拥政爱民(p, enemies, target, battle):
    p.abilities_active.append("拥政爱民")
    return "永久：每出技能牌+2格挡"

def _自力更生(p, enemies, target, battle):
    p.abilities_active.append("自力更生")
    return "永久：未用能量转化为等量格挡"

def _长期打算(p, enemies, target, battle):
    p.draw_bonus += 2
    p.hp.position_max += 10
    p.hp.position += 10
    p.abilities_active.append("长期打算")
    return "永久：每回合多抽2+阵地上限+10"


# ══════════════════════════════════════
#  战役专属牌 (10张)
# ══════════════════════════════════════

def _大洼反击(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    base = 12
    if t.turn_count > 0:
        base += 6
    dmg = int((base + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    actual = t.take_damage(dmg)
    return f"{'暴击！' if crit else ''}{t.name}受{actual}伤害" + ("(反击加成!)" if base > 12 else "")

def _断敌后路(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    dmg = int((8 + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    actual = t.take_damage(dmg)
    t.add_debuff("补给中断", 2)
    return f"{'暴击！' if crit else ''}{t.name}受{actual}伤害+攻-4持续2回合"

def _城市巷战(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if not t:
        return "无目标"
    dmg = int((5 + p.get_flat_attack_bonus()) * p.get_damage_mult())
    dmg, crit = p.try_crit(dmg)
    actual = t.take_damage(dmg)
    blk = 5
    if p.frontline > 0:
        blk += 3
    blk = int(blk * p.get_block_mult())
    p.block += blk
    return f"{'暴击！' if crit else ''}{t.name}受{actual}+{blk}格挡"

def _百里防线(p, enemies, target, battle):
    base = 14
    if len([e for e in enemies if e.is_alive()]) >= 3:
        base += 6
    blk = int(base * p.get_block_mult())
    p.block += blk
    p.draw_temp -= 1
    return f"+{blk}格挡(下回合抽牌-1)"

def _化四平为马德里(p, enemies, target, battle):
    p.add_buff("马德里精神", 1, "本回合不死+攻击+50%")
    p.hp.command = max(1, p.hp.command)  # 本回合不死
    return "本回合不死+攻击+50%，回合末-10HP"

def _招募志愿兵(p, enemies, target, battle):
    for _ in range(2):
        recruit = Card("新兵", 0, "攻击", "3伤害或3格挡", _新兵, exhaust=True)
        p.discard_pile.append(recruit)
    return "加入2张新兵牌到弃牌堆"

def _新兵(p, enemies, target, battle):
    t = target or (enemies[0] if enemies else None)
    if t:
        t.take_damage(3)
    p.block += 3
    return f"3伤害+3格挡"

def _塔子山死守(p, enemies, target, battle):
    if p.tazishan_max > 0:
        p.tazishan = min(p.tazishan_max, p.tazishan + 10)
        p.block += 10
        return f"塔子山+10HP，+10格挡"
    else:
        p.block += 15
        return "+15格挡"

def _主动撤离(p, enemies, target, battle):
    battle.battle_result = "retreat"
    reward = p.turn_count * 5
    p.negotiation_chips += reward
    return f"主动撤退！获得{reward}谈判筹码(坚守{p.turn_count}回合)"

def _以战取和(p, enemies, target, battle):
    p.abilities_active.append("以战取和")
    return "永久：每回合+1谈判筹码"

def _城防与野战(p, enemies, target, battle):
    p.abilities_active.append("城防与野战")
    p.add_buff("城防加成", -1, "技能牌+3格挡/攻击牌+2伤害")
    return "永久：技能+3格挡，攻击+2伤害"

def _四平精神(p, enemies, target, battle):
    p.abilities_active.append("四平精神")
    return "永久：阵地<50%时攻击+4"


# ══════════════════════════════════════
#  卡牌工厂
# ══════════════════════════════════════

def create_base_deck():
    """创建基础牌组(20张)"""
    deck = []
    # 基础攻击 x5
    for _ in range(5):
        deck.append(Card("集中兵力", 1, "攻击", "8伤害；已出攻击牌则+5", _集中兵力))
    # 基础防御 x5
    for _ in range(5):
        deck.append(Card("运动防御", 1, "技能", "7格挡；HP<50%则16格挡", _运动防御))
    # 奇袭 x2
    for _ in range(2):
        deck.append(Card("奇袭夺城", 0, "攻击", "6伤害；首张牌则抽2", _奇袭夺城))
    # 荫蔽集结 x2
    for _ in range(2):
        deck.append(Card("荫蔽集结", 0, "技能", "抽3牌+下回合+1能量", _荫蔽集结))
    # 整军经武 x2
    for _ in range(2):
        deck.append(Card("整军经武", 1, "技能", "6格挡+每出攻击牌额外+3格挡", _整军经武))
    # 战场侦察 x2
    for _ in range(2):
        deck.append(Card("战场侦察", 0, "技能", "抽2牌+侦察敌意图", _战场侦察))
    # 夜战突袭 x2
    for _ in range(2):
        deck.append(Card("夜战突袭", 1, "攻击", "9伤害；上回合未出攻击牌则翻倍", _夜战突袭))
    return deck


def create_all_cards():
    """返回所有卡牌定义(不含基础牌组里已有的)"""
    cards = {
        # 攻击牌
        "各个击破": Card("各个击破", 2, "攻击", "最低HP敌18伤害，其余6", _各个击破),
        "反复肉搏": Card("反复肉搏", 2, "攻击", "5伤害×4次", _反复肉搏),
        "侧翼包抄": Card("侧翼包抄", 1, "攻击", "7伤害+敌受伤+30%", _侧翼包抄),
        "围点打援": Card("围点打援", 2, "攻击", "10伤害+围困+援敌8伤害", _围点打援),
        "南线牵制": Card("南线牵制", 1, "攻击", "全体5伤害+随机牵制", _南线牵制),
        "破袭游击": Card("破袭游击", 1, "攻击", "5伤害+永久攻-2", _破袭游击),
        "力战不退": Card("力战不退", 2, "攻击", "13伤害+8格挡", _力战不退),
        "全军出击": Card("全军出击", 3, "攻击", "28伤害，本回合结束", _全军出击),
        # 技能牌
        "战略后撤": Card("战略后撤", 1, "技能", "11格挡+抽2牌", _战略后撤),
        "破敌交通": Card("破敌交通", 1, "技能", "敌攻-4+3层断粮", _破敌交通),
        "诱敌深入": Card("诱敌深入", 1, "技能", "受伤-75%，下回合首攻翻倍", _诱敌深入),
        "坚守阵地": Card("坚守阵地", 2, "技能", "20格挡(保留)", _坚守阵地),
        "构筑工事": Card("构筑工事", 1, "技能", "9格挡+下回合+6格挡", _构筑工事),
        "养精蓄锐": Card("养精蓄锐", 1, "技能", "3层蓄力(每层攻+5)", _养精蓄锐),
        "统筹全局": Card("统筹全局", 2, "技能", "能量+3，最低费牌费用归0", _统筹全局),
        # 能力牌
        "土地改革": Card("土地改革", 2, "能力", "永久每回合+1能量", _土地改革),
        "人民战争": Card("人民战争", 3, "能力", "出≥3牌→+4格挡+3伤害", _人民战争),
        "灵活应变": Card("灵活应变", 1, "能力", "每回合可转换1手牌", _灵活应变),
        "建立根据地": Card("建立根据地", 2, "能力", "每回合+2HP+每3回合+1灵活度", _建立根据地),
        "高树勋运动": Card("高树勋运动", 2, "能力", "击杀30%使敌起义", _高树勋运动),
        "拥政爱民": Card("拥政爱民", 1, "能力", "每出技能牌+2格挡", _拥政爱民),
        "自力更生": Card("自力更生", 1, "能力", "未用能量→等量格挡", _自力更生),
        "长期打算": Card("长期打算", 3, "能力", "多抽2+阵地上限+10", _长期打算),
        # 战役专属
        "大洼反击": Card("大洼反击", 2, "攻击", "12伤害，敌已行动则+6", _大洼反击, tags=["战役"]),
        "断敌后路": Card("断敌后路", 2, "攻击", "8伤害+攻-4两回合", _断敌后路, tags=["战役"]),
        "城市巷战": Card("城市巷战", 1, "攻击", "5伤害+5格挡(有防线+3)", _城市巷战, tags=["战役"]),
        "百里防线": Card("百里防线", 2, "技能", "14格挡(≥3敌+6)，抽牌-1", _百里防线, tags=["战役"]),
        "化四平为马德里": Card("化四平为马德里", 3, "技能", "本回合不死+攻+50%，-10HP", _化四平为马德里, tags=["战役"]),
        "招募志愿兵": Card("招募志愿兵", 1, "技能", "加2张新兵牌(3伤/3挡)", _招募志愿兵, tags=["战役"]),
        "塔子山死守": Card("塔子山死守", 2, "技能", "塔子山+10HP+10格挡", _塔子山死守, tags=["战役"]),
        "主动撤离": Card("主动撤离", 0, "技能", "结束战斗，按坚守回合获奖励", _主动撤离, tags=["战役"]),
        "以战取和": Card("以战取和", 2, "能力", "每回合+1谈判筹码", _以战取和, tags=["战役"]),
        "城防与野战": Card("城防与野战", 1, "能力", "技能+3格挡，攻击+2伤害", _城防与野战, tags=["战役"]),
        "四平精神": Card("四平精神", 1, "能力", "阵地<50%时攻击+4", _四平精神, tags=["战役"]),
    }
    return cards


def create_siping_deck():
    """创建四平战役专用牌组(25张)"""
    all_cards = create_all_cards()
    deck = create_base_deck()  # 20张基础
    # 加入战役专属卡
    for name in ["大洼反击", "城市巷战", "百里防线", "招募志愿兵", "塔子山死守"]:
        deck.append(all_cards[name].copy())
    return deck
