import threading
from datetime import datetime, timedelta, timezone

import requests

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label


# ===============================
# НАСТРОЙКИ И КОНСТАНТЫ
# ===============================

USGS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
HTTP_TIMEOUT = 20

# Усреднённые глобальные интервалы
# M7+ : ~15 событий в год  ->  1/15 года
# M8+ : ~1 событие в год   ->  1 год
CONSTANTS = {
    "calculated_at": "2025-12-20",
    "model": "global long-term average (simplified)",
    "m7_mean_sec": (1.0 / 15.0) * 365.2425 * 24 * 3600,
    "m8_mean_sec": 1.0 * 365.2425 * 24 * 3600,
}


# ===============================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===============================

def dt_to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def fetch_last_event_time(min_mag: float) -> datetime | None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365 * 120)

    params = {
        "format": "geojson",
        "starttime": dt_to_iso(start),
        "endtime": dt_to_iso(now),
        "minmagnitude": str(min_mag),
        "orderby": "time-desc",
        "limit": "1",
    }

    r = requests.get(USGS_API, params=params, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    feats = data.get("features", [])
    if not feats:
        return None

    t_ms = feats[0]["properties"].get("time")
    return datetime.fromtimestamp(t_ms / 1000.0, tz=timezone.utc)


def format_duration(seconds: float) -> str:
    minutes = int(seconds // 60)
    hours = minutes // 60
    days = hours // 24
    return f"{days}д {hours % 24}ч"


def color_for_percent(p: float):
    """
    Цвет фона по прогрессу.
    Это НЕ опасность, а индикатор времени.
    """
    if p < 70:
        return (0.2, 0.75, 0.2, 1)   # зелёный
    elif p < 130:
        return (1.0, 0.8, 0.2, 1)    # жёлтый
    else:
        return (0.85, 0.2, 0.2, 1)   # красный


# ===============================
# UI
# ===============================

class QuakeUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical",
            padding=dp(16),
            spacing=dp(16),
            **kwargs
        )

        self.title = Label(
            text=(
                "Глобальные землетрясения\n"
                "Индикатор времени (НЕ прогноз)"
            ),
            font_size="22sp",
            halign="center",
            valign="middle",
            size_hint=(1, 0.18),
        )
        self.title.bind(size=lambda *a: setattr(self.title, "text_size", self.title.size))

        self.big = Label(
            text="M7+: —\nM8+: —",
            font_size="44sp",
            halign="center",
            valign="middle",
            size_hint=(1, 0.34),
        )
        self.big.bind(size=lambda *a: setattr(self.big, "text_size", self.big.size))

        self.details = Label(
            text=(
                "Проценты =\n"
                "(время с последнего события /\n"
                "средний исторический интервал) × 100%\n\n"
                "Нажми кнопку для расчёта."
            ),
            font_size="18sp",
            halign="center",
            valign="middle",
            size_hint=(1, 0.33),
        )
        self.details.bind(size=lambda *a: setattr(self.details, "text_size", self.details.size))

        self.btn = Button(
            text="Рассчитать\nна сегодня",
            font_size="26sp",
            size_hint=(1, 0.15),
        )
        self.btn.bind(on_press=self.on_press)

        self.add_widget(self.title)
        self.add_widget(self.big)
        self.add_widget(self.details)
        self.add_widget(self.btn)

    def on_press(self, *_):
        self.btn.disabled = True
        self.details.text = "Запрашиваю данные USGS…"
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            now = datetime.now(timezone.utc)

            last7 = fetch_last_event_time(7.0)
            last8 = fetch_last_event_time(8.0)

            if not last7 or not last8:
                raise RuntimeError("Не удалось получить данные.")

            elapsed7 = (now - last7).total_seconds()
            elapsed8 = (now - last8).total_seconds()

            p7 = (elapsed7 / CONSTANTS["m7_mean_sec"]) * 100.0
            p8 = (elapsed8 / CONSTANTS["m8_mean_sec"]) * 100.0

            big_text = f"M7+: {p7:.1f}%\nM8+: {p8:.1f}%"

            worst = max(p7, p8)
            bg_color = color_for_percent(worst)

            details_text = (
                "Это НЕ вероятность.\n"
                "Это отношение прошедшего времени\n"
                "к среднему интервалу.\n\n"
                f"M7+ прошло: {format_duration(elapsed7)}\n"
                f"M8+ прошло: {format_duration(elapsed8)}\n\n"
                "Зелёный < 70%\n"
                "Жёлтый 70–130%\n"
                "Красный > 130%"
            )

            Clock.schedule_once(
                lambda dt: self._show(big_text, details_text, bg_color),
                0
            )

        except Exception as e:
            Clock.schedule_once(lambda dt: self._error(str(e)), 0)

    def _show(self, big_text, details_text, bg_color):
        Window.clearcolor = bg_color
        self.big.text = big_text
        self.details.text = details_text
        self.btn.disabled = False

    def _error(self, msg):
        self.details.text = "Ошибка:\n" + msg
        self.btn.disabled = False


class QuakeApp(App):
    def build(self):
        Window.clearcolor = (0, 0, 0, 1)
        return QuakeUI()


if __name__ == "__main__":
    QuakeApp().run()
