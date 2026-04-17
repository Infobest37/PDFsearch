"""
Local AI Search — семантический поиск по PDF
"""

import re
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

VECTOR_SIZE = 512


class LocalAISearch:
    """Локальный семантический поиск"""

    def __init__(self, model_path: str = "ai_search_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.abbreviations = self._load_abbreviations()

    def _load_abbreviations(self) -> Dict[str, List[str]]:
        """Загружает аббревиатуры"""
        all_abbr = {}

        auto_file = Path("abbreviations_db.json")
        if auto_file.exists():
            try:
                with open(auto_file, 'r', encoding='utf-8') as f:
                    all_abbr.update(json.load(f))
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

    def _load_patterns(self) -> Dict:
        """Загружает паттерны поиска"""
        patterns = {
            "синонимы": {
                "двигатель": ["мотор", "гтд", "твд"],
                "ремонт": ["восстановление", "обслуживание"],
                "масло": ["лз-240", "б-зв", "асмо-200"],
                "топливо": ["тс-1", "рт", "керосин"],
                "технологическая карта": ["тк", "карта", "техкарта"],
                "карта": ["технологическая карта", "тк", "техкарта"],
            }
        }

        # Добавляем аббревиатуры
        for abbr, exps in self.abbreviations.items():
            if abbr.lower() not in patterns["синонимы"]:
                patterns["синонимы"][abbr.lower()] = exps

        return patterns

    def _text_to_vector(self, text: str) -> np.ndarray:
        """Преобразует текст в вектор (только слова длиной >= 3 буквы)"""
        words = re.findall(r'[а-яёa-z]{3,}', text.lower())
        vector = np.zeros(VECTOR_SIZE, dtype=np.float32)

        for word in words:
            idx = hash(word) % VECTOR_SIZE
            vector[idx] += 1.0

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm

        return vector

    def _expand_query(self, query: str) -> List[str]:
        """Расширяет запрос синонимами"""
        expanded = [query.lower()]
        patterns = self._load_patterns()
        synonyms = patterns.get("синонимы", {})

        for term, syns in synonyms.items():
            if term in query.lower():
                expanded.extend(syns)

        return list(set(expanded))

    def semantic_search(self, query: str, documents: List[Dict], top_k: int = 20) -> List[Dict]:
        """Семантический поиск"""
        if not documents:
            return []

        expanded = self._expand_query(query)
        query_vector = self._text_to_vector(query)

        results = []
        for doc in documents:
            doc_text = doc.get('text', '')
            if not doc_text or len(doc_text.strip()) < 20:
                continue

            doc_vector = self._text_to_vector(doc_text)
            similarity = float(np.dot(query_vector, doc_vector))

            bonus = 0.0
            doc_lower = doc_text.lower()
            for term in expanded:
                if term in doc_lower:
                    bonus += 0.1

            if query.lower() in doc_lower:
                bonus += 0.25

            total = min(similarity + bonus, 1.0)

            if total > 0.05:
                results.append({
                    'doc': doc,
                    'score': total,
                    'page_num': doc.get('page_num', 0),
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def rerank_results(self, results: List[Dict], query: str) -> List[Dict]:
        """Переранжирует результаты"""
        for r in results:
            base = r.get('score', 0.0)
            r['ai_reranked_score'] = min(base + 0.1, 1.0)

        results.sort(key=lambda x: x.get('ai_reranked_score', 0), reverse=True)
        return results