#!/usr/bin/env python3
"""
MapleStory Worlds Artale 關鍵字監控機器人設置腳本
"""
import os
import sys

def create_env_file():
    """創建 .env 文件"""
    if os.path.exists('.env'):
        print("✅ .env 文件已存在")
        return True
    
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write("# Discord 機器人 Token\n")
            f.write("# 請到 https://discord.com/developers/applications 創建應用程式並獲取 token\n")
            f.write("DISCORD_TOKEN=your_discord_bot_token_here\n")
        print("✅ .env 文件已創建")
        return True
    except Exception as e:
        print(f"❌ 創建 .env 文件失敗: {e}")
        return False

def check_token():
    """檢查 Discord Token 是否已設定"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        token = os.getenv('DISCORD_TOKEN')
        if not token or token == 'your_discord_bot_token_here':
            return False
        return True
    except Exception:
        return False

def main():
    print("🤖 MapleStory Worlds Artale 關鍵字監控機器人設置")
    print("=" * 60)
    
    # 創建 .env 文件
    if not create_env_file():
        return
    
    # 檢查 Token
    if not check_token():
        print("\n⚠️  Discord Token 尚未設定")
        print("請按照以下步驟設定你的 Discord 機器人:")
        print()
        print("1. 前往 https://discord.com/developers/applications")
        print("2. 創建新應用程式並設定機器人")
        print("3. 複製機器人 Token")
        print("4. 編輯 .env 文件，將 'your_discord_bot_token_here' 替換為實際 Token")
        print("5. 在 Discord Developer Portal 啟用 'Message Content Intent'")
        print("6. 邀請機器人到你的 Discord 伺服器")
        print()
        print("設定完成後，執行以下命令啟動機器人:")
        print("python bot.py")
        
        # 詢問是否要立即設定 Token
        try:
            token = input("\n如果你已經有 Discord Token，請貼上 (直接按 Enter 跳過): ").strip()
            if token and token != 'your_discord_bot_token_here':
                with open('.env', 'w', encoding='utf-8') as f:
                    f.write("# Discord 機器人 Token\n")
                    f.write(f"DISCORD_TOKEN={token}\n")
                print("✅ Token 已設定！")
                print("現在可以執行: python bot.py")
        except KeyboardInterrupt:
            print("\n設置已取消")
    else:
        print("✅ Discord Token 已設定")
        print("可以執行以下命令啟動機器人:")
        print("python bot.py")

if __name__ == "__main__":
    main() 