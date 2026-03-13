; NovaPaw Desktop NSIS installer. Run makensis from repo root after
; building dist/win-unpacked (see scripts/pack/build_win.ps1).
; Usage: makensis /DNOVAPAW_VERSION=1.2.3 /DOUTPUT_EXE=dist\NovaPaw-Setup-1.2.3.exe scripts\pack\novapaw_desktop.nsi

!include "MUI2.nsh"
!define MUI_ABORTWARNING
; Use custom icon from unpacked env (copied by build_win.ps1)
!define MUI_ICON "${UNPACKED}\icon.ico"
!define MUI_UNICON "${UNPACKED}\icon.ico"

!ifndef NOVAPAW_VERSION
  !define NOVAPAW_VERSION "0.0.0"
!endif
!ifndef OUTPUT_EXE
  !define OUTPUT_EXE "dist\NovaPaw-Setup-${NOVAPAW_VERSION}.exe"
!endif

Name "NovaPaw Desktop"
OutFile "${OUTPUT_EXE}"
InstallDir "$LOCALAPPDATA\NovaPaw"
InstallDirRegKey HKCU "Software\NovaPaw" "InstallPath"
RequestExecutionLevel user

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

; Pass /DUNPACKED=full_path from build_win.ps1 so path works when cwd != repo root
!ifndef UNPACKED
  !define UNPACKED "dist\win-unpacked"
!endif

Section "NovaPaw Desktop" SEC01
  SetOutPath "$INSTDIR"
  File /r /x "*.pyc" /x "__pycache__" "${UNPACKED}\*.*"
  WriteRegStr HKCU "Software\NovaPaw" "InstallPath" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Main shortcut - uses VBS to hide console window
  CreateShortcut "$SMPROGRAMS\NovaPaw Desktop.lnk" "$INSTDIR\NovaPaw Desktop.vbs" "" "$INSTDIR\icon.ico" 0
  CreateShortcut "$DESKTOP\NovaPaw Desktop.lnk" "$INSTDIR\NovaPaw Desktop.vbs" "" "$INSTDIR\icon.ico" 0
  
  ; Debug shortcut - shows console window for troubleshooting
  CreateShortcut "$SMPROGRAMS\NovaPaw Desktop (Debug).lnk" "$INSTDIR\NovaPaw Desktop (Debug).bat" "" "$INSTDIR\icon.ico" 0
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\NovaPaw Desktop.lnk"
  Delete "$SMPROGRAMS\NovaPaw Desktop (Debug).lnk"
  Delete "$DESKTOP\NovaPaw Desktop.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\NovaPaw"
SectionEnd
