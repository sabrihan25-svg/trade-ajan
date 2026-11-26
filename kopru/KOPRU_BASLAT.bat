@echo off
title TRADE AJANI - KOPRU
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ================================================
echo   TRADE AJANI - KOPRU
echo   MetaTrader 5 acik ve hesaba giris yapilmis olmali.
echo   Bu pencere acik kaldigi surece kopru calisir.
echo ================================================
echo.

set "PY="
call :pythonbul
if not defined PY (
  echo Calisan Python bulunamadi. Once MT5_KONTROL.bat dosyasini calistirin.
  pause
  exit /b
)
call :paketkur
if errorlevel 1 goto paketyok

%PY% "%~dp0kopru.py"
echo.
echo Kopru durdu.
pause
exit /b

:paketyok
echo.
echo HATA: MetaTrader5 paketi kurulamadi.
echo Bu ekranin fotografini Claude'a gonderin.
pause
exit /b

:paketkur
%PY% -c "import MetaTrader5" >nul 2>nul
if not errorlevel 1 exit /b 0
echo Gerekli paket kuruluyor (ilk seferde 1-2 dakika surebilir)...
%PY% -m pip install --user --disable-pip-version-check MetaTrader5
%PY% -c "import MetaTrader5" >nul 2>nul
exit /b %errorlevel%

:pythonbul
rem Once paketin destekledigi surumler, sonra digerleri. Windows Magaza kisayolu elenir.
call :dene "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY call :dene py -3.12
if not defined PY call :dene py -3.11
if not defined PY call :dene py -3.13
if not defined PY call :dene "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY call :dene "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY call :dene "C:\Program Files\Python312\python.exe"
if not defined PY call :dene py -3
if not defined PY call :dene python
exit /b

:dene
rem Python gercekten calisiyor mu ve 64 bit mi? (Magaza kisayolu burada elenir)
%* -c "import sys,struct;sys.exit(0 if struct.calcsize('P')==8 and sys.version_info>=(3,8) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%*"
exit /b
