@echo off
setlocal
set "ROOT=%~dp0.."
set "SRC=%ROOT%\WarbandTogether"
set "BIN=%ROOT%\build\bin"
call "%ROOT%\tools\msvc-bootstrap\msvc\setup_x86.bat"
if errorlevel 1 exit /b 1
if not exist "%BIN%" mkdir "%BIN%"
if not exist "%ROOT%\build\obj\client" mkdir "%ROOT%\build\obj\client"
if not exist "%ROOT%\build\obj\plugin" mkdir "%ROOT%\build\obj\plugin"
if not exist "%ROOT%\build\obj\loader" mkdir "%ROOT%\build\obj\loader"
if not exist "%ROOT%\build\obj\asi-loader" mkdir "%ROOT%\build\obj\asi-loader"
set "CFLAGS=/nologo /O1 /MT /GS- /W3 /DWIN32 /DNDEBUG"

pushd "%ROOT%\build\obj\client"
cl.exe %CFLAGS% /c /I"%SRC%\src\shared" "%SRC%\src\asi\coop.c" "%SRC%\src\shared\hook.c" "%SRC%\src\shared\modglobals.c" "%SRC%\src\shared\warband_addrs_wse2.c" "%SRC%\src\asi\steam_flat.c" "%SRC%\src\asi\steam_tunnel.c"
if errorlevel 1 exit /b 1
link.exe /nologo /DLL /MACHINE:X86 /OUT:"%BIN%\warband_coop.asi" coop.obj hook.obj modglobals.obj warband_addrs_wse2.obj steam_flat.obj steam_tunnel.obj kernel32.lib user32.lib ws2_32.lib
if errorlevel 1 exit /b 1
popd

pushd "%ROOT%\build\obj\plugin"
cl.exe %CFLAGS% /c /I"%SRC%\src" /I"%SRC%\src\shared" /I"%SRC%\enet\include" /TP "%SRC%\src\plugin_main.cpp"
if errorlevel 1 exit /b 1
cl.exe %CFLAGS% /c /I"%SRC%\src" /I"%SRC%\src\shared" /I"%SRC%\enet\include" "%SRC%\src\coop_campaign.c" "%SRC%\src\shared\battle_net.c" "%SRC%\src\shared\hook.c" "%SRC%\src\shared\crash_report.c" "%SRC%\src\shared\wsedict.c" "%SRC%\src\shared\modglobals.c" "%SRC%\src\shared\warband_addrs_wse2.c" "%SRC%\src\shared\nettune.c" "%SRC%\src\shared\xp.c"
if errorlevel 1 exit /b 1
cl.exe %CFLAGS% /W0 /c /I"%SRC%\enet\include" "%SRC%\enet\callbacks.c" "%SRC%\enet\compress.c" "%SRC%\enet\host.c" "%SRC%\enet\list.c" "%SRC%\enet\packet.c" "%SRC%\enet\peer.c" "%SRC%\enet\protocol.c" "%SRC%\enet\win32.c"
if errorlevel 1 exit /b 1
link.exe /nologo /DLL /MACHINE:X86 /MAP:"%BIN%\CoopWSEPlugin.map" /OUT:"%BIN%\CoopWSEPlugin.dll" plugin_main.obj coop_campaign.obj battle_net.obj hook.obj crash_report.obj wsedict.obj modglobals.obj warband_addrs_wse2.obj nettune.obj xp.obj callbacks.obj compress.obj host.obj list.obj packet.obj peer.obj protocol.obj win32.obj kernel32.lib user32.lib ws2_32.lib winmm.lib shell32.lib
if errorlevel 1 exit /b 1
popd

pushd "%ROOT%\build\obj\loader"
cl.exe %CFLAGS% /c "%SRC%\src\loader\coop_loader.c"
if errorlevel 1 exit /b 1
link.exe /nologo /DLL /MACHINE:X86 /OUT:"%BIN%\winmm.dll" /IMPLIB:"%BIN%\winmm_proxy.lib" /DEF:"%SRC%\src\loader\winmm_proxy.def" coop_loader.obj kernel32.lib user32.lib winmm.lib
if errorlevel 1 exit /b 1
popd

pushd "%ROOT%\build\obj\asi-loader"
cl.exe /nologo /O1 /GS- /W3 /Zl /c /DWIN32 /DNDEBUG "%SRC%\asi_loader\dinput8_loader.c"
if errorlevel 1 exit /b 1
link.exe /nologo /DLL /MACHINE:X86 /NODEFAULTLIB /ENTRY:DllMain /DEF:"%SRC%\asi_loader\dinput8.def" /OUT:"%BIN%\dinput8.dll" dinput8_loader.obj kernel32.lib user32.lib
if errorlevel 1 exit /b 1
popd
echo All four native components built successfully.
exit /b 0
