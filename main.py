from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
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
import hashlib
import threading
import websockets
import ssl

# 載入環境變數
load_dotenv()

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 應用程式
app = FastAPI(title="MapleStory Worlds Artale 關鍵字監控", description="Discord 機器人 Web 控制台")

# Discord 機器人設置
intents = discord.Intents.default()
intents.message_content = True

# 自定義前綴函數 - 只在被提及時才處理指令
def get_prefix(bot, message):
    # 如果機器人被提及，則允許 ! 前綴
    if bot.user and bot.user.mentioned_in(message):
        return '!'
    # 否則返回一個不可能的前綴，這樣就不會處理指令
    return "NEVER_MATCH_THIS_PREFIX_12345"

bot = commands.Bot(command_prefix=get_prefix, intents=intents)

# 全域變數
monitored_keywords = {}
user_notification_channels = {}  # 儲存每個用戶的通知頻道
previous_messages = set()
notification_channel = None  # 全域通知頻道（備用）
last_warning_time = None
bot_status = {"status": "停止", "last_update": None, "users_count": 0, "keywords_count": 0}

class KeywordCatcher:
    def __init__(self):
        self.url = "https://pal.tw/"
        self.ws_url = "wss://api.pal.tw"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.test_mode = True
        self.message_counter = 0
        self.latest_messages = []
        self.ws_connected = False
    
    async def connect_websocket(self):
        """連接到 WebSocket 並監聽訊息"""
        while True:  # 無限重連機制
            try:
                logger.info(f"🔌 正在連接 WebSocket: {self.ws_url}")
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                async with websockets.connect(self.ws_url, ssl=ssl_context) as websocket:
                    self.ws_connected = True
                    logger.info("✅ WebSocket 連接成功！開始監聽訊息...")
                    
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            logger.info(f"📦 收到原始訊息: {len(data) if isinstance(data, list) else 1} 條")
                            
                            if isinstance(data, list):
                                logger.info(f"📋 處理訊息批次: {len(data)} 條訊息")
                                for msg in data:
                                    self.process_message(msg)
                            else:
                                logger.info("📋 處理單條訊息")
                                self.process_message(data)
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"❌ JSON 解析錯誤: {e}")
                            logger.error(f"原始訊息: {message}")
                        except Exception as e:
                            logger.error(f"❌ 處理 WebSocket 訊息時發生錯誤: {e}")
                            
            except Exception as e:
                logger.error(f"❌ WebSocket 連接錯誤: {e}")
                self.ws_connected = False
                logger.info("⏳ 5秒後重新連接...")
                await asyncio.sleep(5)
    
    def process_message(self, msg):
        """處理單條訊息"""
        try:
            if not isinstance(msg, dict):
                logger.warning(f"收到非字典格式訊息: {type(msg)} - {msg}")
                return
                
            channel = msg.get('channel', '')
            username = msg.get('username', '')
            text = msg.get('text', '')
            timestamp = msg.get('timestamp', datetime.now().isoformat())
            
            if text:
                channel_display = f"[{str(channel).zfill(4)}]" if channel else ""
                full_message = f"{channel_display} {username}: {text}"
                
                message_data = {
                    'text': text,
                    'full_text': full_message,
                    'channel': channel_display,
                    'username': username,
                    'timestamp': timestamp
                }
                
                # 保留最新的 100 條訊息
                self.latest_messages.append(message_data)
                if len(self.latest_messages) > 100:
                    self.latest_messages.pop(0)
                
                # 詳細日誌記錄每條訊息
                logger.info(f"📨 WebSocket 訊息: {channel_display} {username}: {text}")
                
                # 如果訊息包含常見關鍵字，特別標記
                if any(keyword in text.lower() for keyword in ['雪', '楓葉', '收', '賣', '組隊']):
                    logger.info(f"🎯 包含關鍵字的訊息: {full_message}")
                
                # 立即檢查用戶關鍵字並發送通知
                asyncio.create_task(self.check_user_keywords_and_notify(message_data))
            else:
                logger.debug(f"收到空訊息: {msg}")
                
        except Exception as e:
            logger.error(f"處理訊息時發生錯誤: {e}")
    
    async def check_user_keywords_and_notify(self, message_data):
        """檢查用戶關鍵字並發送通知"""
        try:
            global monitored_keywords, previous_messages
            
            message_text = message_data['text']
            message_hash = hashlib.md5(message_text.encode()).hexdigest()
            
            # 避免重複通知
            if message_hash in previous_messages:
                return
            
            previous_messages.add(message_hash)
            
            # 檢查每個用戶的關鍵字
            for user_id, keywords in monitored_keywords.items():
                if keywords:
                    matched_keywords = self.check_keywords(message_text, keywords)
                    
                    if matched_keywords:
                        logger.info(f"🔔 為用戶 {user_id} 找到匹配關鍵字: {matched_keywords}")
                        await send_notification(user_id, message_data, matched_keywords)
            
            # 清理舊的訊息哈希
            if len(previous_messages) > 1000:
                previous_messages = set(list(previous_messages)[-500:])
                
        except Exception as e:
            logger.error(f"檢查用戶關鍵字時發生錯誤: {e}")
    
    def fetch_messages(self):
        """獲取最新訊息（用於定時檢查）"""
        global last_warning_time
        
        # 如果 WebSocket 連接正常，返回最新訊息
        if self.ws_connected and self.latest_messages:
            messages = self.latest_messages.copy()
            self.latest_messages.clear()  # 清空已處理的訊息
            return messages
        
        # 如果沒有 WebSocket 連接，使用測試模式
        current_time = datetime.now()
        
        if (last_warning_time is None or 
            current_time - last_warning_time > timedelta(minutes=5)):
            logger.warning("WebSocket 未連接，使用測試模式")
            last_warning_time = current_time
        
        # 測試模式：每10次抓取生成一個測試訊息
        self.message_counter += 1
        if self.message_counter % 10 == 0:
            test_messages = [
                "3362頻6洞收拳套攻擊10% 1:5雪/收拉圖斯腰帶談價",
                "收楓葉 1:100 大量收購",
                "賣+7武器 屬性優秀 價格面議",
                "組隊打扎昆 缺坦克和治療",
                "公會招募 歡迎新手加入"
            ]
            
            import random
            test_msg = random.choice(test_messages)
            return [{
                'text': test_msg,
                'full_text': f"[測試] TestUser#1234: {test_msg}",
                'channel': "[測試]",
                'username': "TestUser#1234",
                'timestamp': datetime.now().isoformat()
            }]
        
        return []
    
    def check_keywords(self, message_text, keywords):
        message_lower = message_text.lower()
        matched_keywords = []
        
        for keyword in keywords:
            if keyword.lower() in message_lower:
                matched_keywords.append(keyword)
        
        return matched_keywords

keyword_catcher = KeywordCatcher()

# Discord 機器人事件和指令
@bot.event
async def on_ready():
    global bot_status
    print(f'{bot.user} 已經上線!')
    logger.info(f'🤖 Bot {bot.user} is ready!')
    
    bot_status["status"] = "運行中"
    bot_status["last_update"] = datetime.now().isoformat()
    
    load_keywords()
    load_user_settings()
    
    # 啟動 WebSocket 連接
    asyncio.create_task(keyword_catcher.connect_websocket())
    
    if not monitor_website.is_running():
        monitor_website.start()
        logger.info("📊 網站監控任務已啟動")

@bot.event
async def on_message(message):
    # 記錄所有非機器人訊息
    if not message.author.bot:
        logger.info(f"💬 收到訊息: {message.author.name}: {message.content}")
        
        # 檢查是否提及機器人且包含指令
        if bot.user.mentioned_in(message):
            logger.info(f"📢 收到提及: {message.author.name}: {message.content}")
            
            # 提取指令部分（移除 @ 機器人的部分）
            content = message.content
            # 移除所有提及（包括用戶和角色）
            import re
            content = re.sub(r'<@[!&]?\d+>', '', content).strip()
            
            # 檢查是否為指令
            if content.startswith('!'):
                logger.info(f"🎯 檢測到提及指令: {content}")
                # 創建一個新的訊息對象來處理指令
                message.content = content
    
    # 處理指令
    await bot.process_commands(message)

@bot.command(name='add_keyword')
async def add_keyword(ctx, *, keyword):
    logger.info(f"🎯 收到添加關鍵字指令: 用戶={ctx.author.name}({ctx.author.id}), 關鍵字={keyword}")
    user_id = ctx.author.id
    
    if user_id not in monitored_keywords:
        monitored_keywords[user_id] = []
        logger.info(f"👤 為新用戶 {ctx.author.name} 創建關鍵字列表")
    
    if keyword not in monitored_keywords[user_id]:
        monitored_keywords[user_id].append(keyword)
        save_keywords()
        update_bot_status()
        
        embed = discord.Embed(
            title="✅ 關鍵字已添加",
            description=f"已添加關鍵字: **{keyword}**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        logger.info(f"✅ 用戶 {ctx.author.name} 成功添加關鍵字: {keyword}")
    else:
        embed = discord.Embed(
            title="⚠️ 關鍵字已存在",
            description=f"關鍵字 **{keyword}** 已經在監控列表中",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        logger.info(f"⚠️ 用戶 {ctx.author.name} 嘗試添加已存在的關鍵字: {keyword}")

@bot.command(name='remove_keyword')
async def remove_keyword(ctx, *, keyword):
    user_id = ctx.author.id
    
    if user_id in monitored_keywords and keyword in monitored_keywords[user_id]:
        monitored_keywords[user_id].remove(keyword)
        save_keywords()
        update_bot_status()
        
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
    global user_notification_channels
    user_id = ctx.author.id
    user_notification_channels[user_id] = ctx.channel.id
    
    # 同時儲存到文件
    save_user_settings()
    
    embed = discord.Embed(
        title="✅ 個人通知頻道已設定",
        description=f"您的關鍵字匹配通知將發送到 {ctx.channel.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)
    logger.info(f"用戶 {ctx.author.name} 設定通知頻道為: {ctx.channel.name}")

@bot.command(name='channel_info')
async def channel_info(ctx):
    user_id = ctx.author.id
    
    if user_id in user_notification_channels and user_notification_channels[user_id]:
        channel_obj = bot.get_channel(user_notification_channels[user_id])
        if channel_obj:
            embed = discord.Embed(
                title="📍 您的通知頻道設定",
                description=f"通知將發送到: {channel_obj.mention}",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title="⚠️ 通知頻道無效",
                description="您設定的通知頻道已失效，請重新設定",
                color=discord.Color.orange()
            )
    else:
        embed = discord.Embed(
            title="📍 您的通知頻道設定",
            description="您還沒有設定通知頻道，將嘗試發送私訊",
            color=discord.Color.blue()
        )
    
    await ctx.send(embed=embed)

@bot.command(name='test_fetch')
async def test_fetch(ctx):
    await ctx.send("🔍 正在測試抓取網站內容...")
    
    messages = keyword_catcher.fetch_messages()
    
    if messages:
        embed = discord.Embed(
            title="✅ 測試成功",
            description=f"成功抓取到 {len(messages)} 條訊息",
            color=discord.Color.green()
        )
        
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

@bot.command(name='test_notify')
async def test_notify(ctx):
    """測試關鍵字匹配和通知功能"""
    await ctx.send("🧪 正在測試關鍵字匹配和通知功能...")
    
    user_id = ctx.author.id
    if user_id not in monitored_keywords or not monitored_keywords[user_id]:
        embed = discord.Embed(
            title="⚠️ 沒有關鍵字",
            description="您還沒有設定任何關鍵字，請先使用 `!add_keyword` 添加關鍵字",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        return
    
    # 獲取訊息並檢查關鍵字
    messages = keyword_catcher.fetch_messages()
    
    if not messages:
        # 如果沒有真實訊息，創建測試訊息
        test_keywords = monitored_keywords[user_id]
        test_message = {
            'text': f"測試訊息包含關鍵字: {test_keywords[0]} - 這是一條測試通知",
            'full_text': f"[測試] TestUser: 測試訊息包含關鍵字: {test_keywords[0]} - 這是一條測試通知",
            'channel': "[測試]",
            'username': "TestUser",
            'timestamp': datetime.now().isoformat()
        }
        messages = [test_message]
    
    notification_sent = False
    for message in messages:
        message_text = message['text']
        matched_keywords = keyword_catcher.check_keywords(message_text, monitored_keywords[user_id])
        
        if matched_keywords:
            await send_notification(user_id, message, matched_keywords)
            notification_sent = True
            
            embed = discord.Embed(
                title="✅ 測試成功",
                description=f"找到匹配關鍵字: {', '.join(matched_keywords)}\n已發送通知！",
                color=discord.Color.green()
            )
            embed.add_field(
                name="測試訊息",
                value=message_text[:200] + "..." if len(message_text) > 200 else message_text,
                inline=False
            )
            await ctx.send(embed=embed)
            break
    
    if not notification_sent:
        embed = discord.Embed(
            title="📋 測試結果",
            description=f"檢查了 {len(messages)} 條訊息，沒有找到匹配的關鍵字",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="您的關鍵字",
            value=", ".join(monitored_keywords[user_id]),
            inline=False
        )
        if messages:
            embed.add_field(
                name="最新訊息示例",
                value=messages[0]['text'][:200] + "..." if len(messages[0]['text']) > 200 else messages[0]['text'],
                inline=False
            )
        await ctx.send(embed=embed)

@bot.command(name='toggle_test_mode')
async def toggle_test_mode(ctx):
    keyword_catcher.test_mode = not keyword_catcher.test_mode
    status = "開啟" if keyword_catcher.test_mode else "關閉"
    
    embed = discord.Embed(
        title="⚙️ 測試模式切換",
        description=f"測試模式已{status}",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)
    logger.info(f"測試模式已{status}")

@bot.command(name='commands')
async def help_command(ctx):
    embed = discord.Embed(
        title="🤖 Keyword Catcher 使用說明",
        description="以下是所有可用的指令：",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📝 關鍵字管理",
        value="`@機器人 !add_keyword <關鍵字>` - 添加監控關鍵字\n"
              "`@機器人 !remove_keyword <關鍵字>` - 移除監控關鍵字\n"
              "`@機器人 !list_keywords` - 查看您的關鍵字列表",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ 設定",
        value="`@機器人 !set_channel` - 設定個人通知頻道\n"
              "`@機器人 !channel_info` - 查看通知頻道設定\n"
              "`@機器人 !commands` - 顯示此說明訊息",
        inline=False
    )
    
    embed.add_field(
        name="🔧 測試功能",
        value="`@機器人 !test_fetch` - 測試網站抓取功能\n"
              "`@機器人 !test_notify` - 測試關鍵字匹配和通知\n"
              "`@機器人 !toggle_test_mode` - 切換測試模式",
        inline=False
    )
    
    embed.add_field(
        name="📋 使用說明",
        value="• **必須先 @ 機器人才能使用指令**\n"
              "• 機器人會監控 pal.tw 網站的聊天訊息\n"
              "• 當出現您設定的關鍵字時會自動通知\n"
              "• 通知優先發送私訊，如設定頻道則備援發送\n"
              "• 每30秒檢查一次新訊息",
        inline=False
    )
    
    embed.add_field(
        name="🌐 監控網站",
        value="[MapleStory Worlds Artale 公頻廣播](https://pal.tw/)",
        inline=False
    )
    
    embed.set_footer(text="如有問題請聯繫管理員")
    
    await ctx.send(embed=embed)
    logger.info(f"用戶 {ctx.author.name} 查看了指令說明")

@tasks.loop(seconds=30)
async def monitor_website():
    global previous_messages, notification_channel, bot_status
    
    try:
        messages = keyword_catcher.fetch_messages()
        bot_status["last_update"] = datetime.now().isoformat()
        
        for message in messages:
            message_text = message['text']
            message_hash = hashlib.md5(message_text.encode()).hexdigest()
            
            if message_hash in previous_messages:
                continue
            
            previous_messages.add(message_hash)
            
            for user_id, keywords in monitored_keywords.items():
                if keywords:
                    matched_keywords = keyword_catcher.check_keywords(message_text, keywords)
                    
                    if matched_keywords:
                        await send_notification(user_id, message, matched_keywords)
        
        if len(previous_messages) > 1000:
            previous_messages = set(list(previous_messages)[-500:])
    
    except Exception as e:
        logger.error(f"監控任務發生錯誤: {e}")
        bot_status["status"] = f"錯誤: {e}"

async def send_notification(user_id, message_data, matched_keywords):
    try:
        user = bot.get_user(user_id)
        if user:
            # 處理訊息數據格式
            if isinstance(message_data, dict):
                message_text = message_data.get('text', '')
                full_text = message_data.get('full_text', message_text)
                username = message_data.get('username', '未知用戶')
                channel = message_data.get('channel', '')
            else:
                message_text = str(message_data)
                full_text = message_text
                username = '未知用戶'
                channel = ''
            
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
            
            if username and username != '未知用戶':
                embed.add_field(
                    name="發言者",
                    value=f"`{username}`",
                    inline=True
                )
            
            if channel:
                embed.add_field(
                    name="頻道",
                    value=f"`{channel}`",
                    inline=True
                )
            
            embed.add_field(
                name="訊息內容",
                value=f"```{message_text[:800]}```" + ("..." if len(message_text) > 800 else ""),
                inline=False
            )
            
            embed.set_footer(text="MapleStory Worlds Artale 公頻監控")
            
            # 優先發送到用戶設定的通知頻道
            if user_id in user_notification_channels and user_notification_channels[user_id]:
                try:
                    channel_obj = bot.get_channel(user_notification_channels[user_id])
                    if channel_obj:
                        await channel_obj.send(f"{user.mention}", embed=embed)
                        logger.info(f"已發送通知到用戶 {user.name} 的設定頻道: {matched_keywords}")
                        return
                except Exception as e:
                    logger.error(f"發送到用戶設定頻道失敗: {e}")
            
            # 如果沒有設定個人頻道，嘗試發送私訊
            try:
                await user.send(embed=embed)
                logger.info(f"已發送私訊通知給用戶 {user.name}: {matched_keywords}")
            except discord.Forbidden:
                # 私訊失敗，發送到全域通知頻道
                if notification_channel:
                    await notification_channel.send(f"{user.mention}", embed=embed)
                    logger.info(f"已發送通知到全域頻道: {matched_keywords}")
                else:
                    logger.warning(f"無法發送通知給用戶 {user.name}，請設定通知頻道")
    
    except Exception as e:
        logger.error(f"發送通知時發生錯誤: {e}")

def save_keywords():
    try:
        with open('keywords.json', 'w', encoding='utf-8') as f:
            json.dump(monitored_keywords, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"儲存關鍵字時發生錯誤: {e}")

def save_user_settings():
    try:
        with open('user_settings.json', 'w', encoding='utf-8') as f:
            json.dump(user_notification_channels, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"儲存用戶設定時發生錯誤: {e}")

def load_keywords():
    global monitored_keywords
    try:
        if os.path.exists('keywords.json'):
            with open('keywords.json', 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                monitored_keywords = {int(k): v for k, v in loaded_data.items()}
                logger.info(f"已載入 {len(monitored_keywords)} 個用戶的關鍵字")
        update_bot_status()
    except Exception as e:
        logger.error(f"載入關鍵字時發生錯誤: {e}")
        monitored_keywords = {}

def load_user_settings():
    global user_notification_channels
    try:
        if os.path.exists('user_settings.json'):
            with open('user_settings.json', 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
                user_notification_channels = {int(k): v for k, v in loaded_data.items()}
                logger.info(f"已載入 {len(user_notification_channels)} 個用戶的通知頻道設定")
    except Exception as e:
        logger.error(f"載入用戶設定時發生錯誤: {e}")
        user_notification_channels = {}

def update_bot_status():
    global bot_status
    bot_status["users_count"] = len(monitored_keywords)
    bot_status["keywords_count"] = sum(len(keywords) for keywords in monitored_keywords.values())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    
    embed = discord.Embed(
        title="❌ 發生錯誤",
        description=str(error),
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)
    logger.error(f"指令錯誤: {error}")

# FastAPI 路由
@app.get("/", response_class=HTMLResponse)
async def home():
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MapleStory Worlds Artale 關鍵字監控</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; }}
            .status {{ padding: 15px; margin: 20px 0; border-radius: 5px; }}
            .status.running {{ background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; }}
            .status.stopped {{ background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }}
            .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
            .stat-card {{ background: #e9ecef; padding: 20px; border-radius: 5px; text-align: center; }}
            .commands {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 MapleStory Worlds Artale 關鍵字監控</h1>
            
            <div class="status {'running' if bot_status['status'] == '運行中' else 'stopped'}">
                <strong>機器人狀態:</strong> {bot_status['status']}<br>
                <strong>最後更新:</strong> {bot_status.get('last_update', '未知')}
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <h3>{bot_status['users_count']}</h3>
                    <p>註冊用戶</p>
                </div>
                <div class="stat-card">
                    <h3>{bot_status['keywords_count']}</h3>
                    <p>監控關鍵字</p>
                </div>
            </div>
            
            <div class="commands">
                <h3>🎮 Discord 機器人指令</h3>
                <p><code>!add_keyword &lt;關鍵字&gt;</code> - 添加監控關鍵字</p>
                <p><code>!remove_keyword &lt;關鍵字&gt;</code> - 移除監控關鍵字</p>
                <p><code>!list_keywords</code> - 查看你的關鍵字</p>
                <p><code>!set_channel</code> - 設定通知頻道</p>
                <p><code>!test_fetch</code> - 測試網站抓取</p>
                <p><code>!toggle_test_mode</code> - 切換測試模式</p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="/api/status" class="btn">查看 API 狀態</a>
                <a href="/api/test" class="btn">測試網站抓取</a>
                <a href="/health" class="btn">健康檢查</a>
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #6c757d;">
                <p>監控網站: <a href="https://pal.tw/" target="_blank">pal.tw</a></p>
                <p>檢查頻率: 每 30 秒</p>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "bot_status": bot_status}

@app.get("/api/status")
async def api_status():
    return {
        "bot_status": bot_status,
        "monitored_users": len(monitored_keywords),
        "total_keywords": sum(len(keywords) for keywords in monitored_keywords.values()),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/test")
async def api_test():
    messages = keyword_catcher.fetch_messages()
    return {
        "success": len(messages) > 0,
        "message_count": len(messages),
        "messages": messages[:3],
        "timestamp": datetime.now().isoformat()
    }

# 在背景運行 Discord 機器人
def run_discord_bot():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("請在環境變數中設定 DISCORD_TOKEN")
        return
    
    logger.info("正在啟動 Discord 機器人...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot.run(token)
    except Exception as e:
        logger.error(f"Discord 機器人啟動失敗: {e}")

# 啟動 Discord 機器人
if __name__ == "__main__":
    # 在背景執行緒中啟動 Discord 機器人
    bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
    bot_thread.start()
    
    # 啟動 FastAPI 服務器
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"正在啟動 Web 服務器，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
else:
    # 如果被其他模組導入，在背景啟動機器人
    bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
    bot_thread.start() 