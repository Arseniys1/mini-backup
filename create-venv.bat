@echo off
REM Go to the main folder
cd /d %~dp0

REM Create a virtual environment in the main folder
echo Creating virtual environment in the main folder...
python -m venv .venv
echo Virtual environment created.

REM Activate the virtual environment and install requirements.txt in the main folder
echo Installing dependencies from requirements.txt in the main folder...
call .venv\Scripts\activate
pip install -r requirements.txt
echo Dependencies installed.

REM Go to the scripts folder
cd scripts

REM Create a virtual environment in the scripts folder
echo Creating virtual environment in the scripts folder...
python -m venv .venv
echo Virtual environment created.

REM Activate the virtual environment and install requirements.txt in the scripts folder
echo Installing dependencies from requirements.txt in the scripts folder...
call .venv\Scripts\activate
pip install -r requirements.txt
echo Dependencies installed.

REM Deactivate the virtual environment
deactivate

echo All actions completed successfully.
pause