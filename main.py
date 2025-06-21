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
bot = commands.Bot(command_prefix='!', intents=intents)

# 全域變數
monitored_keywords = {}
previous_messages = set()
notification_channel = None
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
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with websockets.connect(self.ws_url, ssl=ssl_context) as websocket:
                self.ws_connected = True
                logger.info("WebSocket 連接成功！")
                
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if isinstance(data, list):
                            for msg in data:
                                self.process_message(msg)
                        else:
                            self.process_message(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 解析錯誤: {e}")
                    except Exception as e:
                        logger.error(f"處理 WebSocket 訊息時發生錯誤: {e}")
                        
        except Exception as e:
            logger.error(f"WebSocket 連接錯誤: {e}")
            self.ws_connected = False
    
    def process_message(self, msg):
        """處理單條訊息"""
        try:
            if not isinstance(msg, dict):
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
                
                logger.debug(f"收到訊息: {username}: {text}")
                
        except Exception as e:
            logger.error(f"處理訊息時發生錯誤: {e}")
    
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
    logger.info(f'Bot {bot.user} is ready!')
    
    bot_status["status"] = "運行中"
    bot_status["last_update"] = datetime.now().isoformat()
    
    load_keywords()
    
    # 啟動 WebSocket 連接
    asyncio.create_task(keyword_catcher.connect_websocket())
    
    if not monitor_website.is_running():
        monitor_website.start()
        logger.info("網站監控任務已啟動")

@bot.command(name='add_keyword')
async def add_keyword(ctx, *, keyword):
    user_id = ctx.author.id
    
    if user_id not in monitored_keywords:
        monitored_keywords[user_id] = []
    
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
    try:
        with open('keywords.json', 'w', encoding='utf-8') as f:
            json.dump(monitored_keywords, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"儲存關鍵字時發生錯誤: {e}")

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