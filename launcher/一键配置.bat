@echo off
cd /d "%~dp0\.."
echo ========================================================
echo  163 Mail Read-Only MCP - Setup Wizard
echo ========================================================
python -m mail163_mcp setup
pause