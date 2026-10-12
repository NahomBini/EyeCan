@echo off
:: Creates a desktop shortcut to GazeControl.exe
set SCRIPT="%TEMP%\shortcut.vbs"
set TARGET="%~dp0dist\GazeControl\GazeControl.exe"
set SHORTCUT="%USERPROFILE%\Desktop\GazeControl.lnk"

echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = %SHORTCUT% >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = %TARGET% >> %SCRIPT%
echo oLink.WorkingDirectory = "%~dp0dist\GazeControl" >> %SCRIPT%
echo oLink.Description = "GazeControl Eye Tracker" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%

cscript /nologo %SCRIPT%
del %SCRIPT%

echo ✅ Shortcut created on Desktop!
pause
