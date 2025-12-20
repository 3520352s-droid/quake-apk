from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label


class MainApp(App):
    def build(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)

        self.label = Label(
            text="Quake probability app\n\nНажми кнопку",
            font_size=20
        )

        btn = Button(
            text="Рассчитать вероятность",
            size_hint=(1, 0.3)
        )
        btn.bind(on_press=self.on_button)

        layout.add_widget(self.label)
        layout.add_widget(btn)

        return layout

    def on_button(self, instance):
        self.label.text = "Кнопка нажата ✅\nЛогика работает"


if __name__ == "__main__":
    MainApp().run()
