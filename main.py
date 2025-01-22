import os
import subprocess
import json
from datetime import datetime, timedelta
import schedule
import time
from cryptography.fernet import Fernet
import argparse
import logging
import requests
from requests.auth import HTTPBasicAuth
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
import zipfile
import time  # Для работы с Unix timestamp

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
            return False  # Возвращаем False вместо завершения программы
        return True  # Возвращаем True, если скрипт выполнен успешно
    return True  # Если скрипт не указан, считаем, что все в порядке

# Создание бэкапа с максимальным сжатием
def create_backup(source_dir, backup_dir):
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        logging.info(f"Создана директория для бэкапов: {backup_dir}")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.zip")

    # Создание ZIP-архива с максимальным сжатием
    with zipfile.ZipFile(backup_file, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=source_dir)  # Относительный путь в архиве
                zipf.write(file_path, arcname=arcname)
                logging.info(f"Добавлен файл в архив: {file_path}")

    logging.info(f"Создан бэкап с максимальным сжатием: {backup_file}")
    return backup_file

# Загрузка на собственный сервер
def upload_to_server(file_path, server_url, username, password, client_timestamp=None):
    with open(file_path, 'rb') as f:
        files = {"file": f}
        data = {"client_timestamp": client_timestamp} if client_timestamp else None
        response = requests.post(
            f"{server_url}/upload",
            files=files,
            data=data,
            auth=HTTPBasicAuth(username, password),
            verify=False  # Отключение проверки SSL (для самоподписанных сертификатов)
        )
    if response.status_code == 200:
        logging.info(f"Бэкап {file_path} загружен на сервер.")
    else:
        logging.error(f"Ошибка при загрузке бэкапа: {response.json().get('error')}")

# Генерация SSL-сертификатов
def generate_ssl_certificates(cert_file, key_file):
    # Генерация приватного ключа
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Создание самоподписанного сертификата
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "My Company"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=365))  # Исправлено
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    # Сохранение приватного ключа
    with open(key_file, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Сохранение сертификата
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    logging.info(f"Сертификат и ключ созданы: {cert_file}, {key_file}")

# Основная функция бэкапа
def perform_backup(config):
    logging.info("Начало выполнения бэкапа")
    try:
        # Выполнение пред-бэкап скрипта
        if not run_script(config.get('pre_backup_script')):
            logging.error("Пред-бэкап скрипт завершился с ошибкой. Бэкап отменен.")
            return  # Отменяем бэкап, если скрипт завершился с ошибкой

        # Создание бэкапа
        backup_file = create_backup(config['source_dir'], config['backup_dir'])

        # Шифрование бэкапа (если включено)
        if config.get('encryption', {}).get('enabled', False):
            key_file = config['encryption'].get('key_file', 'encryption_key.key')
            generate_key(key_file)
            key = load_key(key_file)
            backup_file = encrypt_file(backup_file, key)

        # Загрузка на собственный сервер
        if 'server_url' in config and 'username' in config and 'password' in config:
            client_timestamp = int(time.time())  # Генерация Unix timestamp
            upload_to_server(backup_file, config['server_url'], config['username'], config['password'], client_timestamp)

        # Удаление локального архива после успешной загрузки
        if os.path.exists(backup_file):
            os.remove(backup_file)
            logging.info(f"Локальный архив {backup_file} удален.")

        # Выполнение пост-бэкап скрипта
        if not run_script(config.get('post_backup_script')):
            logging.error("Пост-бэкап скрипт завершился с ошибкой. Бэкап завершен с предупреждениями.")
            return  # Отменяем бэкап, если скрипт завершился с ошибкой

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

# Функция для получения списка бэкапов с сервера
def list_backups(server_url, username, password):
    try:
        response = requests.get(
            f"{server_url}/list",
            auth=HTTPBasicAuth(username, password),
            verify=False  # Отключение проверки SSL (для самоподписанных сертификатов)
        )
        if response.status_code == 200:
            return response.json().get("backups", [])
        else:
            logging.error(f"Ошибка при получении списка бэкапов: {response.json().get('error')}")
            return []
    except Exception as e:
        logging.error(f"Ошибка при подключении к серверу: {e}")
        return []

# Функция для скачивания бэкапа с сервера
def download_backup(server_url, username, password, backup_name, download_dir="downloads"):
    try:
        os.makedirs(download_dir, exist_ok=True)  # Создаем директорию для загрузок, если ее нет
        response = requests.get(
            f"{server_url}/download/{backup_name}",
            auth=HTTPBasicAuth(username, password),
            verify=False  # Отключение проверки SSL
        )
        if response.status_code == 200:
            file_path = os.path.join(download_dir, backup_name)
            with open(file_path, "wb") as f:
                f.write(response.content)
            logging.info(f"Бэкап {backup_name} успешно скачан в {file_path}")
            return file_path
        else:
            logging.error(f"Ошибка при скачивании бэкапа: {response.json().get('error')}")
            return None
    except Exception as e:
        logging.error(f"Ошибка при скачивании бэкапа: {e}")
        return None

# Минимальный shell-интерфейс
def shell_interface(config):
    while True:
        print("\n1. Создать бэкап")
        print("2. Расшифровать бэкап")
        print("3. Сгенерировать SSL-сертификаты")
        print("4. Скачать бэкап с сервера")
        print("5. Выйти")
        choice = input("Выберите действие: ")

        if choice == "1":
            perform_backup(config)
        elif choice == "2":
            backup_name = input("Введите имя зашифрованного бэкапа: ")
            key_file = config.get('encryption', {}).get('key_file', 'encryption_key.key')
            key = load_key(key_file)
            decrypt_file(backup_name, key)
        elif choice == "3":
            cert_file = input("Введите путь для сохранения сертификата (например, server.crt): ")
            key_file = input("Введите путь для сохранения ключа (например, server.key): ")
            generate_ssl_certificates(cert_file, key_file)
            print(f"Сертификат и ключ созданы: {cert_file}, {key_file}")
        elif choice == "4":
            if 'server_url' in config and 'username' in config and 'password' in config:
                # Получаем список бэкапов с сервера
                backups = list_backups(config['server_url'], config['username'], config['password'])
                if backups:
                    print("\nДоступные бэкапы на сервере:")
                    for i, backup in enumerate(backups, 1):
                        print(f"{i}. {backup}")
                    backup_choice = input("Введите номер бэкапа для скачивания: ")
                    try:
                        backup_choice = int(backup_choice) - 1
                        if 0 <= backup_choice < len(backups):
                            backup_name = backups[backup_choice]
                            download_backup(config['server_url'], config['username'], config['password'], backup_name)
                        else:
                            print("Неверный выбор.")
                    except ValueError:
                        print("Введите корректный номер.")
                else:
                    print("На сервере нет доступных бэкапов.")
            else:
                print("Не указаны данные для подключения к серверу в конфигурации.")
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
            start_scheduler(config)  # Исправлено
        else:
            perform_backup(config)

if __name__ == "__main__":
    main()