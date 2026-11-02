@echo off
REM Avvia il backend dell'app LP Tablet.
REM Basta fare doppio click su questo file (o metterlo nell'avvio automatico
REM di Windows) per far partire il server senza aprire manualmente il prompt.

cd /d C:\LP\backend

call venv\Scripts\activate.bat

echo Avvio del backend in corso...
uvicorn main:app --reload --host 0.0.0.0 --port 8877

REM Se il server si chiude o da' errore, la finestra resta aperta
REM cosi' puoi leggere il messaggio invece di vederla sparire subito.
pause
