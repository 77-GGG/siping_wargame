"""
终端UI：仿杀戮尖塔的文字界面
支持手动模式和自动演示模式
"""
import os
import sys


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


# ── 方框绘制工具 ──

def box(text, width=20, highlight=False):
    """绘制一个文字卡牌方框"""
    lines = text.split('\n')
    border = '═' if highlight else '─'
    corner_tl = '╔' if highlight else '┌'
    corner_tr = '╗' if highlight else '┐'
    corner_bl = '╚' if highlight else '└'
    corner_br = '╝' if highlight else '┘'
    side = '║' if highlight else '│'

    result = [f"{corner_tl}{border * width}{corner_tr}"]
    for line in lines:
        # 处理中文字符宽度
        display_len = get_display_width(line)
        padding = max(0, width - display_len)
        result.append(f"{side}{line}{' ' * padding}{side}")
    result.append(f"{corner_bl}{border * width}{corner_br}")
    return result


def get_display_width(s):
    """计算字符串的显示宽度（中文=2，ASCII=1）"""
    width = 0
    for ch in s:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            width += 2
        else:
            width += 1
    return width


def pad_to_width(s, target_width):
    """将字符串填充到指定显示宽度"""
    current = get_display_width(s)
    return s + ' ' * max(0, target_width - current)


def render_card(card, index=None, card_width=22):
    """渲染单张卡牌为多行文本"""
    idx_str = f"[{index}] " if index is not None else ""
    type_color = {"攻击": "⚔", "技能": "🛡", "能力": "★"}
    icon = type_color.get(card.card_type, "?")

    name_line = f"{idx_str}{icon}{card.name}"
    cost_line = f"费用:{card.cost} {card.card_type}"
    # 描述拆分为多行
    desc = card.description
    desc_lines = []
    while desc:
        chunk = ""
        chunk_width = 0
        for ch in desc:
            cw = 2 if '\u4e00' <= ch <= '\u9fff' else 1
            if chunk_width + cw > card_width - 2:
                break
            chunk += ch
            chunk_width += cw
        desc_lines.append(chunk)
        desc = desc[len(chunk):]

    text = name_line + '\n' + cost_line
    for dl in desc_lines:
        text += '\n' + dl

    return box(text, card_width)


def render_hand(hand, card_width=22):
    """渲染手牌（横向排列）"""
    if not hand:
        return ["  （无手牌）"]

    card_renders = [render_card(c, i, card_width) for i, c in enumerate(hand)]
    max_height = max(len(r) for r in card_renders)
    # 补齐高度
    for r in card_renders:
        while len(r) < max_height:
            r.append(' ' * (card_width + 2))

    # 横向拼接，每行最多4张
    result = []
    for row_start in range(0, len(card_renders), 4):
        row_cards = card_renders[row_start:row_start + 4]
        for line_idx in range(max_height):
            line = "  ".join(pad_to_width(r[line_idx], card_width + 2) for r in row_cards)
            result.append("  " + line)
        result.append("")
    return result


def render_enemy(enemy, index):
    """渲染敌人信息框"""
    hp_bar_len = 20
    hp_ratio = enemy.hp / enemy.hp_max if enemy.hp_max > 0 else 0
    filled = int(hp_ratio * hp_bar_len)
    hp_bar = '█' * filled + '░' * (hp_bar_len - filled)

    debuffs = ""
    if enemy.debuffs:
        debuffs = f"\nDebuff:{','.join(d.name for d in enemy.debuffs)}"

    intent_icon = {"attack": "⚔ 攻击", "defend": "🛡 防御", "charge": "⚡ 蓄力"}
    intent = intent_icon.get(enemy.intent, enemy.intent)

    text = (f"[敌{index+1}] {enemy.name}\n"
            f"HP:{enemy.hp}/{enemy.hp_max}\n"
            f"{hp_bar}\n"
            f"攻击力:{enemy.get_attack()} 意图:{intent}{debuffs}")
    return box(text, 30, highlight=True)


def render_player_status(player, phase, turn):
    """渲染玩家状态面板"""
    p = player
    # HP条
    pos_ratio = p.hp.position / p.hp.position_max if p.hp.position_max > 0 else 0
    trp_ratio = p.hp.troops / p.hp.troops_max if p.hp.troops_max > 0 else 0
    cmd_ratio = p.hp.command / p.hp.command_max if p.hp.command_max > 0 else 0

    bar_len = 15

    def hp_bar(ratio, l=bar_len):
        filled = int(ratio * l)
        return '█' * filled + '░' * (l - filled)

    lines = [
        f"╔══════════ {p.name} ══════════╗",
        f"║ 阶段 {phase} | 回合 {turn}",
        f"║ 阵地  {hp_bar(pos_ratio)} {p.hp.position}/{p.hp.position_max}",
        f"║ 兵力  {hp_bar(trp_ratio)} {p.hp.troops}/{p.hp.troops_max}",
        f"║ 指挥  {hp_bar(cmd_ratio)} {p.hp.command}/{p.hp.command_max}",
        f"║ 能量:{p.energy}/{p.get_energy()} 格挡:{p.block} 灵活度:{p.flexibility} 主动权:{p.initiative}",
    ]
    if p.frontline_max > 0:
        fl_ratio = p.frontline / p.frontline_max
        lines.append(f"║ 防线  {hp_bar(fl_ratio)} {p.frontline}/{p.frontline_max}")
    if p.tazishan_max > 0:
        tz_ratio = p.tazishan / p.tazishan_max
        lines.append(f"║ 塔子山 {hp_bar(tz_ratio)} {p.tazishan}/{p.tazishan_max}")
    if p.buffs:
        lines.append(f"║ Buff: {', '.join(b.name for b in p.buffs)}")
    if p.debuffs:
        lines.append(f"║ Debuff: {', '.join(d.name for d in p.debuffs)}")
    lines.append(f"║ 牌堆:{len(p.draw_pile)} 弃牌:{len(p.discard_pile)} 消耗:{len(p.exhaust_pile)}")
    lines.append(f"╚{'═' * 35}╝")
    return lines


def render_battle_screen(scenario):
    """渲染完整战斗画面"""
    lines = []
    lines.append("")
    lines.append("  ◆ 四 平 保 卫 战 ◆")
    lines.append("")

    # 敌人区域
    enemy_renders = []
    for i, e in enumerate(scenario.enemies):
        if e.is_alive():
            enemy_renders.append(render_enemy(e, i))

    if enemy_renders:
        max_h = max(len(r) for r in enemy_renders)
        for r in enemy_renders:
            while len(r) < max_h:
                r.append(' ' * 32)
        for line_idx in range(max_h):
            line = "  ".join(r[line_idx] for r in enemy_renders)
            lines.append("  " + line)
    lines.append("")

    # 玩家状态
    status = render_player_status(scenario.player, scenario.phase, scenario.turn)
    lines.extend(["  " + l for l in status])
    lines.append("")

    # 手牌
    lines.append("  ── 手 牌 ──")
    hand_lines = render_hand(scenario.player.hand)
    lines.extend(hand_lines)

    return '\n'.join(lines)


def render_log(logs, n=8):
    """渲染最近的战斗日志"""
    lines = ["  ── 战斗日志 ──"]
    for log in logs[-n:]:
        lines.append(f"  {log}")
    return '\n'.join(lines)


def render_game_over(result, player):
    """渲染游戏结束画面"""
    lines = [
        "",
        "  " + "═" * 40,
    ]
    if result == "victory":
        lines.extend([
            "  ║                                      ║",
            "  ║         ★ ★ ★  胜 利  ★ ★ ★         ║",
            "  ║                                      ║",
            "  ║    四平保卫战取得伟大胜利！           ║",
            f"  ║    坚守{player.turn_count}回合                       ║",
            f"  ║    战略主动权: {player.initiative}                   ║",
        ])
    elif result == "retreat":
        lines.extend([
            "  ║                                      ║",
            "  ║         ◇ 战 略 撤 退 ◇             ║",
            "  ║                                      ║",
            "  ║    主力保存，转入运动战               ║",
            f"  ║    坚守{player.turn_count}回合                       ║",
            f"  ║    谈判筹码: {player.negotiation_chips}              ║",
        ])
    else:
        lines.extend([
            "  ║                                      ║",
            "  ║         ✕ ✕ ✕  失 败  ✕ ✕ ✕         ║",
            "  ║                                      ║",
            "  ║    指挥体系崩溃，四平失守             ║",
            f"  ║    坚守{player.turn_count}回合                       ║",
        ])
    lines.append("  " + "═" * 40)
    return '\n'.join(lines)


def show_title():
    """显示标题画面"""
    clear_screen()
    title = """
  ╔══════════════════════════════════════════════╗
  ║                                              ║
  ║          解 放 战 争 · 东 北 篇              ║
  ║                                              ║
  ║        ── 四 平 保 卫 战 ──                  ║
  ║                                              ║
  ║   "集中优势兵力，各个歼灭敌人"               ║
  ║                        ── 毛泽东             ║
  ║                                              ║
  ║   基于杀戮尖塔(Slay the Spire)战斗机制       ║
  ║   以毛泽东军事思想为理论依据                  ║
  ║                                              ║
  ║   [1] 手动战斗模式                           ║
  ║   [2] 史实自动演示                           ║
  ║   [q] 退出                                   ║
  ║                                              ║
  ╚══════════════════════════════════════════════╝
"""
    print(title)


def show_character_select():
    """角色选择"""
    print("""
  ══ 选择指挥官 ══

  [1] 雷霆（先锋型）
      阵地40/兵力50/指挥20
      能量3  灵活度2  主动权3(暴击15%)
      固有能力：先机 — 首回合多抽2+首攻+50%

  [2] 磐石（基石型）
      阵地60/兵力50/指挥25
      能量3  灵活度1  主动权1(暴击5%)
      固有能力：坚壁 — 回合起始+3格挡+技能牌恢复阵地1
""")


def prompt_action(scenario):
    """提示玩家操作"""
    p = scenario.player
    options = ["  操作："]
    options.append("  [数字] 打出对应手牌")
    options.append("  [e] 结束回合")
    if p.can_retreat:
        options.append("  [r] 主动撤退")
    if p.flexibility > 0 and "灵活应变" in p.abilities_active and p.hand:
        options.append("  [f] 转换手牌(消耗1灵活度)")
    options.append("  [s] 查看状态详情")
    options.append("  [l] 查看战斗日志")
    return '\n'.join(options)
