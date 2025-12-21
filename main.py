# main.py
import datetime as dt
import threading
import traceback
import certifi

import requests

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label


# --- Твои константы (пока как ты просил) ---
AVG_INTERVAL_M7_DAYS = 365.0 / 15.0   # 1/15 года ≈ 24.33 дня
AVG_INTERVAL_M8_DAYS = 365.0          # раз в год


def safe_set_label_text(label: Label, text: str):
    # Обновление UI только из main-thread
    def _set(_dt):
        label.text = text
    Clock.schedule_once(_set, 0)


def format_percent(x: float) -> str:
    if x < 0:
        x = 0
    # не ограничиваем сверху, пусть видно сколько "перешло 100%"
    return f"{x:.1f}%"


class QuakeProbUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(18), spacing=dp(14), **kwargs)
        Window.clearcolor = (0, 0, 0, 1)

        self.title = Label(
            text="Глобальные землетрясения\nИндикатор времени (НЕ прогноз)",
            font_size=sp(22),
            halign="center",
            valign="middle",
            color=(1, 1, 1, 1),
            size_hint=(1, 0.20),
        )
        self.title.bind(size=lambda *_: setattr(self.title, "text_size", self.title.size))
        self.add_widget(self.title)

        self.result = Label(
            text="M7+: —\nM8+: —",
            font_size=sp(44),
            halign="center",
            valign="middle",
            color=(1, 1, 1, 1),
            size_hint=(1, 0.45),
        )
        self.result.bind(size=lambda *_: setattr(self.result, "text_size", self.result.size))
        self.add_widget(self.result)

        self.hint = Label(
            text="Проценты = (время с последнего события / средний исторический интервал) × 100%\n\nНажми кнопку для расчёта.",
            font_size=sp(16),
            halign="center",
            valign="middle",
            color=(0.8, 0.8, 0.8, 1),
            size_hint=(1, 0.20),
        )
        self.hint.bind(size=lambda *_: setattr(self.hint, "text_size", self.hint.size))
        self.add_widget(self.hint)

        self.btn = Button(
            text="Рассчитать\nна сегодня",
            font_size=sp(28),
            size_hint=(1, 0.15),
        )
        self.btn.bind(on_press=self.on_press)
        self.add_widget(self.btn)

    def on_press(self, *_):
        self.btn.disabled = True
        safe_set_label_text(self.hint, "Загрузка данных…")

        # Важно: requests в отдельном потоке
        t = threading.Thread(target=self.compute_thread, daemon=True)
        t.start()

    def compute_thread(self):
        try:
            # 1) Получаем последнее событие M7+ и M8+ (USGS)
            # Используем HTTPS (важно для Android).
            m7_time = self.get_last_event_time(minmag=7.0)
            m8_time = self.get_last_event_time(minmag=8.0)

            now = dt.datetime.utcnow()

            # 2) Считаем проценты
            days7 = (now - m7_time).total_seconds() / 86400.0
            days8 = (now - m8_time).total_seconds() / 86400.0

            p7 = (days7 / AVG_INTERVAL_M7_DAYS) * 100.0
            p8 = (days8 / AVG_INTERVAL_M8_DAYS) * 100.0

            text = f"M7+: {format_percent(p7)}\nM8+: {format_percent(p8)}"
            safe_set_label_text(self.result, text)

            # Подсказка/детали
            hint = (
                "Проценты = (время с последнего события / средний исторический интервал) × 100%\n\n"
                f"Последнее M7+: {m7_time.strftime('%Y-%m-%d %H:%M')} UTC\n"
                f"Последнее M8+: {m8_time.strftime('%Y-%m-%d %H:%M')} UTC\n"
                "Нажми кнопку для обновления."
            )
            safe_set_label_text(self.hint, hint)

        except Exception as e:
            # Покажем ошибку прямо на экране, чтобы больше не гадать
            err = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            safe_set_label_text(self.result, "Ошибка")
            safe_set_label_text(self.hint, "Поймали ошибку (скопируй текст ниже и пришли мне):\n\n" + err)

        finally:
            def _enable(_dt):
                self.btn.disabled = False
            Clock.schedule_once(_enable, 0)

    def get_last_event_time(self, minmag: float) -> dt.datetime:
        url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

        params = {
            "format": "geojson",
            "minmagnitude": str(minmag),
            "orderby": "time",
            "limit": "1",
        }

        # timeout обязателен, иначе может зависнуть
        r = requests.get(url, params=params, timeout=20,verify=where())
        r.raise_for_status()

        data = r.json()

        feats = data.get("features", [])
        if not feats:
            raise RuntimeError(f"USGS не вернул событий для minmag={minmag}")

        # time в миллисекундах
        t_ms = feats[0]["properties"]["time"]
        return dt.datetime.utcfromtimestamp(t_ms / 1000.0)


class QuakeProbApp(App):
    def build(self):
        return QuakeProbUI()


if __name__ == "__main__":
    QuakeProbApp().run()


