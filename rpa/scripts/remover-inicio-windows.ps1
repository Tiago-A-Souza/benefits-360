# Remove a tarefa de início de sessão do robô REAL. NÃO rode sem autorização.
schtasks /Delete /TN "NewportRoboReal" /F
Write-Host "Tarefa NewportRoboReal removida. O robô não sobe mais sozinho no logon."
