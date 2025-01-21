import os
import shutil
import subprocess
import yadisk
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import json
from datetime import datetime
import schedule
import time
from cryptography.fernet import Fernet
import argparse
import logging
import sys

# Настройка логирования
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("backup.log"),  # Логи в файл
            logging.StreamHandler()  # Логи в консоль
        ]
    )

# Генерация ключа шифрования (если его нет)
def generate_key(key_file):
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        logging.info(f"Сгенерирован новый ключ шифрования: {key_file}")

# Загрузка ключа шифрования
def load_key(key_file):
    with open(key_file, 'rb') as f:
        return f.read()

# Шифрование файла
def encrypt_file(file_path, key):
    fernet = Fernet(key)
    with open(file_path, 'rb') as f:
        original_data = f.read()
    encrypted_data = fernet.encrypt(original_data)
    encrypted_file_path = file_path + '.enc'
    with open(encrypted_file_path, 'wb') as f:
        f.write(encrypted_data)
    logging.info(f"Файл {file_path} зашифрован и сохранен как {encrypted_file_path}")
    return encrypted_file_path

# Расшифровка файла
def decrypt_file(file_path, key):
    fernet = Fernet(key)
    with open(file_path, 'rb') as f:
        encrypted_data = f.read()
    decrypted_data = fernet.decrypt(encrypted_data)
    decrypted_file_path = file_path[:-4]  # Убираем расширение .enc
    with open(decrypted_file_path, 'wb') as f:
        f.write(decrypted_data)
    logging.info(f"Файл {file_path} расшифрован и сохранен как {decrypted_file_path}")
    return decrypted_file_path

# Загрузка конфигурации
def load_config(config_file):
    with open(config_file, 'r') as f:
        return json.load(f)

# Выполнение скрипта с проверкой кода возврата
def run_script(script_path):
    if script_path:
        logging.info(f"Запуск скрипта: {script_path}")
        result = subprocess.run(script_path, shell=True)
        if result.returncode != 0:
            logging.error(f"Скрипт {script_path} завершился с ошибкой (код возврата: {result.returncode}). Бэкап отменен.")
            sys.exit(1)  # Прерываем выполнение программы

# Создание бэкапа
def create_backup(source_dir, backup_dir):
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        logging.info(f"Создана директория для бэкапов: {backup_dir}")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.zip")
    shutil.make_archive(backup_file[:-4], 'zip', source_dir)
    logging.info(f"Создан бэкап: {backup_file}")
    return backup_file

# Загрузка на Яндекс.Диск
def upload_to_yandex_disk(file_path, yandex_token, yandex_folder):
    y = yadisk.YaDisk(token=yandex_token)
    if not y.exists(yandex_folder):
        y.mkdir(yandex_folder)
        logging.info(f"Создана папка на Яндекс.Диске: {yandex_folder}")
    y.upload(file_path, os.path.join(yandex_folder, os.path.basename(file_path)))
    logging.info(f"Файл {file_path} загружен на Яндекс.Диск в папку {yandex_folder}")

# Получение ID папки по пути в Google Drive
def get_folder_id_by_path(service, path):
    folders = path.split('/')
    parent_id = 'root'  # Начинаем с корневой папки

    for folder in folders:
        if not folder:
            continue
        query = f"name='{folder}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder'"
        results = service.files().list(q=query, fields="files(id)").execute()
        items = results.get('files', [])
        if not items:
            # Папка не найдена, создаем её
            file_metadata = {
                'name': folder,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            folder = service.files().create(body=file_metadata, fields='id').execute()
            parent_id = folder.get('id')
        else:
            parent_id = items[0]['id']
    return parent_id

# Загрузка на Google Drive
def upload_to_google_drive(file_path, google_creds_file, google_folder_path):
    creds = service_account.Credentials.from_service_account_file(google_creds_file)
    service = build('drive', 'v3', credentials=creds)

    # Получаем ID папки по пути
    folder_id = get_folder_id_by_path(service, google_folder_path)
    logging.info(f"ID папки '{google_folder_path}': {folder_id}")

    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    logging.info(f"Файл {file_path} загружен на Google Drive в папку {google_folder_path}")

# Получение списка бэкапов с Яндекс.Диска
def list_backups_yandex(yandex_token, yandex_folder):
    y = yadisk.YaDisk(token=yandex_token)
    if not y.exists(yandex_folder):
        return []
    backups = [item.name for item in y.listdir(yandex_folder) if item.name.startswith('backup_')]
    logging.info(f"Получен список бэкапов с Яндекс.Диска: {backups}")
    return backups

# Получение списка бэкапов с Google Drive
def list_backups_google(google_creds_file, google_folder_path):
    creds = service_account.Credentials.from_service_account_file(google_creds_file)
    service = build('drive', 'v3', credentials=creds)

    # Получаем ID папки по пути
    folder_id = get_folder_id_by_path(service, google_folder_path)
    logging.info(f"ID папки '{google_folder_path}': {folder_id}")

    results = service.files().list(
        q=f"'{folder_id}' in parents",
        fields="files(name)"
    ).execute()
    backups = [file['name'] for file in results.get('files', []) if file['name'].startswith('backup_')]
    logging.info(f"Получен список бэкапов с Google Drive: {backups}")
    return backups

# Загрузка бэкапа с Яндекс.Диска
def download_from_yandex_disk(backup_name, yandex_token, yandex_folder, download_dir):
    y = yadisk.YaDisk(token=yandex_token)
    remote_path = os.path.join(yandex_folder, backup_name)
    local_path = os.path.join(download_dir, backup_name)
    y.download(remote_path, local_path)
    logging.info(f"Бэкап {backup_name} загружен с Яндекс.Диска в {local_path}")
    return local_path

# Загрузка бэкапа с Google Drive
def download_from_google_drive(backup_name, google_creds_file, google_folder_path, download_dir):
    creds = service_account.Credentials.from_service_account_file(google_creds_file)
    service = build('drive', 'v3', credentials=creds)

    # Получаем ID папки по пути
    folder_id = get_folder_id_by_path(service, google_folder_path)
    logging.info(f"ID папки '{google_folder_path}': {folder_id}")

    results = service.files().list(
        q=f"name='{backup_name}' and '{folder_id}' in parents",
        fields="files(id)"
    ).execute()
    file_id = results.get('files', [])[0]['id']
    local_path = os.path.join(download_dir, backup_name)
    request = service.files().get_media(fileId=file_id)
    with open(local_path, 'wb') as f:
        f.write(request.execute())
    logging.info(f"Бэкап {backup_name} загружен с Google Drive в {local_path}")
    return local_path

# Основная функция бэкапа
def perform_backup(config):
    logging.info("Начало выполнения бэкапа")
    try:
        # Выполнение пред-бэкап скрипта
        run_script(config.get('pre_backup_script'))

        # Создание бэкапа
        backup_file = create_backup(config['source_dir'], config['backup_dir'])

        # Шифрование бэкапа (если включено)
        if config.get('encryption', {}).get('enabled', False):
            key_file = config['encryption'].get('key_file', 'encryption_key.key')
            generate_key(key_file)
            key = load_key(key_file)
            backup_file = encrypt_file(backup_file, key)

        # Загрузка на Яндекс.Диск
        if 'yandex_token' in config and 'yandex_folder' in config:
            upload_to_yandex_disk(backup_file, config['yandex_token'], config['yandex_folder'])

        # Загрузка на Google Drive
        if 'google_creds_file' in config and 'google_folder_path' in config:
            upload_to_google_drive(backup_file, config['google_creds_file'], config['google_folder_path'])

        # Удаление локального архива после успешной загрузки
        if os.path.exists(backup_file):
            os.remove(backup_file)
            logging.info(f"Локальный архив {backup_file} удален.")

        # Выполнение пост-бэкап скрипта
        run_script(config.get('post_backup_script'))

        logging.info("Бэкап успешно завершен")
    except Exception as e:
        logging.error(f"Ошибка при выполнении бэкапа: {e}")

# Планировщик задач
def start_scheduler(config):
    schedule_time = config.get('schedule', {}).get('time')
    schedule_cron = config.get('schedule', {}).get('cron')

    if schedule_time:
        # Ежедневный запуск в указанное время
        schedule.every().day.at(schedule_time).do(perform_backup, config)
        logging.info(f"Бэкап запланирован на ежедневное выполнение в {schedule_time}")
    elif schedule_cron:
        # Использование cron-подобного синтаксиса
        schedule.every().crontab(schedule_cron).do(perform_backup, config)
        logging.info(f"Бэкап запланирован по cron-расписанию: {schedule_cron}")
    else:
        # Если расписание не указано, выполнить бэкап один раз
        perform_backup(config)
        return

    # Бесконечный цикл для выполнения задач по расписанию
    while True:
        schedule.run_pending()
        time.sleep(1)

# Минимальный shell-интерфейс
def shell_interface(config):
    while True:
        print("\n1. Создать бэкап")
        print("2. Получить список бэкапов из облака")
        print("3. Загрузить бэкап из облака")
        print("4. Расшифровать бэкап")
        print("5. Выйти")
        choice = input("Выберите действие: ")

        if choice == "1":
            perform_backup(config)
        elif choice == "2":
            if 'yandex_token' in config and 'yandex_folder' in config:
                print("Бэкапы на Яндекс.Диске:")
                for backup in list_backups_yandex(config['yandex_token'], config['yandex_folder']):
                    print(backup)
            if 'google_creds_file' in config and 'google_folder_path' in config:
                print("Бэкапы на Google Drive:")
                for backup in list_backups_google(config['google_creds_file'], config['google_folder_path']):
                    print(backup)
        elif choice == "3":
            backup_name = input("Введите имя бэкапа: ")
            download_dir = config.get('backup_dir', '.')
            if 'yandex_token' in config and 'yandex_folder' in config:
                download_from_yandex_disk(backup_name, config['yandex_token'], config['yandex_folder'], download_dir)
            if 'google_creds_file' in config and 'google_folder_path' in config:
                download_from_google_drive(backup_name, config['google_creds_file'], config['google_folder_path'], download_dir)
        elif choice == "4":
            backup_name = input("Введите имя зашифрованного бэкапа: ")
            key_file = config.get('encryption', {}).get('key_file', 'encryption_key.key')
            key = load_key(key_file)
            decrypt_file(backup_name, key)
        elif choice == "5":
            break
        else:
            print("Неверный выбор. Попробуйте снова.")

# Основная функция
def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Утилита для бэкапов.")
    parser.add_argument('--gui', action='store_true', help="Запустить в режиме shell-интерфейса.")
    parser.add_argument('config_file', help="Путь к конфигурационному файлу.")
    args = parser.parse_args()

    config = load_config(args.config_file)

    if args.gui:
        shell_interface(config)
    else:
        if 'schedule' in config:
            start_scheduler(config)
        else:
            perform_backup(config)

if __name__ == "__main__":
    main()