import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import asyncio
import os
from datetime import datetime, timedelta
import json
import logging
from dotenv import load_dotenv
import aiohttp
import hashlib

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
last_warning_time = None  # 追踪最後警告時間

class KeywordCatcher:
    def __init__(self):
        self.url = "https://pal.tw/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.test_mode = True  # 開啟測試模式
        self.message_counter = 0
    
    def fetch_messages(self):
        """從 pal.tw 抓取最新訊息"""
        global last_warning_time
        
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            messages = []
            
            # 基於網站分析結果，嘗試抓取動態內容
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
            
            # 如果沒有找到實際訊息，在測試模式下生成模擬訊息
            if not messages and self.test_mode:
                current_time = datetime.now()
                
                # 只有在超過5分鐘沒有警告時才記錄警告
                if (last_warning_time is None or 
                    current_time - last_warning_time > timedelta(minutes=5)):
                    logger.warning("未找到聊天訊息，可能需要 WebSocket 連接或 API 訪問")
                    last_warning_time = current_time
                
                # 生成測試訊息（每10次抓取生成一次）
                self.message_counter += 1
                if self.message_counter % 10 == 0:
                    test_messages = [
                        "測試訊息: 有人在賣楓葉嗎？",
                        "測試訊息: 尋找交易夥伴",
                        "測試訊息: 公會招募中，歡迎新手",
                        "測試訊息: 組隊打王，缺治療",
                        "測試訊息: 賣裝備，價格優惠"
                    ]
                    
                    import random
                    test_msg = random.choice(test_messages)
                    messages.append({
                        'text': f"[測試模式] {test_msg}",
                        'timestamp': datetime.now().isoformat()
                    })
                    logger.info(f"生成測試訊息: {test_msg}")
            
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
        logger.info("網站監控任務已啟動")

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
        logger.info(f"用戶 {ctx.author.name} 添加關鍵字: {keyword}")
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
        logger.info(f"用戶 {ctx.author.name} 移除關鍵字: {keyword}")
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
    logger.info(f"通知頻道已設定為: {ctx.channel.name}")

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

@bot.command(name='toggle_test_mode')
async def toggle_test_mode(ctx):
    """切換測試模式"""
    keyword_catcher.test_mode = not keyword_catcher.test_mode
    status = "開啟" if keyword_catcher.test_mode else "關閉"
    
    embed = discord.Embed(
        title="⚙️ 測試模式切換",
        description=f"測試模式已{status}",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)
    logger.info(f"測試模式已{status}")

@tasks.loop(seconds=30)  # 每30秒檢查一次
async def monitor_website():
    """監控網站的主要任務"""
    global previous_messages, notification_channel
    
    try:
        messages = keyword_catcher.fetch_messages()
        
        for message in messages:
            message_text = message['text']
            message_hash = hashlib.md5(message_text.encode()).hexdigest()
            
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
                logger.info(f"已發送通知給用戶 {user.name}: {matched_keywords}")
            except discord.Forbidden:
                if notification_channel:
                    await notification_channel.send(f"{user.mention}", embed=embed)
                    logger.info(f"已發送通知到頻道: {matched_keywords}")
    
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
                logger.info(f"已載入 {len(monitored_keywords)} 個用戶的關鍵字")
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
    logger.error(f"指令錯誤: {error}")

if __name__ == "__main__":
    # 從環境變數獲取機器人 token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("請在 .env 文件中設定 DISCORD_TOKEN")
        exit(1)
    
    # 啟動訊息
    logger.info("正在啟動 MapleStory Worlds Artale 關鍵字監控機器人...")
    bot.run(token) 