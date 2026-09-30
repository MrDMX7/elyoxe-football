' Tifo football database refresh on the laptop (db/refresh.py). Task Scheduler runs it daily at 04:30 with no console
' window; each stage decides for itself whether it is due. Log: db\.cache\refresh.log (the last run).
Set sh = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c cd /d """ & dir & "\.."" && python -m db.refresh > db\.cache\refresh.log 2>&1", 0, True
