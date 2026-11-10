' Inicia o Fantasma sem janela de terminal. De duplo clique neste arquivo.
pasta = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = pasta
On Error Resume Next
shell.Run "pythonw jarvis_web.py", 0, False
If Err.Number <> 0 Then MsgBox "Nao encontrei o Python (pythonw). Reinstale o Python marcando Add Python to PATH.", 16, "Fantasma"
