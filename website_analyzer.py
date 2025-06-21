#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
import time

def analyze_website():
    """分析 pal.tw 網站結構"""
    url = "https://pal.tw/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print(f"🔍 分析網站: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("\n📋 網頁基本資訊:")
        print(f"標題: {soup.title.string if soup.title else 'N/A'}")
        print(f"內容長度: {len(response.content)} bytes")
        
        # 尋找可能的訊息容器
        print("\n🔍 尋找可能的訊息元素:")
        
        # 常見的訊息容器標籤和類別
        possible_containers = [
            'div[class*="message"]',
            'div[class*="chat"]',
            'div[class*="msg"]',
            'div[class*="content"]',
            'li[class*="message"]',
            'li[class*="chat"]',
            'p[class*="message"]',
            '.message',
            '.chat-message',
            '.msg',
            '.content',
            '[data-message]',
            '[data-chat]'
        ]
        
        found_elements = {}
        
        for selector in possible_containers:
            elements = soup.select(selector)
            if elements:
                found_elements[selector] = len(elements)
                print(f"  ✓ {selector}: {len(elements)} 個元素")
                
                # 顯示前幾個元素的內容
                for i, elem in enumerate(elements[:3]):
                    text = elem.get_text(strip=True)
                    if text and len(text) > 10:
                        print(f"    範例 {i+1}: {text[:100]}...")
        
        if not found_elements:
            print("  ❌ 未找到明顯的訊息容器")
            
            # 嘗試尋找所有文字內容
            print("\n🔍 嘗試分析所有文字元素:")
            all_text_elements = soup.find_all(['p', 'div', 'span', 'li'])
            
            for elem in all_text_elements[:10]:
                text = elem.get_text(strip=True)
                if text and len(text) > 20:
                    print(f"  • {text[:100]}...")
        
        # 檢查是否有 JavaScript 動態載入內容
        scripts = soup.find_all('script')
        print(f"\n📜 JavaScript 腳本數量: {len(scripts)}")
        
        # 儲存完整的 HTML 供分析
        with open('website_dump.html', 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify()))
        print("\n💾 完整 HTML 已儲存到 website_dump.html")
        
        # 檢查是否有 WebSocket 或其他即時通訊
        for script in scripts:
            if script.string:
                script_content = script.string.lower()
                if any(keyword in script_content for keyword in ['websocket', 'socket.io', 'ws://', 'wss://']):
                    print("⚠️  檢測到可能的 WebSocket 連線，網站可能使用即時通訊")
                    break
        
        return found_elements
        
    except Exception as e:
        print(f"❌ 分析失敗: {e}")
        return {}

def test_extraction():
    """測試訊息提取"""
    print("\n🧪 測試訊息提取...")
    
    # 基於分析結果調整選擇器
    selectors_to_test = [
        'div',  # 通用 div
        'p',    # 段落
        'li',   # 列表項目
        'span', # 行內元素
    ]
    
    url = "https://pal.tw/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for selector in selectors_to_test:
            elements = soup.select(selector)
            messages = []
            
            for elem in elements:
                text = elem.get_text(strip=True)
                # 過濾有意義的文字（長度大於15，包含中文或英文）
                if text and len(text) > 15 and any('\u4e00' <= char <= '\u9fff' or char.isalpha() for char in text):
                    messages.append(text)
            
            if messages:
                print(f"\n📝 使用選擇器 '{selector}' 找到 {len(messages)} 條可能的訊息:")
                for i, msg in enumerate(messages[:5]):  # 只顯示前5條
                    print(f"  {i+1}. {msg[:100]}...")
    
    except Exception as e:
        print(f"❌ 測試失敗: {e}")

if __name__ == "__main__":
    print("🤖 pal.tw 網站分析工具")
    print("=" * 50)
    
    # 分析網站結構
    found_elements = analyze_website()
    
    # 測試訊息提取
    test_extraction()
    
    print("\n✅ 分析完成！")
    print("請檢查 website_dump.html 文件以進行更詳細的分析") 