@echo off
echo ================================================
echo 问卷数据一体化处理平台 - 启动器
echo ================================================
echo.
echo 正在启动整合平台...
echo.

cd /d "d:\抽样技术"

pip install -q pandas numpy matplotlib streamlit openpyxl requests

streamlit run integrated_platform.py

pause