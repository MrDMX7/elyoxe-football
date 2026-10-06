' Tifo X reader on the laptop (owner 2026-09-30: off the phone to save its battery). Task Scheduler runs this every 15 min (since 2026-10-07; xreader.js skips a quiet run under min_minutes);
' wscript starts node with no console window. Log: news\.x-reader.log (the last run only).
Set sh = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c cd /d """ & dir & "\.."" && node news\xreader.js --upload > news\.x-reader.log 2>&1", 0, True
