"""
Search learning module — улучшение поиска на основе кликов пользователя.
"""

import json
from typing import List, Dict, Tuple
from datetime import datetime
from collections import Counter


class SearchLearning:
    """Learn from user clicks to improve search ranking."""

    def __init__(self, data_file: str = "search_learning.db"):
        self.data_file = data_file
        self.click_data: List[Dict] = []
        self.query_history: List[Dict] = []
        self._load_data()

    # ─────────────────── Persistence ───────────────────

    def _load_data(self):
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.click_data = data.get('clicks', [])
                self.query_history = data.get('queries', [])
        except Exception:
            pass

    def _save_data(self):
        data = {
            'clicks':  self.click_data[-1000:],
            'queries': self.query_history[-500:],
        }
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Learning] save error: {e}")

    # ─────────────────── Recording ───────────────────

    def record_click(self, query: str, selected_doc: str, position: int):
        """Записываем клик пользователя."""
        self.click_data.append({
            'query':     query,
            'document':  selected_doc,
            'position':  position,
            'timestamp': datetime.now().isoformat(),
        })
        self._save_data()

    def record_query(self, query: str):
        """Записываем поисковый запрос."""
        if isinstance(query, str):
            query = query.encode('utf-8').decode('utf-8')
        self.query_history.append({
            'query':     query,
            'timestamp': datetime.now().isoformat(),
        })
        self._save_data()

    # ─────────────────── History ───────────────────

    def get_popular_queries(self, limit: int = 10) -> List[str]:
        """Возвращает список популярных запросов (только строки)."""
        queries = [q['query'] for q in self.query_history]
        counter = Counter(queries)
        return [q for q, _ in counter.most_common(limit)]

    def get_search_history_rich(self, limit: int = 20) -> List[Tuple[str, str, int]]:
        """
        Возвращает историю в формате (query, last_timestamp, count).
        Используется в HistoryPopup.
        """
        counts: Counter = Counter()
        last_seen: Dict[str, str] = {}

        for item in self.query_history:
            q = item['query']
            ts = item.get('timestamp', '')
            counts[q] += 1
            # Сохраняем последнее время
            if q not in last_seen or ts > last_seen[q]:
                last_seen[q] = ts

        result = [
            (q, last_seen.get(q, ''), cnt)
            for q, cnt in counts.most_common(limit)
        ]
        return result

    # ─────────────────── Popularity ───────────────────

    def get_document_popularity(self, doc_path: str) -> int:
        """Сколько раз пользователь кликал на этот документ."""
        return sum(1 for c in self.click_data if c['document'] == doc_path)

    # ─────────────────── Ranking (ИСПРАВЛЕНО) ───────────────────

    def adjust_ranking(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Повышает рейтинг документов, на которые раньше кликали.

        ИСПРАВЛЕНИЕ: было `result.get('doc', {}).get('path', '')` —
        но после _merge_results структура плоская: result['path'].
        """
        for result in results:
            # Плоская структура после merge
            doc_path = result.get('path', '')

            clicks = self.get_document_popularity(doc_path)
            boost = min(clicks * 0.1, 0.5)   # Максимум +0.5

            base = result.get('ai_reranked_score',
                              result.get('ai_score',
                              result.get('score', 0.0)))
            result['learning_score'] = base + boost

        results.sort(key=lambda x: x.get('learning_score', 0), reverse=True)
        return results