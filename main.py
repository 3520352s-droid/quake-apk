# main.py
# QuakeProb — индикатор времени с последнего глобального землетрясения (НЕ прогноз)
# Проценты = (время с последнего события / средний исторический интервал) × 100%

import datetime as dt
from threading import Thread

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label


# -----------------------------
# НАСТРОЙКИ (константы)
# -----------------------------

# Ты просил: M7+ ~ раз в 1/15 года, M8+ ~ раз в год
YEAR_DAYS = 365.25
AVG_INTERVAL_DAYS_M7 = YEAR_DAYS / 15.0     # ≈ 24.35 дня
AVG_INTERVAL_DAYS_M8 = YEAR_DAYS * 1.0      # ≈ 365.25 дня

# Пороги для цветовой индикации (можешь менять)
# <60% зелёный, 60–100% жёлтый, >100% красный
def percent_to_color(p: float):
    if p < 60:
        return (0.15, 0.85, 0.25, 1)  # green
    if p < 100:
        return (0.95, 0.75, 0.15, 1)  # yellow/orange
    return (0.95, 0.20, 0.20, 1)      # red


# -----------------------------
# USGS (последнее событие)
# -----------------------------

def fetch_last_quake_time_utc(min_magnitude: float) -> dt.datetime:
    """
    Возвращает время последнего события >= min_magnitude (UTC) через USGS GeoJSON.
    """
    # USGS endpoint: latest event for magnitude >= X
    # orderby=time&limit=1 — берём самое свежее
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    params = {
        "format": "geojson",
        "minmagnitude": str(min_magnitude),
        "orderby": "time",
        "limit": "1",
    }

    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    features = data.get("features", [])
    if not features:
        raise RuntimeError(f"USGS не вернул событий для M{min_magnitude}+ (пусто)")

    props = features[0].get("properties", {})
    t_ms = props.get("time")
    if t_ms is None:
        raise RuntimeError("USGS ответ без поля properties.time")

    # time приходит в миллисекундах unix epoch
    t = dt.datetime.fromtimestamp(t_ms / 1000.0, tz=dt.timezone.utc)
    return t


def compute_percent_since(last_time_utc: dt.datetime, avg_interval_days: float) -> float:
    now = dt.datetime.now(dt.timezone.utc)
    elapsed = now - last_time_utc
    elapsed_days = elapsed.total_seconds() / 86400.0
    return (elapsed_days / avg_interval_days) * 100.0


# -----------------------------
# UI
# -----------------------------

class QuakeProbUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(16), spacing=dp(12), **kwargs)
        Window.clearcolor = (0, 0, 0, 1)

        # Заголовок
        self.title = Label(
            text="Глобальные землетрясения\nИндикатор времени (НЕ прогноз)",
            halign="center",
            valign="middle",
            font_size="22sp",
            color=(1, 1, 1, 1),
            size_hint=(1, 0.18),
        )
        self.title.bind(size=self._sync_text)
        self.add_widget(self.title)

        # Большие значения
        self.m7_label = Label(
            text="M7+: —",
            halign="center",
            valign="middle",
            font_size="56sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(1, 0.14),
        )
        self.m7_label.bind(size=self._sync_text)
        self.add_widget(self.m7_label)

        self.m8_label = Label(
            text="M8+: —",
            halign="center",
            valign="middle",
            font_size="56sp",
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(1, 0.14),
        )
        self.m8_label.bind(size=self._sync_text)
        self.add_widget(self.m8_label)

        # Пояснение
        self.help_label = Label(
            text=(
                "Проценты =\n"
                "(время с последнего события /\n"
                "средний исторический интервал) × 100%\n\n"
                "Нажми кнопку для расчёта."
            ),
            halign="center",
            valign="middle",
            font_size="18sp",
            color=(0.85, 0.85, 0.85, 1),
            size_hint=(1, 0.28),
        )
        self.help_label.bind(size=self._sync_text)
        self.add_widget(self.help_label)

        # Кнопка
        self.btn = Button(
            text="Рассчитать\nна сегодня",
            font_size="28sp",
            size_hint=(1, 0.26),
            background_normal="",
            background_color=(0.35, 0.35, 0.35, 1),
            color=(1, 1, 1, 1),
        )
        self.btn.bind(on_release=self.on_press)
        self.add_widget(self.btn)

        # Статус
        self.status = Label(
            text="",
            halign="center",
            valign="middle",
            font_size="14sp",
            color=(0.7, 0.7, 0.7, 1),
            size_hint=(1, 0.08),
        )
        self.status.bind(size=self._sync_text)
        self.add_widget(self.status)

    def _sync_text(self, label, _size):
        label.text_size = label.size

    def on_press(self, *_):
        # ВАЖНО: запросы и расчёты — в отдельном потоке, иначе Android часто «убивает» приложение.
        self.btn.disabled = True
        self.status.text = "Считаю…"
        Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            last_m7 = fetch_last_quake_time_utc(7.0)
            last_m8 = fetch_last_quake_time_utc(8.0)

            p7 = compute_percent_since(last_m7, AVG_INTERVAL_DAYS_M7)
            p8 = compute_percent_since(last_m8, AVG_INTERVAL_DAYS_M8)

            # Передаём результат в UI-поток
            Clock.schedule_once(lambda dt_: self._update_ui(p7, p8, last_m7, last_m8), 0)

        except Exception as e:
            Clock.schedule_once(lambda dt_: self._show_error(str(e)), 0)

    def _update_ui(self, p7, p8, last_m7, last_m8):
        # Округление
        p7_show = round(p7, 1)
        p8_show = round(p8, 1)

        self.m7_label.text = f"M7+: {p7_show}%"
        self.m8_label.text = f"M8+: {p8_show}%"

        self.m7_label.color = percent_to_color(p7)
        self.m8_label.color = percent_to_color(p8)

        # Покажем дату последнего события (UTC) маленьким текстом
        self.status.text = (
            f"Последнее M7+ (UTC): {last_m7.strftime('%Y-%m-%d %H:%M')}\n"
            f"Последнее M8+ (UTC): {last_m8.strftime('%Y-%m-%d %H:%M')}"
        )

        self.btn.disabled = False

    def _show_error(self, msg: str):
        self.m7_label.text = "M7+: ошибка"
        self.m8_label.text = "M8+: ошибка"
        self.m7_label.color = (1, 0.3, 0.3, 1)
        self.m8_label.color = (1, 0.3, 0.3, 1)

        # Частые причины: нет интернета, USGS временно недоступен
        self.status.text = "Ошибка: " + msg
        self.btn.disabled = False


class QuakeProbApp(App):
    def build(self):
        self.title = "QuakeProb"
        return QuakeProbUI()


if __name__ == "__main__":
    QuakeProbApp().run()
