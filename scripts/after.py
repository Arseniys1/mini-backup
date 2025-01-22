import subprocess
import sys


def run_bat_file(bat_file_path):
    try:
        # Запускаем bat файл в фоновом режиме (без окна)
        process = subprocess.run(
            bat_file_path,
            shell=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW  # Скрываем окно
        )

        # Если выполнение успешно, возвращаем 0
        return 0
    except subprocess.CalledProcessError as e:
        # Если произошла ошибка, возвращаем код возврата
        return e.returncode


if __name__ == "__main__":
    # Проверяем, передан ли аргумент с путем к bat файлу
    if len(sys.argv) < 2:
        print("Ошибка: Укажите путь к bat файлу в качестве аргумента.")
        sys.exit(1)

    # Получаем путь к bat файлу из аргументов командной строки
    bat_file_path = sys.argv[1]

    # Запускаем bat файл и получаем returncode
    returncode = run_bat_file(bat_file_path)

    # Выводим результат
    print(f"Return code: {returncode}")