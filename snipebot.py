"""Discord bot that searches  public catalog pages."""

from __future__ import annotations

import asyncio
import html
import os
import re
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, List, Optional, Sequence

import discord
from discord.ext import commands

from dotenv import load_dotenv
load_dotenv() 

import http.server
import threading

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args):
        return # Verhindert, dass UptimeRobot deine Logs zuspamt

def run_health_server():
    # Render übergibt automatisch den benötigten Port als Umgebungsvariable
    port = int(os.getenv("PORT", 10000))
    server = http.server.HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Startet den Server im Hintergrund, BEVOR der Discord-Bot blockiert
threading.Thread(target=run_health_server, daemon=True).start()
# -------------------------------------------

# ... Hier drunter kommt dein ganz normaler DISCORD-BOT Code ...
# Zum Beispiel: client.run(DISCORD_TOKEN)

VINTED_MARKETPLACE = "Germany"
VINTED_BASE_URL = "https://www.vinted.de/catalog"
KLEINANZEIGEN_BASE_URL = "https://www.kleinanzeigen.de"
MARKETPLACE_ALIASES = {
    "germany": {"germany", "de", "deutschland"},
}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
MAX_RESULTS = 5
RESULT_EMBED_COLOR = 0x6EB6FF
SEARCH_TIMEOUT_SECONDS = 8


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

_channel_id = os.getenv("DISCORD_DEDICATED_CHANNEL_ID")
DISCORD_DEDICATED_CHANNEL_ID = int(_channel_id) if _channel_id else None

CATEGORY_ALIASES = {
    "shirts": {"shirt", "shirts", "tee", "tees", "tshirt", "t-shirts", "t-shirts", "top", "tops", "blouse", "blouses"},
    "pants": {"pants", "pant", "trackpants", "trackpant", "sweatpants", "sweatpant", "trousers", "trouser", "jeans", "jean", "cargo", "cargos", "joggers", "jogger"},
    "shoes": {"shoes", "shoe", "sneaker", "sneakers", "trainers", "trainer", "boots", "boot", "sandals", "sandal"},
    "hoodies": {"hoodie", "hoodies", "sweatshirt", "sweatshirts", "crewneck", "crewnecks"},
    "jackets": {"jacket", "jackets", "coat", "coats", "outerwear", "parka", "parka"},
    "shorts": {"shorts", "short", "bermuda", "bermudas"},
    "accessories": {"accessory", "accessories", "bag", "bags", "backpack", "backpacks", "belt", "belts", "hat", "hats", "cap", "caps", "beanie", "beanies", "scarf", "scarves", "socks", "watch", "watches", "wallet", "wallets", "jewelry", "jewelery", "necklace", "necklaces", "bracelet", "bracelets", "ring", "rings"},
    "dresses": {"dress", "dresses", "skirt", "skirts", "romper", "rompers", "jumpsuit", "jumpsuits"},
    "activewear": {"activewear", "gym", "sport", "sports", "tracksuit", "tracksuits", "leggings", "legging", "workout"},
    "kids": {"kids", "kid", "children", "child", "baby", "babies"},
    "underwear": {"underwear", "socks", "sock", "boxers", "boxer", "bra", "bras", "briefs", "brief"},
    "formal": {"suit", "suits", "blazer", "blazers", "shirt", "shirts", "tie", "ties"},
}

CATEGORY_QUERY = {
    "shirts": "shirt",
    "pants": "pants",
    "shoes": "shoes",
    "hoodies": "hoodie",
    "jackets": "jacket",
    "shorts": "shorts",
    "accessories": "accessories",
    "dresses": "dress",
    "activewear": "activewear",
    "kids": "kids",
    "underwear": "underwear",
    "formal": "suit",
}


@dataclass
class SearchFilters:
    query: str
    marketplace: str = "germany"
    category: Optional[str] = None
    brand: Optional[str] = None
    terms: tuple[str, ...] = ()
    size: Optional[str] = None
    gender: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    page: int = 1
    limit: int = MAX_RESULTS


@dataclass
class Listing:
    source: str
    listing_id: str
    title: str
    description: str
    url: str
    price: Optional[float] = None
    image_url: Optional[str] = None


def _normalize_token(token: str) -> str:
    return token.strip().lower()


def _extract_number(text: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def _parse_price_text(text: str) -> Optional[float]:
    cleaned = html.unescape(text).strip()
    patterns = [
        r"(?<!\d)(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)\s*€",
        r"€\s*(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if not match:
            continue
        raw = match.group(1).replace(" ", "")
        raw = raw.replace(".", "")
        if "," in raw:
            raw = raw.replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _extract_price_value(token: str) -> Optional[float]:
    if "€" not in token and "eur" not in token.lower():
        return None
    return _parse_price_text(token)


def _is_size_candidate(token: str) -> bool:
    if not re.fullmatch(r"\d{1,3}(?:\.\d)?", token):
        return False
    value = float(token)
    return 20 <= value <= 60


def _normalize_category(raw: str) -> Optional[str]:
    token = re.sub(r"[-_/]+", " ", raw.strip().lower())
    token = re.sub(r"\s+", " ", token)
    for category, aliases in CATEGORY_ALIASES.items():
        normalized_aliases = {re.sub(r"[-_/]+", " ", alias.lower()) for alias in aliases}
        if token in normalized_aliases:
            return category
    return None


def _extract_param(token: str) -> str:
    if "=" in token:
        return token.split("=", 1)[1]
    if ":" in token:
        return token.split(":", 1)[1]
    return ""


def _normalize_marketplace(raw: str) -> Optional[str]:
    token = re.sub(r"[-_/]+", " ", raw.strip().lower())
    token = re.sub(r"\s+", " ", token)
    for marketplace, aliases in MARKETPLACE_ALIASES.items():
        if token in aliases:
            return marketplace
    return None


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return re.sub(r"-+", "-", slug).strip("-")


def _shorten_text(text: str, length: int = 90) -> str:
    cleaned = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return textwrap.shorten(cleaned, width=length, placeholder="...") if cleaned else ""


def _normalize_match_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", html.unescape(text).lower())


def _matches_required_terms(text: str, terms: Iterable[str]) -> bool:
    normalized_text = _normalize_match_text(text)
    return all(_normalize_match_text(term) in normalized_text for term in terms)


def _extract_price_range(raw_query: str) -> tuple[str, Optional[float], Optional[float]]:
    text = raw_query
    min_price: Optional[float] = None
    max_price: Optional[float] = None

    range_patterns = [
        r"(?:from|von|zwischen)\s*(?P<min>\d+(?:[.,]\d+)?)\s*(?:to|bis|and|und)\s*(?P<max>\d+(?:[.,]\d+)?)\s*€?",
        r"(?P<min>\d+(?:[.,]\d+)?)\s*(?:-|\.\.|to|bis|until|and)\s*(?P<max>\d+(?:[.,]\d+)?)\s*€?",
    ]
    for pattern in range_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        min_price = _extract_number(match.group("min"))
        max_price = _extract_number(match.group("max"))
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        break

    return text, min_price, max_price


def parse_user_query(raw_query: str) -> SearchFilters:
    raw_query, range_min, range_max = _extract_price_range(raw_query)
    tokens = raw_query.replace(",", " ").split()
    query_terms: List[str] = []
    required_terms: List[str] = []
    marketplace = "germany"
    category: Optional[str] = None
    brand: Optional[str] = None
    size: Optional[str] = None
    gender: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    page = 1
    limit = MAX_RESULTS

    i = 0
    while i < len(tokens):
        token = tokens[i]
        lowered = _normalize_token(token)
        category_candidate = _normalize_category(token)

        if lowered.startswith("area=") or lowered.startswith("area:") or lowered.startswith("marketplace=") or lowered.startswith("marketplace:"):
            marketplace = _normalize_marketplace(_extract_param(token)) or marketplace
        elif lowered in {"area", "marketplace", "region", "country"} and i + 1 < len(tokens):
            marketplace = _normalize_marketplace(tokens[i + 1]) or marketplace
            i += 1
        elif lowered.startswith("category=") or lowered.startswith("category:"):
            category = _normalize_category(_extract_param(token)) or category
        elif lowered == "category" and i + 1 < len(tokens):
            category = _normalize_category(tokens[i + 1]) or category
            i += 1
        elif category_candidate:
            category = category_candidate
            if lowered not in {category_candidate, CATEGORY_QUERY.get(category_candidate, "")}:
                query_terms.append(token)
                required_terms.append(token)
        elif lowered.startswith("brand=") or lowered.startswith("brand:"):
            brand = _extract_param(token) or brand
        elif lowered == "brand" and i + 1 < len(tokens):
            brand = tokens[i + 1]
            i += 1
        elif lowered.startswith("size=") or lowered.startswith("size:"):
            size = _extract_param(token) or size
        elif lowered == "size" and i + 1 < len(tokens):
            size = tokens[i + 1]
            i += 1
        elif lowered.startswith("gender=") or lowered.startswith("gender:"):
            gender = _extract_param(token) or gender
        elif lowered in {"gender", "sex"} and i + 1 < len(tokens):
            gender = tokens[i + 1]
            i += 1
        elif lowered.startswith("max=") or lowered.startswith("max:"):
            value = _extract_param(token) or token[5:]
            max_price = _extract_number(value)
            if max_price is None and i + 1 < len(tokens):
                max_price = _extract_number(tokens[i + 1])
                i += 1
        elif lowered == "max" and i + 1 < len(tokens):
            max_price = _extract_number(tokens[i + 1])
            i += 1
        elif lowered.startswith("under"):
            value = _extract_param(token) or token[5:]
            max_price = _extract_number(value)
            if max_price is None and i + 1 < len(tokens):
                max_price = _extract_number(tokens[i + 1])
                i += 1
        elif lowered in {"price", "budget", "deal"} and i + 1 < len(tokens):
            max_price = _extract_number(tokens[i + 1])
            i += 1
        elif (price_value := _extract_price_value(token)) is not None:
            max_price = price_value
        elif lowered.startswith("min=") or lowered.startswith("min:"):
            value = _extract_param(token) or token[4:]
            min_price = _extract_number(value)
            if min_price is None and i + 1 < len(tokens):
                min_price = _extract_number(tokens[i + 1])
                i += 1
        elif lowered == "min" and i + 1 < len(tokens):
            min_price = _extract_number(tokens[i + 1])
            i += 1
        elif lowered.startswith("over"):
            value = _extract_param(token) or token[4:]
            min_price = _extract_number(value)
            if min_price is None and i + 1 < len(tokens):
                min_price = _extract_number(tokens[i + 1])
                i += 1
        elif lowered.startswith("page=") or lowered.startswith("page:"):
            value = _extract_param(token)
            if value.isdigit():
                page = max(1, int(value))
        elif lowered == "page" and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            page = max(1, int(tokens[i + 1]))
            i += 1
        elif lowered.startswith("limit=") or lowered.startswith("limit:"):
            value = _extract_param(token)
            if value.isdigit():
                limit = max(1, min(10, int(value)))
        elif lowered == "limit" and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            limit = max(1, min(10, int(tokens[i + 1])))
            i += 1
        elif lowered.isdigit() and i > 0 and _normalize_token(tokens[i - 1]) in {"page", "p"}:
            page = max(1, int(lowered))
        elif size is None and _is_size_candidate(lowered):
            size = token
        else:
            query_terms.append(token)
            required_terms.append(token)

        i += 1

    summary_terms: List[str] = []
    for part in [brand, *query_terms, CATEGORY_QUERY[category] if category else None]:
        if part and part not in summary_terms:
            summary_terms.append(part)
    query = " ".join(summary_terms).strip()
    if not query and gender:
        query = gender
    if not query:
        query = "clothes"

    return SearchFilters(
        marketplace=marketplace,
        query=query,
        category=category,
        brand=brand,
        terms=tuple(dict.fromkeys(required_terms)),
        size=size,
        gender=gender,
        min_price=range_min if range_min is not None else min_price,
        max_price=range_max if range_max is not None else max_price,
        page=page,
        limit=limit,
    )


def build_catalog_url(filters: SearchFilters) -> str:
    base_url = VINTED_BASE_URL if filters.marketplace == "germany" else VINTED_BASE_URL
    parts: List[str] = []
    if filters.brand:
        parts.append(filters.brand)
    if filters.category:
        parts.append(CATEGORY_QUERY[filters.category])
    if filters.query:
        parts.append(filters.query)
    params = {
        "search_text": " ".join(dict.fromkeys(parts)) if parts else filters.query,
        "page": str(filters.page),
        "order": "newest_first",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def _dedupe_listings(listings: Iterable[Listing]) -> List[Listing]:
    seen = set()
    deduped: List[Listing] = []
    for listing in listings:
        key = listing.url.lower().rstrip("/") or listing.listing_id
        if key in seen:
            continue
        seen.add(key)
        deduped.append(listing)
    return deduped


def _listing_sort_key(listing: Listing) -> tuple[float, int, str]:
    price = listing.price if listing.price is not None else float("inf")
    source_rank = 0 if listing.source == "Vinted" else 1
    return (price, source_rank, listing.title.lower())


def _merge_balanced(left: Sequence[Listing], right: Sequence[Listing], limit: int) -> List[Listing]:
    merged: List[Listing] = []
    left_index = right_index = 0
    while len(merged) < limit and (left_index < len(left) or right_index < len(right)):
        if left_index < len(left):
            merged.append(left[left_index])
            left_index += 1
            if len(merged) >= limit:
                break
        if right_index < len(right):
            merged.append(right[right_index])
            right_index += 1
    return merged[:limit]


def _extract_first_price(text: str) -> Optional[float]:
    return _parse_price_text(text)


def parse_listings(html_text: str) -> List[Listing]:
    listings: List[Listing] = []
    seen_ids = set()
    anchor_pattern = re.compile(
        r'<a[^>]*data-testid="product-item-id-(?P<id>\d+)--overlay-link"[^>]*>',
        re.IGNORECASE,
    )

    for match in anchor_pattern.finditer(html_text):
        anchor = match.group(0)
        listing_id = match.group("id")
        if listing_id in seen_ids:
            continue

        href_match = re.search(r'href="([^"]+)"', anchor, re.IGNORECASE)
        title_match = re.search(r'title="([^"]+)"', anchor, re.IGNORECASE)
        if not href_match or not title_match:
            continue

        url = html.unescape(href_match.group(1))
        title = html.unescape(title_match.group(1))
        window_start = max(0, match.start() - 1200)
        window_end = min(len(html_text), match.end() + 800)
        window = html_text[window_start:window_end]
        image_match = re.search(
            rf'<img[^>]+data-testid="product-item-id-{listing_id}--image--img"[^>]*src="([^"]+)"',
            window,
            re.IGNORECASE,
        ) or re.search(
            rf'<img[^>]*src="([^"]+)"[^>]+data-testid="product-item-id-{listing_id}--image--img"',
            window,
            re.IGNORECASE,
        )
        description = _shorten_text(title)
        listings.append(
            Listing(
                source="Vinted",
                listing_id=listing_id,
                title=title,
                description=description,
                url=url,
                price=_extract_first_price(title),
                image_url=html.unescape(image_match.group(1)) if image_match else None,
            )
        )
        seen_ids.add(listing_id)

    return listings


def build_kleinanzeigen_url(filters: SearchFilters) -> str:
    parts: List[str] = []
    if filters.brand:
        parts.append(filters.brand)
    if filters.query:
        parts.append(filters.query)
    slug = _slugify(" ".join(dict.fromkeys(parts))) or "suchen"
    path = f"/s-{slug}/k0"
    if filters.page > 1:
        path = f"/s-seite:{filters.page}/{slug}/k0"
    return f"{KLEINANZEIGEN_BASE_URL}{path}"


def parse_kleinanzeigen_listings(html_text: str) -> List[Listing]:
    listings: List[Listing] = []
    article_pattern = re.compile(
        r'<article class="aditem" data-adid="(?P<id>\d+)"\s*data-href="(?P<href>[^"]+)">(?P<body>.*?)</article>',
        re.IGNORECASE | re.DOTALL,
    )

    for match in article_pattern.finditer(html_text):
        body = match.group("body")
        title_match = re.search(r'<a class="ellipsis"[^>]*>(?P<title>.*?)</a>', body, re.IGNORECASE | re.DOTALL)
        if not title_match:
            continue

        title = _shorten_text(title_match.group("title"), 100)
        desc_match = re.search(
            r'<p class="aditem-main--middle--description">(.*?)</p>',
            body,
            re.IGNORECASE | re.DOTALL,
        )
        description = _shorten_text(desc_match.group(1), 120) if desc_match else title
        price_match = re.search(
            r'<p class="aditem-main--middle--price-shipping--price">\s*([^<]+?)\s*</p>',
            body,
            re.IGNORECASE | re.DOTALL,
        )
        price = _parse_price_text(price_match.group(1).replace("€", "")) if price_match else None
        image_match = re.search(r'<img[^>]+src="([^"]+)"', body, re.IGNORECASE)
        url = urllib.parse.urljoin(KLEINANZEIGEN_BASE_URL, match.group("href"))

        listings.append(
            Listing(
                source="Kleinanzeigen",
                listing_id=match.group("id"),
                title=title,
                description=description,
                url=url,
                price=price,
                image_url=html.unescape(image_match.group(1)) if image_match else None,
            )
        )

    return listings


def _matches_keyword(text: str, keywords: Iterable[str]) -> bool:
    normalized = text.lower()
    return any(keyword in normalized for keyword in keywords)


def _matches_size(text: str, size: str) -> bool:
    normalized = text.lower()
    value = re.escape(size.lower())
    return bool(
        re.search(rf"\bsize[:\s\-_/]*{value}\b", normalized)
        or re.search(rf"\b{value}\b", normalized)
    )


def apply_post_filters(listings: Iterable[Listing], filters: SearchFilters) -> List[Listing]:
    required_terms = list(filters.terms)
    brand_keywords = []
    if filters.brand:
        brand_keywords.append(filters.brand.lower())

    gender_keywords = []
    if filters.gender:
        normalized_gender = filters.gender.lower()
        gender_keywords.extend(
            {
                "female": ["female", "woman", "women", "womens", "girl", "girls"],
                "male": ["male", "man", "men", "mens", "boy", "boys"],
                "unisex": ["unisex"],
            }.get(normalized_gender, [normalized_gender])
        )

    results: List[Listing] = []
    for listing in listings:
        if (filters.min_price is not None or filters.max_price is not None) and listing.price is None:
            continue
        if filters.min_price is not None and listing.price is not None and listing.price < filters.min_price:
            continue
        if filters.max_price is not None and listing.price is not None and listing.price > filters.max_price:
            continue
        searchable_text = f"{listing.title} {listing.description}"
        if required_terms and not _matches_required_terms(searchable_text, required_terms):
            continue
        if filters.size and not _matches_size(searchable_text, filters.size):
            continue
        if brand_keywords and not _matches_keyword(searchable_text, brand_keywords):
            continue
        if gender_keywords and not _matches_keyword(searchable_text, gender_keywords):
            continue
        results.append(listing)

    return results


def fetch_catalog_page(filters: SearchFilters) -> str:
    url = build_catalog_url(filters)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Vinted request failed: {exc}") from exc

    return payload.decode("utf-8", errors="replace")


async def search_vinted(filters: SearchFilters) -> List[Listing]:
    html_text = await asyncio.to_thread(fetch_catalog_page, filters)
    listings = parse_listings(html_text)
    return apply_post_filters(listings, filters)


async def search_kleinanzeigen(filters: SearchFilters) -> List[Listing]:
    def fetch_page() -> str:
        request = urllib.request.Request(
            build_kleinanzeigen_url(filters),
            headers={"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9,en;q=0.7"},
        )
        with urllib.request.urlopen(request, timeout=SEARCH_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8", errors="replace")

    html_text = await asyncio.to_thread(fetch_page)
    listings = parse_kleinanzeigen_listings(html_text)
    return apply_post_filters(listings, filters)


async def search_all_sources(filters: SearchFilters) -> tuple[List[Listing], List[str]]:
    tasks = [
        asyncio.wait_for(search_vinted(filters), timeout=SEARCH_TIMEOUT_SECONDS),
        asyncio.wait_for(search_kleinanzeigen(filters), timeout=SEARCH_TIMEOUT_SECONDS),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    vinted_results: List[Listing] = []
    kleinanzeigen_results: List[Listing] = []
    errors: List[str] = []
    for source_name, result in zip(["Vinted", "Kleinanzeigen"], results):
        if isinstance(result, Exception):
            errors.append(f"{source_name}: {result}")
            continue
        sorted_result = sorted(_dedupe_listings(result), key=_listing_sort_key)
        if source_name == "Vinted":
            vinted_results = sorted_result
        else:
            kleinanzeigen_results = sorted_result

    combined = _merge_balanced(vinted_results, kleinanzeigen_results, filters.limit)
    if len(combined) < filters.limit:
        seen_urls = {listing.url.lower().rstrip("/") for listing in combined}
        for source_results in (vinted_results, kleinanzeigen_results):
            for listing in source_results:
                key = listing.url.lower().rstrip("/")
                if key in seen_urls:
                    continue
                combined.append(listing)
                seen_urls.add(key)
                if len(combined) >= filters.limit:
                    break
            if len(combined) >= filters.limit:
                break

    return combined, errors


async def acknowledge(ctx: commands.Context) -> None:
    if ctx.interaction is not None:
        await ctx.defer()


def _format_filter_summary(filters: SearchFilters) -> str:
    header = f"Query: `{filters.query}`"
    header += f" | area `{filters.marketplace}`"
    if filters.category:
        header += f" | category `{filters.category}`"
    if filters.brand:
        header += f" | brand `{filters.brand}`"
    if filters.size:
        header += f" | size `{filters.size}`"
    if filters.gender:
        header += f" | gender `{filters.gender}`"
    if filters.min_price is not None:
        header += f" | min `{_format_price(filters.min_price)}`"
    if filters.max_price is not None:
        header += f" | max `{_format_price(filters.max_price)}`"

    return header


def _format_price(price: Optional[float]) -> str:
    if price is None:
        return "price n/a"
    whole = f"{price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if whole.endswith(",00"):
        whole = whole[:-3]
    return f"€{whole}"


def build_listing_embed(listing: Listing) -> discord.Embed:
    short_title = _shorten_text(listing.title, 70)
    short_info = _shorten_text(listing.description, 120)
    embed = discord.Embed(
        title=short_title,
        url=listing.url,
        description=short_info,
        color=RESULT_EMBED_COLOR,
    )
    embed.add_field(name="Price", value=_format_price(listing.price), inline=True)
    embed.add_field(name="Source", value=listing.source, inline=True)
    if listing.image_url:
        embed.set_thumbnail(url=listing.image_url)
    return embed


async def send_result(
    send_func: Callable[..., Awaitable[discord.Message]],
    filters: SearchFilters,
    listings: Sequence[Listing],
    errors: Sequence[str] = (),
    *,
    reference: Optional[discord.MessageReference] = None,
) -> None:
    header = _format_filter_summary(filters)
    results = list(listings)[: filters.limit]
    if not results:
        text = f"{header}\n\nNo matching listings found."
        if errors:
            text += f"\n\nSource errors: {'; '.join(errors)}"
        kwargs = {"reference": reference, "mention_author": False} if reference is not None else {}
        await send_func(text, **kwargs)
        return

    embeds = [build_listing_embed(listing) for listing in results]
    kwargs = {"reference": reference, "mention_author": False, "embeds": embeds}
    content = header if not errors else f"{header}\nSources: {'; '.join(errors)}"
    await send_func(content, **kwargs)


def extract_search_text(content: str, bot_user_id: Optional[int]) -> Optional[str]:
    if bot_user_id is not None:
        content = re.sub(rf"<@!?{bot_user_id}>", "", content)
    content = content.strip()
    if not content:
        return None
    lowered = content.lower()
    for prefix in ("snipe:", "snipes:", "search:", "search me:", "find:"):
        if lowered.startswith(prefix):
            return content[len(prefix):].strip() or None
    return content


class SnipeBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("!", "?"),
            intents=intents,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def setup_hook(self) -> None:
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id and guild_id.isdigit():
            guild = discord.Object(id=int(guild_id))
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = SnipeBot()


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} (id={bot.user.id if bot.user else 'unknown'})")


@bot.hybrid_command(name="snipe", description="Search Vinted for listings")
async def snipe(ctx: commands.Context, *, query: str) -> None:
    filters = parse_user_query(query)
    await acknowledge(ctx)
    try:
        listings, errors = await search_all_sources(filters)
    except RuntimeError as exc:
        await ctx.send(f"Search failed: {exc}")
        return

    await send_result(ctx.send, filters, listings, errors)


@bot.command(name="snipesample")
async def snipesample(ctx: commands.Context) -> None:
    await ctx.send(
        "Try `!snipe shirts brand nike size M gender female max 50` or `/snipe shoes page 2 limit 3`."
    )


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    if message.content.startswith(("!", "?")):
        await bot.process_commands(message)
        return

    bot_user_id = bot.user.id if bot.user else None
    in_dedicated_channel = DISCORD_DEDICATED_CHANNEL_ID and message.channel.id == DISCORD_DEDICATED_CHANNEL_ID
    has_bot_mention = bot_user_id is not None and (
        any(user.id == bot_user_id for user in message.mentions)
        or f"<@!{bot_user_id}>" in message.content
        or f"<@{bot_user_id}>" in message.content
    )
    search_text = extract_search_text(message.content, bot_user_id)

    if in_dedicated_channel and search_text:
        filters = parse_user_query(search_text)
        async with message.channel.typing():
            try:
                listings, errors = await search_all_sources(filters)
            except RuntimeError as exc:
                await message.channel.send(
                    f"Search failed: {exc}",
                    reference=message.to_reference(fail_if_not_exists=False),
                    mention_author=False,
                )
            else:
                await send_result(
                    message.channel.send,
                    filters,
                    listings,
                    errors,
                    reference=message.to_reference(fail_if_not_exists=False),
                )
        return

    if has_bot_mention:
        return

    await bot.process_commands(message)


def main() -> None:
    token = DISCORD_TOKEN.strip()
    if not token:
        raise SystemExit("Set DISCORD_TOKEN in snipebot.py before starting the bot.")
    bot.run(token)


if __name__ == "__main__":
    main()
