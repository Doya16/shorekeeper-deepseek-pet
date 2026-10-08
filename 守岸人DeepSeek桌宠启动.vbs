Option Explicit
Dim shell, fso, root, python
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
python = root & "\.venv\Scripts\pythonw.exe"
shell.CurrentDirectory = root
If Not fso.FileExists(python) Then
  MsgBox "Please install the source dependencies first. See README.md, or download the Windows portable edition.", 48, "Shorekeeper"
  WScript.Quit 1
End If
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & root & "\tools\run_pet.py" & Chr(34), 0, False
