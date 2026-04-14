"""
GUI渲染引擎：使用pygame绘制卡牌、血条、敌人、玩家状态
- 全局缩放系统：所有坐标/尺寸/字号通过 S() 缩放，保证不同分辨率下清晰锐利
- HiDPI支持：字体在原生分辨率渲染，不做后期放大，边缘始终锐利
- 预留图片资源接口
"""
import os
import pygame

# ══════════════════════════════════════
#  全局缩放
# ══════════════════════════════════════

# 逻辑基准分辨率（所有绘制坐标基于此）
BASE_W = 1200
BASE_H = 800

_scale = 1.0          # 当前缩放因子
_ui_scale = 1.0       # 用户额外UI缩放


def set_scale(screen_w, screen_h, ui_scale=1.0):
    """根据实际屏幕尺寸和用户偏好计算缩放因子"""
    global _scale, _ui_scale
    _ui_scale = ui_scale
    base_scale = min(screen_w / BASE_W, screen_h / BASE_H)
    _scale = base_scale * ui_scale


def S(v):
    """将逻辑像素值缩放到实际像素"""
    return int(v * _scale)


def SF(v):
    """缩放浮点数（用于字号等需要精确值的场景）"""
    return max(1, int(v * _scale))


# ── 颜色常量 ──
C_BG          = (25, 25, 35)
C_BG_TOP      = (15, 18, 30)
C_BG_MID      = (30, 28, 40)
C_BG_HAND     = (20, 22, 32)

C_WHITE       = (240, 240, 240)
C_GRAY        = (160, 160, 160)
C_DARK_GRAY   = (80, 80, 80)
C_BLACK       = (0, 0, 0)

C_RED         = (200, 60, 60)
C_RED_DARK    = (120, 30, 30)
C_GREEN       = (60, 180, 80)
C_GREEN_DARK  = (30, 100, 40)
C_BLUE        = (60, 120, 200)
C_BLUE_DARK   = (30, 60, 120)
C_YELLOW      = (220, 200, 60)
C_GOLD        = (200, 170, 50)
C_ORANGE      = (220, 140, 40)
C_PURPLE      = (140, 80, 200)
C_CYAN        = (80, 200, 200)

CARD_COLORS = {
    "攻击": {"bg": (120, 35, 35), "border": (200, 80, 80), "icon": "⚔"},
    "技能": {"bg": (35, 80, 120), "border": (80, 160, 220), "icon": "🛡"},
    "能力": {"bg": (90, 60, 120), "border": (160, 100, 220), "icon": "★"},
}

# ── 图片资源管理 ──
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class AssetManager:
    """图片资源管理器 — 后期替换纯色为图片素材"""

    def __init__(self):
        self.images = {}
        self._ensure_asset_dir()

    def _ensure_asset_dir(self):
        os.makedirs(ASSET_DIR, exist_ok=True)
        for sub in ["cards", "enemies", "backgrounds", "icons", "effects"]:
            os.makedirs(os.path.join(ASSET_DIR, sub), exist_ok=True)

    def load_image(self, category, name, size=None):
        key = f"{category}/{name}/{size}"
        if key in self.images:
            return self.images[key]
        path = os.path.join(ASSET_DIR, category, f"{name}.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            if size:
                img = pygame.transform.smoothscale(img, size)
            self.images[key] = img
            return img
        return None

    def get_card_image(self, card_name, size):
        return self.load_image("cards", card_name, size)

    def get_enemy_image(self, enemy_name, size):
        return self.load_image("enemies", enemy_name, size)

    def get_background(self, phase, size):
        return self.load_image("backgrounds", f"phase{phase}", size)

    def get_icon(self, name, size):
        return self.load_image("icons", name, size)


# ── 字体管理 ──

class FontManager:
    """
    字体管理器：按实际像素字号缓存字体对象。
    所有字号已经过 SF() 缩放后传入，直接渲染在原生分辨率上，
    因此文字边缘始终锐利，不存在模糊放大问题。
    """
    def __init__(self):
        self._fonts = {}
        self._font_path = None
        self._find_font()

    def _find_font(self):
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                self._font_path = c
                return

    def get(self, size):
        """获取指定像素大小的字体（size已经是缩放后的实际像素值）"""
        actual_size = max(10, size)
        if actual_size not in self._fonts:
            if self._font_path:
                self._fonts[actual_size] = pygame.font.Font(self._font_path, actual_size)
            else:
                self._fonts[actual_size] = pygame.font.SysFont("pingfang,simhei,microsoftyahei", actual_size)
        return self._fonts[actual_size]


# 全局实例
assets = None
fonts = None


def init():
    global assets, fonts
    assets = AssetManager()
    fonts = FontManager()


# ══════════════════════════════════════
#  绘制工具函数
# ══════════════════════════════════════

def draw_text(surface, text, pos, size=16, color=C_WHITE, anchor="topleft", max_width=None):
    """
    绘制文字。
    size: 逻辑字号（会自动乘以缩放因子）
    pos:  逻辑坐标（会自动缩放）
    """
    actual_size = SF(size)
    font = fonts.get(actual_size)
    sx, sy = S(pos[0]), S(pos[1])
    actual_max_w = S(max_width) if max_width else None

    if actual_max_w:
        rendered = text
        while font.size(rendered)[0] > actual_max_w and len(rendered) > 1:
            rendered = rendered[:-1]
        if rendered != text:
            rendered = rendered[:-1] + "…"
        text = rendered

    surf = font.render(text, True, color)
    rect = surf.get_rect(**{anchor: (sx, sy)})
    surface.blit(surf, rect)
    return rect


def draw_text_wrapped(surface, text, rect, size=14, color=C_WHITE, line_spacing=2):
    """在矩形区域内自动换行绘制文字（rect为逻辑坐标）"""
    actual_size = SF(size)
    font = fonts.get(actual_size)
    x, y, max_w, max_h = S(rect[0]), S(rect[1]), S(rect[2]), S(rect[3])
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        if font.size(test)[0] > max_w:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)

    line_h = font.get_linesize() + S(line_spacing)
    for i, line in enumerate(lines):
        if y + i * line_h > y + max_h:
            break
        surf = font.render(line, True, color)
        surface.blit(surf, (x, y + i * line_h))


def draw_hp_bar(surface, x, y, w, h, current, maximum, color, bg_color=C_DARK_GRAY, border=True):
    """绘制血条（参数为逻辑坐标）"""
    sx, sy, sw, sh = S(x), S(y), S(w), S(h)
    pygame.draw.rect(surface, bg_color, (sx, sy, sw, sh))
    if maximum > 0:
        fill_w = int(sw * current / maximum)
        pygame.draw.rect(surface, color, (sx, sy, fill_w, sh))
    if border:
        pygame.draw.rect(surface, C_GRAY, (sx, sy, sw, sh), max(1, S(1)))


def draw_rounded_rect(surface, color, rect, radius=8, border=0, border_color=None):
    """绘制圆角矩形（参数为逻辑坐标）"""
    sx, sy, sw, sh = S(rect[0]), S(rect[1]), S(rect[2]), S(rect[3])
    sr = max(1, S(radius))
    if border > 0 and border_color:
        sb = max(1, S(border))
        pygame.draw.rect(surface, border_color, (sx, sy, sw, sh), border_radius=sr)
        pygame.draw.rect(surface, color,
                         (sx + sb, sy + sb, sw - 2*sb, sh - 2*sb),
                         border_radius=max(1, sr - sb))
    else:
        pygame.draw.rect(surface, color, (sx, sy, sw, sh), border_radius=sr)


# ══════════════════════════════════════
#  卡牌绘制
# ══════════════════════════════════════

def draw_card(surface, card, x, y, w=140, h=190, hover=False, selected=False, index=None):
    """绘制单张卡牌（x, y, w, h 为逻辑坐标）"""
    colors = CARD_COLORS.get(card.card_type, CARD_COLORS["攻击"])

    if selected:
        y -= 20
    elif hover:
        y -= 10

    card_img = assets.get_card_image(card.name, (S(w), S(h)))
    if card_img:
        surface.blit(card_img, (S(x), S(y)))
    else:
        border_w = 3 if selected else 2
        border_c = C_YELLOW if selected else (colors["border"] if hover else C_GRAY)
        draw_rounded_rect(surface, colors["bg"], (x, y, w, h), radius=10,
                          border=border_w, border_color=border_c)
        # 顶部色带
        pygame.draw.rect(surface, colors["border"],
                         (S(x + 3), S(y + 3), S(w - 6), S(6)), border_radius=S(3))

    # 费用圆圈
    cost_cx, cost_cy = S(x + 20), S(y + 24)
    cr = S(16)
    pygame.draw.circle(surface, C_GOLD, (cost_cx, cost_cy), cr)
    pygame.draw.circle(surface, C_BLACK, (cost_cx, cost_cy), cr, max(1, S(2)))
    draw_text(surface, str(card.cost), (x + 20, y + 24), size=20, color=C_BLACK, anchor="center")

    # 名称
    draw_text(surface, card.name, (x + 40, y + 15), size=17, color=C_WHITE, max_width=w - 48)

    # 类型
    draw_text(surface, card.card_type, (x + w - 8, y + 36), size=12,
              color=colors["border"], anchor="topright")

    # 分隔线
    pygame.draw.line(surface, colors["border"],
                     (S(x + 8), S(y + 44)), (S(x + w - 8), S(y + 44)), max(1, S(1)))

    # 描述
    draw_text_wrapped(surface, card.description, (x + 8, y + 52, w - 16, h - 66),
                      size=14, color=C_WHITE, line_spacing=3)

    # 编号
    if index is not None:
        draw_text(surface, f"[{index}]", (x + w // 2, y + h - 16), size=12,
                  color=C_GRAY, anchor="center")

    return pygame.Rect(S(x), S(y), S(w), S(h))


def draw_hand(surface, hand, area_rect, hover_idx=-1, selected_idx=-1):
    """绘制手牌区域（area_rect为逻辑坐标），返回实际像素矩形列表"""
    ax, ay, aw, ah = area_rect
    card_w, card_h = 140, 190
    rects = []
    if not hand:
        draw_text(surface, "（无手牌）", (ax + aw // 2, ay + ah // 2),
                  size=20, color=C_GRAY, anchor="center")
        return rects

    total_w = len(hand) * (card_w + 8) - 8
    if total_w > aw:
        gap = max(24, (aw - card_w) // max(1, len(hand) - 1))
    else:
        gap = card_w + 8

    start_x = ax + (aw - min(total_w, (len(hand) - 1) * gap + card_w)) // 2

    for i, card in enumerate(hand):
        cx = start_x + i * gap
        cy = ay + 8
        is_hover = (i == hover_idx)
        is_selected = (i == selected_idx)
        r = draw_card(surface, card, cx, cy, card_w, card_h,
                      hover=is_hover, selected=is_selected, index=i)
        rects.append(r)
    return rects


# ══════════════════════════════════════
#  敌人绘制
# ══════════════════════════════════════

def draw_enemy(surface, enemy, x, y, w=230, h=220, hover=False, index=0):
    """绘制敌人（逻辑坐标）"""
    enemy_img = assets.get_enemy_image(enemy.name, (S(w - 20), S(90)))
    if enemy_img:
        surface.blit(enemy_img, (S(x + 10), S(y + 10)))
    else:
        border_c = C_YELLOW if hover else C_RED
        draw_rounded_rect(surface, C_RED_DARK, (x, y, w, h), radius=8,
                          border=2, border_color=border_c)
        cx_s, cy_s = S(x + w // 2), S(y + 50)
        pygame.draw.circle(surface, C_RED, (cx_s, cy_s - S(12)), S(20))
        pygame.draw.rect(surface, C_RED,
                         (cx_s - S(17), cy_s + S(8), S(34), S(32)))
        draw_text(surface, str(index + 1), (x + w // 2, y + 38),
                  size=18, color=C_WHITE, anchor="center")

    draw_text(surface, enemy.name, (x + w // 2, y + 96), size=17, color=C_WHITE,
              anchor="midtop", max_width=w - 10)

    draw_hp_bar(surface, x + 10, y + 120, w - 20, 16, enemy.hp, enemy.hp_max, C_RED)
    draw_text(surface, f"{enemy.hp}/{enemy.hp_max}", (x + w // 2, y + 120),
              size=13, color=C_WHITE, anchor="midtop")

    atk = enemy.get_attack()
    intent_map = {"attack": f"⚔{atk}", "defend": "🛡防御", "charge": "⚡蓄力"}
    intent_str = intent_map.get(enemy.intent, f"⚔{atk}")
    draw_text(surface, f"攻:{atk}", (x + 10, y + 144), size=15, color=C_ORANGE)
    draw_text(surface, f"意图:{intent_str}", (x + w - 10, y + 144), size=15,
              color=C_ORANGE, anchor="topright")

    if enemy.debuffs:
        debuff_str = " ".join(d.name for d in enemy.debuffs)
        draw_text(surface, debuff_str, (x + 10, y + 170), size=13, color=C_PURPLE, max_width=w - 20)

    if enemy.traits:
        trait_str = " ".join(enemy.traits)
        draw_text(surface, trait_str, (x + 10, y + 192), size=13, color=C_CYAN, max_width=w - 20)

    return pygame.Rect(S(x), S(y), S(w), S(h))


def draw_enemies(surface, enemies, area_rect, hover_idx=-1):
    """绘制所有敌人（area_rect为逻辑坐标）"""
    ax, ay, aw, ah = area_rect
    alive = [(i, e) for i, e in enumerate(enemies) if e.is_alive()]
    rects = {}
    if not alive:
        return rects

    ew, eh = 230, 220
    total_w = len(alive) * (ew + 24) - 24
    start_x = ax + (aw - total_w) // 2

    for j, (i, e) in enumerate(alive):
        ex = start_x + j * (ew + 24)
        ey = ay + 8
        is_hover = (i == hover_idx)
        r = draw_enemy(surface, e, ex, ey, ew, eh, hover=is_hover, index=i)
        rects[i] = r
    return rects


# ══════════════════════════════════════
#  玩家状态面板
# ══════════════════════════════════════

def draw_player_panel(surface, player, phase, turn, area_rect):
    """绘制玩家状态面板（area_rect为逻辑坐标）"""
    ax, ay, aw, ah = area_rect
    draw_rounded_rect(surface, (30, 30, 45), (ax, ay, aw, ah), radius=10,
                      border=2, border_color=C_BLUE)

    px = ax + 14
    py = ay + 8

    draw_text(surface, f"{player.name}  阶段{phase} 回合{turn}", (px, py), size=20, color=C_GOLD)
    py += 30

    label_w = 56
    bar_w = 190
    bar_h = 16
    layers = [
        ("阵地", player.hp.position, player.hp.position_max, C_GREEN),
        ("兵力", player.hp.troops, player.hp.troops_max, C_BLUE),
        ("指挥", player.hp.command, player.hp.command_max, C_RED),
    ]
    for name, cur, mx, color in layers:
        draw_text(surface, name, (px, py), size=15, color=color)
        draw_hp_bar(surface, px + label_w, py + 2, bar_w, bar_h, cur, mx, color)
        draw_text(surface, f"{cur}/{mx}", (px + label_w + bar_w + 6, py), size=13, color=C_WHITE)
        py += 22

    if player.frontline_max > 0:
        draw_text(surface, "防线", (px, py), size=15, color=C_ORANGE)
        draw_hp_bar(surface, px + label_w, py + 2, bar_w, bar_h,
                    player.frontline, player.frontline_max, C_ORANGE)
        draw_text(surface, f"{player.frontline}/{player.frontline_max}",
                  (px + label_w + bar_w + 6, py), size=13, color=C_WHITE)
        py += 22
    if player.tazishan_max > 0:
        draw_text(surface, "塔子山", (px, py), size=15, color=C_YELLOW)
        draw_hp_bar(surface, px + label_w, py + 2, bar_w, bar_h,
                    player.tazishan, player.tazishan_max, C_YELLOW)
        draw_text(surface, f"{player.tazishan}/{player.tazishan_max}",
                  (px + label_w + bar_w + 6, py), size=13, color=C_WHITE)
        py += 22

    py += 4
    draw_text(surface, f"能量 {player.energy}/{player.get_energy()}", (px, py),
              size=16, color=C_CYAN)
    draw_text(surface, f"格挡 {player.block}", (px + 130, py), size=16, color=C_BLUE)
    py += 24
    draw_text(surface, f"灵活度 {player.flexibility}", (px, py), size=16, color=C_GREEN)
    draw_text(surface, f"主动权 {player.initiative}", (px + 130, py), size=16, color=C_GOLD)
    py += 24

    draw_text(surface,
              f"牌堆:{len(player.draw_pile)} 弃:{len(player.discard_pile)} 消耗:{len(player.exhaust_pile)}",
              (px, py), size=13, color=C_GRAY)
    py += 20

    if player.buffs:
        buff_str = " ".join(f"[{b.name}]" for b in player.buffs)
        draw_text(surface, f"Buff: {buff_str}", (px, py), size=13,
                  color=C_GREEN, max_width=aw - 28)
        py += 18
    if player.debuffs:
        debuff_str = " ".join(f"[{d.name}]" for d in player.debuffs)
        draw_text(surface, f"Debuff: {debuff_str}", (px, py), size=13,
                  color=C_RED, max_width=aw - 28)


# ══════════════════════════════════════
#  战斗日志面板
# ══════════════════════════════════════

def draw_log_panel(surface, logs, area_rect, max_lines=11):
    ax, ay, aw, ah = area_rect
    draw_rounded_rect(surface, (20, 20, 30), (ax, ay, aw, ah), radius=8,
                      border=1, border_color=C_DARK_GRAY)

    draw_text(surface, "战斗日志", (ax + 10, ay + 6), size=16, color=C_GOLD)

    recent = logs[-max_lines:]
    for i, log in enumerate(recent):
        color = C_WHITE
        if "暴击" in log or "击杀" in log or "☠" in log:
            color = C_YELLOW
        elif "敌" in log and "攻击" in log:
            color = C_RED
        elif "格挡" in log or "防御" in log:
            color = C_BLUE
        elif "📜" in log or "政治" in log:
            color = C_CYAN
        draw_text(surface, log.strip(), (ax + 10, ay + 32 + i * 20), size=13,
                  color=color, max_width=aw - 20)


# ══════════════════════════════════════
#  按钮
# ══════════════════════════════════════

def draw_button(surface, text, rect, color=C_BLUE, hover=False, disabled=False):
    x, y, w, h = rect
    if disabled:
        bg = C_DARK_GRAY
        border_c = C_GRAY
        text_c = C_GRAY
    elif hover:
        bg = tuple(min(255, c + 30) for c in color)
        border_c = C_WHITE
        text_c = C_WHITE
    else:
        bg = color
        border_c = tuple(min(255, c + 60) for c in color)
        text_c = C_WHITE

    draw_rounded_rect(surface, bg, (x, y, w, h), radius=6, border=2, border_color=border_c)
    draw_text(surface, text, (x + w // 2, y + h // 2), size=17, color=text_c, anchor="center")
    return pygame.Rect(S(x), S(y), S(w), S(h))


# ══════════════════════════════════════
#  提示框
# ══════════════════════════════════════

def draw_tooltip(surface, text, pos, size=15):
    """pos为实际屏幕像素坐标（鼠标位置），内部处理缩放"""
    actual_size = SF(size)
    font = fonts.get(actual_size)
    lines = text.split('\n')
    max_w = max(font.size(l)[0] for l in lines) + S(16)
    total_h = len(lines) * (font.get_linesize() + S(2)) + S(10)
    x, y = pos
    sw, sh = surface.get_size()
    if x + max_w > sw:
        x = sw - max_w - S(5)
    if y + total_h > sh:
        y = y - total_h - S(5)

    # 直接用像素坐标绘制（不经过S()）
    r = max(1, S(6))
    pygame.draw.rect(surface, (40, 40, 50), (x, y, max_w, total_h), border_radius=r)
    pygame.draw.rect(surface, C_GOLD, (x, y, max_w, total_h), max(1, S(1)), border_radius=r)
    for i, line in enumerate(lines):
        surf = font.render(line, True, C_WHITE)
        surface.blit(surf, (x + S(8), y + S(5) + i * (font.get_linesize() + S(2))))


# ══════════════════════════════════════
#  游戏结束画面
# ══════════════════════════════════════

def draw_game_over(surface, result, player, screen_w, screen_h):
    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surface.blit(overlay, (0, 0))

    # 逻辑坐标居中
    cx = BASE_W // 2
    cy = BASE_H // 2
    panel_w, panel_h = 500, 350
    px = cx - panel_w // 2
    py = cy - panel_h // 2

    if result == "victory":
        border_c, title, title_c = C_GOLD, "★ 胜 利 ★", C_GOLD
        msg = "四平保卫战取得伟大胜利！"
    elif result == "retreat":
        border_c, title, title_c = C_CYAN, "◇ 战略撤退 ◇", C_CYAN
        msg = "主力保存，转入运动战"
    else:
        border_c, title, title_c = C_RED, "✕ 失 败 ✕", C_RED
        msg = "指挥体系崩溃，四平失守"

    draw_rounded_rect(surface, (20, 20, 30), (px, py, panel_w, panel_h),
                      radius=15, border=3, border_color=border_c)
    draw_text(surface, title, (cx, py + 40), size=36, color=title_c, anchor="center")
    draw_text(surface, msg, (cx, py + 90), size=20, color=C_WHITE, anchor="center")

    if player:
        draw_text(surface, f"坚守 {player.turn_count} 回合", (cx, py + 140),
                  size=18, color=C_WHITE, anchor="center")
        draw_text(surface, f"战略主动权: {player.initiative}", (cx, py + 170),
                  size=16, color=C_GOLD, anchor="center")
        if player.negotiation_chips > 0:
            draw_text(surface, f"谈判筹码: {player.negotiation_chips}", (cx, py + 200),
                      size=16, color=C_CYAN, anchor="center")
        draw_text(surface,
                  f"阵地:{player.hp.position} 兵力:{player.hp.troops} 指挥:{player.hp.command}",
                  (cx, py + 240), size=14, color=C_GRAY, anchor="center")

    draw_text(surface, "按 回车 返回主菜单", (cx, py + panel_h - 40),
              size=16, color=C_GRAY, anchor="center")


# ══════════════════════════════════════
#  标题画面
# ══════════════════════════════════════

def draw_title_screen(surface, screen_w, screen_h, hover_btn=-1):
    surface.fill(C_BG)
    cx = BASE_W // 2

    bg_img = assets.get_background("title", (screen_w, screen_h)) if assets else None
    if bg_img:
        surface.blit(bg_img, (0, 0))

    draw_text(surface, "解放战争·东北篇", (cx, 80), size=42, color=C_GOLD, anchor="center")
    draw_text(surface, "── 四平保卫战 ──", (cx, 140), size=28, color=C_WHITE, anchor="center")
    draw_text(surface, "\"集中优势兵力，各个歼灭敌人\"", (cx, 205), size=18,
              color=C_CYAN, anchor="center")
    draw_text(surface, "── 毛泽东", (cx, 232), size=14, color=C_GRAY, anchor="center")

    btn_w, btn_h = 280, 50
    btn_x = cx - btn_w // 2
    buttons = []

    r1 = draw_button(surface, "手动战斗模式", (btn_x, 290, btn_w, btn_h),
                     color=(50, 100, 50), hover=(hover_btn == 0))
    buttons.append(r1)

    r2 = draw_button(surface, "史实自动演示", (btn_x, 360, btn_w, btn_h),
                     color=(50, 50, 120), hover=(hover_btn == 1))
    buttons.append(r2)

    r3 = draw_button(surface, "设置", (btn_x, 430, btn_w, btn_h),
                     color=(60, 60, 70), hover=(hover_btn == 2))
    buttons.append(r3)

    r4 = draw_button(surface, "退出", (btn_x, 500, btn_w, btn_h),
                     color=(80, 40, 40), hover=(hover_btn == 3))
    buttons.append(r4)

    draw_text(surface, "基于杀戮尖塔(Slay the Spire)战斗机制", (cx, BASE_H - 55),
              size=13, color=C_DARK_GRAY, anchor="center")
    draw_text(surface, "以毛泽东军事思想为理论依据", (cx, BASE_H - 38),
              size=13, color=C_DARK_GRAY, anchor="center")

    return buttons


# ══════════════════════════════════════
#  角色选择画面
# ══════════════════════════════════════

def draw_character_select(surface, screen_w, screen_h, hover_btn=-1):
    surface.fill(C_BG)
    cx = BASE_W // 2

    draw_text(surface, "选择指挥官", (cx, 40), size=32, color=C_GOLD, anchor="center")

    buttons = []

    panel_w, panel_h = 320, 260
    px1 = cx - panel_w - 30
    py = 100
    border_c = C_YELLOW if hover_btn == 0 else C_ORANGE
    draw_rounded_rect(surface, (50, 35, 25), (px1, py, panel_w, panel_h),
                      radius=12, border=2, border_color=border_c)
    draw_text(surface, "⚔ 雷霆（先锋型）", (px1 + panel_w // 2, py + 15), size=22,
              color=C_ORANGE, anchor="center")
    info1 = [
        "阵地:40 / 兵力:50 / 指挥:20",
        "能量:3  灵活度:2  主动权:3",
        "暴击率: 15%",
        "",
        "固有能力：先机",
        "首回合多抽2张牌",
        "首次攻击伤害+50%",
        "",
        "特点：高爆发，高风险",
    ]
    for i, line in enumerate(info1):
        c = C_GOLD if "固有" in line else C_WHITE
        draw_text(surface, line, (px1 + 20, py + 50 + i * 22), size=14, color=c)
    buttons.append(pygame.Rect(S(px1), S(py), S(panel_w), S(panel_h)))

    px2 = cx + 30
    border_c = C_YELLOW if hover_btn == 1 else C_BLUE
    draw_rounded_rect(surface, (25, 35, 50), (px2, py, panel_w, panel_h),
                      radius=12, border=2, border_color=border_c)
    draw_text(surface, "🛡 磐石（基石型）", (px2 + panel_w // 2, py + 15), size=22,
              color=C_BLUE, anchor="center")
    info2 = [
        "阵地:60 / 兵力:50 / 指挥:25",
        "能量:3  灵活度:1  主动权:1",
        "暴击率: 5%",
        "",
        "固有能力：坚壁",
        "回合起始+3格挡",
        "技能牌恢复阵地1点",
        "",
        "特点：高防御，稳扎稳打",
    ]
    for i, line in enumerate(info2):
        c = C_GOLD if "固有" in line else C_WHITE
        draw_text(surface, line, (px2 + 20, py + 50 + i * 22), size=14, color=c)
    buttons.append(pygame.Rect(S(px2), S(py), S(panel_w), S(panel_h)))

    r3 = draw_button(surface, "返回", (cx - 60, BASE_H - 70, 120, 40),
                     color=(80, 40, 40), hover=(hover_btn == 2))
    buttons.append(r3)

    return buttons


# ══════════════════════════════════════
#  设置画面
# ══════════════════════════════════════

RESOLUTION_OPTIONS = [
    (1200, 800,  "1200×800"),
    (1440, 960,  "1440×960"),
    (1600, 1000, "1600×1000"),
    (1920, 1080, "1920×1080"),
    (2560, 1440, "2560×1440"),
    (0, 0,       "全屏"),
]

UI_SCALE_OPTIONS = [
    (1.0,  "100%"),
    (1.15, "115%"),
    (1.25, "125%"),
    (1.5,  "150%"),
    (1.75, "175%"),
    (2.0,  "200%"),
]


def draw_settings_screen(surface, screen_w, screen_h, hover_btn=-1,
                          current_res_idx=0, current_scale_idx=0):
    """绘制设置画面，返回可点击矩形列表"""
    surface.fill(C_BG)
    cx = BASE_W // 2

    draw_text(surface, "设 置", (cx, 30), size=36, color=C_GOLD, anchor="center")

    buttons = []

    # ── 分辨率选择 ──
    draw_text(surface, "分辨率", (cx, 90), size=20, color=C_WHITE, anchor="center")

    btn_w, btn_h = 160, 38
    cols = 3
    gap_x, gap_y = 10, 8
    total_row_w = cols * btn_w + (cols - 1) * gap_x
    start_x = cx - total_row_w // 2

    for i, (rw, rh, label) in enumerate(RESOLUTION_OPTIONS):
        row = i // cols
        col = i % cols
        bx = start_x + col * (btn_w + gap_x)
        by = 120 + row * (btn_h + gap_y)
        is_current = (i == current_res_idx)
        color = (40, 100, 40) if is_current else (50, 50, 65)
        hover = (hover_btn == i)
        r = draw_button(surface, label, (bx, by, btn_w, btn_h),
                        color=color, hover=hover)
        buttons.append(r)

    # ── UI缩放选择 ──
    scale_offset = len(RESOLUTION_OPTIONS)
    draw_text(surface, "UI 缩放", (cx, 230), size=20, color=C_WHITE, anchor="center")

    for i, (sv, label) in enumerate(UI_SCALE_OPTIONS):
        row = i // cols
        col = i % cols
        bx = start_x + col * (btn_w + gap_x)
        by = 260 + row * (btn_h + gap_y)
        is_current = (i == current_scale_idx)
        color = (40, 100, 40) if is_current else (50, 50, 65)
        hover = (hover_btn == scale_offset + i)
        r = draw_button(surface, label, (bx, by, btn_w, btn_h),
                        color=color, hover=hover)
        buttons.append(r)

    # ── 当前设置信息 ──
    res_label = RESOLUTION_OPTIONS[current_res_idx][2]
    scale_label = UI_SCALE_OPTIONS[current_scale_idx][1]
    rw, rh = RESOLUTION_OPTIONS[current_res_idx][:2]
    if rw == 0:
        info = f"当前: 全屏 / UI缩放 {scale_label}"
    else:
        info = f"当前: {res_label} / UI缩放 {scale_label}"
    draw_text(surface, info, (cx, 380), size=16, color=C_CYAN, anchor="center")

    draw_text(surface, "提示：更高分辨率+更大缩放 = 更清晰的文字", (cx, 410),
              size=13, color=C_GRAY, anchor="center")

    # ── 应用 & 返回 ──
    apply_idx = scale_offset + len(UI_SCALE_OPTIONS)
    r_apply = draw_button(surface, "应用设置", (cx - 140, 460, 120, 44),
                          color=(40, 90, 40), hover=(hover_btn == apply_idx))
    buttons.append(r_apply)

    back_idx = apply_idx + 1
    r_back = draw_button(surface, "返回", (cx + 20, 460, 120, 44),
                         color=(80, 40, 40), hover=(hover_btn == back_idx))
    buttons.append(r_back)

    return buttons
