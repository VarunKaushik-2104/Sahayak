@echo off
rem Windows: serves the app to phones on the same Wi-Fi.  Double-click, then open http://<IPv4 shown below>:8000 on the phone.
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv || python -m venv .venv)
call .venv\Scripts\activate.bat
pip install -q -r backend\requirements.txt
echo.
echo Your PC's address on this network (use the IPv4 line that starts 192.168 or 10.):
ipconfig | findstr /i "IPv4"
echo.
echo On the phone (same Wi-Fi) open  http://THAT-ADDRESS:8000
echo If Windows asks about the firewall, allow it on PRIVATE networks.
cd backend
set SEED_DEMO=1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
