import discord
from discord.ext import commands, tasks
import yfinance as yf
import requests
from datetime import datetime, timezone
import os

# ===================== CONFIG =====================

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

CHANNEL_ID = 1460290831356264704

PERSONAL_STOCKS = {
    "AAPL": {"up": 180, "down": 170, "pct": 3},
    "TSLA": {"up": 250, "down": 230, "pct": 5},
    "NVDA": {"up": 500, "down": 460, "pct": 4},
}

NEWS_SITES = [
    "cnbc.com",
    "finance.yahoo.com",
    "bloomberg.com",
    "reuters.com",
    "marketwatch.com",
    "forbes.com",
    "businessinsider.com",
    "seekingalpha.com",
]

MAX_ARTICLES = 4

STATE = {
    "alerted": set(),
    "penny_seen": set(),
    "market_news_seen": set()
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
        if (now - published).days > 2:
            continue

        link = a["url"]
        if any(site in link for site in NEWS_SITES):
            articles.append((a["title"], link))

        if len(articles) >= MAX_ARTICLES:
            break

    return articles


async def send_auto(msg):
    try:
        channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        await channel.send(msg)
    except Exception as e:
        print("AUTO SEND ERROR:", e)

# ===================== AUTO TASKS =====================

@tasks.loop(minutes=10)
async def auto_price_alerts():
    for s, cfg in PERSONAL_STOCKS.items():
        prev, cur = get_price(s)
        if not cur:
            continue

        pct = ((cur - prev) / prev) * 100

        if abs(pct) >= cfg["pct"]:
            await send_auto(f"🚨 **VOLATILITY ALERT**\n{s} moved {pct:+.2f}%")


@tasks.loop(minutes=30)
async def auto_market_news():
    articles = fetch_articles(
        "US stock market OR Federal Reserve OR inflation OR interest rates "
        "OR AI stocks OR bank stocks OR oil prices"
    )

    if not articles:
        return

    msg = "📰 **MARKET-MOVING US NEWS**\n\n"

    sent = False
    for t, l in articles:
        if l not in STATE["market_news_seen"]:
            msg += f"• {t}\n{l}\n\n"
            STATE["market_news_seen"].add(l)
            sent = True

    if sent:
        await send_auto(msg)

# ===================== COMMANDS =====================

@bot.command()
async def price(ctx, symbol: str):
    _, cur = get_price(symbol.upper())
    await ctx.send(f"{symbol.upper()}: ${cur:.2f}" if cur else "Price unavailable")


@bot.command()
async def stocknews(ctx, symbol: str):
    articles = fetch_articles(f"{symbol} stock")
    msg = f"📰 **{symbol.upper()} NEWS**\n\n"
    for t, l in articles:
        msg += f"• {t}\n{l}\n\n"
    await ctx.send(msg)


@bot.command()
async def earnings(ctx, symbol: str):
    symbol = symbol.upper()
    try:
        cal = yf.Ticker(symbol).calendar
        date = cal.columns[0].strftime("%Y-%m-%d") if not cal.empty else "Unknown"
    except:
        date = "Unknown"

    articles = fetch_articles(f"{symbol} earnings")

    msg = f"📅 **{symbol} EARNINGS**\n"
    msg += f"🗓 Date: {date}\n\n"

    for t, l in articles:
        msg += f"• {t}\n{l}\n\n"

    await ctx.send(msg)


@bot.command()
async def news(ctx):
    articles = fetch_articles(
        "US stock market OR Federal Reserve OR inflation OR interest rates "
        "OR AI stocks OR banks OR oil prices"
    )

    if not articles:
        await ctx.send("No major market-moving news right now.")
        return

    msg = "📰 **IMPORTANT US MARKET NEWS**\n\n"
    for t, l in articles:
        msg += f"• {t}\n{l}\n\n"

    await ctx.send(msg)


@bot.command()
async def status(ctx):
    await ctx.send("✅ Bot running")

# ===================== START =====================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    auto_price_alerts.start()
    auto_market_news.start()

bot.run(DISCORD_BOT_TOKEN)







