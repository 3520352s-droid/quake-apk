import math
from datetime import datetime, timezone, timedelta

import requests
from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.label import Label

USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"

KV = r"""
BoxLayout:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(10)

    Label:
        text: "Earthquake probability (stats)"
        font_size: "20sp"
        size_hint_y: None
        height: self.texture_size[1] + dp(6)

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        spacing: dp(10)

        Button:
            text: "Обновить"
            on_press: app.refresh()

        Spinner:
            id: years_spinner
            text: "10"
            values: ["5","10","20","30"]
            size_hint_x: None
            width: dp(90)

        Spinner:
            id: horizon_spinner
            text: "24"
            values: ["6","12","24","48","72"]
            size_hint_x: None
            width: dp(90)

        Label:
            text: "лет / часов"
            size_hint_x: None
            width: dp(90)

    ScrollView:
        do_scroll_x: False
        GridLayout:
            id: out
            cols: 1
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(10)
            padding: [0, 0, 0, dp(20)]
"""

def utc_now():
    return datetime.now(timezone.utc)

def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def parse_usgs_time_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)

def fmt_td(seconds: float) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hrs, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    if days > 0:
        return f"{days}д {hrs}ч {mins}м"
    return f"{hrs}ч {mins}м"

def traffic_light(p: float) -> str:
    if p < 0.10:
        return "🟢 низкая"
    if p < 0.25:
        return "🟡 умеренная"
    return "🔴 повышенная"

def fetch_last_event(minmag: float):
    params = {
        "format": "geojson",
        "orderby": "time",
        "limit": 1,
        "minmagnitude": minmag,
    }
    r = requests.get(USGS, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    f = feats[0]
    p = f["properties"]
    return {
        "mag": p.get("mag"),
        "place": p.get("place"),
        "time": parse_usgs_time_ms(p["time"]),
        "url": p.get("url"),
    }

def fetch_events_since(minmag: float, start: datetime, end: datetime):
    params = {
        "format": "geojson",
        "orderby": "time-asc",
        "minmagnitude": minmag,
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "limit": 20000,
    }
    r = requests.get(USGS, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    times = []
    for f in feats:
        p = f.get("properties", {})
        t = p.get("time")
        if t is not None:
            times.append(parse_usgs_time_ms(t))
    return times

def mean_interarrival(times):
    if len(times) < 2:
        return None
    times = sorted(times)
    diffs = []
    for a, b in zip(times[:-1], times[1:]):
        d = (b - a).total_seconds()
        if d > 0:
            diffs.append(d)
    if not diffs:
        return None
    return sum(diffs) / len(diffs)

def weibull_conditional_prob(t_elapsed_s: float, horizon_s: float, mean_interval_s: float, k: float = 1.5) -> float:
    gamma = math.gamma(1.0 + 1.0 / k)
    eta = mean_interval_s / gamma

    def F(x):
        if x <= 0:
            return 0.0
        return 1.0 - math.exp(-((x / eta) ** k))

    Ft = F(t_elapsed_s)
    Fth = F(t_elapsed_s + horizon_s)
    denom = max(1e-12, (1.0 - Ft))
    p = (Fth - Ft) / denom
    return max(0.0, min(1.0, p))

def compute_block(minmag: float, years_for_mean: int, horizon_hours: int, k: float = 1.5) -> str:
    now = utc_now()
    last = fetch_last_event(minmag)

    start = now - timedelta(days=365 * years_for_mean)
    times = fetch_events_since(minmag, start, now)
    mean_s = mean_interarrival(times)

    header = f"=== M{minmag}+ ==="
    if last is None:
        return f"{header}\nНет событий в ответе USGS.\n"

    elapsed_s = (now - last["time"]).total_seconds()
    horizon_s = horizon_hours * 3600

    if mean_s is None:
        return (f"{header}\n"
                f"Последнее: {iso_utc(last['time'])}\n"
                f"Место: {last['place']}\n"
                f"Прошло: {fmt_td(elapsed_s)}\n"
                f"Недостаточно данных для среднего интервала.\n"
                f"URL: {last['url']}\n")

    p = weibull_conditional_prob(elapsed_s, horizon_s, mean_s, k=k)
    return (f"{header}\n"
            f"Последнее: {iso_utc(last['time'])}\n"
            f"Место: {last['place']}\n"
            f"Прошло: {fmt_td(elapsed_s)}\n"
            f"Средний интервал: {fmt_td(mean_s)} (событий: {len(times)} за {years_for_mean} лет)\n"
            f"P(≥1 за {horizon_hours}ч): {p*100:.1f}%  {traffic_light(p)}\n"
            f"URL: {last['url']}\n")

class QuakeApp(App):
    def build(self):
        self.title = "Quake Prob"
        root = Builder.load_string(KV)
        self.root_widget = root
        Clock.schedule_once(lambda *_: self.refresh(), 0.3)
        return root

    def set_output(self, text: str):
        out = self.root_widget.ids.out
        out.clear_widgets()
        for block in text.strip().split("\n\n"):
            lbl = Label(text=block, halign="left", valign="top")
            lbl.bind(
                size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None))
            )
            lbl.size_hint_y = None
            lbl.padding = (dp(8), dp(8))
            lbl.bind(texture_size=lambda inst, *_: setattr(inst, "height", inst.texture_size[1] + dp(16)))
            out.add_widget(lbl)

    def refresh(self):
        years = int(self.root_widget.ids.years_spinner.text)
        horizon = int(self.root_widget.ids.horizon_spinner.text)

        def work():
            try:
                b7 = compute_block(7.0, years, horizon)
                b8 = compute_block(8.0, years, horizon)
                note = ("Примечание: это статистический индикатор по прошлым данным, не прогноз.\n"
                        "Модель: Weibull renewal (k=1.5).")
                return f"{b7}\n\n{b8}\n\n{note}"
            except Exception as e:
                return f"Ошибка: {e}"

        # чтобы UI не подвисал — считаем чуть позже (на практике норм и так, но оставим мягко)
        def do(_dt):
            self.set_output(work())
        Clock.schedule_once(do, 0)

if __name__ == "__main__":
    QuakeApp().run()
