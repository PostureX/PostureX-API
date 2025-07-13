@echo off
echo [%date% %time%]: START

echo [%date% %time%]: Creating virtual env
uv venv

echo [%date% %time%]: Activating venv
call .venv\Scripts\activate

echo [%date% %time%]: Installing the requirements
uv pip install -r requirements.txt

echo [%date% %time%]: Creating folders and files
python template.py

echo [%date% %time%]: END
pause