#!/bin/zsh
set -euo pipefail

ROOT='/Users/kefei/Desktop/codex/Mooncool看板'
CORE="$ROOT/看板核心"

cd "$ROOT"

echo '[1/4] 生成看板...'
python3 "$CORE/update_meta_dashboard.py"

echo '[2/4] 打开预览...'
open "$CORE/index.html"

echo '[3/4] 提交变更...'
git add "$CORE/index.html" "$CORE/meta-dashboard-template.html" "$CORE/update_meta_dashboard.py" "$ROOT/一键更新看板.command" .gitignore 2>/dev/null || true
if git diff --cached --quiet; then
  echo '没有变更可提交。'
else
  MSG="update mooncool dashboard $(date '+%Y-%m-%d %H:%M:%S')"
  git commit -m "$MSG"
fi

echo '[4/4] 推送到 GitHub...'
git push

echo ''
echo '完成：已生成并推送。'
read -k 1 '?按任意键关闭窗口...'
echo ''
