@echo off
rem ---------------------------------------------------------------------------
rem  Builds and opens the wall-dodge demo. Double-click it, or run:  run_game.bat
rem  Add the word "force" to redo the simulation even if its results exist:  run_game.bat force
rem  Steps whose results already exist are skipped, so a second run takes seconds.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

if /i "%~1"=="force" (
    echo Forcing a fresh run: removing the old sub-circuit, layout and simulation results...
    del /q "wall-dodge\output\data\subnetwork.npz" "wall-dodge\output\data\layout.json" "wall-dodge\output\data\trials_for_3d.json" "wall-dodge\output\data\results_summary.json" 2>nul
)

echo.
echo === 1/7 Python packages ===
python -m pip install -q -r requirements.txt || goto :fail

echo.
echo === 2/7 Connectome data (about 1.9 GB, only downloaded if missing) ===
set MISSING=0
if not exist "data\body-annotations-male-cns-v1.0-minconf-0.5.feather" set MISSING=1
if not exist "data\body-neurotransmitters-male-cns-v1.0.feather" set MISSING=1
if not exist "data\connectome-weights-male-cns-v1.0-minconf-0.5.feather" set MISSING=1
if "%MISSING%"=="1" (
    python download_data.py --core || goto :fail
) else (
    echo found in %CD%\data
)

echo.
echo === 3/7 Cut the sub-circuit out of the connectome ===
if exist "wall-dodge\output\data\subnetwork.npz" (
    echo already done
) else (
    python wall-dodge\scripts\build_subnetwork.py || goto :fail
)

echo.
echo === 4/7 Simulate 100 walls x 4 conditions (about 3 minutes) ===
if exist "wall-dodge\output\data\trials_for_3d.json" (
    echo already done
) else (
    python wall-dodge\scripts\simulate.py 100 || goto :fail
)

echo.
echo === 5/7 Neuron positions for the brain view ===
if exist "wall-dodge\output\data\layout.json" (
    echo already done
) else (
    python wall-dodge\scripts\build_layout.py || goto :fail
)

echo.
echo === 6/7 Charts ===
python wall-dodge\scripts\plot_results.py || goto :fail

echo.
echo === 7/7 3D page ===
python wall-dodge\scripts\build_web.py || goto :fail

echo.
echo Done. Opening the game page...
if not defined NOPAUSE start "" "wall-dodge\output\web\wall_dodge_3d.html"
if not defined NOPAUSE pause
exit /b 0

:fail
echo.
echo A step failed, see the message above. Fix it and run this file again; finished steps are skipped.
if not defined NOPAUSE pause
exit /b 1
