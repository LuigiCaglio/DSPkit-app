@echo off
setlocal
cd /d "%~dp0"

REM ---- versions: the app's from manifest.json, the library's from the bundled
REM      wheel's filename, so neither needs Python and neither can go stale.
set "APP_VER=?"
for /f "tokens=2 delims=:," %%v in ('findstr /c:"\"version\"" manifest.json') do set "APP_VER=%%v"
set "APP_VER=%APP_VER: =%"
set "APP_VER=%APP_VER:"=%"
set "DSP_VER=?"
set "DSP_WHL="
for %%w in ("vendor\dspkit-*.whl") do (
    set "DSP_WHL=%%~fw"
    for /f "tokens=2 delims=-" %%n in ("%%~nw") do set "DSP_VER=%%n"
)

echo.
echo    .-.   .-.   .-.                    _
echo __/   \_/   \_/   \__    ---:      _ [ ] _
echo                                  [ ] [ ] [ ]
echo.
echo    D S P k i t
echo    Exploratory signal analysis for vibration data
echo.
echo    Version   %APP_VER%  (DSPkit library %DSP_VER%)
echo    Author    Luigi Caglio
echo    License   MIT
echo    Cite      https://doi.org/10.5281/zenodo.22257120
echo    Source    https://github.com/LuigiCaglio/DSPkit-app
echo.

REM ---- locate Python ---------------------------------------------------------
set "PY_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
    echo   ERROR: Python was not found on this computer.
    echo.
    echo   Install Python 3.10 or newer from https://www.python.org/downloads/
    echo   and tick "Add python.exe to PATH" during setup, then run this again.
    echo.
    pause
    exit /b 1
)

REM ---- first run: build the environment --------------------------------------
if not exist "venv_dspkit\Scripts\python.exe" (
    echo   First run - setting up. This takes a few minutes, only once.
    echo.
    %PY_CMD% -m venv venv_dspkit
    if errorlevel 1 (
        echo.
        echo   ERROR: Could not create the Python environment.
        pause
        exit /b 1
    )
    "venv_dspkit\Scripts\python.exe" -m pip install --upgrade pip --quiet
    echo   Installing dependencies...
    "venv_dspkit\Scripts\pip.exe" install -r "backend\requirements.txt"
    if errorlevel 1 (
        echo.
        echo   ERROR: Could not install dependencies.
        echo   Check your internet connection and try again.
        echo.
        rmdir /s /q venv_dspkit
        pause
        exit /b 1
    )
    echo.
    echo   Setup complete.
    echo.
)

REM ---- keep the library in step with the bundled wheel -------------------------
REM An environment is only built once, so a newer wheel shipped with an update
REM would otherwise never reach it: the app would run the old library while
REM reporting the new version.
if defined DSP_WHL (
    "venv_dspkit\Scripts\python.exe" -c "import sys, dspkit; sys.exit(dspkit.__version__ != '%DSP_VER%')" >nul 2>&1
    if errorlevel 1 (
        echo   Updating the DSPkit library to %DSP_VER%...
        "venv_dspkit\Scripts\python.exe" -m pip install --no-deps --force-reinstall --quiet "%DSP_WHL%"
        echo.
    )
)

REM ---- the interface must be built -------------------------------------------
if not exist "frontend\dist\index.html" (
    echo   ERROR: The interface has not been built yet.
    echo.
    echo   Run this once, from the frontend folder:
    echo       npm install
    echo       npm run build
    echo.
    pause
    exit /b 1
)

echo   Starting DSPkit. Your browser will open automatically.
echo   Keep this window open while using the app - close it to quit.
echo.

REM %* lets you drag a data file onto this launcher (or set it as the
REM "Open with" program for .csv) and have the app start on that file.
REM It stays empty when there is no argument, and keeps quoting when there is.
"venv_dspkit\Scripts\python.exe" run.py %*
if errorlevel 1 (
    echo.
    echo   DSPkit stopped with an error. The message above explains why.
    pause
)
endlocal
