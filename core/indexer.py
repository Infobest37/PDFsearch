"""
PDF indexer for fast searching
"""

import os
import json
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import fitz  # PyMuPDF


class PDFIndexer:
    """Indexes PDF documents for fast searching"""

    def __init__(self, index_path: str = "pdf_index.json"):
        self.index_path = index_path
        self.index = self._load_index()

    def _load_index(self) -> Dict:
        """Load existing index from disk"""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def index_pdf(self, pdf_path: str) -> bool:
        """Index a single PDF file"""
        try:
            # Проверяем, нужно ли переиндексировать
            file_hash = self._get_file_hash(pdf_path)
            if pdf_path in self.index:
                if self.index[pdf_path].get('hash') == file_hash:
                    return True  # Already indexed

            # Открываем PDF
            doc = fitz.open(pdf_path)

            pdf_data = {
                'path': pdf_path,
                'name': os.path.basename(pdf_path),
                'pages': [],
                'hash': file_hash,
                'full_text': ''
            }

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                pdf_data['pages'].append({
                    'num': page_num + 1,
                    'text': text,
                    'length': len(text)
                })
                pdf_data['full_text'] += text + "\n"

            self.index[pdf_path] = pdf_data
            doc.close()
            self._save_index()
            return True

        except Exception as e:
            print(f"Error indexing {pdf_path}: {e}")
            return False

    def index_folder(self, folder_path: str, progress_cb=None) -> List[str]:
        """Index all PDFs in a folder"""
        indexed = []
        pdf_files = list(Path(folder_path).glob("*.pdf"))

        total = len(pdf_files)
        for i, pdf_path in enumerate(pdf_files):
            if self.index_pdf(str(pdf_path)):
                indexed.append(str(pdf_path))
            if progress_cb:
                progress_cb((i + 1) / total * 100)

        self._save_index()
        return indexed

    def _get_file_hash(self, file_path: str) -> str:
        """Calculate file hash for change detection"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(65536)
            while buf:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def _save_index(self):
        """Save index to disk"""
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving index: {e}")

    def search(self, query: str) -> List[Dict]:
        """Search indexed documents"""
        results = []
        query_lower = query.lower()

        for path, data in self.index.items():
            if query_lower in data['full_text'].lower():
                results.append(data)

        return results

    def get_page_text(self, pdf_path: str, page_num: int) -> Optional[str]:
        """Get text from specific page"""
        if pdf_path in self.index:
            pages = self.index[pdf_path].get('pages', [])
            for page in pages:
                if page.get('num') == page_num + 1:
                    return page.get('text', '')

        # Если не в индексе, читаем напрямую
        try:
            doc = fitz.open(pdf_path)
            if page_num < len(doc):
                text = doc[page_num].get_text()
                doc.close()
                return text
        except:
            pass

        return None

    # ─────────────────── Аббревиатуры ───────────────────

    # ─────────────────── Аббревиатуры ───────────────────

    def extract_abbreviations_from_text(self, text: str) -> Dict[str, List[str]]:
        """
        Автоматически извлекает аббревиатуры из текста PDF.
        Ищет паттерны: "ОРМ (ограничитель режимов)" или "РМО - реле максимальных оборотов"
        """
        abbreviations = {}

        # Фильтр: только русские буквы, длина 2-5 символов
        def is_valid_abbr(s: str) -> bool:
            return bool(re.match(r'^[А-ЯЁ]{2,5}$', s))

        # Расшифровка: минимум 5 символов, максимум 80, только русские буквы и пробелы
        def clean_expansion(s: str) -> str:
            # Убираем мусор: цифры, спецсимволы, латиницу
            s = re.sub(r'[^а-яё\s]', '', s.lower())
            # Убираем лишние пробелы
            s = re.sub(r'\s+', ' ', s).strip()
            # Минимальная длина после очистки
            if len(s) < 5 or len(s) > 80:
                return None
            return s

        # Паттерн 1: АББРЕВИАТУРА (расшифровка)
        pattern1 = r'([А-ЯЁ]{2,5})\s*\(([^)]{5,80})\)'
        for match in re.findall(pattern1, text):
            abbr = match[0].upper()
            expansion_raw = match[1].strip()
            expansion = clean_expansion(expansion_raw)
            if is_valid_abbr(abbr) and expansion:
                if abbr not in abbreviations:
                    abbreviations[abbr] = []
                if expansion not in abbreviations[abbr]:
                    abbreviations[abbr].append(expansion)

        # Паттерн 2: АББРЕВИАТУРА — расшифровка
        pattern2 = r'([А-ЯЁ]{2,5})\s*[-—]\s*([^.\n]{5,80})'
        for match in re.findall(pattern2, text):
            abbr = match[0].upper()
            expansion_raw = match[1].strip()
            expansion = clean_expansion(expansion_raw)
            if is_valid_abbr(abbr) and expansion:
                if abbr not in abbreviations:
                    abbreviations[abbr] = []
                if expansion not in abbreviations[abbr]:
                    abbreviations[abbr].append(expansion)

        # Паттерн 3: расшифровка (АББРЕВИАТУРА)
        pattern3 = r'([а-яё][^\(\)]{5,80})\s*\(([А-ЯЁ]{2,5})\)'
        for match in re.findall(pattern3, text):
            expansion_raw = match[0].strip()
            expansion = clean_expansion(expansion_raw)
            abbr = match[1].upper()
            if is_valid_abbr(abbr) and expansion:
                if abbr not in abbreviations:
                    abbreviations[abbr] = []
                if expansion not in abbreviations[abbr]:
                    abbreviations[abbr].append(expansion)

        return abbreviations

    def build_abbreviation_database(self, folder_path: str) -> Dict[str, List[str]]:
        """
        Сканирует все PDF в папке и собирает все аббревиатуры с расшифровками
        """
        all_abbr = {}
        pdf_files = list(Path(folder_path).glob("*.pdf"))

        # Чёрный список мусорных аббревиатур
        blacklist = {'КККОВВ', 'АРИТОВ', 'АЖНОГО', 'АПАНОМ', 'РСУНКА', 'ИЛТРОВ', 'ПАРЕ', 'УГ', 'ЗА'}

        for pdf_path in pdf_files:
            try:
                doc = fitz.open(str(pdf_path))
                for page_num in range(len(doc)):
                    text = doc[page_num].get_text()
                    abbr_on_page = self.extract_abbreviations_from_text(text)

                    for abbr, expansions in abbr_on_page.items():
                        if abbr in blacklist:
                            continue
                        if abbr not in all_abbr:
                            all_abbr[abbr] = []
                        for exp in expansions:
                            if exp not in all_abbr[abbr] and len(exp) > 5:
                                all_abbr[abbr].append(exp)
                doc.close()
            except Exception as e:
                print(f"Error processing {pdf_path}: {e}")

        # Оставляем только аббревиатуры с хорошими расшифровками
        filtered = {}
        for abbr, exps in all_abbr.items():
            good_exps = [e for e in exps if len(e) > 5 and len(e) < 80 and not any(c.isdigit() for c in e)]
            if good_exps:
                filtered[abbr] = good_exps[:5]  # Берём максимум 5 расшифровок

        # Сохраняем в файл
        with open('../manual_abbreviations.json', 'w', encoding='utf-8') as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)

        print(f"✅ Найдено {len(filtered)} качественных аббревиатур")

        # Выводим хорошие примеры
        print("\n📝 Хорошие примеры:")
        for abbr, exps in list(filtered.items())[:20]:
            if len(exps) > 0 and len(abbr) <= 5:
                print(f"   {abbr} → {exps[0][:50]}...")

        return filtered