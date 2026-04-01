@echo off

set /p nota=Nota: 
set /p empresa=Empresa 1(Matriz) 2(Filial): 
set /p mes=Mes: 

py auth_cofre_lote.py "%nota%" "%empresa%" "%mes%"

pause