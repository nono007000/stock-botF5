import discord
from discord.ext import commands, tasks
import yfinance as yf
import requests
from datetime import datetime, timezone
import os

# ===================== CONFIG =====================

DISCORD_BOT_TOKEN = "bt"
NEWS_API_KEY = "api"

CHANNEL_ID = None  # optional

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
    # Major US finance
    "cnbc.com",
    "finance.yahoo.com",
    "marketwatch.com",
    "bloomberg.com",
    "reuters.com",

    # Trading / investing focused
    "seekingalpha.com",
    "benzinga.com",
    "fool.com",
    "investopedia.com",
    "thestreet.com",
    "zacks.com",

    # Market news & analysis
    "wsj.com",
    "fortune.com",
    "forbes.com",
    "businessinsider.com",
    "axios.com",

    # Earnings & company news
    "prnewswire.com",
    "globenewswire.com"
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

    articles = []
    now = datetime.now(timezone.utc)

    for a in r["articles"]:
        published = datetime.fromisoformat(
            a["publishedAt"].replace("Z", "+00:00")
        )

        if (now - published).days > 7:
            continue

        link = a["url"]
        if any(site in link for site in NEWS_SITES):
            articles.append((a["title"], link))

        if len(articles) >= MAX_ARTICLES:
            break

    return articles


async def send_auto(msg):
    if CHANNEL_ID:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(msg)

# ===================== AUTO TASKS =====================

@tasks.loop(minutes=10)
async def auto_price_alerts():
    for s, cfg in PERSONAL_STOCKS.items():
        prev, cur = get_price(s)
        if not cur:
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


@tasks.loop(minutes=30)
async def auto_market_news():
    articles = fetch_articles("US stock market OR wall street")
    if not articles:
        return
    msg = "📰 **MARKET NEWS (US)**\n\n"
    for t, l in articles:
        if l not in STATE["news_seen"]:
            msg += f"• {t}\n{l}\n\n"
            STATE["news_seen"].add(l)
    await send_auto(msg)


@tasks.loop(hours=24)
async def auto_earnings():
    articles = fetch_articles("earnings preview OR reporting earnings")
    if articles:
        msg = "📅 **EARNINGS TO WATCH**\n\n"
        for t, l in articles:
            msg += f"• {t}\n{l}\n\n"
        await send_auto(msg)


@tasks.loop(hours=24)
async def auto_calendar():
    articles = fetch_articles("earnings calendar next week US stocks")
    if articles:
        msg = "📅 **EARNINGS CALENDAR**\n\n"
        for t, l in articles:
            msg += f"• {t}\n{l}\n\n"
        await send_auto(msg)


@tasks.loop(hours=24)
async def auto_premarket():
    articles = fetch_articles("US premarket movers stocks")
    if articles:
        msg = "🌅 **PREMARKET MOVERS**\n\n"
        for t, l in articles:
            msg += f"• {t}\n{l}\n\n"
        await send_auto(msg)


@tasks.loop(hours=24)
async def auto_penny():
    articles = fetch_articles("penny stocks to watch")
    if articles:
        msg = "🪙 **PENNY STOCK TO WATCH**\n\n"
        for t, l in articles:
            if l not in STATE["penny_seen"]:
                msg += f"• {t}\n{l}\n\n"
                STATE["penny_seen"].add(l)
        await send_auto(msg)


@tasks.loop(minutes=15)
async def auto_volume_spike():
    for s in PERSONAL_STOCKS:
        try:
            hist = yf.Ticker(s).history(period="10d")
            if len(hist) < 10:
                continue
            avg_vol = hist["Volume"][:-1].mean()
            latest = hist["Volume"].iloc[-1]
            if latest >= avg_vol * 2:
                await send_auto(f"🚀 **VOLUME SPIKE**\n{s} unusually high volume")
        except:
            continue


@tasks.loop(hours=24)
async def auto_options():
    articles = fetch_articles("unusual options activity US stocks")
    if articles:
        msg = "🧠 **OPTIONS FLOW**\n\n"
        for t, l in articles:
            msg += f"• {t}\n{l}\n\n"
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
async def earnings(ctx):
    articles = fetch_articles("earnings preview OR reporting earnings")
    msg = "📅 **EARNINGS**\n\n"
    for t, l in articles:
        msg += f"• {t}\n{l}\n\n"
    await ctx.send(msg)

@bot.command()
async def calendar(ctx):
    articles = fetch_articles("earnings calendar next week US stocks")
    msg = "📅 **EARNINGS CALENDAR**\n\n"
    for t, l in articles:
        msg += f"• {t}\n{l}\n\n"
    await ctx.send(msg)

@bot.command()
async def premarket(ctx):
    articles = fetch_articles("US premarket movers stocks")
    msg = "🌅 **PREMARKET MOVERS**\n\n"
    for t, l in articles:
        msg += f"• {t}\n{l}\n\n"
    await ctx.send(msg)

@bot.command()
async def penny(ctx):
    articles = fetch_articles("penny stocks to watch")
    msg = "🪙 **PENNY STOCK**\n\n"
    for t, l in articles:
        msg += f"• {t}\n{l}\n\n"
    await ctx.send(msg)

@bot.command()
async def options(ctx):
    articles = fetch_articles("unusual options activity US stocks")
    msg = "🧠 **OPTIONS FLOW**\n\n"
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
    auto_earnings.start()
    auto_calendar.start()
    auto_premarket.start()
    auto_penny.start()
    auto_volume_spike.start()
    auto_options.start()

bot.run(DISCORD_BOT_TOKEN)
