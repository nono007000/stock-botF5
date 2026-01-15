import discord
from discord.ext import commands, tasks
import yfinance as yf
import requests
from datetime import datetime, timezone
import os

# ===================== CONFIG =====================

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

CHANNEL_ID = 1460290831356264704  # your channel ID

PERSONAL_STOCKS = {
    "AAPL": {"up": 180, "down": 170, "pct": 3},
    "TSLA": {"up": 250, "down": 230, "pct": 5},
    "NVDA": {"up": 500, "down": 460, "pct": 4},
}

NEWS_SITES = [
    "cnbc.com", "finance.yahoo.com", "marketwatch.com",
    "bloomberg.com", "reuters.com", "benzinga.com"
]

MAX_ARTICLES = 3

STATE = {
    "alerted": set(),
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

    r = requests.get(url, timeout=10).json()
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
        channel = await bot.fetch_channel(CHANNEL_ID)
        await channel.send(msg)
        print("AUTO MESSAGE SENT")
    except Exception as e:
        print("AUTO SEND ERROR:", e)

# ===================== AUTO TASKS =====================

@tasks.loop(minutes=10)
async def auto_price_alerts():
    print("PRICE LOOP RUNNING")
    for s, cfg in PERSONAL_STOCKS.items():
        prev, cur = get_price(s)
        if not cur:
            continue

        pct = ((cur - prev) / prev) * 100

        if abs(pct) >= cfg["pct"]:
            await send_auto(f"🚨 **{s} moved {pct:+.2f}%**")

@auto_price_alerts.before_loop
async def before_price():
    await bot.wait_until_ready()


@tasks.loop(minutes=1)  # FAST for testing
async def auto_penny():
    print("PENNY LOOP RUNNING")
    articles = fetch_articles("penny stocks to watch")

    if not articles:
        print("NO PENNY ARTICLES")
        return

    msg = "🪙 **PENNY STOCKS (LAST 7 DAYS)**\n\n"
    for t, l in articles:
        if l not in STATE["penny_seen"]:
            msg += f"• {t}\n{l}\n\n"
            STATE["penny_seen"].add(l)

    await send_auto(msg)

@auto_penny.before_loop
async def before_penny():
    await bot.wait_until_ready()

# ===================== COMMANDS =====================

@bot.command()
async def testauto(ctx):
    await ctx.send("🧪 testauto command received")
    await send_auto("✅ AUTO SYSTEM WORKS")
)

@bot.command()
async def status(ctx):
    await ctx.send("✅ Bot running")

# ===================== START =====================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    auto_price_alerts.start()
    auto_penny.start()

bot.run(DISCORD_BOT_TOKEN)




