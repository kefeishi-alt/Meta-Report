#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CORE="$ROOT/看板核心"

cd "$ROOT"

echo '[1/4] 拉取 Meta API 数据...'
python3 "$CORE/fetch_meta_dashboard_data.py"

echo '[2/4] 生成看板...'
python3 "$CORE/update_meta_dashboard.py" --source json

echo '[3/4] 打开预览...'
open "$ROOT/index.html"

echo '[4/4] 提交并推送...'
git add "$ROOT/index.html" "$ROOT/一键更新看板.command" .gitignore 2>/dev/null || true
if git diff --cached --quiet; then
  echo '没有变更可提交。'
else
  MSG="update mooncool dashboard $(date '+%Y-%m-%d %H:%M:%S')"
  git commit -m "$MSG"
fi

git push

echo ''
echo '完成：已生成并推送。'
read -k 1 '?按任意键关闭窗口...'
echo ''
