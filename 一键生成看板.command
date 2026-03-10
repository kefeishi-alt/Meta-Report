#!/bin/zsh
set -e
cd '/Users/kefei/Desktop/codex/Mooncool看板'
python3 '/Users/kefei/Desktop/codex/Mooncool看板/update_meta_dashboard.py'
open '/Users/kefei/Desktop/codex/Mooncool看板/index.html'
echo ''
echo '看板已更新：/Users/kefei/Desktop/codex/Mooncool看板/index.html'
read -k 1 '?按任意键关闭窗口...'
echo ''
