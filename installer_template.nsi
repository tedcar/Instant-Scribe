; NSIS template to extend default Pynsist installer with post-install autostart registration.
; This file is minimal – it wraps Pynsist's generated template and injects a post-install macro.

!include "MUI2.nsh"

!macro customPageHook
  ; After files have been installed (${PostInstall}
  DetailPrint "Registering autostart shortcut…"
  ExecShell "open" "$INSTDIR\\scripts\\register_watchdog_autostart.ps1" ""
!macroend

!insertmacro MUI_PAGE_LICENSE
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES "customPageHook"
!insertmacro MUI_PAGE_FINISH

;---------------------------------------------------------------------
Section "MainSection" SEC00
  SetOutPath $INSTDIR
  File /r "*"
SectionEnd 