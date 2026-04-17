"""
Spell checking and abbreviation handling for PDF search.
Исправление опечаток + обработка аббревиатур (строчные → заглавные).
"""

import re
from typing import List, Dict, Tuple, Optional
from difflib import get_close_matches
from collections import Counter


# Известные аббревиатуры: строчные → канонический вид
KNOWN_ABBREVIATIONS: Dict[str, str] = {
    # Вертолёты / ЛА
    'ка':   'Ка',   'ми':   'Ми',   'ан':   'Ан',
    'ил':   'Ил',   'ту':   'Ту',   'як':   'Як',
    # Несущие / рулевые системы
    'нв':   'НВ',   'рв':   'РВ',   'хв':   'ХВ',
    'рнв':  'РНВ',  'внв':  'ВНВ',
    # Двигатели
    'гтд':  'ГТД',  'тд':   'ТД',   'твд':  'ТВД',
    'трд':  'ТРД',  'тва':  'ТВА',  'ад':   'АД',
    'рд':   'РД',   'эд':   'ЭД',   'вд':   'ВД',
    'нд':   'НД',   'кнд':  'КНД',  'квд':  'КВД',
    # Агрегаты / блоки
    'би':   'БИ',   'ки':   'КИ',   'кас':  'КАС',
    'ппд':  'ППД',  'пзу':  'ПЗУ',  'сду':  'СДУ',
    'бсу':  'БСУ',  'сту':  'СТУ',  'апи':  'АПИ',
    'асп':  'АСП',  'аб':   'АБ',   'ба':   'БА',
    'бк':   'БК',   'бп':   'БП',   'бу':   'БУ',
    'ки':   'КИ',   'пк':   'ПК',   'пн':   'ПН',
    # Документация
    'то':   'ТО',   'рэ':   'РЭ',   'ам':   'АМ',
    'тр':   'ТР',   'тз':   'ТЗ',   'кд':   'КД',
    'тк':   'ТК',   'иэ':   'ИЭ',   'ирп':  'ИРП',
    'лтх':  'ЛТХ',  'тту':  'ТТУ',  'нтд':  'НТД',
    'рп':   'РП',   'ри':   'РИ',   'рл':   'РЛ',
    'пс':   'ПС',   'фо':   'ФО',
    # Организации / стандарты
    'га':   'ГА',   'гост': 'ГОСТ', 'нии':  'НИИ',
    'цаги': 'ЦАГИ', 'цнии': 'ЦНИИ', 'рф':   'РФ',
    'снг':  'СНГ',  'мвт':  'МВТ',  'квт':  'КВт',
    # Системы
    'сау':  'САУ',  'сто':  'СТО',  'сиу':  'СИУ',
    'суо':  'СУО',  'рлс':  'РЛС',  'нго':  'НГО',
}


class SpellChecker:
    """
    Spell checker для поиска по техническим PDF.
    - Исправляет опечатки по словарю из индекса (авто, без подтверждения)
    - Обнаруживает аббревиатуры в нижнем регистре (требует подтверждения)
    """

    def __init__(self):
        self.vocabulary: Counter = Counter()

    # ─────────────────── Построение словаря ───────────────────

    def build_from_index(self, index: dict):
        """Строим словарь из проиндексированных PDF (только русские слова 4+ букв)."""
        self.vocabulary.clear()
        for data in index.values():
            text = data.get('full_text', '')
            if text:
                words = re.findall(r'[а-яёА-ЯЁ]{4,}', text)
                self.vocabulary.update(w.lower() for w in words)

    # ─────────────────── Аббревиатуры ───────────────────

    def _detect_abbreviation(self, word: str) -> Optional[str]:
        """
        Проверяет, является ли слово аббревиатурой в нижнем регистре.
        Возвращает канонический вид или None.
        """
        word_lower = word.lower()

        # Прямое совпадение (простое, например "би" → "БИ")
        if word_lower in KNOWN_ABBREVIATIONS:
            canonical = KNOWN_ABBREVIATIONS[word_lower]
            if canonical != word:
                return canonical

        # Составная аббревиатура через дефис, например "би-2а" → "БИ-2А"
        if '-' in word and word == word_lower:
            parts = word_lower.split('-')
            first = parts[0]
            if first in KNOWN_ABBREVIATIONS:
                rest = '-'.join(parts[1:]).upper()
                return f"{KNOWN_ABBREVIATIONS[first]}-{rest}"

        # Эвристика: 2–5 кириллических символов, написаны строчными
        # → вероятно аббревиатура, предлагаем ЗАГЛАВНЫЕ
        if re.match(r'^[а-яё]{2,5}$', word_lower) and word == word_lower:
            return word.upper()

        return None

    # ─────────────────── Исправление опечаток ───────────────────

    def _correct_spelling(self, word: str, cutoff: float = 0.82) -> Optional[str]:
        """
        Находит ближайшее слово в словаре через difflib.
        Возвращает исправление или None (если слово верное или нет кандидатов).
        """
        if not self.vocabulary or len(word) < 4:
            return None

        word_lower = word.lower()

        # Слово уже есть в словаре
        if self.vocabulary[word_lower] > 0:
            return None

        # Только русские слова
        if not re.match(r'^[а-яё]+$', word_lower):
            return None

        # Кандидаты похожей длины (ускорение)
        length = len(word_lower)
        candidates = [
            w for w, cnt in self.vocabulary.most_common(6000)
            if abs(len(w) - length) <= 2 and cnt >= 2
        ]

        if not candidates:
            return None

        matches = get_close_matches(word_lower, candidates, n=1, cutoff=cutoff)
        if matches and matches[0] != word_lower:
            return matches[0]

        return None

    # ─────────────────── Публичный API ───────────────────

    def check_query(self, query: str) -> Tuple[str, List[Dict]]:
        """
        Анализирует запрос на опечатки и аббревиатуры.

        Возвращает:
            (auto_corrected_query, suggestions)

        auto_corrected_query:
            Запрос с авто-исправленными опечатками.
            Аббревиатуры НЕ применяются — ждут подтверждения пользователя.

        Каждый suggestion:
            {
                'type':        'abbreviation' | 'spell',
                'original':    str,
                'suggested':   str,
                'message':     str,       # текст для показа пользователю
                'auto_applied': bool,     # True = уже применено в returned query
            }
        """
        tokens = query.split()
        suggestions: List[Dict] = []
        corrected_tokens: List[str] = []

        for token in tokens:
            # ── Аббревиатуры: предлагаем, но не применяем ──
            abbr = self._detect_abbreviation(token)
            if abbr:
                suggestions.append({
                    'type':        'abbreviation',
                    'original':    token,
                    'suggested':   abbr,
                    'message':     f'Вы имели в виду «{abbr}»?',
                    'auto_applied': False,
                })
                corrected_tokens.append(token)   # оригинал до подтверждения
                continue

            # ── Опечатки: исправляем автоматически ──
            correction = self._correct_spelling(token)
            if correction:
                suggestions.append({
                    'type':        'spell',
                    'original':    token,
                    'suggested':   correction,
                    'message':     f'Опечатка исправлена: «{token}» → «{correction}»',
                    'auto_applied': True,
                })
                corrected_tokens.append(correction)
                continue

            corrected_tokens.append(token)

        corrected_query = ' '.join(corrected_tokens)
        return corrected_query, suggestions

    def apply_abbreviations(self, query: str, suggestions: List[Dict]) -> str:
        """Применяет подтверждённые аббревиатуры к запросу."""
        result = query
        for s in suggestions:
            if s['type'] == 'abbreviation':
                result = result.replace(s['original'], s['suggested'])
        return result