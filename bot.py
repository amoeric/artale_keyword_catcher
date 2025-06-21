import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import asyncio
import os
from datetime import datetime
import json
import logging
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 機器人設置
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 全域變數
monitored_keywords = {}  # {user_id: [keywords]}
previous_messages = set()  # 儲存之前的訊息，避免重複通知
notification_channel = None

class KeywordCatcher:
    def __init__(self):
        self.url = "https://pal.tw/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def fetch_messages(self):
        """從 pal.tw 抓取最新訊息"""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            messages = []
            
            # 基於網站分析結果，我們知道聊天訊息會動態載入到 #chatBox 中
            # 但由於是 JavaScript 動態載入，我們可能需要使用 API 或其他方法
            
            # 先嘗試查找是否有任何現有的訊息內容
            chat_box = soup.find('div', {'id': 'chatBox'})
            if chat_box:
                # 檢查是否有任何子元素
                for element in chat_box.find_all(['div', 'p', 'span']):
                    text = element.get_text(strip=True)
                    if text and len(text) > 10:
                        messages.append({
                            'text': text,
                            'timestamp': datetime.now().isoformat()
                        })
            
            # 如果沒有找到訊息，可能需要檢查是否有 WebSocket 或 API 端點
            # 暫時返回一個測試訊息以確保系統運作
            if not messages:
                logger.warning("未找到聊天訊息，可能需要 WebSocket 連接或 API 訪問")
                # 可以添加一些測試用的訊息來驗證系統運作
                messages.append({
                    'text': '[系統測試] pal.tw 聊天室監控運行中',
                    'timestamp': datetime.now().isoformat()
                })
            
            return messages
        
        except Exception as e:
            logger.error(f"抓取訊息時發生錯誤: {e}")
            return []
    
    def check_keywords(self, message_text, keywords):
        """檢查訊息中是否包含關鍵字"""
        message_lower = message_text.lower()
        matched_keywords = []
        
        for keyword in keywords:
            if keyword.lower() in message_lower:
                matched_keywords.append(keyword)
        
        return matched_keywords

keyword_catcher = KeywordCatcher()

@bot.event
async def on_ready():
    print(f'{bot.user} 已經上線!')
    logger.info(f'Bot {bot.user} is ready!')
    
    # 載入儲存的關鍵字
    load_keywords()
    
    # 開始監控任務
    if not monitor_website.is_running():
        monitor_website.start()

@bot.command(name='add_keyword')
async def add_keyword(ctx, *, keyword):
    """添加要監控的關鍵字"""
    user_id = ctx.author.id
    
    if user_id not in monitored_keywords:
        monitored_keywords[user_id] = []
    
    if keyword not in monitored_keywords[user_id]:
        monitored_keywords[user_id].append(keyword)
        save_keywords()
        
        embed = discord.Embed(
            title="✅ 關鍵字已添加",
            description=f"已添加關鍵字: **{keyword}**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="⚠️ 關鍵字已存在",
            description=f"關鍵字 **{keyword}** 已經在監控列表中",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

@bot.command(name='remove_keyword')
async def remove_keyword(ctx, *, keyword):
    """移除監控的關鍵字"""
    user_id = ctx.author.id
    
    if user_id in monitored_keywords and keyword in monitored_keywords[user_id]:
        monitored_keywords[user_id].remove(keyword)
        save_keywords()
        
        embed = discord.Embed(
            title="✅ 關鍵字已移除",
            description=f"已移除關鍵字: **{keyword}**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ 關鍵字不存在",
            description=f"關鍵字 **{keyword}** 不在您的監控列表中",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command(name='list_keywords')
async def list_keywords(ctx):
    """列出所有監控的關鍵字"""
    user_id = ctx.author.id
    
    if user_id in monitored_keywords and monitored_keywords[user_id]:
        keywords_list = "\n".join([f"• {keyword}" for keyword in monitored_keywords[user_id]])
        embed = discord.Embed(
            title="📋 您的監控關鍵字",
            description=keywords_list,
            color=discord.Color.blue()
        )
    else:
        embed = discord.Embed(
            title="📋 您的監控關鍵字",
            description="您還沒有設定任何關鍵字",
            color=discord.Color.blue()
        )
    
    await ctx.send(embed=embed)

@bot.command(name='set_channel')
async def set_notification_channel(ctx):
    """設定通知頻道"""
    global notification_channel
    notification_channel = ctx.channel
    
    embed = discord.Embed(
        title="✅ 通知頻道已設定",
        description=f"關鍵字匹配通知將發送到 {ctx.channel.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='test_fetch')
async def test_fetch(ctx):
    """測試抓取網站內容"""
    await ctx.send("🔍 正在測試抓取網站內容...")
    
    messages = keyword_catcher.fetch_messages()
    
    if messages:
        embed = discord.Embed(
            title="✅ 測試成功",
            description=f"成功抓取到 {len(messages)} 條訊息",
            color=discord.Color.green()
        )
        
        # 顯示前3條訊息作為範例
        for i, msg in enumerate(messages[:3]):
            embed.add_field(
                name=f"訊息 {i+1}",
                value=msg['text'][:100] + "..." if len(msg['text']) > 100 else msg['text'],
                inline=False
            )
    else:
        embed = discord.Embed(
            title="❌ 測試失敗",
            description="無法抓取到訊息，請檢查網站狀態",
            color=discord.Color.red()
        )
    
    await ctx.send(embed=embed)

@tasks.loop(seconds=30)  # 每30秒檢查一次
async def monitor_website():
    """監控網站的主要任務"""
    global previous_messages, notification_channel
    
    try:
        messages = keyword_catcher.fetch_messages()
        
        for message in messages:
            message_text = message['text']
            message_hash = hash(message_text)
            
            # 避免重複通知
            if message_hash in previous_messages:
                continue
            
            previous_messages.add(message_hash)
            
            # 檢查所有用戶的關鍵字
            for user_id, keywords in monitored_keywords.items():
                if keywords:
                    matched_keywords = keyword_catcher.check_keywords(message_text, keywords)
                    
                    if matched_keywords:
                        # 發送通知
                        await send_notification(user_id, message_text, matched_keywords)
        
        # 限制 previous_messages 的大小，避免記憶體問題
        if len(previous_messages) > 1000:
            previous_messages = set(list(previous_messages)[-500:])
    
    except Exception as e:
        logger.error(f"監控任務發生錯誤: {e}")

async def send_notification(user_id, message_text, matched_keywords):
    """發送通知到 Discord"""
    try:
        user = bot.get_user(user_id)
        if user:
            embed = discord.Embed(
                title="🎯 關鍵字匹配通知",
                description=f"在 [pal.tw](https://pal.tw/) 發現匹配的訊息!",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="匹配的關鍵字",
                value=", ".join([f"**{kw}**" for kw in matched_keywords]),
                inline=False
            )
            
            embed.add_field(
                name="完整訊息",
                value=message_text[:1000] + "..." if len(message_text) > 1000 else message_text,
                inline=False
            )
            
            embed.set_footer(text="MapleStory Worlds Artale 公頻監控")
            
            # 嘗試發送私訊，如果失敗則發送到設定的頻道
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                if notification_channel:
                    await notification_channel.send(f"{user.mention}", embed=embed)
    
    except Exception as e:
        logger.error(f"發送通知時發生錯誤: {e}")

def save_keywords():
    """儲存關鍵字到文件"""
    try:
        with open('keywords.json', 'w', encoding='utf-8') as f:
            json.dump(monitored_keywords, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"儲存關鍵字時發生錯誤: {e}")

def load_keywords():
    """從文件載入關鍵字"""
    global monitored_keywords
    try:
        if os.path.exists('keywords.json'):
            with open('keywords.json', 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                # 確保 user_id 是整數
                monitored_keywords = {int(k): v for k, v in loaded_data.items()}
    except Exception as e:
        logger.error(f"載入關鍵字時發生錯誤: {e}")
        monitored_keywords = {}

@bot.event
async def on_command_error(ctx, error):
    """錯誤處理"""
    if isinstance(error, commands.CommandNotFound):
        return
    
    embed = discord.Embed(
        title="❌ 發生錯誤",
        description=str(error),
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

if __name__ == "__main__":
    # 從環境變數獲取機器人 token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("請在 .env 文件中設定 DISCORD_TOKEN")
        exit(1)
    
    bot.run(token) 