# tooltip_button.py

# Импортируем необходимые компоненты Kivy
from kivy.uix.button import Button                     # Для создания пользовательской кнопки
from kivy.core.window import Window                   # Для отслеживания положения мыши и работы с окном
from kivy.clock import Clock                          # Для периодической проверки положения мыши
from kivy.animation import Animation                  # Для плавного появления/исчезновения подсказки
from kivy.uix.textinput import TextInput              # Для проверки наличия фокуса на текстовом поле

# Импорт стандартного модуля регулярных выражений
import re                                              # Для выделения поисковых слов в подсказке

# Импорт собственного виджета — всплывающей подсказки
from .tooltip_label import TooltipLabel

# Класс кнопки с поддержкой всплывающей подсказки
class TooltipButton(Button):
    def __init__(self, tooltip_text, highlight_terms=None, **kwargs):
        super().__init__(**kwargs)                     # Инициализируем родительский класс Button
        self.tooltip_text_raw = tooltip_text           # Исходный текст подсказки
        self.tooltip_label = None                      # Пока не используется, можно убрать при необходимости
        self.tooltip = None                            # Объект всплывающей подсказки
        self.highlight_terms = highlight_terms or []   # Слова, которые будут выделены в подсказке
        self.tooltip_event = Clock.schedule_interval(self.check_hover, 0.1)  # Проверка наведения каждые 0.1 сек

    def check_hover(self, dt):
        if not self.get_root_window():
            return

        mouse_pos = Window.mouse_pos

        # ❗ Если курсор слишком низко — не показываем подсказку вообще
        if mouse_pos[1] < 150:
            if self.tooltip:
                Animation(opacity=0, d=0.2).start(self.tooltip)
            return

        if self.collide_point(*self.to_widget(*mouse_pos)):
            widget_under_mouse = self.get_widget_under_mouse(mouse_pos)

            if isinstance(widget_under_mouse, TextInput) or (
                    isinstance(widget_under_mouse, Button) and widget_under_mouse.text.strip().lower() == "найти"
            ):
                if self.tooltip:
                    Animation(opacity=0, d=0.2).start(self.tooltip)
                return

            if not self.tooltip:
                self.create_tooltip()

            self.update_tooltip_position(mouse_pos)
            Animation(opacity=1, d=0.2).start(self.tooltip)
        else:
            if self.tooltip:
                Animation(opacity=0, d=0.2).start(self.tooltip)
    def create_tooltip(self):
        tooltip_text = self.tooltip_text_raw           # Берем текст подсказки
        for term in self.highlight_terms:              # Для каждого слова из запроса
            tooltip_text = re.sub(
                f"({re.escape(term)})",                # Ищем слово с экранированием спецсимволов
                r"[b]\1[/b]",                          # Выделяем его жирным
                tooltip_text,
                flags=re.IGNORECASE                   # Независимо от регистра
            )
        self.tooltip = TooltipLabel(text=tooltip_text)  # Создаем виджет подсказки
        Window.add_widget(self.tooltip)                # Добавляем подсказку на экран

    def update_tooltip_position(self, mouse_pos):
        self.tooltip.texture_update()
        self.tooltip.size = self.tooltip.texture_size

        screen_width, screen_height = Window.size
        tooltip_width, tooltip_height = self.tooltip.size
        offset_x, offset_y = 20, 20

        x = mouse_pos[0] + offset_x
        y = mouse_pos[1] - offset_y

        # ❗ Не показывать подсказку, если мышь слишком низко (над кнопкой "Найти")
        if y < 150:  # например, 150 пикселей от нижнего края
            Animation(opacity=0, d=0.2).start(self.tooltip)
            return

        # Корректировка границ
        if x + tooltip_width > screen_width:
            x = screen_width - tooltip_width - 5
        if y + tooltip_height > screen_height:
            y = screen_height - tooltip_height - 100
        if x < 0:
            x = 5
        if y < 0:
            y = 5

        self.tooltip.pos = (x, y)

    def get_widget_under_mouse(self, pos):
        from kivy.base import EventLoop                # Импорт EventLoop для доступа к корневым виджетам

        def find_recursive(widget):
            if not widget.collide_point(*widget.to_widget(*pos)):  # Проверяем, попала ли мышь в виджет
                return None
            for child in reversed(widget.children):    # Рекурсивно проверяем детей (сверху вниз)
                found = find_recursive(child)
                if found:
                    return found
            return widget                               # Возвращаем подходящий виджет

        for root in EventLoop.window.children:          # Проверяем все корневые виджеты окна
            result = find_recursive(root)
            if result:
                return result
        return None                                     # Если ничего не нашли — возвращаем None

    def on_parent(self, *args):
        if not self.parent and self.tooltip_event:     # Если кнопка была удалена со сцены
            self.tooltip_event.cancel()                # Отменяем таймер, чтобы не засорять память

# Функция для извлечения фраз и слов из поискового запроса
def extract_phrases_and_words(query):
    phrases = re.findall(r'"(.*?)"', query)            # Ищем фразы в кавычках
    query_without_phrases = re.sub(r'"(.*?)"', '', query)  # Удаляем фразы из запроса
    words = [word for word in query_without_phrases.strip().split() if word]  # Остальные — отдельные слова
    return phrases + words                             # Объединяем и возвращаем все поисковые термины
