!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Stopping running Operator Local processes before install..."
  nsExec::ExecToLog 'taskkill /IM "backend_app.exe" /F /T'
  nsExec::ExecToLog 'taskkill /IM "Operator Local.exe" /F /T'
  Sleep 1000
!macroend
