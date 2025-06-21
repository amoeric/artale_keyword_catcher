# MapleStory Worlds Artale 關鍵字監控機器人

這是一個 Discord 機器人，用於監控 [pal.tw](https://pal.tw/) 網站上的 MapleStory Worlds Artale 公頻訊息，當出現符合用戶設定的關鍵字時會自動通知。

## 功能特色

- 🔍 **即時監控**: 每30秒自動檢查網站新訊息
- 🎯 **關鍵字匹配**: 支援多個關鍵字同時監控
- 💬 **智能通知**: 匹配到關鍵字時立即通知用戶
- 📋 **關鍵字管理**: 可以添加、移除和查看監控的關鍵字
- 🔒 **私人通知**: 優先發送私訊，失敗時發送到指定頻道

## 安裝指南

### 1. 創建 Discord 機器人

1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. 點擊 "New Application" 創建新應用程式
3. 在左側選單選擇 "Bot"
4. 點擊 "Add Bot" 創建機器人
5. 複製 Token（保密！）
6. 在 "Privileged Gateway Intents" 部分啟用 "Message Content Intent"

### 2. 邀請機器人到你的伺服器

1. 在 Discord Developer Portal 中選擇你的應用程式
2. 點擊左側的 "OAuth2" > "URL Generator"
3. 在 "Scopes" 選擇 "bot"
4. 在 "Bot Permissions" 選擇以下權限：
   - Send Messages
   - Embed Links
   - Read Message History
   - Use Slash Commands
5. 複製生成的邀請連結，在瀏覽器中開啟並邀請機器人

### 3. 設定環境

```bash
# 1. 安裝 Python 依賴
pip install -r requirements.txt

# 2. 設定環境變數
cp .env.example .env

# 3. 編輯 .env 文件，填入你的 Discord Bot Token
# DISCORD_TOKEN=your_actual_bot_token_here
```

### 4. 執行機器人

```bash
python bot.py
```

## 使用方法

### 基本指令

- `!add_keyword <關鍵字>` - 添加要監控的關鍵字
- `!remove_keyword <關鍵字>` - 移除監控的關鍵字
- `!list_keywords` - 查看你的所有監控關鍵字
- `!set_channel` - 設定當前頻道為通知頻道
- `!test_fetch` - 測試抓取網站內容功能

### 使用範例

```
!add_keyword 楓葉
!add_keyword 交易
!add_keyword 公會招募
!list_keywords
!set_channel
```

## 通知機制

1. **私訊優先**: 機器人會優先嘗試發送私訊通知
2. **頻道備援**: 如果無法發送私訊，會發送到你設定的通知頻道
3. **避免重複**: 相同的訊息不會重複通知
4. **即時監控**: 每30秒檢查一次網站更新

## 注意事項

- 機器人需要保持運行才能進行監控
- 請確保機器人有足夠的權限發送訊息
- 監控頻率為30秒，可在代碼中調整
- 關鍵字不區分大小寫
- 請遵守網站的使用條款，避免過度請求

## 故障排除

### 常見問題

1. **機器人無法發送私訊**
   - 請確保你的 Discord 設定允許來自伺服器成員的私訊
   - 使用 `!set_channel` 設定通知頻道作為備援

2. **無法抓取網站內容**
   - 檢查網路連線
   - 使用 `!test_fetch` 測試功能
   - 網站結構可能有變更，需要更新代碼

3. **機器人無回應**
   - 檢查 Discord Token 是否正確
   - 確認機器人有必要的權限
   - 查看控制台錯誤訊息

## 技術細節

- **語言**: Python 3.8+
- **主要依賴**: 
  - discord.py - Discord API 
  - requests - HTTP 請求
  - beautifulsoup4 - HTML 解析
  - python-dotenv - 環境變數管理

## 貢獻

歡迎提交 Issue 和 Pull Request 來改善這個專案！

## 授權

此專案採用 MIT 授權條款。 