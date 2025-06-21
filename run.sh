#!/bin/bash

echo "🤖 MapleStory Worlds Artale 關鍵字監控機器人"
echo "=============================================="

# 檢查虛擬環境是否存在
if [ ! -d "venv" ]; then
    echo "❌ 虛擬環境不存在，正在創建..."
    python3 -m venv venv
fi

# 啟動虛擬環境
echo "🔄 啟動虛擬環境..."
source venv/bin/activate

# 檢查並安裝依賴
echo "📦 檢查依賴..."
pip install -r requirements.txt --quiet

# 檢查環境設定
echo "⚙️  檢查環境設定..."
python setup.py

echo ""
echo "🚀 啟動機器人..."
echo "按 Ctrl+C 停止機器人"
echo ""

# 啟動機器人
python bot.py 