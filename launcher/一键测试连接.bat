@echo off
cd /d "%~dp0\.."
echo ========================================================
echo  163 Mail Read-Only MCP - Self Check
echo ========================================================
python -m mail163_mcp check
pause