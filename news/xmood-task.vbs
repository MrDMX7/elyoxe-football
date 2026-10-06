' «نبض الجمهور» on the laptop (owner bold idea 9, 2026-10-06). Task Scheduler starts this every 10 minutes; the reader
' exits at once when no watched match is on or when a run already holds news\.x-mood.lock. Log: news\.x-mood.log (last run).
Set sh = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c cd /d """ & dir & "\.."" && node news\xmood.js --loop --upload > news\.x-mood.log 2>&1", 0, False
