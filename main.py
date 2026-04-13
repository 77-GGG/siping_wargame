"""
解放战争·东北篇 ── 四平保卫战
主入口：手动战斗 + 史实自动演示
"""
import sys
import os

# 确保能找到同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenarios import SipingBattle, AutoPlayScript, create_player_leitong, create_player_panshi
from cards import create_all_cards
from ui import (clear_screen, show_title, show_character_select,
                render_battle_screen, render_log, render_game_over, prompt_action)


def select_target(scenario):
    """让玩家选择攻击目标"""
    alive = [e for e in scenario.enemies if e.is_alive()]
    if len(alive) <= 1:
        return alive[0] if alive else None
    print("  选择目标：")
    for i, e in enumerate(scenario.enemies):
        if e.is_alive():
            print(f"    [{i}] {e.name} HP:{e.hp}/{e.hp_max} 攻:{e.get_attack()}")
    while True:
        choice = input("  目标编号> ").strip()
        try:
            idx = int(choice)
            if 0 <= idx < len(scenario.enemies) and scenario.enemies[idx].is_alive():
                return scenario.enemies[idx]
        except ValueError:
            pass
        print("  无效选择，请重新输入")


def manual_mode():
    """手动战斗模式"""
    clear_screen()
    show_character_select()
    while True:
        choice = input("  选择指挥官 [1/2]> ").strip()
        if choice == '1':
            player = create_player_leitong()
            break
        elif choice == '2':
            player = create_player_panshi()
            break

    scenario = SipingBattle(player)
    player.init_combat()

    while not scenario.game_over:
        # 开始回合
        scenario.start_turn()

        # 战斗循环
        while True:
            clear_screen()
            print(render_battle_screen(scenario))
            print()
            recent_logs = scenario.get_recent_logs(6)
            print(render_log(recent_logs, 6))
            print()
            print(prompt_action(scenario))
            print()

            action = input("  > ").strip().lower()

            if action == 'e':
                # 结束回合
                break

            elif action == 'r' and player.can_retreat:
                print("  确定要主动撤退吗？ [y/n]")
                confirm = input("  > ").strip().lower()
                if confirm == 'y':
                    scenario.battle.battle_result = "retreat"
                    scenario.game_over = True
                    scenario.result = "retreat"
                    break

            elif action == 's':
                # 详细状态
                clear_screen()
                print(scenario.get_status())
                print()
                print(f"  已激活能力: {', '.join(player.abilities_active) or '无'}")
                print(f"  牌堆({len(player.draw_pile)}): {', '.join(c.short() for c in player.draw_pile[:5])}...")
                print(f"  弃牌({len(player.discard_pile)}): {', '.join(c.short() for c in player.discard_pile[:5])}...")
                input("\n  按回车返回...")

            elif action == 'l':
                # 战斗日志
                clear_screen()
                print(render_log(scenario.all_logs, 30))
                input("\n  按回车返回...")

            elif action == 'f' and player.flexibility > 0 and "灵活应变" in player.abilities_active:
                if not player.hand:
                    print("  无手牌可转换")
                    continue
                print("  选择要转换的手牌编号：")
                for i, c in enumerate(player.hand):
                    print(f"    [{i}] {c}")
                try:
                    idx = int(input("  > ").strip())
                    if 0 <= idx < len(player.hand):
                        old_card = player.hand[idx]
                        all_cards = create_all_cards()
                        same_cost = [c for c in all_cards.values()
                                     if c.cost == old_card.cost and c.name != old_card.name]
                        if same_cost:
                            import random
                            new_card = random.choice(same_cost).copy()
                            player.hand[idx] = new_card
                            player.flexibility -= 1
                            scenario.log(f"  灵活应变：{old_card.name} → {new_card.name}")
                except (ValueError, IndexError):
                    print("  无效输入")

            else:
                # 尝试打出卡牌
                try:
                    card_idx = int(action)
                    if 0 <= card_idx < len(player.hand):
                        card = player.hand[card_idx]
                        target = None
                        if card.card_type == "攻击":
                            target = select_target(scenario)
                        ok, result = scenario.play_card(card_idx, target)
                        if not ok:
                            print(f"  ✕ {result}")
                            input("  按回车继续...")
                    else:
                        print(f"  无效编号(0-{len(player.hand)-1})")
                        input("  按回车继续...")
                except ValueError:
                    print("  无效输入，输入数字选牌或 e 结束回合")
                    input("  按回车继续...")

        if scenario.game_over:
            break

        # 敌方回合
        scenario.end_turn()

    # 游戏结束
    clear_screen()
    print(render_game_over(scenario.result or scenario.battle.battle_result, player))
    print()
    print(render_log(scenario.get_recent_logs(10), 10))
    print()
    input("  按回车返回主菜单...")


def auto_mode():
    """史实自动演示模式"""
    clear_screen()
    print("""
  ══ 史实自动演示 ══

  本模式将按照1946年四平保卫战史实自动出牌。
  每回合出牌后需按回车确认才继续。

  使用磐石（基石型）指挥官，体现我军坚守四平的战略。
""")
    input("  按回车开始演示...")

    player = create_player_panshi()
    scenario = SipingBattle(player)
    player.init_combat()
    script = AutoPlayScript(scenario)

    # 开场叙事
    narratives = {
        1: "1946年4月，国民党集结重兵进攻四平。东北民主联军奉命坚守。",
        2: "新一军先头部队抵达四平外围，运动防御战开始。",
        3: "马歇尔特使抵达调停，但战事仍在继续...",
        4: "运动防御阶段接近尾声，城防工事加紧修筑。",
        5: "国军主力逼近，四平保卫战进入城防阶段！防线建立。",
        6: "东北局急电：\"死守四平，寸土必争！\"新六军前锋开始出现...",
        7: "战斗日趋激烈，双方反复争夺阵地。",
        8: "第52军增援抵达，敌军兵力进一步增强。指挥部开始考虑撤退...",
        9: "南线告急！本溪方向压力增大。",
        10: "新六军主力直扑塔子山！四平保卫战进入最危急时刻！",
        11: "塔子山争夺白热化，我军伤亡惨重但寸土不让。",
        12: "经过近一个月的浴血奋战，为保存有生力量，我军主动撤出四平...",
    }

    while not scenario.game_over:
        scenario.start_turn()

        clear_screen()
        # 叙事文本
        if scenario.turn in narratives:
            print(f"\n  📜 {narratives[scenario.turn]}")
            print()

        print(render_battle_screen(scenario))
        print()

        # AI选牌
        plays = script.pick_cards()
        if not plays:
            print("  （本回合无法出牌）")
        else:
            print(f"  本回合出牌计划({len(plays)}张)：")
            for c in plays:
                print(f"    → {c}")
            print()

        input("  按回车执行出牌...")

        # 依次打出
        for card in plays:
            if card in player.hand:
                target = script.pick_target(scenario.enemies)
                ok, result = scenario.play_card(card, target)
                if ok:
                    print(f"  ✓ {card.name}: {result}")

        print()
        print(render_log(scenario.get_recent_logs(5), 5))
        print()

        # 检查是否撤退
        if script.should_retreat():
            print("  ◇ 指挥部决定：战略撤退，保存有生力量。")
            scenario.battle.battle_result = "retreat"
            scenario.game_over = True
            scenario.result = "retreat"
            input("  按回车继续...")
            break

        input("  按回车进入敌方回合...")

        # 敌方行动
        scenario.end_turn()

        clear_screen()
        print(f"\n  ── 敌方行动结果 ──")
        print()
        print(render_log(scenario.get_recent_logs(8), 8))
        print()
        print(scenario.get_status())
        print()

        if scenario.game_over:
            break

        input("  按回车进入下一回合...")

    # 结局
    clear_screen()
    result = scenario.result or scenario.battle.battle_result or "defeat"
    print(render_game_over(result, player))
    print()

    # 历史结语
    if result == "retreat":
        print("""
  ══ 史实结语 ══
  1946年5月19日，东北民主联军在坚守四平一个月后主动撤出。
  虽然四平失守，但此战消耗了国军大量有生力量，
  为后来的夏季攻势和三下江南四保临江奠定了基础。

  毛泽东后来总结：\"让开大路，占领两厢\"
  \"以歼灭敌有生力量为主要目标，不以保守或夺取城市和地方为主要目标\"
""")
    elif result == "victory":
        print("""
  ══ 历史假设 ══
  在您的指挥下，四平保卫战取得了历史未能实现的胜利！
  这展示了集中兵力、各个击破的军事原则的威力。
""")
    else:
        print("""
  ══ 史实参考 ══
  四平保卫战中，我军面对数倍优势之敌，
  英勇奋战近一个月。虽最终失守，但打出了军威。
""")

    input("  按回车返回主菜单...")


def main():
    while True:
        show_title()
        choice = input("  请选择> ").strip().lower()
        if choice == '1':
            manual_mode()
        elif choice == '2':
            auto_mode()
        elif choice == 'q':
            print("\n  再见！\n")
            sys.exit(0)
        else:
            print("  无效选择")


if __name__ == "__main__":
    main()
