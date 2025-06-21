#!/usr/bin/env python3
import os
import sys
import subprocess

def check_dependencies():
    """檢查並安裝必要的依賴"""
    try:
        import discord
        import requests
        import bs4
        from dotenv import load_dotenv
        print("✅ 所有依賴都已安裝")
        return True
    except ImportError as e:
        print(f"❌ 缺少依賴: {e}")
        print("正在安裝依賴...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("✅ 依賴安裝完成")
            return True
        except subprocess.CalledProcessError:
            print("❌ 依賴安裝失敗，請手動運行: pip install -r requirements.txt")
            return False

def check_config():
    """檢查配置文件"""
    if not os.path.exists('.env'):
        print("❌ 找不到 .env 文件")
        print("請按照以下步驟設定:")
        print("1. 複製 config.example 為 .env")
        print("2. 編輯 .env 文件，填入你的 Discord Token")
        print("3. Token 獲取方式: https://discord.com/developers/applications")
        return False
    
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv('DISCORD_TOKEN')
    if not token or token == 'your_discord_bot_token_here':
        print("❌ 請在 .env 文件中設定正確的 DISCORD_TOKEN")
        return False
    
    print("✅ 配置文件檢查通過")
    return True

def main():
    print("🤖 MapleStory Worlds Artale 關鍵字監控機器人")
    print("=" * 50)
    
    # 檢查依賴
    if not check_dependencies():
        return
    
    # 檢查配置
    if not check_config():
        return
    
    print("🚀 啟動機器人...")
    
    # 運行主程式
    try:
        import bot
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")

if __name__ == "__main__":
    main() 