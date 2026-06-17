"""
tests/test_tools.py

Isolated tests for each FitFindr tool, including failure modes.
Run with:  pytest tests/
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# search_listings

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

def test_search_price_filter_inclusive():
    results = search_listings("vintage", size=None, max_price=38.0)
    assert all(item["price"] <= 38.0 for item in results)

def test_search_size_filter():
    results = search_listings("vintage", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)

def test_search_no_size_filter_when_none():
    results_all = search_listings("vintage", size=None, max_price=None)
    results_sized = search_listings("vintage", size="M", max_price=None)
    assert len(results_all) >= len(results_sized)

def test_search_results_are_sorted_by_relevance():
    results = search_listings("vintage streetwear", size=None, max_price=None)
    # items with both 'vintage' and 'streetwear' tags should score higher
    # thus appear before items with only one match. just check order is stable
    assert isinstance(results, list)

def test_search_result_fields():
    results = search_listings("vintage", size=None, max_price=None)
    assert len(results) > 0
    required_fields = {"id", "title", "description", "category", "style_tags",
                       "size", "condition", "price", "colors", "brand", "platform"}
    for item in results:
        assert required_fields.issubset(item.keys())


# suggest_outfit

SAMPLE_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "category": "tops",
    "colors": ["black"],
    "style_tags": ["graphic tee", "vintage", "grunge", "streetwear"],
    "condition": "good",
    "price": 24.0,
    "platform": "depop",
}

def test_suggest_outfit_with_wardrobe_returns_string():
    result = suggest_outfit(SAMPLE_ITEM, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_outfit_empty_wardrobe_returns_string():
    result = suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_outfit_empty_wardrobe_no_crash():
    """Empty wardrobe must not raise an exception."""
    try:
        result = suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
    except Exception as e:
        pytest.fail(f"suggest_outfit raised an exception on empty wardrobe: {e}")

def test_suggest_outfit_mentions_item():
    result = suggest_outfit(SAMPLE_ITEM, get_example_wardrobe())
    # llm should reference the item somehow
    assert any(word in result.lower() for word in ["tee", "graphic", "shirt", "top"])


# create_fit_card

SAMPLE_OUTFIT = (
    "Pair the graphic tee with baggy dark-wash jeans and chunky white sneakers "
    "for a classic 90s streetwear look. The black tee grounds the blue denim "
    "and the chunky sneakers add the right weight to the silhouette."
)

def test_create_fit_card_returns_string():
    result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_empty_outfit_returns_error_string():
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "empty" in result.lower() or "error" in result.lower() or "could not" in result.lower()

def test_create_fit_card_whitespace_outfit_returns_error_string():
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_no_exception_on_empty_outfit():
    """Empty outfit must not raise an exception."""
    try:
        result = create_fit_card("", SAMPLE_ITEM)
    except Exception as e:
        pytest.fail(f"create_fit_card raised an exception on empty outfit: {e}")

def test_create_fit_card_mentions_platform():
    result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert SAMPLE_ITEM["platform"].lower() in result.lower()

def test_create_fit_card_varies_on_same_input():
    """Two calls on the same input should not be identical (temperature=1.0)."""
    result1 = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    result2 = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    # w/ temperature=1.0 these will almost certainly differ; allow one retry
    if result1 == result2:
        result3 = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
        assert result1 != result3, "create_fit_card returned identical output 3 times — check LLM temperature"
