"""
Hybrid search — комбинирует FTS текстовый поиск с локальным AI.
"""

import os
from typing import List, Dict, Tuple, Optional

from .openclaw_ai import OpenClawAI
from .local_ai_search import LocalAISearch
from .learning import SearchLearning
from .indexer import PDFIndexer
from .spell_checker import SpellChecker


class HybridSearch:
    """AI-powered hybrid search for PDF documents."""

    def __init__(self):
        self.ai_enhancer  = OpenClawAI()
        self.local_ai     = LocalAISearch()
        self.learner      = SearchLearning()
        self.spell_checker = SpellChecker()
        self.indexer: Optional[PDFIndexer] = None
        self.index: Dict = {}

    # ─────────────────── Индексирование ───────────────────

    def ensure_indexed(self, folder_path: str, progress_cb=None, status_cb=None):
        """Индексирует PDF из папки (с кэшем — повторно не переиндексирует)."""
        if status_cb:
            status_cb("🔍 Индексирование PDF файлов...")

        self.indexer = PDFIndexer()

        pdf_files = []
        if os.path.exists(folder_path):
            for fname in os.listdir(folder_path):
                if fname.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(folder_path, fname))

        if not pdf_files:
            if status_cb:
                status_cb("❌ PDF файлы не найдены")
            return

        total = len(pdf_files)
        for i, pdf_path in enumerate(pdf_files):
            if status_cb:
                status_cb(f"📄 Индексация: {os.path.basename(pdf_path)}")
            if progress_cb:
                progress_cb((i + 1) / total * 100)
            self.indexer.index_pdf(pdf_path)

        self.index = self.indexer.index

        # Строим словарь для spell checker из реального текста документов
        self.spell_checker.build_from_index(self.index)

        pages = self._get_total_pages()
        if status_cb:
            status_cb(f"✅ Готово. {total} файлов, {pages} страниц")

    def _get_total_pages(self) -> int:
        return sum(len(d.get('pages', [])) for d in self.index.values())

    # ─────────────────── Pre-check запроса ───────────────────
    def _search_tech_card(self, query: str) -> List[Dict]:
        """
        Специальный поиск для технологических карт
        Ищет по заголовку "ТЕХНОЛОГИЧЕСКАЯ КАРТА", а не по номеру в колонтитуле
        """
        import re

        # Извлекаем номер карты из запроса
        card_number = None
        patterns = [
            r'(\d{2,3}\.\d{2}\.\d{2})',  # 049.70.00
            r'(\d{2,3}\.\d{2})',  # 49.70
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                card_number = match.group(1)
                break

        if not card_number:
            return []

        print(f"🔍 Ищу технологическую карту с номером: {card_number}")

        results = []

        for path, data in self.index.items():
            for page in data.get('pages', []):
                page_num = page.get('num', 0)
                page_text = page.get('text', '')
                page_upper = page_text.upper()

                # Признаки ЧТО ЭТО ТЕХНОЛОГИЧЕСКАЯ КАРТА, а не просто упоминание
                is_tech_card = False

                # 1. В начале страницы есть заголовок "ТЕХНОЛОГИЧЕСКАЯ КАРТА"
                first_500_chars = page_upper[:500]
                if "ТЕХНОЛОГИЧЕСКАЯ КАРТА" in first_500_chars or "ТЕХНОЛОГИЧЕСКАЯ КАРТА" in page_upper:
                    is_tech_card = True

                # 2. Или "КРО" + "ТЕХНОЛОГИЧЕСКАЯ" в начале страницы
                if not is_tech_card and "КРО" in first_500_chars and "ТЕХНОЛОГИЧЕСКАЯ" in first_500_chars:
                    is_tech_card = True

                # 3. Или "ТЕХНОЛОГИЧЕСКАЯ КАРТА № XXX" где XXX совпадает с номером
                if not is_tech_card:
                    card_pattern = rf'ТЕХНОЛОГИЧЕСКАЯ КАРТА\s+№?\s*{re.escape(card_number)}'
                    if re.search(card_pattern, page_upper):
                        is_tech_card = True

                if not is_tech_card:
                    continue

                # Теперь проверяем, что номер карты действительно есть на этой странице
                # (не в колонтитуле, а в теле карты)
                lines = page_text.split('\n')
                has_number_in_body = False
                card_title_line = ""

                for i, line in enumerate(lines[:30]):
                    if card_number in line:
                        # Пропускаем строки с "Стр." или "Page" (это колонтитулы)
                        if "Стр." not in line and "Page" not in line:
                            has_number_in_body = True
                            if "ТЕХНОЛОГИЧЕСКАЯ" in line.upper():
                                card_title_line = line.strip()
                            break

                if not has_number_in_body:
                    # Номер только в колонтитуле - пропускаем
                    continue

                # Извлекаем название карты
                card_title = ""
                card_content = ""
                found_title = False

                for i, line in enumerate(lines[:40]):
                    line_upper = line.upper()
                    if not found_title and ("ТЕХНОЛОГИЧЕСКАЯ" in line_upper or "КРО" in line_upper):
                        card_title = line.strip()
                        found_title = True
                    elif found_title and len(card_content) < 500:
                        card_content += line.strip() + " "

                snippet = f"📋 {card_title}\n{card_content[:300]}..."

                results.append({
                    'path': path,
                    'page_num': page_num - 1,  # 0-based
                    'text': snippet,
                    'score': 1.0,
                    'source': 'tech_card'
                })
                print(f"✅ Карта {card_number} в {data.get('name', '')}, стр. {page_num}")
                print(f"   Заголовок: {card_title[:80]}")
                break  # Берем только первую страницу карты в этом файле

        # Сортируем результаты: сначала те, где заголовок начинается с "КРО" или "ТЕХНОЛОГИЧЕСКАЯ"
        def sort_key(r):
            text = r.get('text', '').upper()
            if 'КРО' in text:
                return 0
            if 'ТЕХНОЛОГИЧЕСКАЯ' in text:
                return 1
            return 2

        results.sort(key=sort_key)

        if not results:
            print(f"❌ Технологическая карта {card_number} не найдена")

        return results
    def check_query(self, query: str) -> Dict:
        """
        Проверяет запрос до поиска.
        Возвращает dict с информацией о найденных исправлениях и аббревиатурах.
        Вызывается из UI до запуска search().
        """
        auto_corrected, suggestions = self.spell_checker.check_query(query)
        abbr = [s for s in suggestions if s['type'] == 'abbreviation']
        spell = [s for s in suggestions if s['type'] == 'spell']

        return {
            'original':               query,
            'auto_corrected':         auto_corrected,  # с исправленными опечатками
            'suggestions':            suggestions,
            'has_abbreviations':      bool(abbr),
            'abbreviation_suggestions': abbr,
            'spell_fixes':            spell,
        }

    # ─────────────────── Основной поиск ───────────────────

    def search(self, folder_path: str, query: str, progress_cb=None) -> List[Tuple]:
        """
        AI-поиск с использованием локального AI для точных совпадений
        """
        print(f"\n{'=' * 60}")
        print(f"🔍 ПОИСК: {query}")
        print(f"{'=' * 60}")

        if not self.indexer:
            self.ensure_indexed(folder_path)

        # ─────────────────────────────────────────────────────────
        # СПЕЦИАЛЬНЫЙ ПОИСК: Технологические карты
        # ─────────────────────────────────────────────────────────
        import re
        is_card_query = bool(re.search(r'\d{2,3}\.\d{2}', query) or
                             ("технологическая" in query.lower() and "карта" in query.lower()) or
                             ("тк" in query.lower() and re.search(r'\d', query)))

        print(f"📋 Это запрос техкарты? {is_card_query}")

        if is_card_query:
            tech_results = self._search_tech_card(query)
            if tech_results:
                print(f"📋 Найдено {len(tech_results)} технологических карт!")
                formatted = []
                for r in tech_results:
                    formatted.append((r['path'], r['page_num'], r['text']))
                self.learner.record_query(query)
                return formatted
            else:
                print(f"⚠️ Техкарта не найдена, пробуем обычный поиск")
        """
        
        AI-поиск с использованием локального AI для точных совпадений
        """
        if not self.indexer:
            self.ensure_indexed(folder_path)

        # ─────────────────────────────────────────────────────────
        # СПЕЦИАЛЬНЫЙ ПОИСК: Технологические карты
        # ─────────────────────────────────────────────────────────
        import re
        is_card_query = bool(re.search(r'\d{2,3}\.\d{2}', query) or
                             ("технологическая" in query.lower() and "карта" in query.lower()))

        if is_card_query:
            tech_results = self._search_tech_card(query)
            if tech_results:
                print(f"📋 Найдена технологическая карта!")
                # Показываем только лучший результат (с заголовком "КРО" или "ТЕХНОЛОГИЧЕСКАЯ")
                best_result = tech_results[0]  # Первый после сортировки

                # Опционально: показываем максимум 3 результата
                formatted = []
                for r in tech_results[:3]:
                    formatted.append((r['path'], r['page_num'], r['text']))

                self.learner.record_query(query)
                return formatted

        # ─────────────────────────────────────────────────────────
        # ОБЫЧНЫЙ ПОИСК
        # ─────────────────────────────────────────────────────────

        if progress_cb:
            progress_cb(10)

        enhanced_query = self.ai_enhancer.enhance_query(query)
        print(f"🔍 AI расширил: '{query}' -> '{enhanced_query}'")

        if progress_cb:
            progress_cb(30)

        # Семантический поиск
        documents_for_ai = []
        for path, data in self.index.items():
            for page in data.get('pages', []):
                documents_for_ai.append({
                    'path': path,
                    'page_num': page.get('num', 0),
                    'text': page.get('text', '')
                })

        semantic_results = self.local_ai.semantic_search(enhanced_query, documents_for_ai, top_k=20)

        if progress_cb:
            progress_cb(60)

        traditional_results = self._traditional_search(query)

        if progress_cb:
            progress_cb(80)

        all_results = self._merge_results(semantic_results, traditional_results)
        ranked_results = self.ai_enhancer.rank_results(all_results, query)
        reranked_results = self.local_ai.rerank_results(ranked_results, query)
        final_results = self.learner.adjust_ranking(reranked_results, query)

        if progress_cb:
            progress_cb(100)

        self.learner.record_query(query)

        formatted = []
        for r in final_results[:50]:
            path = r.get('path', '')
            page_num = r.get('page_num', 0) - 1
            text = r.get('text', '')[:300]
            score = r.get('learning_score', r.get('ai_reranked_score', r.get('ai_score', r.get('score', 0.0))))

            if score > 0.6:
                text = "⭐ " + text

            formatted.append((path, page_num, text))

        return formatted
    # ─────────────────── Традиционный поиск ───────────────────

    def _traditional_search(self, query: str) -> List[Dict]:
        """Точный текстовый поиск по целым словам"""
        results = []

        # Если запрос - аббревиатура (2-6 заглавных букв), ищем как целое слово
        if 2 <= len(query) <= 6 and query.isupper():
            search_term = query.lower()
            print(f"🔍 Поиск аббревиатуры как целого слова: '{search_term}'")

            for path, data in self.index.items():
                for page in data.get('pages', []):
                    page_text = page.get('text', '').lower()
                    # Ищем слово целиком (границы слова)
                    import re
                    if re.search(rf'\b{re.escape(search_term)}\b', page_text):
                        # Находим контекст
                        pos = page_text.find(search_term)
                        start = max(0, pos - 150)
                        end = min(len(page_text), pos + len(search_term) + 150)
                        ctx = page.get('text', '')[start:end]

                        results.append({
                            'path': path,
                            'page_num': page.get('num', 0),
                            'text': ctx,
                            'score': 0.8,
                            'source': 'traditional',
                        })
                        break  # Одна страница на документ
            return results

        # Обычный поиск по словам (длина >= 3)
        search_words = [w.lower() for w in query.split() if len(w) >= 3]

        if not search_words:
            return results

        for path, data in self.index.items():
            full_text = data.get('full_text', '').lower()
            if not all(word in full_text for word in search_words):
                continue

            for page in data.get('pages', []):
                page_text = page.get('text', '').lower()
                if all(word in page_text for word in search_words):
                    # Находим контекст для первого слова
                    first_word = search_words[0]
                    pos = page_text.find(first_word)
                    start = max(0, pos - 150)
                    end = min(len(page_text), pos + len(first_word) + 150)
                    ctx = page.get('text', '')[start:end]

                    results.append({
                        'path': path,
                        'page_num': page.get('num', 0),
                        'text': ctx,
                        'score': 0.55,
                        'source': 'traditional',
                    })
                    break

        return results

    # ─────────────────── Объединение результатов ───────────────────

    def _merge_results(self, semantic: List[Dict],
                       traditional: List[Dict]) -> List[Dict]:
        """
        Объединяет семантические и текстовые результаты.
        Семантические (AI) приоритетнее при конфликте.
        Результат — плоская структура: {path, page_num, text, score, source}.
        """
        merged: Dict[str, Dict] = {}

        # Семантические результаты (вложенная структура от local_ai)
        for r in semantic:
            doc      = r.get('doc', {})
            path     = doc.get('path', '')
            page_num = r.get('page_num', doc.get('page_num', 0))
            key      = f"{path}_{page_num}"

            if key not in merged or merged[key]['score'] < r['score']:
                merged[key] = {
                    'path':     path,
                    'page_num': page_num,
                    'text':     doc.get('text', '')[:300],
                    'score':    r['score'],
                    'source':   'ai',
                }

        # Традиционные (уже плоские)
        for r in traditional:
            key = f"{r['path']}_{r['page_num']}"
            if key not in merged:
                merged[key] = r
            else:
                # Если уже есть AI-результат, немного бустим за точное совпадение
                merged[key]['score'] = min(merged[key]['score'] + 0.05, 1.0)

        return list(merged.values())

    # ─────────────────── Вспомогательные методы ───────────────────

    def record_click(self, query: str, filepath: str, page_num: int, rank: int):
        """Записывает клик для обучения."""
        self.learner.record_click(query, filepath, page_num)
        self.ai_enhancer.learn_from_selection(query, {'path': filepath, 'page': page_num})

    def get_search_history(self) -> List[Tuple[str, str, int]]:
        """Возвращает историю в формате (query, timestamp, count) для HistoryPopup."""
        return self.learner.get_search_history_rich()

    def get_stats(self) -> Dict:
        return {
            'files':    len(self.index),
            'pages':    self._get_total_pages(),
            'searches': len(self.learner.query_history),
            'clicks':   len(self.learner.click_data),
            'patterns': len(self.ai_enhancer.search_history),
        }