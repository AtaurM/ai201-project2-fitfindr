"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()

    # Apply hard filters first (price and size)
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    if size:
        size_lower = size.lower()
        listings = [l for l in listings if size_lower in l["size"].lower()]

    # Score each remaining listing by keyword overlap with description
    keywords = [kw.lower() for kw in description.split() if kw]

    def score(listing: dict) -> int:
        searchable = " ".join([
            listing["title"].lower(),
            listing["description"].lower(),
            " ".join(listing["style_tags"]),
        ])
        return sum(1 for kw in keywords if kw in searchable)

    scored = [(score(l), l) for l in listings]
    scored = [(s, l) for s, l in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [l for _, l in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    client = _get_groq_client()

    item_summary = (
        f"Item: {new_item.get('title', 'Unknown item')}\n"
        f"Category: {new_item.get('category', 'unknown')}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Condition: {new_item.get('condition', 'unknown')}\n"
        f"Price: ${new_item.get('price', '?')}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            f"A thrift shopper is considering buying the following item:\n\n"
            f"{item_summary}\n\n"
            f"They have no wardrobe entered yet. Give them 1–2 specific outfit ideas — "
            f"describe what kinds of pieces would pair well with this item (bottoms, shoes, outerwear, etc.), "
            f"what vibe or aesthetic it suits, and one concrete styling tip. Be casual and direct."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {item['name']} ({item['category']}, colors: {', '.join(item.get('colors', []))}, "
            f"tags: {', '.join(item.get('style_tags', []))})"
            for item in wardrobe_items
        )
        prompt = (
            f"A thrift shopper is considering buying the following item:\n\n"
            f"{item_summary}\n\n"
            f"Their current wardrobe includes:\n{wardrobe_lines}\n\n"
            f"Suggest 1–2 specific outfits using the new item combined with named pieces from their wardrobe. "
            f"For each outfit, name the exact wardrobe pieces and explain why the combination works "
            f"(colors, vibe, silhouette). Be casual and specific — like a friend who knows fashion."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=400,
    )

    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)
    """
    if not outfit or not outfit.strip():
        return (
            "Could not generate a fit card: outfit suggestion was empty. "
            "Try running suggest_outfit first and pass its output here."
        )

    title = new_item.get("title", "thrifted find")
    price = new_item.get("price", "?")
    platform = new_item.get("platform", "a thrift app")
    colors = ", ".join(new_item.get("colors", []))
    style_tags = ", ".join(new_item.get("style_tags", []))

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok OOTD caption for this thrift find.\n\n"
        f"Item: {title}\n"
        f"Price: ${price} from {platform}\n"
        f"Colors: {colors}\n"
        f"Vibes: {style_tags}\n\n"
        f"Outfit context:\n{outfit}\n\n"
        f"Rules:\n"
        f"- Casual, first-person, authentic — like a real post, not an ad\n"
        f"- Mention the item name, price, and platform once each, naturally\n"
        f"- Be specific about the vibe (don't just say 'cute' or 'stylish')\n"
        f"- No hashtags\n"
        f"- 2–4 sentences max"
    )

    client = _get_groq_client()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0,
        max_tokens=200,
    )

    return response.choices[0].message.content.strip()
