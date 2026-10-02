; Установщик русской версии Path of Building (неофициальный форк).
; Ставит в профиль пользователя без прав администратора, рядом с программой создаёт installed.cfg:
; тогда PoB хранит билды и настройки в "Документы\Path of Building", как официальная установка.
;
; Сборка: makensis -DVERSION=<версия> -DSRCDIR=<папка пакета> -DOUTFILE=<exe> ru/installer/PathOfBuilding-RU.nsi

Unicode true
!include "MUI2.nsh"

!ifndef VERSION
	!define VERSION "dev"
!endif
!ifndef SRCDIR
	!define SRCDIR "..\dist\pkg"
!endif
!ifndef OUTFILE
	!define OUTFILE "..\dist\PathOfBuilding-RU-Setup.exe"
!endif

!define APPNAME "Path of Building RU"
!define EXENAME "Path{space}of{space}Building.exe"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\PathOfBuildingRU"

Name "${APPNAME}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\${APPNAME}"
InstallDirRegKey HKCU "${UNINSTKEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!define MUI_ICON "PathOfBuilding.ico"
!define MUI_UNICON "PathOfBuilding.ico"
!define MUI_LICENSEPAGE_CHECKBOX
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXENAME}"

!insertmacro MUI_PAGE_LICENSE "notice.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Russian"

Section "Install"
	SetOutPath "$INSTDIR"
	File /r "${SRCDIR}\*.*"
	FileOpen $0 "$INSTDIR\installed.cfg" w
	FileClose $0

	WriteUninstaller "$INSTDIR\Uninstall.exe"
	CreateDirectory "$SMPROGRAMS\${APPNAME}"
	CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${EXENAME}"
	CreateShortcut "$SMPROGRAMS\${APPNAME}\Удалить ${APPNAME}.lnk" "$INSTDIR\Uninstall.exe"
	CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${EXENAME}"

	WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "${APPNAME}"
	WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
	WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "panchishen (неофициальный форк)"
	WriteRegStr HKCU "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
	WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\${EXENAME}"
	WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
	WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
	WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
	; Билды и настройки в "Документы\Path of Building" не трогаем
	RMDir /r "$INSTDIR"
	Delete "$DESKTOP\${APPNAME}.lnk"
	RMDir /r "$SMPROGRAMS\${APPNAME}"
	DeleteRegKey HKCU "${UNINSTKEY}"
SectionEnd
