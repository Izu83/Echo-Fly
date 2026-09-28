@echo off
rem ---------------------------------------------------------------------------
rem  Builds and opens the wall-dodge demo. Double-click it, or run:  run.bat
rem  Add the word "force" to redo the simulation even if its results exist:  run.bat force
rem  Steps whose results already exist are skipped, so a second run takes seconds.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
set ROOT=..\..

if /i "%~1"=="force" (
    echo Forcing a fresh run: removing the old sub-circuit, layout and simulation results...
    del /q "output\data\subnetwork.npz" "output\data\layout.json" "output\data\trials_for_3d.json" "output\data\results_summary.json" 2>nul
)

echo.
echo === 1/6 Python packages ===
python -m pip install -q -r "%ROOT%\requirements.txt" || goto :fail

echo.
echo === 2/6 Connectome data (about 1.9 GB, only downloaded if missing) ===
set MISSING=0
if not exist "%ROOT%\data\body-annotations-male-cns-v1.0-minconf-0.5.feather" set MISSING=1
if not exist "%ROOT%\data\body-neurotransmitters-male-cns-v1.0.feather" set MISSING=1
if not exist "%ROOT%\data\connectome-weights-male-cns-v1.0-minconf-0.5.feather" set MISSING=1
if "%MISSING%"=="1" (
    python "%ROOT%\data\download_data.py" --core || goto :fail
) else (
    echo found in the data folder
)

echo.
echo === 3/6 Cut the sub-circuit out of the connectome ===
if exist "output\data\subnetwork.npz" (
    echo already done
) else (
    python scripts\build_subnetwork.py || goto :fail
)

echo.
echo === 4/6 Simulate 100 walls x 4 conditions (about 3 minutes) ===
if exist "output\data\trials_for_3d.json" (
    echo already done
) else (
    python scripts\simulate.py 100 || goto :fail
)

echo.
echo === 5/6 Neuron positions for the brain view ===
if exist "output\data\layout.json" (
    echo already done
) else (
    python scripts\build_layout.py || goto :fail
)

echo.
echo === 6/6 3D page ===
python scripts\build_web.py || goto :fail

echo.
echo Done. Opening the game page...
if not defined NOPAUSE start "" "output\web\wall_dodge_3d.html"
if not defined NOPAUSE pause
exit /b 0

:fail
echo.
echo A step failed, see the message above. Fix it and run this file again; finished steps are skipped.
if not defined NOPAUSE pause
exit /b 1
