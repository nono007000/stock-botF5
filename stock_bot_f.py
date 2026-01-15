import discord
from discord.ext import commands, tasks
import yfinance as yf
import requests
from datetime import datetime, timezone
import os

# ===================== CONFIG =====================

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

CHANNEL_ID = 1461013783383248946  # your channel ID

PERSONAL_STOCKS = {
    "AAPL": {"up": 180, "down": 170, "pct": 3},
    "TSLA": {"up": 250, "down": 230, "pct": 5},
    "NVDA": {"up": 500, "down": 460, "pct": 4},
    "NKE": {"up": 110, "down": 95, "pct": 4},
    "ELF": {"up": 210, "down": 180, "pct": 4},
    "NVO": {"up": 130, "down": 115, "pct": 3},
    "CAKE": {"up": 45, "down": 38, "pct": 4},
    "AMD": {"up": 180, "down": 160, "pct": 3},
    "CRM": {"up": 320, "down": 290, "pct": 3},
    "ADBE": {"up": 650, "down": 600, "pct": 3},
    "SOFI": {"up": 12, "down": 9, "pct": 6},
    "PYPL": {"up": 75, "down": 65, "pct": 4},
    "CELH": {"up": 95, "down": 80, "pct": 5},
    "MSFT": {"up": 390, "down": 360, "pct": 3},
    "META": {"up": 550, "down": 500, "pct": 4},
    "GOOGL": {"up": 170, "down": 150, "pct": 3},
    "AMZN": {"up": 190, "down": 170, "pct": 3},
}

NEWS_SITES = [
    "cnbc.com", "finance.yahoo.com", "marketwatch.com",
    "bloomberg.com", "reuters.com", "seekingalpha.com",
    "benzinga.com", "fool.com", "investopedia.com",
    "forbes.com", "businessinsider.com"
]

MAX_ARTICLES = 3

STATE = {
    "alerted": set(),
    "news_seen": set(),
    "penny_seen": set()
}

# ===================== BOT SETUP =====================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===================== HELPERS =====================

def get_price(symbol):
    try:
        hist = yf.Ticker(symbol).history(period="2d")
        if len(hist) < 2:
            return None, None
        return hist["Close"].iloc[-2], hist["Close"].iloc[-1]
    except:
        return None, None


def fetch_articles(query):
    url = (
        "https://newsapi.org/v2/everything?"
        f"q={query}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
    )

    r = requests.get(url).json()
    if r.get("status") != "ok":
        return []

    now = datetime.now(timezone.utc)
    articles = []

    for a in r["articles"]:
        published = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
        if (now - published).days > 7:
            continue

        link = a["url"]
        if any(site in link for site in NEWS_SITES):
            articles.append((a["title"], link))

        if len(articles) >= MAX_ARTICLES:
            break

    return articles


async def send_auto(msg):
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel is None:
            channel = await bot.fetch_channel(CHANNEL_ID)
        await channel.send(msg)
    except Exception as e:
        print("AUTO SEND ERROR:", e)

# ===================== COMMANDS =====================

@bot.command()
async def testauto(ctx):
    await send_auto("✅ AUTO SYSTEM WORKS")


@bot.command()
async def price(ctx, symbol: str):
    _, cur = get_price(symbol.upper())
    await ctx.send(f"{symbol.upper()}: ${cur:.2f}" if cur else "Price unavailable")


@bot.command()
async def stocknews(ctx, symbol: str):
    articles = fetch_articles(f"{symbol} stock")
    if not articles:
        await ctx.send("No recent articles found.")
        return

    msg = f"📰 **{symbol.upper()} NEWS**\n\n"
    for t, l in articles:
        msg += f"• {t}\n{l}\n\n"
    await ctx.send(msg)


@bot.command()
async def penny(ctx):
    articles = fetch_articles("penny stocks to watch")
    if not articles:
        await ctx.send("No recent penny stock news.")
        return

    msg = "🪙 **PENNY STOCK NEWS**\n\n"
    for t, l in articles:
        msg += f"• {t}\n{l}\n\n"
    await ctx.send(msg)


@bot.command()
async def status(ctx):
    await ctx.send("✅ Bot running")

# ===================== AUTO TASKS =====================

@tasks.loop(minutes=10)
async def auto_price_alerts():
    for s, cfg in PERSONAL_STOCKS.items():
        prev, cur = get_price(s)
        if not cur or not prev:
            continue

        pct = ((cur - prev) / prev) * 100

        if cur >= cfg["up"] and (s, "up") not in STATE["alerted"]:
            await send_auto(f"📈 **PRICE ALERT**\n{s} hit ${cur:.2f}")
            STATE["alerted"].add((s, "up"))

        if cur <= cfg["down"] and (s, "down") not in STATE["alerted"]:
            await send_auto(f"📉 **DROP ALERT**\n{s} dropped to ${cur:.2f}")
            STATE["alerted"].add((s, "down"))

        if abs(pct) >= cfg["pct"]:
            await send_auto(f"🚨 **VOLATILITY**\n{s} moved {pct:+.2f}%")


@tasks.loop(hours=24)
async def auto_penny():
    articles = fetch_articles("penny stocks to watch")
    if not articles:
        print("NO PENNY ARTICLES")
        return

    msg = "🪙 **PENNY STOCKS (LAST 7 DAYS)**\n\n"
    for t, l in articles:
        if l not in STATE["penny_seen"]:
            msg += f"• {t}\n{l}\n\n"
            STATE["penny_seen"].add(l)

    if msg.strip():
        await send_auto(msg)

# ===================== START =====================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not auto_price_alerts.is_running():
        auto_price_alerts.start()
    if not auto_penny.is_running():
        auto_penny.start()

bot.run(DISCORD_BOT_TOKEN)





