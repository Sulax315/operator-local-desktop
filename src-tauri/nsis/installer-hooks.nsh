!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Stopping running Operator Local processes before install..."
  nsExec::ExecToLog 'taskkill /IM "backend_app.exe" /F /T'
  nsExec::ExecToLog 'taskkill /IM "Operator Local.exe" /F /T'
  nsExec::ExecToLog 'taskkill /IM "operator-local-desktop.exe" /F /T'
  nsExec::ExecToLog 'taskkill /IM "msedgewebview2.exe" /F /T'
  Sleep 2000
!macroend
