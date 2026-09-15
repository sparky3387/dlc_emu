@echo off
rem Build BOTH the nolog and log variants in one go, the way pgo_stub does,
rem into out\nolog and out\log.
rem
rem The solution has a single Release configuration and Dlc.Common.props sends
rem every build to out\<Platform>_<Configuration>, so a log build would otherwise
rem overwrite the nolog one. OutDir and IntDir are overridden per variant here;
rem MSBuild global properties (/p:) win over the values the props file sets.
rem
rem Logging is a preprocessor switch rather than a configuration:
rem SCE_DLC_EMU_LOG defaults to 0 in src\dlc_modules\dlc_config.h and is
rem overridden through DlcExtraPreprocessorDefinitions.

setlocal
set SLN=%~dp0DlcEmu.sln
set MSBUILD="C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\MSBuild\Current\Bin\MSBuild.exe"
if not exist %MSBUILD% (
  echo MSBuild not found at %MSBUILD%
  echo Edit build_both.cmd if your Visual Studio edition or version differs.
  exit /b 1
)

echo === nolog ===
%MSBUILD% "%SLN%" /p:Configuration=ReleaseHooks /p:Platform=Prospero ^
  /p:OutDir=%~dp0out\nolog\ /p:IntDir=%~dp0out\obj\nolog\ %*
if errorlevel 1 exit /b 1

echo === log ===
%MSBUILD% "%SLN%" /p:Configuration=ReleaseHooks /p:Platform=Prospero ^
  /p:OutDir=%~dp0out\log\ /p:IntDir=%~dp0out\obj\log\ ^
  /p:DlcExtraPreprocessorDefinitions=SCE_DLC_EMU_LOG=1 %*
if errorlevel 1 exit /b 1

echo.
echo Done.  nolog -^> out\nolog   log -^> out\log
endlocal
