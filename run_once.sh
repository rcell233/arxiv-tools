#!/bin/bash

set -e

# 切到项目根目录（脚本所在目录）
cd "$(dirname "$0")"

echo "🚜 收集论文..."
python daily_paper_collector.py

echo "🈶 翻译论文..."
python llm_process.py

echo "🧹 清理空JSON..."
python cleanup_empty_papers.py

echo "📝 提交与推送..."
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m 'Auto update: daily papers, translations, cleanup'
  git push
  echo "✅ 已提交并推送。"
else
  echo "ℹ️ 无变更，无需提交。"
fi

echo "🎉 完成。"


