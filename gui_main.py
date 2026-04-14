"""
解放战争·东北篇 ── 四平保卫战 (GUI版)
pygame图形界面，支持：
- 手动战斗 / 史实自动演示两种模式
- 分辨率选择 + UI缩放（HiDPI锐利渲染）
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# macOS HiDPI: 让 SDL 使用原生像素而非逻辑点
os.environ["SDL_VIDEO_HIGHDPI_DISABLED"] = "0"

import pygame
from scenarios import SipingBattle, AutoPlayScript, create_player_leitong, create_player_panshi
from cards import create_all_cards
import gui_renderer as R

# ── 设置持久化 ──
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_SETTINGS = {
    "resolution_index": 0,   # 对应 R.RESOLUTION_OPTIONS
    "ui_scale_index": 0,     # 对应 R.UI_SCALE_OPTIONS
}


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH) as f:
                saved = json.load(f)
            s = DEFAULT_SETTINGS.copy()
            s.update(saved)
            return s
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


# ── 游戏状态 ──
STATE_TITLE      = "title"
STATE_CHARSEL    = "charsel"
STATE_SETTINGS   = "settings"
STATE_BATTLE     = "battle"
STATE_TARGETING  = "targeting"
STATE_ENEMY_TURN = "enemy_turn"
STATE_GAME_OVER  = "game_over"
STATE_AUTO_PLAY  = "auto_play"
STATE_AUTO_WAIT  = "auto_wait"
STATE_AUTO_ENEMY = "auto_enemy"

FPS = 60

# 逻辑布局区域（基于1200x800基准）
L_ENEMIES = (0, 10, 1200, 235)
L_PLAYER  = (10, 250, 340, 260)
L_LOG     = (360, 250, 830, 260)
L_HAND    = (0, 515, 1200, 205)
L_BUTTONS = (10, 725, 1180, 60)


class Game:
    def __init__(self):
        pygame.init()
        self.settings = load_settings()

        # 初始化显示
        self.screen_w = 0
        self.screen_h = 0
        self.screen = None
        self._apply_resolution()

        R.init()

        self.state = STATE_TITLE
        self.scenario = None
        self.auto_script = None

        # 交互状态
        self.hover_card = -1
        self.selected_card = -1
        self.hover_enemy = -1
        self.hover_btn = -1
        self.card_rects = []
        self.enemy_rects = {}
        self.btn_rects = []

        # 动画/消息
        self.float_texts = []
        self.message = ""
        self.message_timer = 0

        # 自动模式
        self.auto_phase_text = ""
        self.auto_cards_to_play = []
        self.auto_play_delay = 0
        self.auto_mode_type = 0

        # 设置界面临时值
        self.tmp_res_idx = self.settings["resolution_index"]
        self.tmp_scale_idx = self.settings["ui_scale_index"]

        self.clock = pygame.time.Clock()
        self.running = True

    def _apply_resolution(self):
        """根据当前设置创建窗口并设置缩放"""
        res_idx = self.settings["resolution_index"]
        scale_idx = self.settings["ui_scale_index"]

        rw, rh, _ = R.RESOLUTION_OPTIONS[res_idx]
        ui_scale = R.UI_SCALE_OPTIONS[scale_idx][0]

        if rw == 0:
            # 全屏
            info = pygame.display.Info()
            self.screen_w = info.current_w
            self.screen_h = info.current_h
            self.screen = pygame.display.set_mode(
                (self.screen_w, self.screen_h), pygame.FULLSCREEN)
        else:
            self.screen_w = rw
            self.screen_h = rh
            self.screen = pygame.display.set_mode((rw, rh), pygame.RESIZABLE)

        pygame.display.set_caption("解放战争·东北篇 ── 四平保卫战")
        R.set_scale(self.screen_w, self.screen_h, ui_scale)

    def _to_logical(self, screen_x, screen_y):
        """将实际屏幕像素坐标转换为逻辑坐标"""
        if R._scale == 0:
            return screen_x, screen_y
        return screen_x / R._scale, screen_y / R._scale

    def add_float_text(self, text, lx, ly, color=R.C_YELLOW):
        """lx, ly为逻辑坐标"""
        self.float_texts.append([text, lx, ly, color, 60])

    def show_message(self, msg, duration=120):
        self.message = msg
        self.message_timer = duration

    def run(self):
        while self.running:
            self.clock.tick(FPS)
            self.handle_events()
            self.update()
            self.render()
        pygame.quit()

    # ══════════════════════════════════════
    #  事件处理
    # ══════════════════════════════════════

    def handle_events(self):
        mx, my = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN:
                self._handle_key(event.key)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_click(mx, my)

        self._update_hover(mx, my)

    def _handle_key(self, key):
        if key == pygame.K_ESCAPE:
            if self.state in (STATE_BATTLE, STATE_TARGETING, STATE_AUTO_PLAY,
                              STATE_AUTO_WAIT, STATE_AUTO_ENEMY):
                self.state = STATE_TITLE
                self.scenario = None
            elif self.state in (STATE_CHARSEL, STATE_SETTINGS):
                self.state = STATE_TITLE
            elif self.state == STATE_TITLE:
                self.running = False
            elif self.state == STATE_GAME_OVER:
                self.state = STATE_TITLE

        if key == pygame.K_RETURN:
            if self.state == STATE_GAME_OVER:
                self.state = STATE_TITLE
            elif self.state == STATE_AUTO_WAIT:
                self._auto_execute_cards()
            elif self.state == STATE_AUTO_ENEMY:
                self._auto_next_turn()

        if self.state == STATE_BATTLE:
            if key == pygame.K_e:
                self._end_player_turn()
            elif key == pygame.K_r and self.scenario and self.scenario.player.can_retreat:
                self.scenario.battle.battle_result = "retreat"
                self.scenario.game_over = True
                self.scenario.result = "retreat"
                self.state = STATE_GAME_OVER

    def _handle_click(self, mx, my):
        if self.state == STATE_TITLE:
            for i, r in enumerate(self.btn_rects):
                if r.collidepoint(mx, my):
                    if i == 0:
                        self.auto_mode_type = 0
                        self.state = STATE_CHARSEL
                    elif i == 1:
                        self.auto_mode_type = 1
                        self._start_auto_mode()
                    elif i == 2:
                        self.tmp_res_idx = self.settings["resolution_index"]
                        self.tmp_scale_idx = self.settings["ui_scale_index"]
                        self.state = STATE_SETTINGS
                    elif i == 3:
                        self.running = False
                    return

        elif self.state == STATE_SETTINGS:
            self._handle_settings_click(mx, my)

        elif self.state == STATE_CHARSEL:
            for i, r in enumerate(self.btn_rects):
                if r.collidepoint(mx, my):
                    if i == 0:
                        self._start_battle(create_player_leitong())
                    elif i == 1:
                        self._start_battle(create_player_panshi())
                    elif i == 2:
                        self.state = STATE_TITLE
                    return

        elif self.state == STATE_BATTLE:
            for i, r in enumerate(self.card_rects):
                if r.collidepoint(mx, my):
                    card = self.scenario.player.hand[i]
                    if card.cost > self.scenario.player.energy:
                        self.show_message("能量不足！")
                        return
                    if card.card_type == "攻击" and any(e.is_alive() for e in self.scenario.enemies):
                        self.selected_card = i
                        self.state = STATE_TARGETING
                        self.show_message("选择攻击目标（点击敌人）")
                    else:
                        self._play_card(i, None)
                    return

            for i, r in enumerate(self.btn_rects):
                if r.collidepoint(mx, my):
                    if i == 0:
                        self._end_player_turn()
                    elif i == 1 and self.scenario.player.can_retreat:
                        self.scenario.battle.battle_result = "retreat"
                        self.scenario.game_over = True
                        self.scenario.result = "retreat"
                        self.state = STATE_GAME_OVER
                    return

        elif self.state == STATE_TARGETING:
            for idx, r in self.enemy_rects.items():
                if r.collidepoint(mx, my) and self.scenario.enemies[idx].is_alive():
                    self._play_card(self.selected_card, self.scenario.enemies[idx])
                    self.state = STATE_BATTLE
                    self.selected_card = -1
                    return
            self.state = STATE_BATTLE
            self.selected_card = -1

    def _handle_settings_click(self, mx, my):
        n_res = len(R.RESOLUTION_OPTIONS)
        n_scale = len(R.UI_SCALE_OPTIONS)

        for i, r in enumerate(self.btn_rects):
            if r.collidepoint(mx, my):
                if i < n_res:
                    self.tmp_res_idx = i
                elif i < n_res + n_scale:
                    self.tmp_scale_idx = i - n_res
                elif i == n_res + n_scale:
                    # 应用
                    self.settings["resolution_index"] = self.tmp_res_idx
                    self.settings["ui_scale_index"] = self.tmp_scale_idx
                    save_settings(self.settings)
                    self._apply_resolution()
                    # 重新初始化字体缓存（字号变了）
                    R.fonts._fonts.clear()
                    self.show_message("设置已应用！")
                elif i == n_res + n_scale + 1:
                    # 返回
                    self.state = STATE_TITLE
                return

    def _update_hover(self, mx, my):
        self.hover_card = -1
        self.hover_enemy = -1
        self.hover_btn = -1

        if self.state in (STATE_BATTLE, STATE_TARGETING):
            for i, r in enumerate(self.card_rects):
                if r.collidepoint(mx, my):
                    self.hover_card = i
                    break
            for idx, r in self.enemy_rects.items():
                if r.collidepoint(mx, my):
                    self.hover_enemy = idx
                    break
            for i, r in enumerate(self.btn_rects):
                if r.collidepoint(mx, my):
                    self.hover_btn = i
                    break

        elif self.state in (STATE_TITLE, STATE_CHARSEL, STATE_SETTINGS):
            for i, r in enumerate(self.btn_rects):
                if r.collidepoint(mx, my):
                    self.hover_btn = i
                    break

    # ══════════════════════════════════════
    #  游戏逻辑
    # ══════════════════════════════════════

    def _start_battle(self, player):
        self.scenario = SipingBattle(player)
        player.init_combat()
        self.scenario.start_turn()
        self.state = STATE_BATTLE
        self.show_message(f"四平保卫战开始！指挥官：{player.name}")

    def _start_auto_mode(self):
        player = create_player_panshi()
        self.scenario = SipingBattle(player)
        player.init_combat()
        self.auto_script = AutoPlayScript(self.scenario)
        self.scenario.start_turn()
        self._auto_prepare_turn()

    def _auto_prepare_turn(self):
        self.auto_cards_to_play = self.auto_script.pick_cards()

        narratives = {
            1: "1946年4月，国民党集结重兵进攻四平。\n东北民主联军奉命坚守。",
            2: "新一军先头部队抵达四平外围，\n运动防御战开始。",
            3: "马歇尔特使抵达调停，\n但战事仍在继续...",
            5: "国军主力逼近，\n四平保卫战进入城防阶段！",
            6: "东北局急电：\n\"死守四平，寸土必争！\"",
            8: "第52军增援抵达，\n指挥部开始考虑撤退...",
            10: "新六军主力直扑塔子山！\n四平保卫战进入最危急时刻！",
            12: "经过近一个月的浴血奋战，\n为保存有生力量...",
        }
        self.auto_phase_text = narratives.get(self.scenario.turn, f"回合 {self.scenario.turn}")

        plan = "  ".join(c.name for c in self.auto_cards_to_play) if self.auto_cards_to_play else "（无法出牌）"
        self.show_message(f"出牌计划: {plan}", 300)
        self.state = STATE_AUTO_WAIT

    def _auto_execute_cards(self):
        for card in self.auto_cards_to_play:
            if card in self.scenario.player.hand:
                target = self.auto_script.pick_target(self.scenario.enemies)
                ok, result = self.scenario.play_card(card, target)
                if ok:
                    self.add_float_text(f"{card.name}: {result}", R.BASE_W // 2, 400)

        self.auto_cards_to_play = []

        if self.auto_script.should_retreat():
            self.scenario.battle.battle_result = "retreat"
            self.scenario.game_over = True
            self.scenario.result = "retreat"
            self.state = STATE_GAME_OVER
            return

        self.show_message("敌方回合 — 按回车继续", 600)
        self.state = STATE_AUTO_ENEMY

    def _auto_next_turn(self):
        self.scenario.end_turn()
        if self.scenario.game_over:
            self.state = STATE_GAME_OVER
            return
        self.scenario.start_turn()
        self._auto_prepare_turn()

    def _play_card(self, card_idx, target):
        p = self.scenario.player
        card = p.hand[card_idx]
        ok, result = self.scenario.play_card(card_idx, target)
        if ok:
            self.show_message(f"{card.name}: {result}")
            if target and target in self.scenario.enemies:
                idx = self.scenario.enemies.index(target)
                if idx in self.enemy_rects:
                    er = self.enemy_rects[idx]
                    # 浮动文字用逻辑坐标
                    lx, _ = self._to_logical(er.centerx, er.y)
                    _, ly = self._to_logical(er.centerx, er.y)
                    self.add_float_text(result[:12], lx, ly)
        else:
            self.show_message(f"✕ {result}")

        if self.scenario.game_over:
            self.state = STATE_GAME_OVER

    def _end_player_turn(self):
        self.state = STATE_ENEMY_TURN
        self.scenario.end_turn()
        if self.scenario.game_over:
            self.state = STATE_GAME_OVER
            return
        self.scenario.start_turn()
        self.state = STATE_BATTLE
        self.show_message(f"回合 {self.scenario.turn} 开始 | 阶段 {self.scenario.phase}")

    # ══════════════════════════════════════
    #  更新
    # ══════════════════════════════════════

    def update(self):
        for ft in self.float_texts[:]:
            ft[2] -= 0.5
            ft[4] -= 1
            if ft[4] <= 0:
                self.float_texts.remove(ft)

        if self.message_timer > 0:
            self.message_timer -= 1

    # ══════════════════════════════════════
    #  渲染
    # ══════════════════════════════════════

    def render(self):
        if self.state == STATE_TITLE:
            self._render_title()
        elif self.state == STATE_CHARSEL:
            self._render_charsel()
        elif self.state == STATE_SETTINGS:
            self._render_settings()
        elif self.state in (STATE_BATTLE, STATE_TARGETING, STATE_ENEMY_TURN):
            self._render_battle()
        elif self.state == STATE_GAME_OVER:
            self._render_game_over()
        elif self.state in (STATE_AUTO_WAIT, STATE_AUTO_ENEMY, STATE_AUTO_PLAY):
            self._render_auto()
        pygame.display.flip()

    def _render_title(self):
        self.btn_rects = R.draw_title_screen(
            self.screen, self.screen_w, self.screen_h, self.hover_btn)

    def _render_charsel(self):
        self.btn_rects = R.draw_character_select(
            self.screen, self.screen_w, self.screen_h, self.hover_btn)

    def _render_settings(self):
        self.btn_rects = R.draw_settings_screen(
            self.screen, self.screen_w, self.screen_h, self.hover_btn,
            self.tmp_res_idx, self.tmp_scale_idx)

    def _render_battle(self):
        self.screen.fill(R.C_BG)

        s = self.scenario
        p = s.player

        bg = R.assets.get_background(s.phase, (self.screen_w, self.screen_h))
        if bg:
            self.screen.blit(bg, (0, 0))

        phase_names = {1: "运动防御", 2: "城防对峙", 3: "塔子山危机"}
        R.draw_text(self.screen, f"阶段{s.phase}: {phase_names.get(s.phase, '')}",
                    (10, 4), size=16, color=R.C_GOLD, anchor="topleft")

        self.enemy_rects = R.draw_enemies(self.screen, s.enemies, L_ENEMIES, self.hover_enemy)
        R.draw_player_panel(self.screen, p, s.phase, s.turn, L_PLAYER)
        R.draw_log_panel(self.screen, s.all_logs, L_LOG)

        # 手牌分隔线
        pygame.draw.line(self.screen, R.C_DARK_GRAY,
                         (0, R.S(L_HAND[1]) - 2), (self.screen_w, R.S(L_HAND[1]) - 2),
                         max(1, R.S(1)))

        sel = self.selected_card if self.state == STATE_TARGETING else -1
        self.card_rects = R.draw_hand(self.screen, p.hand, L_HAND,
                                      hover_idx=self.hover_card, selected_idx=sel)

        # 按钮
        self.btn_rects = []
        btn_y = L_BUTTONS[1]
        r1 = R.draw_button(self.screen, "结束回合 [E]",
                           (R.BASE_W - 170, btn_y, 150, 40),
                           color=(50, 80, 50), hover=(self.hover_btn == 0))
        self.btn_rects.append(r1)

        if p.can_retreat:
            r2 = R.draw_button(self.screen, "撤退 [R]",
                               (R.BASE_W - 340, btn_y, 150, 40),
                               color=(120, 50, 50), hover=(self.hover_btn == 1))
            self.btn_rects.append(r2)

        if self.state == STATE_TARGETING:
            R.draw_text(self.screen, "▶ 点击敌人选择攻击目标 ◀",
                        (R.BASE_W // 2, L_HAND[1] - 20), size=20,
                        color=R.C_YELLOW, anchor="center")

        self._render_float_texts()
        self._render_message()

        # 卡牌悬停提示
        if 0 <= self.hover_card < len(p.hand):
            card = p.hand[self.hover_card]
            mx, my = pygame.mouse.get_pos()
            tooltip = f"{card.name} ({card.card_type}/{card.cost}费)\n{card.description}"
            if card.tags:
                tooltip += f"\n标签: {', '.join(card.tags)}"
            R.draw_tooltip(self.screen, tooltip, (mx + R.S(15), my - R.S(60)))

    def _render_auto(self):
        self.screen.fill(R.C_BG)

        s = self.scenario
        p = s.player

        phase_names = {1: "运动防御", 2: "城防对峙", 3: "塔子山危机"}
        R.draw_text(self.screen, f"【史实演示】 阶段{s.phase}: {phase_names.get(s.phase, '')}",
                    (10, 4), size=16, color=R.C_CYAN, anchor="topleft")

        if self.auto_phase_text:
            for i, line in enumerate(self.auto_phase_text.split('\n')):
                R.draw_text(self.screen, line, (10, 28 + i * 24),
                            size=17, color=R.C_CYAN, anchor="topleft")

        self.enemy_rects = R.draw_enemies(self.screen, s.enemies, L_ENEMIES)
        R.draw_player_panel(self.screen, p, s.phase, s.turn, L_PLAYER)
        R.draw_log_panel(self.screen, s.all_logs, L_LOG)

        pygame.draw.line(self.screen, R.C_DARK_GRAY,
                         (0, R.S(L_HAND[1]) - 2), (self.screen_w, R.S(L_HAND[1]) - 2),
                         max(1, R.S(1)))
        R.draw_hand(self.screen, p.hand, L_HAND)

        if self.state == STATE_AUTO_WAIT and self.auto_cards_to_play:
            plan_y = L_HAND[1] - 30
            plan_text = "出牌计划: " + " → ".join(c.name for c in self.auto_cards_to_play)
            R.draw_text(self.screen, plan_text, (R.BASE_W // 2, plan_y),
                        size=17, color=R.C_GOLD, anchor="center", max_width=R.BASE_W - 40)

        if self.state == STATE_AUTO_WAIT:
            R.draw_text(self.screen, "按 回车 执行出牌",
                        (R.BASE_W // 2, R.BASE_H - 30), size=20,
                        color=R.C_GREEN, anchor="center")
        elif self.state == STATE_AUTO_ENEMY:
            R.draw_text(self.screen, "按 回车 进入下一回合",
                        (R.BASE_W // 2, R.BASE_H - 30), size=20,
                        color=R.C_ORANGE, anchor="center")

        self._render_float_texts()
        self._render_message()

    def _render_game_over(self):
        if self.scenario:
            self.screen.fill(R.C_BG)
            R.draw_enemies(self.screen, self.scenario.enemies, L_ENEMIES)
            R.draw_player_panel(self.screen, self.scenario.player,
                                self.scenario.phase, self.scenario.turn, L_PLAYER)
        else:
            self.screen.fill(R.C_BG)

        result = "defeat"
        if self.scenario:
            result = self.scenario.result or self.scenario.battle.battle_result or "defeat"
        R.draw_game_over(self.screen, result,
                         self.scenario.player if self.scenario else None,
                         self.screen_w, self.screen_h)

    def _render_float_texts(self):
        for text, lx, ly, color, timer in self.float_texts:
            R.draw_text(self.screen, text, (int(lx), int(ly)), size=20,
                        color=color, anchor="center")

    def _render_message(self):
        if self.message and self.message_timer > 0:
            alpha = min(180, self.message_timer * 4)
            msg_h = R.S(32)
            msg_y = R.S(L_HAND[1]) - msg_h - R.S(4)
            s = pygame.Surface((self.screen_w, msg_h), pygame.SRCALPHA)
            s.fill((0, 0, 0, alpha))
            self.screen.blit(s, (0, msg_y))
            R.draw_text(self.screen, self.message, (R.BASE_W // 2, L_HAND[1] - 20),
                        size=17, color=R.C_WHITE, anchor="center")


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
