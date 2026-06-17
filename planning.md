# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Filters the full listings dataset (loaded with `load_listings()`) with the user's stated style preferences, size, and budget. Returns every listing that matches all provided filters. Unspecified filters are ignored.

**Input parameters:**
- `description` (str): Keywords extracted from the user's query (e.g. "vintage graphic tee"). Matched against each listing's `title`, `description`, and `style_tags` fields using case-insensitive substring search. Any keyword hit counts as a match.
- `size` (str, optional): The user's size (e.g. "M", "W30"). Matched against the listing's `size` field using case-insensitive substring match. Size not filtered if omitted or empty string.
- `max_price` (float, optional): Upper price bound. Only listings with `price <= max_price` are returned. Price not filtered if omitted or 0.

**What it returns:**
A list of listing dicts, each containing: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str). Returns an empty list `[]` if no listings match.

**What happens if it fails or returns nothing:**
If the list is empty, the agent responds: "I couldn't find any listings matching those filters. Try a broader style description, a higher budget, or leave the size open." Instead of proceeding to `suggest_outfit`, the agent returns this message and ends the turn.

---

### Tool 2: suggest_outfit

**What it does:**
Suggests which wardrobe pieces pair well with a new item given the single new listing item and the user's current wardrobe. Matching is based on overlapping `style_tags` and complementary `colors` between the new item and wardrobe items.

**Input parameters:**
- `new_item` (dict): A single listing dict as returned by `search_listings`. Must include at minimum `title` (str), `category` (str), `colors` (list[str]), and `style_tags` (list[str]).
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str or None). Use `get_example_wardrobe()` for a real user's wardrobe or `get_empty_wardrobe()` for a new user.

**What it returns:**
A dict with two keys:
- `outfit` (list[dict]): The subset of wardrobe items that pair well with the new item, each with `id`, `name`, and `category`.
- `reasoning` (str): One sentence explanation of why these pieces work together (e.g. "The flannel's grunge tags match your combat boots and baggy jeans for a layered streetwear look.").

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, return `{"outfit": [], "reasoning": "Your wardrobe is empty. This item would be a great starting piece. Add more items to get outfit suggestions."}`. If no wardrobe items share style tags or compatible colors, return `{"outfit": [], "reasoning": "Nothing in your current wardrobe is a strong match, but this piece would work as a standalone statement item."}`. The agent still proceeds to `create_fit_card` in both cases.

---

### Tool 3: create_fit_card

**What it does:**
Formats the new listing and suggested outfit pairing into a single concise summary the user receives as the final output of the interaction ("fit card" string).

**Input parameters:**
- `outfit` (dict): The full return value from `suggest_outfit`: a dict with `outfit` (list[dict]) and `reasoning` (str).
- `new_item` (dict): The listing dict selected from `search_listings` results. Must include `title`, `price`, `platform`, `condition`, and `colors`.

**What it returns:**
A single formatted string (the fit card) structured as:
```
+ FIT CARD
New find: {title} - ${price} on {platform} ({condition})
Colors: {colors joined by ", "}

Pairs with:
  - {wardrobe item name} ({category})   [repeated for each item in outfit]

Why it works: {reasoning}
```
If `outfit["outfit"]` is empty, the "Pairs with" section reads "Nothing in your wardrobe yet--style it solo."

**What happens if it fails or returns nothing:**
If `new_item` is missing required fields (`title`, `price`, `platform`), return a minimal card: `"+ FIT CARD\nNew find: [item details unavailable]\n{reasoning}"`. The agent always returns something to the user rather than silently failing.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent runs a linear planning loop with early exit on failure. Here is the conditional logic step by step:

1. **Parse the query.** Extract `description` (style keywords), `size` (if mentioned), and `max_price` (if a dollar amount is mentioned) from the user's message. If no size or price is mentioned, pass empty string or 0 respectively.

2. **Call `search_listings(description, size, max_price)`.**
   - If `results` is an empty list, then set `session["error"] = "no_listings"`, respond with the no-results message, and **return early** (do not call any further tools).
   - If `results` is non-empty, then set `session["selected_item"] = results[0]` (the first/best match) and continue.

3. **Call `suggest_outfit(session["selected_item"], wardrobe)`.**
   - `wardrobe` is loaded at session start via `get_example_wardrobe()` (or `get_empty_wardrobe()` if the user has no wardrobe).
   - Store the return value: `session["outfit_suggestion"] = result`.
   - This step never triggers an early exit, even an empty outfit dict proceeds.

4. **Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`.**
   - Store the return value: `session["fit_card"] = result`.

5. **Return `session["fit_card"]` to the user.** The loop is done.

The agent knows it is done when `session["fit_card"]` is set, or when an early-exit error is set. There is no retry or looping back. Only one pass through the pipeline per user query.

---

## State Management

**How does information from one tool get passed to the next?**

A `session` dict is created at the start of each interaction and passed through the planning loop. It holds:

- `session["query"]` (str): The original user message, set before any tools are called.
- `session["selected_item"]` (dict): Set after `search_listings` succeeds. This is the listing dict passed into `suggest_outfit` and `create_fit_card`.
- `session["outfit_suggestion"]` (dict): Set after `suggest_outfit` returns. This contains `outfit` and `reasoning` keys, which are passed into `create_fit_card`.
- `session["fit_card"]` (str): Set after `create_fit_card` returns. This is the final output shown to the user.
- `session["error"]` (str, optional): Set if an early-exit condition is triggered (e.g. `"no_listings"`). Used to skip downstream tool calls.

The wardrobe is not stored in `session`. It is loaded once at the start of the interaction via `get_example_wardrobe()` and passed directly as an argument to `suggest_outfit`.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match the filters | Respond: "I couldn't find any listings matching those filters. Try a broader style description, a higher budget, or leave the size open." Set `session["error"] = "no_listings"` and return early. Do not call suggest_outfit or create_fit_card. |
| suggest_outfit | Wardrobe is empty (`wardrobe["items"] == []`) | Return `{"outfit": [], "reasoning": "Your wardrobe is empty. This item would be a great starting piece."}` and continue to create_fit_card. The fit card will note "style it solo" in the Pairs With section. |
| create_fit_card | `new_item` is missing required fields (title, price, platform) | Return a minimal fit card: `"+ FIT CARD\nNew find: [item details unavailable]\n"` + the reasoning string. Always return a string. Never raise an exception to the user. |

---

## Architecture

```
User query
    │
    v
[Parse query]
    │  description (str), size (str), max_price (float)
    v
Planning Loop
    │
    |-> search_listings(description, size, max_price)
    │       │
    │       |-> results == [] --> [ERROR] "No listings found. Try broader filters." --> return
    │       │
    │       |-> results = [item, ...]
    │               │
    │               v
    │       session["selected_item"] = results[0]
    │               │
    |-> suggest_outfit(selected_item, wardrobe)
    │       │
    │       |-> wardrobe empty --> {outfit: [], reasoning: "empty wardrobe..."}
    │       │                           │
    │       |-> wardrobe has items --> {outfit: [...], reasoning: "..."}
    │               │
    │               v
    │       session["outfit_suggestion"] = {outfit, reasoning}
    │               │
    |-> create_fit_card(outfit_suggestion, selected_item)
            │
            v
    session["fit_card"] = formatted string
            │
            v
    Return fit_card to user
```

State / Session dict:
```
session = {
  "query":             str,   # original user message
  "selected_item":     dict,  # listing from search_listings
  "outfit_suggestion": dict,  # {outfit, reasoning} from suggest_outfit
  "fit_card":          str,   # final output from create_fit_card
  "error":             str    # set only on early exit
}
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For `search_listings`: I'll give Claude the Tool 1 block from planning.md (the parameter list, return value description, and failure mode) and ask it to implement the function using `load_listings()` from `utils/data_loader.py`. I'll verify the output by checking that it filters by all three parameters independently, handles missing/empty inputs, and actually returns the correct fields. I'll test with a query that matches multiple listings, one where size filters out everything, and one with a max_price of $20.

For `suggest_outfit`: I'll give Claude the Tool 2 block and the wardrobe schema from `data/wardrobe_schema.json`. I'll ask it to match on `style_tags` overlap and complementary colors. I'll verify by running it with `get_example_wardrobe()` against a known listing and checking that the `outfit` list and `reasoning` string are present. I'll also test the empty wardrobe path using `get_empty_wardrobe()`.

For `create_fit_card`: I'll give Claude the Tool 3 block including the exact output format template. I'll verify by checking that the returned string contains all five sections (header, new find line, colors, pairs with, reasoning) for a normal case and that the fallback for missing fields produces a valid string without crashing.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Planning Loop section, the State Management section, and the Architecture diagram from this file. I'll ask it to implement a `run_agent(user_query, wardrobe)` function that initializes the session dict, calls the three tools in order, applies the early exit condition after `search_listings`, and returns `session["fit_card"]` or `session["error"]`. I'll verify by tracing through the example query manually and confirming `session` contains all expected keys at the end. I'll also test the early exit path by passing a query guaranteed to return no results (e.g. description="abcxyz", max_price=0.01).

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**What FitFindr does:**
FitFindr is a personal thrifting assistant that takes a request (style preferences, size, budget) and uses `search_listings` to find matching secondhand items from the local dataset, then calls `suggest_outfit` to pair a chosen result with the user's existing wardrobe, and finally calls `create_fit_card` to produce a shareable outfit summary. If `search_listings` does not return a match, the agent tells the user and may widen the filters rather than proceeding to outfit suggestion. If the wardrobe is empty, `suggest_outfit` skips pairing and `create_fit_card` is called with the new item alone.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query and extracts: `description = "vintage graphic tee"`, `size = ""` (not specified), `max_price = 30.0`. It calls `search_listings("vintage graphic tee", "", 30.0)`. The function scans all listings and finds two matches: `lst_002` (Y2K Baby Tee, $18) and `lst_006` (Graphic Tee — 2003 Tour Bootleg Style, $24). Both have "vintage" and "graphic tee" in their style tags and are under $30. Returns `[lst_002, lst_006]`.

**Step 2:**
`results` is non-empty, so the agent sets `session["selected_item"] = results[0]` -> the Y2K Baby Tee (`lst_002`). It calls `suggest_outfit(lst_002, get_example_wardrobe())`. The function compares `lst_002`'s style tags (`["y2k", "vintage", "graphic tee", "cottagecore"]`) and colors (`["white", "pink", "purple"]`) against the 10 wardrobe items. It finds matches: `w_001` (baggy dark-wash jeans, "streetwear" overlap), `w_007` (chunky white sneakers, "streetwear" + white color overlap). Returns `{"outfit": [w_001, w_007], "reasoning": "The baby tee's vintage crop pairs with your baggy jeans and chunky sneakers for a classic y2k streetwear look."}`.

**Step 3:**
The agent sets `session["outfit_suggestion"]` to the result above. It calls `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. The function formats the fit card string using `lst_002`'s title, price ($18.00), platform (depop), condition (excellent), and colors (white, pink, purple), plus the two outfit items and reasoning.

**Final output to user:**
```
+ FIT CARD
New find: Y2K Baby Tee - Butterfly Print - $18.00 on depop (excellent)
Colors: white, pink, purple

Pairs with:
  - Baggy straight-leg jeans, dark wash (bottoms)
  - Chunky white sneakers (shoes)

Why it works: The baby tee's vintage crop pairs with your baggy jeans and chunky sneakers for a classic y2k streetwear look.
```
