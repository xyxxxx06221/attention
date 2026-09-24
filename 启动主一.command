#!/bin/zsh
cd "${0:A:h}"
python3 launch.py
if [ $? -ne 0 ]; then read "?按回车关闭窗口。"; fi
