import os
# main.py — Улучшенная версия с обучением, быстрым поиском и spell-check
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle
from functools import partial
import threading
import os


from core.hybrid_search import HybridSearch
from core.viewer import show_page


# ─────────── Цветовая схема ───────────
COLORS = {
    'bg':        (0.08, 0.09, 0.12, 1),
    'panel':     (0.12, 0.14, 0.18, 1),
    'accent':    (0.18, 0.52, 0.95, 1),
    'accent2':   (0.10, 0.72, 0.61, 1),
    'text':      (0.92, 0.93, 0.95, 1),
    'subtext':   (0.55, 0.60, 0.68, 1),
    'hover':     (0.20, 0.23, 0.30, 1),
    'border':    (0.22, 0.26, 0.34, 1),
    'highlight': (0.95, 0.75, 0.18, 1),
    'danger':    (0.90, 0.32, 0.32, 1),
}


class StatusBar(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None,
                        height=dp(28), padding=[dp(10), 0], **kwargs)
        with self.canvas.before:
            Color(*COLORS['panel'])
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.status_label = Label(
            text="Готов к поиску",
            color=COLORS['subtext'],
            font_size=dp(11),
            halign='left',
            text_size=(None, None)
        )
        self.stats_label = Label(
            text="",
            color=COLORS['accent'],
            font_size=dp(11),
            halign='right',
            size_hint_x=0.4
        )
        self.add_widget(self.status_label)
        self.add_widget(self.stats_label)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def set_status(self, text):
        Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', text))

    def set_stats(self, text):
        Clock.schedule_once(lambda dt: setattr(self.stats_label, 'text', text))


class SearchInput(BoxLayout):
    def __init__(self, on_search, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None,
                        height=dp(50), spacing=dp(8), **kwargs)
        self.on_search_cb = on_search

        self.text_input = TextInput(
            hint_text="🔍  Поиск по документам... (например: техкарта 201)",
            multiline=False,
            font_size=dp(14),
            background_color=COLORS['panel'],
            foreground_color=COLORS['text'],
            cursor_color=COLORS['accent'],
            hint_text_color=COLORS['subtext'],
            padding=[dp(12), dp(12)],
        )
        self.text_input.bind(on_text_validate=self._on_enter)

        self.search_btn = Button(
            text="Найти",
            size_hint_x=None,
            width=dp(90),
            background_color=COLORS['accent'],
            color=COLORS['text'],
            font_size=dp(13),
            bold=True,
        )
        self.search_btn.bind(on_press=self._on_press)

        self.add_widget(self.text_input)
        self.add_widget(self.search_btn)

    def _on_enter(self, instance):
        self._on_press(None)

    def _on_press(self, instance):
        query = self.text_input.text.strip()
        if query:
            self.on_search_cb(query)

    def get_query(self):
        return self.text_input.text.strip()

    def set_loading(self, loading):
        self.search_btn.disabled = loading
        self.search_btn.text = "..." if loading else "Найти"

    def set_text(self, text):
        self.text_input.text = text


class ResultCard(BoxLayout):
    def __init__(self, filename, page_num, snippet, is_learned=False,
                 on_press_cb=None, **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(80),
            spacing=dp(6),
            padding=[dp(0), dp(0), dp(0), dp(0)],
            **kwargs
        )
        self._cb = on_press_cb

        border_col = COLORS['accent2'] if is_learned else COLORS['border']
        stripe = Widget(size_hint_x=None, width=dp(4))
        with stripe.canvas:
            Color(*border_col)
            stripe._rect = Rectangle(pos=stripe.pos, size=stripe.size)
        stripe.bind(pos=lambda w, v: setattr(w._rect, 'pos', v))
        stripe.bind(size=lambda w, v: setattr(w._rect, 'size', v))
        self.add_widget(stripe)

        with self.canvas.before:
            Color(*COLORS['panel'])
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda w, v: setattr(w._bg, 'pos', v))
        self.bind(size=lambda w, v: setattr(w._bg, 'size', v))

        text_area = BoxLayout(
            orientation='vertical',
            padding=[dp(10), dp(8), dp(8), dp(8)],
            spacing=dp(4),
        )

        star = "⭐ " if is_learned else ""
        title_col = list(COLORS['accent2']) if is_learned else list(COLORS['accent'])

        title = Label(
            text=f"{star}{filename}   стр. {page_num}",
            color=title_col,
            font_size=dp(12),
            bold=True,
            halign='left',
            valign='middle',
            size_hint_y=0.38,
        )
        title.bind(size=lambda w, v: setattr(w, 'text_size', v))

        clean = snippet.replace('⭐ ', '').strip()
        if len(clean) > 220:
            clean = clean[:220] + '...'

        snip = Label(
            text=clean,
            color=list(COLORS['subtext']),
            font_size=dp(11),
            halign='left',
            valign='top',
            size_hint_y=0.62,
        )
        snip.bind(size=lambda w, v: setattr(w, 'text_size', v))

        text_area.add_widget(title)
        text_area.add_widget(snip)
        self.add_widget(text_area)

        open_btn = Button(
            text='▶',
            size_hint=(None, 1),
            width=dp(40),
            background_normal='',
            background_color=COLORS['accent'],
            color=COLORS['text'],
            font_size=dp(16),
        )
        if on_press_cb:
            open_btn.bind(on_press=on_press_cb)
        self.add_widget(open_btn)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos) and self._cb:
            self._cb(self)
            return True
        return super().on_touch_up(touch)


class AbbreviationPopup(Popup):
    """
    Диалог подтверждения аббревиатуры.
    Показывается когда пользователь пишет, например, "би-2а" → предлагаем "БИ-2А".
    """
    def __init__(self, suggestions, original_query,
                 on_confirm, on_decline, **kwargs):
        content = BoxLayout(orientation='vertical',
                           spacing=dp(10), padding=dp(16))
        super().__init__(
            title="✏️ Уточнение запроса",
            content=content,
            size_hint=(0.55, None),
            height=dp(220),
            **kwargs
        )
        self.on_confirm_cb = on_confirm
        self.on_decline_cb = on_decline

        # Текст подсказки
        msgs = "\n".join(f"  {s['message']}" for s in suggestions)
        info = Label(
            text=f"Запрос: «{original_query}»\n\n{msgs}",
            color=COLORS['text'],
            font_size=dp(13),
            halign='center',
            valign='middle',
        )
        info.bind(size=lambda w, v: setattr(w, 'text_size', v))
        content.add_widget(info)

        # Кнопки
        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))

        yes_btn = Button(
            text="✅ Да, исправить",
            background_color=COLORS['accent'],
            color=COLORS['text'],
            font_size=dp(13),
        )
        yes_btn.bind(on_press=self._on_yes)

        no_btn = Button(
            text="❌ Нет, оставить",
            background_color=COLORS['danger'],
            color=COLORS['text'],
            font_size=dp(13),
        )
        no_btn.bind(on_press=self._on_no)

        btn_row.add_widget(yes_btn)
        btn_row.add_widget(no_btn)
        content.add_widget(btn_row)

    def _on_yes(self, instance):
        self.dismiss()
        self.on_confirm_cb()

    def _on_no(self, instance):
        self.dismiss()
        self.on_decline_cb()


class SpellFixBar(BoxLayout):
    """
    Полоска-уведомление об авто-исправленных опечатках (под строкой поиска).
    """
    def __init__(self, fixes, **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(22),
            padding=[dp(10), 0],
            **kwargs
        )
        with self.canvas.before:
            Color(0.12, 0.22, 0.12, 1)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda w, v: setattr(w.bg, 'pos', v))
        self.bind(size=lambda w, v: setattr(w.bg, 'size', v))

        msg = "  |  ".join(s['message'] for s in fixes)
        lbl = Label(
            text=f"✍️ {msg}",
            color=COLORS['accent2'],
            font_size=dp(10),
            halign='left',
        )
        lbl.bind(size=lambda w, v: setattr(w, 'text_size', v))
        self.add_widget(lbl)


class HistoryPopup(Popup):
    def __init__(self, history, on_select, **kwargs):
        content = BoxLayout(orientation='vertical', spacing=dp(6), padding=dp(10))
        super().__init__(
            title="История поисков",
            content=content,
            size_hint=(0.7, 0.7),
            **kwargs
        )

        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        # history: List[Tuple[str, str, int]]  — (query, timestamp, count)
        for item in history[:20]:
            if isinstance(item, (tuple, list)) and len(item) >= 3:
                query, _, count = item[0], item[1], item[2]
            else:
                query, count = str(item), 1

            btn = Button(
                text=f"{query}  ({count}×)",
                size_hint_y=None,
                height=dp(36),
                font_size=dp(12),
                background_color=COLORS['panel'],
                color=COLORS['text'],
            )
            btn.bind(on_press=lambda x, q=query: (on_select(q), self.dismiss()))
            grid.add_widget(btn)

        scroll.add_widget(grid)
        content.add_widget(scroll)

        close_btn = Button(
            text="Закрыть",
            size_hint_y=None,
            height=dp(40),
            background_color=COLORS['danger'],
        )
        close_btn.bind(on_press=self.dismiss)
        content.add_widget(close_btn)


class PDFSearchApp(App):
    title = "PDF Search Pro"

    def build(self):
        self.folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdfs")
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
            print(f"📁 Создана папка: {self.folder}")
        print(f"📁 Папка PDF: {self.folder}")

        self.current_query  = ""
        self.search_results = []
        self._spell_fix_bar = None    # текущая полоска spell-fix

        Window.clearcolor   = COLORS['bg']
        Window.minimum_width  = 800
        Window.minimum_height = 600
        Window.size = (1000, 700)

        self.searcher = HybridSearch()

        root = BoxLayout(orientation='vertical', spacing=dp(6), padding=dp(10))

        # ── Верхняя панель ──
        top_panel = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40),
            spacing=dp(8),
        )

        app_label = Label(
            text="PDF Search Pro",
            color=COLORS['accent'],
            font_size=dp(16),
            bold=True,
            size_hint_x=None,
            width=dp(160),
        )

        self.index_status = Label(
            text="⏳ Индексирование...",
            color=COLORS['subtext'],
            font_size=dp(11),
            halign='left',
        )

        history_btn = Button(
            text="📋 История",
            size_hint_x=None,
            width=dp(100),
            background_color=COLORS['panel'],
            color=COLORS['subtext'],
            font_size=dp(12),
        )
        history_btn.bind(on_press=self.show_history)

        stats_btn = Button(
            text="📊 Статистика",
            size_hint_x=None,
            width=dp(110),
            background_color=COLORS['panel'],
            color=COLORS['subtext'],
            font_size=dp(12),
        )
        stats_btn.bind(on_press=self.show_stats)

        reindex_btn = Button(
            text="🔄 Переиндекс",
            size_hint_x=None,
            width=dp(120),
            background_color=COLORS['panel'],
            color=COLORS['subtext'],
            font_size=dp(12),
        )
        reindex_btn.bind(on_press=self.force_reindex)

        top_panel.add_widget(app_label)
        top_panel.add_widget(self.index_status)
        top_panel.add_widget(history_btn)
        top_panel.add_widget(stats_btn)
        top_panel.add_widget(reindex_btn)

        # ── Поле поиска ──
        self.search_input = SearchInput(on_search=self.on_search)

        # ── Прогресс ──
        self.progress = ProgressBar(
            max=100, value=0,
            size_hint_y=None, height=dp(4)
        )

        # ── Счётчик результатов ──
        self.result_count = Label(
            text="",
            color=COLORS['subtext'],
            font_size=dp(11),
            size_hint_y=None,
            height=dp(20),
            halign='left',
        )

        # ── Список результатов ──
        self.result_layout = GridLayout(
            cols=1,
            spacing=dp(2),
            size_hint_y=None,
            padding=[0, dp(4)],
        )
        self.result_layout.bind(minimum_height=self.result_layout.setter('height'))

        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.result_layout)

        # ── Статусная строка ──
        self.status_bar = StatusBar()

        # Основной layout
        self._root_layout = root
        root.add_widget(top_panel)
        root.add_widget(self.search_input)
        root.add_widget(self.progress)
        root.add_widget(self.result_count)
        root.add_widget(scroll)
        root.add_widget(self.status_bar)

        # Фоновое индексирование
        self._start_indexing()

        return root

    def _start_indexing(self):
        def on_status(text):
            Clock.schedule_once(lambda dt: setattr(self.index_status, 'text', text))

        self.searcher.ensure_indexed(
            self.folder,
            progress_cb=lambda p: None,
            status_cb=on_status
        )

    # ─────────────────── Поиск (главная логика) ───────────────────

    def on_search(self, query: str):
        """
        Точка входа из UI. Сначала проверяем запрос на аббревиатуры/опечатки,
        затем запускаем поиск.
        """
        query = query.strip()
        if not query:
            return

        # Убираем старую полоску spell-fix
        self._remove_spell_bar()

        info = self.searcher.check_query(query)

        if info['has_abbreviations']:
            # Показываем диалог подтверждения аббревиатуры
            def on_confirm():
                # Применяем аббревиатуры
                corrected = self.searcher.spell_checker.apply_abbreviations(
                    info['auto_corrected'], info['abbreviation_suggestions']
                )
                self.search_input.set_text(corrected)
                self._show_spell_fixes(info['spell_fixes'])
                self._run_search(corrected)

            def on_decline():
                # Используем без аббревиатурных замен (опечатки всё равно исправлены)
                self._show_spell_fixes(info['spell_fixes'])
                self._run_search(info['auto_corrected'])

            popup = AbbreviationPopup(
                suggestions=info['abbreviation_suggestions'],
                original_query=query,
                on_confirm=on_confirm,
                on_decline=on_decline,
            )
            popup.open()
        else:
            # Нет аббревиатур — сразу ищем (опечатки уже исправлены авто)
            if info['spell_fixes']:
                self._show_spell_fixes(info['spell_fixes'])
            self._run_search(info['auto_corrected'])

    def _show_spell_fixes(self, fixes):
        """Показывает полоску с авто-исправлениями опечаток."""
        if not fixes:
            return
        bar = SpellFixBar(fixes, size_hint_y=None, height=dp(22))
        # Вставляем после search_input (индекс 1)
        self._root_layout.add_widget(bar, index=len(self._root_layout.children) - 2)
        self._spell_fix_bar = bar

    def _remove_spell_bar(self):
        """Убирает полоску spell-fix если есть."""
        if self._spell_fix_bar and self._spell_fix_bar.parent:
            self._root_layout.remove_widget(self._spell_fix_bar)
        self._spell_fix_bar = None

    def _run_search(self, query: str):
        """Запускает фактический поиск в фоновом потоке."""
        self.current_query = query
        self.result_layout.clear_widgets()
        self.progress.value = 0
        self.result_count.text = ""
        self.search_input.set_loading(True)
        self.status_bar.set_status(f"🔍 Ищем: {query}")

        def update_progress(value):
            Clock.schedule_once(lambda dt: setattr(self.progress, 'value', value))

        def run():
            results = self.searcher.search(self.folder, query, update_progress)
            self.search_results = results

            def render(dt):
                self.result_layout.clear_widgets()

                if results:
                    self.result_count.text = f"Найдено: {len(results)} результатов"

                    for idx, (filepath, page_num, text) in enumerate(results[:50]):
                        filename   = os.path.basename(filepath)
                        is_learned = text.startswith("⭐")

                        cb = partial(self.open_page, filepath, page_num, query, idx)
                        card = ResultCard(
                            filename=filename,
                            page_num=page_num + 1,
                            snippet=text,
                            is_learned=is_learned,
                            on_press_cb=cb,
                        )
                        self.result_layout.add_widget(card)

                    self.status_bar.set_status(f"✅ Найдено {len(results)} результатов")
                    stats = self.searcher.get_stats()
                    self.status_bar.set_stats(
                        f"📄 {stats['files']} файлов • 🎓 {stats['clicks']} кликов"
                    )
                else:
                    self.result_count.text = "Ничего не найдено"
                    no_result = Label(
                        text="😔 По вашему запросу ничего не найдено.\n"
                             "Проверьте написание или попробуйте другие слова.",
                        color=COLORS['subtext'],
                        font_size=dp(13),
                        halign='center',
                        size_hint_y=None,
                        height=dp(80),
                    )
                    self.result_layout.add_widget(no_result)
                    self.status_bar.set_status("Ничего не найдено")

                self.progress.value = 100
                self.search_input.set_loading(False)
            print(f"DEBUG: render called with {len(results) if results else 0} results")  # ← добавить
            self.result_layout.clear_widgets()
            Clock.schedule_once(render, 0)

        threading.Thread(target=run, daemon=True).start()


    # ─────────────────── Открытие страницы ───────────────────

    def open_page(self, filepath, page_num, query, rank, instance):
        try:
            self.searcher.record_click(query, filepath, page_num, rank)
            show_page(filepath, page_num)
            fname = os.path.basename(filepath)
            self.status_bar.set_status(f"📖 Открываю {fname}, стр. {page_num + 1}")
            print(f"📖 Открываю: {fname}, страница {page_num + 1}")
        except Exception as e:
            self.status_bar.set_status(f"❌ Ошибка: {e}")
            print(f"Ошибка открытия: {e}")

    # ─────────────────── Переиндексирование ───────────────────

    def force_reindex(self, instance):
        try:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf_index.db")
            if os.path.exists(db_path):
                os.remove(db_path)
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf_index.json")
            if os.path.exists(json_path):
                os.remove(json_path)
            self.status_bar.set_status("🗑️ Старый индекс удалён, переиндексирую...")
            from core.hybrid_search import HybridSearch
            self.searcher = HybridSearch()
            self._start_indexing()
        except Exception as e:
            self.status_bar.set_status(f"❌ Ошибка: {e}")

    # ─────────────────── История / Статистика ───────────────────

    def show_history(self, instance):
        history = self.searcher.get_search_history()
        if not history:
            self.status_bar.set_status("История поисков пуста")
            return

        def on_select(query):
            self.search_input.set_text(query)
            self.on_search(query)

        popup = HistoryPopup(history, on_select)
        popup.open()

    def show_stats(self, instance):
        stats = self.searcher.get_stats()

        content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        popup = Popup(
            title="📊 Статистика системы",
            content=content,
            size_hint=(0.5, 0.5),
        )

        items = [
            ("📄 Файлов в индексе",       stats.get('files', 0)),
            ("📃 Страниц проиндексировано", f"{stats.get('pages', 0):,}"),
            ("🔍 Всего поисков",           stats.get('searches', 0)),
            ("👆 Кликов (обучение)",       stats.get('clicks', 0)),
            ("🧠 Паттернов запомнено",     stats.get('patterns', 0)),
        ]

        for label, value in items:
            row = BoxLayout(size_hint_y=None, height=dp(32))
            row.add_widget(Label(
                text=label, color=COLORS['subtext'],
                halign='left', font_size=dp(12)
            ))
            row.add_widget(Label(
                text=str(value), color=COLORS['accent'],
                bold=True, font_size=dp(14)
            ))
            content.add_widget(row)

        close = Button(
            text="Закрыть", size_hint_y=None, height=dp(40),
            background_color=COLORS['accent']
        )
        close.bind(on_press=popup.dismiss)
        content.add_widget(close)
        popup.open()


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    PDFSearchApp().run()