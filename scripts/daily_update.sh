#!/usr/bin/env bash
# TING 每日研究笔记自动更新脚本
# 用法：添加到 crontab 中每天 09:00 执行
# 0 9 * * * /bin/bash /path/to/TING/scripts/daily_update.sh >> /var/log/ting-daily.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${LOG_FILE:-/var/log/ting-daily.log}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$REPO_DIR"

# 1. 拉取最新代码
log "拉取最新代码..."
git pull origin main

# 2. 检查今日是否已更新（通过检查最新文件日期）
TODAY=$(date +%Y-%m-%d)
LATEST_NOTE=$(ls -1 posts/note-*.html 2>/dev/null | sort | tail -n 1 || true)

if [[ "$LATEST_NOTE" == *"$TODAY"* ]]; then
    log "今日 ($TODAY) 已更新过，跳过。"
    exit 0
fi

# 3. 安装依赖
log "检查Python依赖..."
pip install -q requests beautifulsoup4 2>/dev/null || true

# 4. 生成笔记
log "生成研究笔记..."
python3 scripts/generate_note.py

# 5. 推送变更（如果有）
if git diff --quiet && git diff --cached --quiet; then
    log "无变更需要推送。"
else
    log "检测到变更，正在推送..."
    git add -A
    git commit -m "每日研究笔记自动更新 $TODAY"
    git push origin main
    log "推送完成。"
fi

log "执行结束。"
