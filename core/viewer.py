#viewer
import os
import platform
import subprocess
import psutil


def close_all_sumatra():
    for proc in psutil.process_iter(['name']):
        try:
            if 'SumatraPDF.exe' in proc.info['name']:
                proc.terminate()
                proc.wait(timeout=3)
        except Exception:
            continue


def show_page(filepath, page_number):
    page_to_open = page_number + 1  # PDF начинается с 1, а не с 0

    if platform.system() == 'Windows':
        # Путь к SumatraPDF
        sumatra_path = r"C:\Program Files\SumatraPDF\SumatraPDF.exe"
        if os.path.exists(sumatra_path):
            # Открываем нужную страницу через параметр -page
            subprocess.Popen([
                sumatra_path,
                '-page', str(page_to_open),

                filepath
            ])
        else:
            # Если SumatraPDF не найден — откроется просто файл
            os.startfile(filepath)
    else:
        # Поддержка для других ОС (если нужно)
        subprocess.Popen(['xdg-open', filepath])