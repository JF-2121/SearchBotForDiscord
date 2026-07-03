# Discord SnipeBot (Updated)

A fast, automated search bot for Vinted & Kleinanzeigen.

## New Features

* **Private Results:** Results are sent via **Direct Message (DM)** to avoid channel spam.
* **Query Expansion:** Automatically maps sizes (e.g., US to EU) and brand synonyms.
* **Smart Filtering:** Auto-removes items > 7 days old, sorts by price (ascending), and limits to top 10.

## How to use

1. **Slash command:** `/snipe [query]`
2. **Ping:** `@SnipeBot [query]`
3. **Prefix:** `!snipe [query]`

**Note:** The bot confirms the search in the channel via an ephemeral message, but sends full result embeds directly to your DMs.

## How the bot works

1. **Normalize:** `expand_query` maps sizes and brand synonyms into search variations.
2. **Fetch:** Executes parallel requests to Vinted/Kleinanzeigen for all variations.
3. **Parse:** Extracts listing cards.
4. **Filter & Sort:** `filter_and_sort` discards items older than 7 days, sorts by price ascending, and limits to top 10.
5. **Deliver:** Sends embeds via DM.

## Setup & Config

(Configuration remains unchanged.)

```python
DISCORD_TOKEN = "PASTE_YOUR_DISCORD_BOT_TOKEN_HERE"
DISCORD_DEDICATED_CHANNEL_ID = 0 # 0 = responds in all channels

```

## Supported Parameters

| Parameter | Example | Meaning |
| --- | --- | --- |
| area | `area germany` | Marketplace/region |
| brand | `brand Nike` | Filters by brand (with expansion) |
| size | `size M` | Filters by size (with expansion) |
| max/min | `max 50` | Price constraints |
| limit | `limit 5` | Max results (capped at 10) |

*(All previous instructions, requirements, and testing steps remain valid.)*