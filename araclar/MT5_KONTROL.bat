@echo off
title MT5 Hesap Kontrol (sadece okur)
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ================================================
echo   MT5 HESAP KONTROL - SADECE OKUR, EMIR GONDERMEZ
echo   Once MetaTrader 5 acik ve hesaba giris yapilmis olmali.
echo ================================================
echo.

set "PY="
call :pythonbul
if not defined PY (
  echo Calisan Python bulunamadi. Python 3.12 otomatik kuruluyor...
  echo Bir izin penceresi cikarsa EVET deyin. Birkac dakika surebilir.
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  call :pythonbul
)
if not defined PY (
  echo.
  echo HATA: Python kurulamadi.
  echo Lutfen python.org adresinden Python 3.12 indirip kurun.
  echo Kurarken alttaki "Add python.exe to PATH" kutusunu isaretleyin.
  echo Sonra bu dosyayi tekrar cift tiklayin.
  pause
  exit /b
)
echo Kullanilan Python: %PY%

call :paketkur
if errorlevel 1 (
  echo Bu Python surumu ile paket kurulamadi. Python 3.12 deneniyor...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  set "PY="
  call :dene "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  if not defined PY call :dene py -3.12
  if defined PY call :paketkur
)
if not defined PY goto paketyok
%PY% -c "import MetaTrader5" >nul 2>nul
if errorlevel 1 goto paketyok

echo.
%PY% "%~dp0hesap_kontrol.py"
echo.
echo Raporun tamami bu klasordeki rapor.txt dosyasinda.
echo rapor.txt icerigini kopyalayip Claude'a yapistirin.
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
