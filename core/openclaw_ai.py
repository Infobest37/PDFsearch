"""
OpenClaw AI integration for intelligent PDF search
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


class OpenClawAI:
    """AI-powered search enhancement for PDF documents"""

    def __init__(self, model_path: str = None):
        self.model_path = model_path
        self.embeddings_cache = {}
        self.search_history = []
        self.abbreviations = self._load_abbreviations()

    def _load_abbreviations(self) -> Dict[str, List[str]]:
        """Загружает автоматические и ручные аббревиатуры"""
        all_abbr = {}

        auto_file = Path("abbreviations_db.json")
        if auto_file.exists():
            try:
                with open(auto_file, 'r', encoding='utf-8') as f:
                    auto = json.load(f)
                    all_abbr.update(auto)
            except:
                pass

        manual_file = Path("manual_abbreviations.json")
        if manual_file.exists():
            try:
                with open(manual_file, 'r', encoding='utf-8') as f:
                    manual = json.load(f)
                    for abbr, exps in manual.items():
                        if abbr not in all_abbr:
                            all_abbr[abbr] = []
                        for exp in exps:
                            if exp not in all_abbr[abbr]:
                                all_abbr[abbr].append(exp)
            except:
                pass

        return all_abbr

    def enhance_query(self, query: str) -> str:
        """Расширяет запрос с использованием аббревиатур"""
        query_upper = query.upper().strip()
        query_lower = query.lower()
        enhanced_parts = [query]

        # Специальная обработка для технологических карт
        # Ищем "ТЕХНОЛОГИЧЕСКАЯ КАРТА XXX" или "ТК XXX" или "КАРТА XXX"
        patterns = [
            r'(?:ТЕХНОЛОГИЧЕСКА[ЯЮ]?\s+КАРТА|ТК|ТЕХКАРТА|КАРТА)\s+(\d{2,3})',
            r'(?:ТЕХНОЛОГИЧЕСКА[ЯЮ]?\s+КАРТА|ТК|ТЕХКАРТА|КАРТА)\s+№\s*(\d{2,3})',
            r'(?:ТЕХНОЛОГИЧЕСКА[ЯЮ]?\s+КАРТА|ТК|ТЕХКАРТА|КАРТА)[-\s]*№?(\d{2,3})',
        ]

        for pattern in patterns:
            card_match = re.search(pattern, query_upper)
            if card_match:
                card_num = card_match.group(1)
                variants = [
                    f"технологическая карта {card_num}",
                    f"технологическая карта №{card_num}",
                    f"тк {card_num}",
                    f"тк №{card_num}",
                    f"карта {card_num}",
                    f"карта №{card_num}",
                    f"технологическая карта {card_num}",
                    f"тк-{card_num}",
                    f"техкарта {card_num}",
                ]
                for v in variants:
                    if v not in enhanced_parts:
                        enhanced_parts.append(v)
                print(f"🔍 Техкарта: поиск по вариантам для {card_num}")
                break

        # Если запрос - аббревиатура (2-6 букв)
        if 2 <= len(query_upper) <= 6 and query_upper.isalpha():
            if query_upper in self.abbreviations:
                expansions = self.abbreviations[query_upper]
                for exp in expansions[:3]:
                    if exp not in enhanced_parts:
                        enhanced_parts.append(exp)

        # Базовые синонимы
        synonyms = {
            "двигатель": ["мотор", "силовая установка", "гтд"],
            "ремонт": ["восстановление", "обслуживание"],
            "масло": ["лз-240", "б-зв", "асмо-200"],
            "топливо": ["тс-1", "рт", "керосин"],
            "карта": ["технологическая карта", "тк", "техкарта"],
            "технологическая": ["тк", "техкарта", "карта"],
        }

        for word, syns in synonyms.items():
            if word in query_lower:
                for syn in syns:
                    if syn not in enhanced_parts:
                        enhanced_parts.append(syn)

        return " ".join(dict.fromkeys(enhanced_parts))

    def rank_results(self, results: List[Dict], query: str) -> List[Dict]:
        """Ранжирует результаты поиска"""
        for result in results:
            score = self._calculate_relevance(result, query)
            result['ai_score'] = score
        return sorted(results, key=lambda x: x.get('ai_score', 0), reverse=True)

    def _calculate_relevance(self, result: Dict, query: str) -> float:
        """Вычисляет релевантность (только для целых слов)"""
        score = 0.0
        text = result.get('text', '').lower()
        query_lower = query.lower()

        # Если запрос - короткая аббревиатура, ищем её как отдельное слово
        if len(query) <= 5 and query.isupper():
            import re
            # Ищем слово целиком (границы слова)
            if re.search(rf'\b{re.escape(query_lower)}\b', text):
                score += 3.0
        else:
            # Обычный поиск по словам
            query_words = query_lower.split()
            for word in query_words:
                if len(word) >= 2:
                    import re
                    if re.search(rf'\b{re.escape(word)}\b', text):
                        score += 1.0

        # Проверка аббревиатуры в словаре
        query_upper = query.upper()
        if query_upper in self.abbreviations:
            for exp in self.abbreviations[query_upper]:
                if exp in text:
                    score += 1.5
                    break

        return min(score, 10.0)

    def learn_from_selection(self, query: str, selected_result: Dict):
        """Учится на кликах пользователя"""
        self.search_history.append({
            'query': query,
            'selected': selected_result,
        })
        self._save_history()

    def _save_history(self, path: str = "search_history.json"):
        """Сохраняет историю"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.search_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")