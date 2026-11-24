@echo off
setlocal
set "CONDA_ROOT=C:\Users\rosha\miniforge3"
set "ENV_PREFIX=%CONDA_ROOT%\envs\powai"

if not exist "%CONDA_ROOT%\Scripts\activate.bat" (
  echo ERROR: Miniforge was not found at %CONDA_ROOT%.
  echo Edit CONDA_ROOT in this file to match your Miniforge installation folder.
  pause
  exit /b 1
)

call "%CONDA_ROOT%\Scripts\activate.bat" "%ENV_PREFIX%"
if errorlevel 1 (
  echo ERROR: Could not activate the powai environment at %ENV_PREFIX%.
  pause
  exit /b 1
)

cd /d "%~dp0"
if not exist "app.py" (
  echo ERROR: app.py is missing. Keep this launcher in the powai-service folder with app.py.
  pause
  exit /b 1
)

python -c "import fastapi,uvicorn,geopandas,rasterio,numpy,skimage,pystac_client,PIL,planetary_computer" >nul 2>&1
if errorlevel 1 (
  echo Installing missing geospatial service packages. This may take several minutes...
  conda install -p "%ENV_PREFIX%" -c conda-forge -y python=3.11 fastapi uvicorn geopandas rasterio numpy scikit-image pystac-client pillow shapely
  if errorlevel 1 (
    echo ERROR: Package installation failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
  python -m pip install planetary-computer
  if errorlevel 1 (
    echo ERROR: Could not install planetary-computer.
    pause
    exit /b 1
  )
)

echo Starting Powai analysis service. Keep this window open while using the website.
python -m uvicorn app:app --host 127.0.0.1 --port 8000
if errorlevel 1 (
  echo The service stopped because of an error above.
  pause
)
