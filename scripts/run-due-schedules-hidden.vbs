Set shell = CreateObject("WScript.Shell")

scriptPath = "C:\Dashboard\MacMarket-Trader\scripts\run-due-schedules.ps1"
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & scriptPath & Chr(34)

exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode
