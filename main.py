from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock


def calculate_probability():
    """
    ТУТ БУДЕТ НАША РЕАЛЬНАЯ ЛОГИКА.

    Пока сделаю заглушку: вернём примерные значения.
    Потом заменим на твои реальные расчёты.
    """
    p_m7 = 12.3   # %
    p_m8 = 2.1    # %
    details = "Пример расчёта (заглушка)"
    return p_m7, p_m8, details


class MainApp(App):
    def build(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)

        self.label = Label(
            text="Quake probability app\n(M7+ / M8+)\n\nНажми кнопку для расчёта.",
            font_size=18,
            halign="center",
            valign="middle"
        )
        self.label.bind(size=self._update_text_width)

        self.btn = Button(
            text="Рассчитать вероятность",
            size_hint=(1, 0.25)
        )
        self.btn.bind(on_press=self.on_button)

        layout.add_widget(self.label)
        layout.add_widget(self.btn)
        return layout

    def _update_text_width(self, *args):
        self.label.text_size = self.label.size

    def on_button(self, instance):
        # чтобы было видно, что кнопка сработала сразу
        self.label.text = "Считаю... ⏳"
        self.btn.disabled = True

        # запускаем вычисление "чуть позже", чтобы UI успел перерисоваться
        Clock.schedule_once(self._do_calc, 0.1)

    def _do_calc(self, dt):
        try:
            p_m7, p_m8, details = calculate_probability()

            self.label.text = (
                "Результат:\n\n"
                f"M7+ : {p_m7:.2f}%\n"
                f"M8+ : {p_m8:.2f}%\n\n"
                f"{details}"
            )
        except Exception as e:
            self.label.text = "Ошибка расчёта:\n" + str(e)
        finally:
            self.btn.disabled = False


if __name__ == "__main__":
    MainApp().run()
