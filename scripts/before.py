import psutil
import os
import time
import argparse

def find_process_by_executable_path(executable_path):
    """
    Находит все процессы, запущенные из указанного исполняемого файла.
    """
    matching_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            # Получаем путь к исполняемому файлу
            proc_exe = proc.info['exe']
            # Проверяем, что путь не None и совпадает с искомым
            if proc_exe and os.path.normcase(proc_exe) == os.path.normcase(executable_path):
                matching_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return matching_processes

def soft_kill_process(pid):
    """
    Мягко завершает процесс по PID.
    Возвращает 0, если процесс завершился успешно, и 1, если не удалось завершить.
    """
    try:
        process = psutil.Process(pid)
        process.terminate()  # Мягкое завершение
        print(f"Процесс с PID {pid} отправлен на завершение.")
        time.sleep(2)  # Даем процессу время на завершение

        if process.is_running():
            print(f"Процесс с PID {pid} не завершился.")
            return 1  # Код ошибки, если процесс не завершился
        else:
            print(f"Процесс с PID {pid} успешно завершен.")
            return 0  # Успешное завершение
    except psutil.NoSuchProcess:
        print(f"Процесс с PID {pid} уже завершен.")
        return 0  # Успешное завершение (процесс уже завершен)
    except psutil.AccessDenied:
        print(f"Нет прав для завершения процесса с PID {pid}.")
        return 1  # Код ошибки, если нет прав

def main(executable_path):
    """
    Основная функция скрипта.
    """
    # Поиск процессов по пути к исполняемому файлу
    processes = find_process_by_executable_path(executable_path)
    if not processes:
        print(f"Процессы, запущенные из '{executable_path}', не найдены.")
        return 1  # Код ошибки, если процессы не найдены

    # Мягкое завершение всех найденных процессов
    overall_result = 0
    for proc in processes:
        pid = proc.info['pid']
        print(f"Найден процесс с PID {pid}, запущенный из '{executable_path}'")
        result = soft_kill_process(pid)
        if result != 0:
            overall_result = 1  # Если хотя бы один процесс не завершился, возвращаем ошибку

    return overall_result

if __name__ == "__main__":
    # Настройка парсера аргументов
    parser = argparse.ArgumentParser(description="Мягкое завершение процессов по пути к исполняемому файлу.")
    parser.add_argument(
        "executable_path",
        type=str,
        help="Полный путь к исполняемому файлу, процессы которого нужно завершить."
    )
    args = parser.parse_args()

    # Запуск основной функции с переданным путём
    exit(main(args.executable_path))