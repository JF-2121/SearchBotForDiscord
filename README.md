# SnipeBot

Discord bot that watches Vinted and Kleinanzeigen public search pages and returns matching listings instantly.

## What it does

- Accepts search input through slash commands, prefix commands, or direct mention in a dedicated channel.
- Crawls public Vinted and Kleinanzeigen search pages, starting with the Germany marketplace (`vinted.de`).
- Filters results by category, brand, size, gender, and price in euro (`€`).
- Mixes Vinted and Kleinanzeigen results 50/50.
- Sends the best matches back into Discord with links and prices.

## Requirements

- Python 3.9+
- A Discord application and bot token
- Message Content Intent enabled in the Discord Developer Portal
- A Discord server with a dedicated channel for sniping/search requests

## Install

```bash
python3 -m pip install --user -r requirements.txt
```

## Discord setup

1. Create a bot in the Discord Developer Portal.
2. Copy the bot token.
3. Enable **Message Content Intent** for the bot.
4. Invite the bot to your server with:
   - `bot`
   - `applications.commands`
5. Create a dedicated text channel for search requests, for example `#snipe-room`.
6. Copy that channel ID and paste it into `DISCORD_DEDICATED_CHANNEL_ID`.

## Configure the bot

Open `snipebot.py` and edit these constants near the top:

```python
DISCORD_TOKEN = "PASTE_YOUR_DISCORD_BOT_TOKEN_HERE"
DISCORD_DEDICATED_CHANNEL_ID = 0
```

- Replace `DISCORD_TOKEN` with your private bot token.
- Replace `DISCORD_DEDICATED_CHANNEL_ID` with the channel ID where you want ping-to-search to work.
- Leave `DISCORD_DEDICATED_CHANNEL_ID = 0` if you want the bot to respond in any channel.
- The bot currently starts on the Germany marketplace (`vinted.de`).

Optional:

```bash
export DISCORD_GUILD_ID="123456789012345678"
```

`DISCORD_GUILD_ID` still speeds up slash-command sync during development.

## Run

```bash
python3 snipebot.py
```

## How to use it

### 1. Ping the bot in the dedicated channel

In the dedicated channel, mention the bot and send your search:

```text
@SnipeBot shirts size M brand Nike max 50
@SnipeBot pants gender male limit 5
@SnipeBot shoes brand Adidas size 42
```

The bot will answer directly in the same channel.

### 2. Slash command

```text
/snipe shirts size M brand Nike max 50
```

### 3. Prefix command

```text
!snipe shoes size 42 brand Adidas limit 3
```

## Supported parameters

| Parameter | Example | Meaning |
| --- | --- | --- |
| area | `area germany` | Marketplace/region to search |
| category | `shirts`, `pants`, `shoes` | Filters by item category |
| brand | `brand Nike` | Filters by brand text in the listing |
| size | `size M` | Filters by size |
| gender | `gender female` | Filters by gender hints |
| price | `price 50€` | Maximum price in euro |
| max | `max 50` | Maximum price |
| min | `min 10` | Minimum price |
| range | `20-50€` | Min/max range |
| page | `page 2` | Catalog page |
| limit | `limit 5` | Max results returned |

### Category shortcuts

You can type the category directly instead of writing `category ...`:

- `shirts`
- `pants`
- `shoes`
- `hoodies`
- `jackets`
- `shorts`
- `accessories`
- `dresses`
- `activewear`
- `kids`

Examples:

```text
/snipe shirts size L max 30
@SnipeBot pants brand Levi's size 32
!snipe shoes brand Nike limit 3
@SnipeBot area germany shirts brand Adidas size M
@SnipeBot accessories bag
@SnipeBot shoes 50
@SnipeBot nike air shoes size 50
@SnipeBot nike air shoes 100€
@SnipeBot chrome hearts bag 200-800€
```

## How the bot works

1. Reads the user request.
2. Normalizes category words and filters, including bare size numbers like `50` for shoes/sizes.
3. Builds search URLs for Vinted and Kleinanzeigen.
4. Fetches both pages in parallel.
5. Extracts listing cards and images.
6. Applies extra filters locally.
7. Sorts by cheapest deal first, balances the sources 50/50, and sends the top matches back to Discord as compact embeds.

## Testing

### 1. Syntax check

```bash
python3 -m py_compile snipebot.py
```

### 2. Import test

```bash
python3 - <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("snipebot", "snipebot.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["snipebot"] = mod
spec.loader.exec_module(mod)
print(mod.parse_user_query("shirts brand Nike size M max 50"))
PY
```

### 3. Live crawl test

```bash
python3 - <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("snipebot", "snipebot.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["snipebot"] = mod
spec.loader.exec_module(mod)
filters = mod.SearchFilters(query="shirts", category="shirts", page=1, limit=3)
html = mod.fetch_catalog_page(filters)
items = mod.parse_listings(html)
print("items:", len(items))
for item in items[:3]:
    print(item.title, item.price, item.url)
PY
```

### 4. Discord test

1. Run the bot locally.
2. Invite it to a test server.
3. Send a message in the dedicated channel:

   ```text
   @SnipeBot shirts size M brand Nike max 50
   ```

4. Try a slash command:

   ```text
   /snipe shoes size 42 limit 3
   ```

5. Try a prefix command:

   ```text
   !snipe pants brand Levi's page 2
   ```

### 5. Edge cases

Test that the bot handles:

- empty input
- unknown categories
- very high page numbers
- no matching items
- network errors from Vinted

## Notes

- Vinted can change its HTML structure over time, which may require parser updates.
- Keep your token private.
- If you want auto-search in only one channel, set `DISCORD_DEDICATED_CHANNEL_ID`.
