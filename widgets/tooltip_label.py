#widgets\tooltip_label

# Виджет подсказки (всплывающая подсказка для кнопок)

from kivy.graphics import Color, Rectangle
from kivy.uix.label import Label

class TooltipLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)  # Управляем размером вручную
        self.text_size = (300, None)   # Ограничиваем ширину текста
        self.padding = (10, 10)        # Внутренние отступы
        self.color = (1, 1, 1, 1)      # Белый текст
        self.markup = True             # Включаем поддержку разметки
        self.opacity = 0               # Начинаем с прозрачности
        self.pos = (0, 0)              # Стартовая позиция

        # Добавляем фон подсказке
        with self.canvas.before:
            self.bg_color = Color(0, 0, 0, 0.8)  # Полупрозрачный черный
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)

        # Обновляем фон при изменении размера/позиции
        self.bind(pos=self.update_bg, size=self.update_bg)

    def update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size