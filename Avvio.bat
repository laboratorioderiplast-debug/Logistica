@echo off

echo ============================
echo Avvio server Python...
echo ============================

wt ^
  --title "SERVER 8000" cmd /k "cd /d %~dp0 && python -m uvicorn main:app --host 0.0.0.0 --port 8000" ^; ^
  new-tab --title "SERVER 5000" cmd /k "cd /d C:\Rilievi_app && python -m uvicorn app:app --host 0.0.0.0 --port 5000" ^; ^
  new-tab --title "SERVER 3000" cmd /k "cd /d C:\Scarto_produzione && python -m uvicorn app:asgi_app --host 0.0.0.0 --port 3000" ^; ^
  new-tab --title "LP TABLET 8877" cmd /k "cd /d C:\LP\backend && call venv\Scripts\activate.bat && uvicorn main:app --reload --host 0.0.0.0 --port 8877"

echo ============================
echo Tutto avviato correttamente
echo ============================

pause
