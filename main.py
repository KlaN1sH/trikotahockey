# =============================================================================
# ЧАСТЬ 1/3 — ИМПОРТЫ, КОНСТАНТЫ, СОХРАНЕНИЯ, ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ
# =============================================================================

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.image import Image
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.vector import Vector
from kivy.properties import ListProperty, NumericProperty, ObjectProperty, BooleanProperty
from kivy.core.audio import SoundLoader
from kivy.animation import Animation
from random import choice, uniform, randint
from collections import namedtuple
import json
import os

# Мобильные оптимизации
from kivy.config import Config
Config.set('graphics', 'multisamples', '0') # отключаем антиалиасинг
Config.set('graphics', 'maxfps', '60')

# ────────────────────────────────────────────────
# Данные персонажей
# ────────────────────────────────────────────────

Cat = namedtuple("Cat", ["name", "color", "radius", "hit_mult", "ability", "wins_needed"])

ALL_CATS = [
    Cat("Коржик", (1.00, 0.55, 0.00), 34, 1.65, None, 0),
    Cat("Карамелька", (1.00, 0.39, 0.71), 24, 1.75, None, 0),
    Cat("Компот", (0.00, 0.71, 1.00), 48, 0.65, None, 0),
    Cat("Горчица", (0.71, 0.00, 1.00), 43, 1.35, None, 10),
    Cat("Сажик", (0.39, 1.00, 0.39), 26, 1.25, "freeze", 25),
    Cat("Лапочка", (1.00, 0.78, 0.00), 45, 0.75, "remove", 30),
    Cat("Нудик", (0.78, 0.78, 0.78), 32, 0.85, "nudik", 50),
    Cat("Гоня", (1.00, 0.84, 0.00), 28, 1.40, "invade", 100),
]

SAVE_FILE = "saves.json"
total_global_wins = 0
unlocked_cats = ["Коржик", "Карамелька", "Компот"]

def load_saves():
    global total_global_wins, unlocked_cats
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                total_global_wins = d.get("wins", 0)
                unlocked_cats = d.get("unlocked", ["Коржик", "Карамелька", "Компот"])
        except Exception:
            pass

def save_saves():
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump({"wins": total_global_wins, "unlocked": unlocked_cats}, f, ensure_ascii=False)

# ────────────────────────────────────────────────
# Вспомогательные классы
# ────────────────────────────────────────────────

class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = uniform(-5, 5)
        self.vy = uniform(-5, 5)
        self.life = randint(12, 28)
        self.color = (1, uniform(0.55, 1), uniform(0, 0.45))

class Puck(FloatLayout):
    velocity = ListProperty([0, 0])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (44, 44)
        with self.canvas:
            Color(0.96, 0.96, 1, 0.98)
            self.ellipse = Ellipse(pos=self.pos, size=self.size)

    def on_pos(self, *args):
        self.ellipse.pos = self.pos

class Mallet(FloatLayout):
    cat = ObjectProperty(None)
    color = ListProperty([1,1,1,1])
    active = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (96, 96)
        with self.canvas.before:
            Color(*self.color)
            self.ellipse = Ellipse(size=(60, 60))
        self.bind(pos=self.update_graphics, color=self.update_graphics)

    def update_graphics(self, *args):
        r = self.cat.radius * 2
        self.ellipse.pos = (self.center_x - r/2, self.center_y - r/2)
        self.ellipse.size = (r, r)
 # =============================================================================
# ЧАСТЬ 2/3 — ОСНОВНОЙ КЛАСС ИГРЫ (Game)
# =============================================================================

class Game(FloatLayout):
    score_p = NumericProperty(0)
    score_ai = NumericProperty(0)
    WIN_TO = 5

    freeze_end = NumericProperty(0)
    remove_end = NumericProperty(0)
    remove_used = BooleanProperty(False)
    invade_end = NumericProperty(0)
    nudik_next = NumericProperty(0)

    particles = []
    MAX_PARTICLES = 45
    frame_counter = 0

    is_creator_mode = BooleanProperty(False)

    snd_hit = None
    snd_goal = None
    snd_siren = None
    snd_power = None
    bg_music = None

    def __init__(self, player_cat, **kwargs):
        super().__init__(**kwargs)
        load_saves()

        # Фон площадки
        with self.canvas.before:
            Color(0.02, 0.04, 0.12, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg)

        # Объекты
        self.player = Mallet(cat=player_cat, pos=(self.width * 0.18, self.height / 2 - player_cat.radius))
        ai_cat = choice(ALL_CATS) # полностью рандомный выбор врага каждый раз
        self.opponent = Mallet(cat=ai_cat, pos=(self.width * 0.82 - ai_cat.radius * 2, self.height / 2 - ai_cat.radius))
        self.puck = Puck(pos=(self.center_x - 22, self.center_y - 22))

        self.add_widget(self.player)
        self.add_widget(self.opponent)
        self.add_widget(self.puck)

        self.score_lbl = Label(text="0 : 0", font_size='70sp', color=(1,1,1,1),
                               pos_hint={'center_x':0.5, 'top':0.96})
        self.msg_lbl = Label(text="", font_size='40sp', color=(1,0.94,0.35,1),
                             pos_hint={'center_x':0.5, 'center_y':0.55})
        self.add_widget(self.score_lbl)
        self.add_widget(self.msg_lbl)

        # Звуки
        self.snd_hit = SoundLoader.load('hit.wav')
        self.snd_goal = SoundLoader.load('goal.wav')
        self.snd_siren = SoundLoader.load('siren_goal.wav') # сирена гола
        self.snd_power = SoundLoader.load('power.wav')

        self.bg_music = SoundLoader.load('trikota_theme.mp3')
        if self.bg_music:
            self.bg_music.loop = True
            self.bg_music.volume = 0.65
            self.bg_music.play()

        self.touch_start_time = 0
        Clock.schedule_interval(self.update, 1/60.0)
        Clock.schedule_once(self.show_instruction, 0.4)

    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def show_instruction(self, dt):
        instr = (
            "Привет, мой чемпион! ❤️ Я — папа Котя!\n\n"
            "Левый палец — твой котёнок.\n"
            "Долгий тап (>0.6 сек) = суперсила!\n\n"
            "Суперсилы:\n"
            "• Сажик — замораживает Врага на 3 секунды\n"
            "• Лапочка — убирает Врага с поля на 3 секунды (1 раз за игру)\n"
            "• Гоня — ты можешь бегать по всей половине поля 5 секунд\n"
            "• Нудик — каждые \~12 сек может телепортировать Врага в центр\n\n"
            "Игра до 5 голов. Удачи!"
        )
        self.msg_lbl.text = instr
        Clock.schedule_once(self.show_username_input, 12.5)

    def show_username_input(self, dt):
        self.msg_lbl.text = ""
        self.username_input = TextInput(
            hint_text="Введи своё имя",
            multiline=False,
            font_size='38sp',
            size_hint=(0.7, 0.12),
            pos_hint={'center_x':0.5, 'center_y':0.55},
            background_color=(0.95,0.95,1,0.9)
        )
        self.add_widget(self.username_input)

        btn = Button(text="Начать", size_hint=(0.4,0.12), pos_hint={'center_x':0.5, 'center_y':0.38})
        btn.bind(on_press=self.check_username)
        self.add_widget(btn)

    def check_username(self, instance):
        name = self.username_input.text.strip().upper()
        if name == "REIMON":
            # Запрос пароля
            self.remove_widget(self.username_input)
            self.remove_widget(instance)
            self.password_input = TextInput(hint_text="Пароль", password=True, multiline=False, font_size='38sp',
                                            size_hint=(0.7,0.12), pos_hint={'center_x':0.5, 'center_y':0.55})
            self.add_widget(self.password_input)

            btn = Button(text="Войти", size_hint=(0.4,0.12), pos_hint={'center_x':0.5, 'center_y':0.38})
            btn.bind(on_press=self.check_password)
            self.add_widget(btn)
        else:
            self.start_game(name)

    def check_password(self, instance):
        if self.password_input.text.strip() == "Netparolya1":
            global unlocked_cats
            unlocked_cats = [c.name for c in ALL_CATS]
            save_saves()
            self.is_creator_mode = True
            self.msg_lbl.text = "Добро пожаловать, Создатель!"
            Clock.schedule_once(lambda dt: self.start_game("Создатель"), 3)
        else:
            self.msg_lbl.text = "Неверный пароль"
            Clock.schedule_once(lambda dt: setattr(self.msg_lbl, 'text', ''), 2.5)

    def start_game(self, username):
        for w in self.children[:]:
            if isinstance(w, (TextInput, Button)) and w not in [self.score_lbl, self.msg_lbl]:
                self.remove_widget(w)
        self.msg_lbl.text = f"Добро пожаловать, {username}!"
        Clock.schedule_once(lambda dt: setattr(self.msg_lbl, 'text', ''), 3)

    def on_touch_down(self, touch):
        self.touch_start_time = time()
        if touch.x < self.width / 2:
            self.player.center = touch.pos
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.x < self.width / 2:
            self.player.center = touch.pos
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        hold_time = time() - self.touch_start_time if self.touch_start_time else 0
        if hold_time > 0.58 and touch.x < self.width / 2:
            self.activate_ability()
        self.touch_start_time = 0
        return super().on_touch_up(touch)

    def activate_ability(self):
        ab = self.player.cat.ability
        if not ab: return
        now = Clock.get_boottime()
        activated = False
        if ab == "freeze" and now > self.freeze_end:
            self.freeze_end = now + 3.2; activated = True
        elif ab == "remove" and not self.remove_used:
            self.remove_end = now + 3.2; self.remove_used = True; activated = True
        elif ab == "invade" and now > self.invade_end:
            self.invade_end = now + 5.1; activated = True
        if activated and self.snd_power: self.snd_power.play()

    def update(self, dt):
        if dt > 0.1: dt = 0.1
        self.frame_counter += 1
        now = Clock.get_boottime()

        self.puck.pos = Vector(*self.puck.velocity) * dt * 60 + self.puck.pos
        self.puck.velocity[0] *= 0.983
        self.puck.velocity[1] *= 0.983

        if self.puck.y < 0 or self.puck.y > self.height - self.puck.height:
            self.puck.velocity[1] *= -0.89
            self.puck.y = max(0, min(self.height - self.puck.height, self.puck.y))

        half = self.height / 2
        gz = 105
        goal = None
        if self.puck.x < 65:
            if abs(self.puck.center_y - half) < gz: goal = "ai"
            else: self.puck.velocity[0] = abs(self.puck.velocity[0]) * 0.77
        elif self.puck.x > self.width - 65:
            if abs(self.puck.center_y - half) < gz: goal = "player"
            else: self.puck.velocity[0] = -abs(self.puck.velocity[0]) * 0.77

        if goal:
            if goal == "player": self.score_p += 1
            else: self.score_ai += 1
            if self.snd_siren: self.snd_siren.play()
            elif self.snd_goal: self.snd_goal.play()
            self.msg_lbl.text = "ГОЛ ЗАБИТ, НО ВСЁ НЕ ЗАКОНЧЕНО!"
            Clock.schedule_once(lambda dt: setattr(self.msg_lbl, 'text', ''), 2.8)
            self.reset_round()
            self.score_lbl.text = f"{self.score_p} : {self.score_ai}"

            if self.score_p >= self.WIN_TO or self.score_ai >= self.WIN_TO:
                global total_global_wins
                total_global_wins += 1
                save_saves()
                winner = self.player.cat.name if self.score_p >= self.WIN_TO else self.opponent.cat.name
                self.parent.clear_widgets()
                self.parent.add_widget(EndScreen(winner_name=winner, is_win=(self.score_p >= self.WIN_TO)))
                return

        # Столкновения + звук + частицы
        for mallet in [self.player, self.opponent]:
            if not mallet.active: continue
            dx = self.puck.center_x - mallet.center_x
            dy = self.puck.center_y - mallet.center_y
            dist_sq = dx*dx + dy*dy
            rsum = 22 + mallet.cat.radius
            if dist_sq < rsum*rsum:
                dist = max(0.8, dist_sq**0.5)
                nx, ny = dx/dist, dy/dist
                power = 12.2 if mallet == self.player else 8.1
                power *= mallet.cat.hit_mult
                self.puck.velocity = [nx*power + uniform(-1.3,1.3), ny*power + uniform(-1.3,1.3)]
                if self.snd_hit: self.snd_hit.play()
                if len(self.particles) < self.MAX_PARTICLES:
                    for _ in range(8): self.particles.append(Particle(self.puck.center_x, self.puck.center_y))

        # Частицы (каждый 2-й кадр)
        if self.frame_counter % 2 == 0:
            for p in self.particles[:]:
                p.life -= 1
                if p.life <= 0:
                    self.particles.remove(p)
                    continue
                p.x += p.vx * dt * 60
                p.y += p.vy * dt * 60
                p.vx *= 0.96
                p.vy *= 0.96
                with self.canvas.after:
                    Color(*p.color, p.life / 30.0)
                    Ellipse(pos=(p.x-3, p.y-3), size=(6,6))

        # ИИ
        ai_mult = 0.28 if now < self.freeze_end else 1.0
        target_y = self.puck.center_y + self.puck.velocity[1] * 13.5
        self.opponent.y += (target_y - self.opponent.y) * 0.095 * ai_mult * 60 * dt

        invade_active = now < self.invade_end
        player_half_limit = self.width - 90 if invade_active else self.width / 2 - 70
        self.player.x = max(35, min(player_half_limit, self.player.x))
        self.player.y = max(35, min(self.height - 110, self.player.y))

        self.opponent.x = max(self.width / 2 + 15, min(self.width - 110, self.opponent.x))
        self.opponent.y = max(35, min(self.height - 110, self.opponent.y))

        if self.player.cat.ability == "nudik" and now > self.nudik_next:
            if randint(1, 100) < 38:
                self.opponent.center = [self.width/2 + 90, self.height/2]
            self.nudik_next = now + 11.5

        self.opponent.active = now >= self.remove_end

    def reset_round(self):
        self.puck.pos = [self.center_x - 22, self.center_y - 22]
        self.puck.velocity = [0, 0]
        self.player.pos = [self.width*0.18, self.center_y - self.player.cat.radius]
        self.opponent.pos = [self.width*0.82 - self.opponent.cat.radius*2, self.center_y - self.opponent.cat.radius]

    def on_size(self, *args):
        if hasattr(self, 'puck'):
            self.reset_round()
# =============================================================================
# ЧАСТЬ 3/3 — МЕНЮ, НАГРАДЫ, ЭКРАН ПОБЕДЫ/ПОРАЖЕНИЯ, НАСТРОЙКИ, ЗАПУСК
# =============================================================================

class EndScreen(FloatLayout):
    def __init__(self, winner_name, is_win=True, **kwargs):
        super().__init__(**kwargs)
        color = (0.3,1,0.3,1) if is_win else (1,0.4,0.4,1)
        txt = "ПОБЕДА!" if is_win else "ПОРАЖЕНИЕ"
        Label(text=f"{txt}\n{winner_name}", font_size='88sp', color=color,
              pos_hint={'center_x':0.5, 'center_y':0.68})

        winner_cat = Image(source='koty_win.png' if is_win else 'koty_lose.png',
                           size_hint=(0.4,0.4), pos_hint={'center_x':0.5, 'center_y':0.4})
        self.add_widget(winner_cat)

        anim = Animation(size_hint=(0.55,0.55), rotation=720 if is_win else -360,
                         duration=2.5, t='out_bounce') + Animation(size_hint=(0.4,0.4), rotation=0, duration=1)
        anim.start(winner_cat)

        for i in range(12):
            spark = Label(text="🎉" if is_win else "😿", font_size=40,
                          pos_hint={'center_x': uniform(0.1,0.9), 'center_y': uniform(0.2,0.6)})
            self.add_widget(spark)
            a = Animation(pos_hint={'center_y': uniform(0.9,1.1)}, opacity=0, duration=3 + i*0.2)
            a.start(spark)

        btn = Button(text="В меню", size_hint=(0.5,0.13), pos_hint={'center_x':0.5, 'center_y':0.15}, font_size='50sp')
        btn.bind(on_press=lambda x: self.parent.add_widget(Menu()))
        self.add_widget(btn)

class RewardsScreen(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        load_saves()

        Label(text="🏆 НАГРАДЫ И ПРОГРЕСС", font_size='55sp', pos_hint={'center_x':0.5, 'top':0.95})

        y = 0.82
        for cat in ALL_CATS:
            unlocked = cat.name in unlocked_cats
            status = "✅ Разблокирован" if unlocked else f"🔒 Нужно {cat.wins_needed} побед"
            color = (0.3,1,0.3,1) if unlocked else (1,0.6,0.3,1)
            Label(text=f"{cat.name} — {status}", font_size='32sp', color=color,
                  pos_hint={'center_x':0.5, 'top':y})
            y -= 0.11

        Label(text=f"Всего побед: {total_global_wins}", font_size='40sp', pos_hint={'center_x':0.5, 'top':0.2})

        btn = Button(text="← Назад в меню", size_hint=(0.5,0.12), pos_hint={'center_x':0.5, 'top':0.1})
        btn.bind(on_press=lambda x: self.parent.add_widget(Menu()))
        self.add_widget(btn)

class SettingsScreen(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Label(text="Настройки", font_size='65sp', pos_hint={'center_x':0.5, 'top':0.9})
        Label(text="Громкость музыки", font_size='36sp', pos_hint={'center_x':0.5, 'top':0.72})
        sl = Slider(min=0, max=1, value=0.65, size_hint=(0.8,0.08), pos_hint={'center_x':0.5, 'top':0.62})
        sl.bind(value=self.change_vol)
        self.add_widget(sl)
        back = Button(text="← Назад", size_hint=(0.4,0.12), pos_hint={'center_x':0.5, 'top':0.4})
        back.bind(on_press=lambda x: self.parent.add_widget(Menu()))
        self.add_widget(back)

    def change_vol(self, instance, val):
        if Game.bg_music:
            Game.bg_music.volume = val

class Menu(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        load_saves()

        Label(text="ТРИ КОТА\nАЭРОХОККЕЙ", font_size='72sp', color=(1,0.95,0.45,1), pos_hint={'center_x':0.5, 'top':0.92})
        Label(text=f"Всего побед: {total_global_wins}", font_size='34sp', pos_hint={'center_x':0.5, 'top':0.78})

        y = 0.64
        for cat in ALL_CATS:
            unlocked = cat.name in unlocked_cats
            btn = Button(
                text=cat.name if unlocked else f"🔒 {cat.name}",
                size_hint=(0.44, None), height=110,
                pos_hint={'center_x':0.5, 'top':y},
                font_size='42sp',
                background_color=(*cat.color, 0.95) if unlocked else (0.35,0.35,0.35,0.8),
                disabled=not unlocked
            )
            btn.cat = cat
            btn.bind(on_press=self.start_game)
            self.add_widget(btn)
            y -= 0.155

        rewards_btn = Button(text="🏆 Награды", size_hint=(0.35,0.1), pos_hint={'center_x':0.3, 'top':0.18})
        rewards_btn.bind(on_press=lambda x: self.open_rewards())
        self.add_widget(rewards_btn)

        sett_btn = Button(text="🎵 Настройки", size_hint=(0.35,0.1), pos_hint={'center_x':0.7, 'top':0.18})
        sett_btn.bind(on_press=lambda x: self.open_settings())
        self.add_widget(sett_btn)

    def start_game(self, btn):
        self.parent.clear_widgets()
        game = Game(player_cat=btn.cat)
        self.parent.add_widget(game)

    def open_rewards(self):
        self.parent.clear_widgets()
        self.parent.add_widget(RewardsScreen())

    def open_settings(self):
        self.parent.clear_widgets()
        self.parent.add_widget(SettingsScreen())

class TriKotaHockeyApp(App):
    def build(self):
        Window.clearcolor = (0.015, 0.04, 0.16, 1)
        return Menu()

if __name__ == '__main__':
    TriKotaHockeyApp().run()