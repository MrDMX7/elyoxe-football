' Tifo's scheduled jobs on the laptop (tools/runner.py): Task Scheduler runs «Tifo site» hourly at :25, «Tifo journal»
' every 15 min, «Tifo names» Sunday 02:40, «Tifo week» Thursday 15:00 and «Tifo newsletter» Thursday 18:00, each as
'   wscript.exe //B //Nologo runner-task.vbs <job>
' with no console window. Logs: site\cache\runner\<job>.log (the runner's) and <job>.task.log (this launch's output).
Set sh = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
job = WScript.Arguments(0)
sh.Run "cmd /c cd /d """ & dir & "\.."" && set PYTHONIOENCODING=utf-8 && python -m tools.runner " & job & " > site\cache\runner\" & job & ".task.log 2>&1", 0, True
