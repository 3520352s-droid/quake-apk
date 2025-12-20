# main.py
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


USGS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
HTTP_TIMEOUT = 25

# ВСТАВЬ СЮДА СВОИ КОНСТАНТЫ (из compute_constants.py):
CONSTANTS = {
    "calculated_at": "2025-12-20",
    "years_back": 100,
    "m7_mean_sec": 0.0,  # <-- сюда вставится число
    "m8_mean_sec": 0.0,  # <-- сюда вставится число
}


def dt_to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def fetch_last_event_time(min_mag: float) -> datetime | None:
    # Берём период чуть шире 100 лет, чтобы точно захватить "последнее"
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365 * (CONSTANTS.get("years_back", 100) + 1))

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
    t_ms = feats[0].get("properties", {}).get("time")
    if t_ms is None:
        return None
    return datetime.fromtimestamp(t_ms / 1000.0, tz=timezone.utc)


def format_duration(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    mins = int(seconds // 60)
    hours = mins // 60
    days = hours // 24
    hours %= 24
    mins %= 60
    return f"{days}д {hours}ч {mins}м"


def days_from_seconds(seconds: float) -> float:
    return seconds / 86400.0


class QuakeUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(16), spacing=dp(16), **kwargs)

        self.title = Label(
            text=(
                "Quake progress (M7+ / M8+)\n"
                f"Константы рассчитаны: {CONSTANTS.get('calculated_at', '?')} "
                f"(период: {CONSTANTS.get('years_back', 100)} лет)"
            ),
            halign="center",
            valign="middle",
            font_size="22sp",
            size_hint=(1, 0.20),
        )
        self.title.bind(size=lambda *a: setattr(self.title, "text_size", self.title.size))

        # Большие цифры в центре
        self.big = Label(
            text="M7+: —\nM8+: —",
            halign="center",
            valign="middle",
            font_size="44sp",
            size_hint=(1, 0.35),
        )
        self.big.bind(size=lambda *a: setattr(self.big, "text_size", self.big.size))

        # Детали ниже, поменьше
        self.details = Label(
            text="Нажми кнопку для расчёта.",
            halign="center",
            valign="middle",
            font_size="18sp",
            size_hint=(1, 0.30),
        )
        self.details.bind(size=lambda *a: setattr(self.details, "text_size", self.details.size))

        self.btn = Button(
            text="Рассчитать прогресс",
            font_size="26sp",
            size_hint=(1, 0.15),
        )
        self.btn.bind(on_press=self.on_press)

        self.add_widget(self.title)
        self.add_widget(self.big)
        self.add_widget(self.details)
        self.add_widget(self.btn)

    def on_press(self, *_):
        if CONSTANTS.get("m7_mean_sec", 0.0) <= 0 or CONSTANTS.get("m8_mean_sec", 0.0) <= 0:
            self.details.text = (
                "Константы не заданы!\n"
                "Сначала запусти compute_constants.py и вставь числа в CONSTANTS."
            )
            return

        self.btn.disabled = True
        self.details.text = "Запрашиваю последнее событие M7+ и M8+…"
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            now = datetime.now(timezone.utc)

            last7 = fetch_last_event_time(7.0)
            last8 = fetch_last_event_time(8.0)
            if last7 is None or last8 is None:
                raise RuntimeError("Не удалось получить последние события из USGS.")

            elapsed7 = (now - last7).total_seconds()
            elapsed8 = (now - last8).total_seconds()

            p7 = (elapsed7 / CONSTANTS["m7_mean_sec"]) * 100.0
            p8 = (elapsed8 / CONSTANTS["m8_mean_sec"]) * 100.0

            # Ограничивать проценты НЕ надо: бывает >100% — это нормально
            big_text = f"M7+: {p7:.1f}%\nM8+: {p8:.1f}%"

            last7_local = last7.astimezone().strftime("%Y-%m-%d %H:%M")
            last8_local = last8.astimezone().strftime("%Y-%m-%d %H:%M")

            details_text = (
                "Что значит %:\n"
                "(время с последнего события / средний интервал за 100 лет) × 100%\n\n"
                f"M7+ средний интервал: {days_from_seconds(CONSTANTS['m7_mean_sec']):.2f} суток\n"
                f"Прошло с последнего M7+: {format_duration(elapsed7)}\n"
                f"Последнее M7+: {last7_local}\n\n"
                f"M8+ средний интервал: {days_from_seconds(CONSTANTS['m8_mean_sec']):.2f} суток\n"
                f"Прошло с последнего M8+: {format_duration(elapsed8)}\n"
                f"Последнее M8+: {last8_local}\n"
            )

            Clock.schedule_once(lambda dt: self._show(big_text, details_text), 0)

        except Exception as e:
            Clock.schedule_once(lambda dt: self._error(str(e)), 0)

    def _show(self, big_text: str, details_text: str):
        self.big.text = big_text
        self.details.text = details_text
        self.btn.disabled = False

    def _error(self, msg: str):
        self.details.text = "Ошибка:\n" + msg + "\n\nПроверь интернет."
        self.btn.disabled = False


class QuakeApp(App):
    def build(self):
        Window.clearcolor = (0, 0, 0, 1)
        return QuakeUI()


if __name__ == "__main__":
    QuakeApp().run()
