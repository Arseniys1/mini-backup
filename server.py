import os
import shutil
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime
import secrets

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

# Конфигурация сервера
SERVER_BACKUP_DIR = "server_backups"
os.makedirs(SERVER_BACKUP_DIR, exist_ok=True)

# Базовая аутентификация
security = HTTPBasic()

# База данных пользователей (в реальной системе используйте базу данных)
USERS = {
    "admin": "admin_password"  # Пароль в открытом виде (для примера)
}

# Проверка аутентификации
def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, USERS["admin"])
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Загрузка бэкапа на сервер
@app.post("/upload")
async def upload_backup(file: UploadFile = File(...), username: str = Depends(authenticate)):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = os.path.join(SERVER_BACKUP_DIR, f"backup_{timestamp}.zip")
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