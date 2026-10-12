@echo off
echo ================================================
echo   Building GazeControl.exe
echo ================================================

echo [1/3] Installing PyInstaller...
py -3.11 -m pip install pyinstaller --quiet

echo [2/3] Building...

IF EXIST "vosk-model" (
    echo Found vosk-model, bundling offline voice...
    py -3.11 -m PyInstaller ^
      --onedir ^
      --console ^
      --name GazeControl ^
      --add-data "vosk-model;vosk-model" ^
      --hidden-import mediapipe ^
      --hidden-import vosk ^
      --hidden-import sounddevice ^
      --hidden-import speech_recognition ^
      --hidden-import pyaudio ^
      --hidden-import cv2 ^
      --hidden-import pyautogui ^
      --collect-all mediapipe ^
      --collect-all vosk ^
      main.py
) ELSE (
    echo No vosk-model found, building without offline voice...
    py -3.11 -m PyInstaller ^
      --onedir ^
      --console ^
      --name GazeControl ^
      --hidden-import mediapipe ^
      --hidden-import speech_recognition ^
      --hidden-import pyaudio ^
      --hidden-import cv2 ^
      --hidden-import pyautogui ^
      --collect-all mediapipe ^
      main.py
)

echo [3/3] Done!
echo.
echo ================================================
echo   Your exe is at:  dist\GazeControl\GazeControl.exe
echo ================================================
pause
