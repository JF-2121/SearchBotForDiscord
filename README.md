# Discord SnipeBot (Updated)

A fast, automated search bot for Vinted & Kleinanzeigen with intelligent query expansion and private result delivery.

## New Features

* **Auto-Search in Dedicated Channel:** Simply type your search query in the dedicated channel—no commands or mentions needed!
* **Private Results:** All results are sent via **Direct Message (DM)** to keep channels clean.
* **Smart Query Expansion:** Automatically maps sizes (US/EU/UK) and expands 100+ brand synonyms for broader search coverage.
* **Intelligent Filtering:** Filters out items without prices, sorts by price ascending (cheapest first), and returns top 10 results.
* **Mention Stripping:** Discord mentions are automatically removed from queries to prevent pollution.

## How to Use

### In Dedicated Channel (Auto-Search)
Simply type your search query directly in the configured dedicated channel:
```
nike air max size 42 max 80
```
The bot will:
1. React with 🔍 to confirm receipt
2. Process your search with query expansion
3. Send all results directly to your DMs

**No commands, prefixes, or mentions required!**

### In Other Channels
1. **Slash command:** `/snipe [query]`
2. **Ping:** `@SnipeBot [query]`
3. **Prefix:** `!snipe [query]`

**Note:** Slash commands send results to DMs with an ephemeral confirmation in the channel.

## How the Bot Works

1. **Mention Stripping:** Removes all Discord mentions (`<@!?123456>`) from the query to prevent pollution.
2. **Query Expansion:** `expand_query()` maps sizes (US/EU/UK) and brand synonyms into up to 5 search variations.
3. **Parallel Fetch:** Executes concurrent requests to Vinted/Kleinanzeigen for all query variations.
4. **Parse & Aggregate:** Extracts listing cards from HTML and combines results from all variations.
5. **Filter & Sort:** `filter_and_sort()` removes items without prices, sorts by price ascending (cheapest first), and returns top 10.
6. **Private Delivery:** Sends all result embeds directly to user's DMs.

### Query Expansion Examples

- **Size:** `M` → `m`, `medium`, `med`
- **Brand:** `nike` → `nike`, `nke`, `swoosh`
- **Shoe Size:** `us9` → `us9`, `us 9`, `9us`
- **EU Size:** `42` → `42`, `eu42`

## Setup & Config

### Environment Variables

Create a `.env` file or set these environment variables:

```python
DISCORD_TOKEN = "PASTE_YOUR_DISCORD_BOT_TOKEN_HERE"
DISCORD_DEDICATED_CHANNEL_ID = 1234567890  # Channel ID for auto-search (0 = disabled)
DISCORD_GUILD_ID = 9876543210  # Optional: Guild ID for faster slash command sync
```

### Dedicated Channel Setup

1. Create a dedicated channel in your Discord server (e.g., `#snipe-search`)
2. Copy the channel ID (Right-click → Copy ID, requires Developer Mode)
3. Set `DISCORD_DEDICATED_CHANNEL_ID` to this ID
4. Users can now search by simply typing queries in that channel!

**Important:** Make sure users have DMs enabled from server members, or they won't receive results.

## Supported Parameters

| Parameter | Example | Meaning |
| --- | --- | --- |
| area | `area germany` | Marketplace/region |
| brand | `brand Nike` | Filters by brand (auto-expanded to synonyms) |
| size | `size M` or `size 42` | Filters by size (auto-expanded US/EU/UK) |
| max/min | `max 50` or `min 20` | Price constraints (€) |
| limit | `limit 5` | Max results (capped at 10) |
| category | `category shoes` | Filter by category |
| gender | `gender female` | Filter by gender |

### Query Examples

```
nike air max size 42 max 80
adidas hoodie size L brand adidas
jordan 1 us9 max 150
supreme shirt size M gender male
```

## Size & Brand Coverage

### Sizes Supported
- **Letter sizes:** XXS, XS, S, M, L, XL, XXL, XXXL, 4XL, 5XL
- **US numeric:** 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20
- **EU clothing:** 32-56
- **Shoe sizes:** US 6-14, EU 36-48, UK 6-12
- **Special:** One Size

### Brand Coverage (100+ brands)
- **Sportswear:** Nike, Adidas, Puma, Reebok, New Balance, Under Armour, ASICS, etc.
- **Luxury:** Gucci, Louis Vuitton, Balenciaga, Dior, Prada, Off-White, Stone Island, etc.
- **Streetwear:** Supreme, BAPE, Palace, Stüssy, KITH, Fear of God, etc.
- **Outdoor:** The North Face, Patagonia, Arc'teryx, Columbia, etc.
- **Workwear:** Carhartt, Dickies, Timberland, Dr. Martens, etc.
- **Designer:** Tommy Hilfiger, Ralph Lauren, Lacoste, Calvin Klein, Hugo Boss, etc.
- **Japanese:** Comme des Garçons, UNIQLO, Visvim, Neighborhood, etc.

## Requirements

```bash
pip install -r requirements.txt
```

Required packages:
- `discord.py` - Discord bot framework
- `python-dotenv` - Environment variable management

## Running the Bot

```bash
python snipebot.py
```

The bot will:
1. Start a health check server on port 10000 (for hosting platforms)
2. Connect to Discord
3. Sync slash commands
4. Begin listening for messages in the dedicated channel