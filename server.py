from datetime import datetime
import os
import shutil
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, status, Form
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, JSONResponse
import secrets
import json
from typing import Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("server.log"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)

app = FastAPI()

# Загрузка конфигурации из файла
def load_config(config_file: str) -> dict:
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        logging.info(f"Конфигурация загружена из файла: {config_file}")
        return config
    except Exception as e:
        logging.error(f"Ошибка при загрузке конфигурации: {e}")
        raise

# Загрузка конфигурации
CONFIG = load_config("server-config.json")

# Конфигурация сервера
SERVER_BACKUP_DIR = CONFIG.get("server_backup_dir", "server_backups")
os.makedirs(SERVER_BACKUP_DIR, exist_ok=True)

# База данных пользователей
USERS = CONFIG.get("users", {"admin": "admin_password"})

# Шаблон имени файла
BACKUP_NAME_FORMAT = CONFIG.get("backup_name_format", "backup_{timestamp}_{username}.zip")

# Базовая аутентификация
security = HTTPBasic()

# Проверка аутентификации
def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    username = credentials.username
    password = credentials.password
    if username in USERS and secrets.compare_digest(password, USERS[username]):
        return username
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Basic"},
    )

# Формирование имени файла с разделителями
def generate_backup_name(username: str, client_timestamp: Optional[int] = None) -> str:
    # Если клиент передал timestamp, используем его. Иначе — текущее время сервера.
    try:
        timestamp = (
            datetime.fromtimestamp(client_timestamp).strftime("%Y-%m-%d_%H-%M-%S")
            if client_timestamp
            else datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        )
    except (ValueError, OSError) as e:
        logging.error(f"Некорректный Unix timestamp: {client_timestamp}. Ошибка: {e}")
        raise HTTPException(
            status_code=400,
            detail="Некорректный Unix timestamp. Убедитесь, что передано корректное количество секунд."
        )
    return BACKUP_NAME_FORMAT.format(timestamp=timestamp, username=username)

# Загрузка бэкапа на сервер
@app.post("/upload")
async def upload_backup(
    file: UploadFile = File(...),
    username: str = Depends(authenticate),
    client_timestamp: Optional[int] = Form(default=None),  # Передаем Unix timestamp из формы
):
    backup_name = generate_backup_name(username, client_timestamp)  # Генерация имени файла
    backup_path = os.path.join(SERVER_BACKUP_DIR, backup_name)
    with open(backup_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    logging.info(f"Бэкап {file.filename} загружен на сервер как {backup_path}")
    return JSONResponse(content={"message": "Backup uploaded successfully", "path": backup_path})

# Скачивание бэкапа с сервера
@app.get("/download/{filename}")
async def download_backup(filename: str, username: str = Depends(authenticate)):
    backup_path = os.path.join(SERVER_BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(backup_path, filename=filename)

# Получение списка бэкапов
@app.get("/list")
async def list_backups(username: str = Depends(authenticate)):
    backups = [f for f in os.listdir(SERVER_BACKUP_DIR) if f.startswith('backup_')]
    return JSONResponse(content={"backups": backups})

# Удаление бэкапа
@app.delete("/delete/{filename}")
async def delete_backup(filename: str, username: str = Depends(authenticate)):
    backup_path = os.path.join(SERVER_BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(backup_path)
    logging.info(f"Бэкап {filename} удален с сервера")
    return JSONResponse(content={"message": "Backup deleted successfully"})