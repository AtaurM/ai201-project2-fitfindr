# FitFindr

A personal thrifting assistant agent that takes a natural language query, finds matching secondhand listings, suggests an outfit based on the user's wardrobe, and generates a shareable fit card in one multi-step interaction.

## Setup

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Add your Groq API key to a `.env` file in the project root:
```
GROQ_API_KEY=your_key_here
```

Run the app:
```bash
python app.py
```

Run the CLI test:
```bash
python agent.py
```

Run all tests:
```bash
pytest tests/ -v
```

---

## Tool Inventory

### Tool 1 -- `search_listings`

**Purpose:** Filters the full listings dataset (loaded with `load_listings()`) with the user's stated style preferences, size, and budget. Returns every listing that matches all provided filters. Unspecified filters are ignored.

**Inputs:**
- `description` (str): Keywords extracted from the user's query (e.g. "vintage graphic tee"). Matched against each listing's `title`, `description`, and `style_tags` fields using case-insensitive substring search. Any keyword hit counts as a match.
- `size` (str, optional): The user's size (e.g. "M", "W30"). Matched against the listing's `size` field using case-insensitive substring match. Size not filtered if omitted or None.
- `max_price` (float, optional): Upper price bound. Only listings with `price <= max_price` are returned. Price not filtered if omitted or None.

**Returns:** A list of listing dicts sorted by relevance score (highest first). Each dict contains: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str). Returns `[]` if nothing matches -- never raises an exception.

---

### Tool 2 -- `suggest_outfit`

**Purpose:** Suggests which wardrobe pieces pair well with a new item. Calls the Groq LLM (`llama-3.3-70b-versatile`). If the wardrobe is empty, returns general styling advice instead of wardrobe-specific suggestions.

**Inputs:**
- `new_item` (dict): A single listing dict as returned by `search_listings`. Must include at minimum `title` (str), `category` (str), `colors` (list[str]), and `style_tags` (list[str]).
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str or None). Use `get_example_wardrobe()` for a real user's wardrobe or `get_empty_wardrobe()` for a new user.

**Returns:** A non-empty string with outfit suggestions. If the wardrobe is populated, the LLM names specific wardrobe pieces and explains why each combination works (colors, vibe, silhouette). If the wardrobe is empty, the LLM gives general advice about what kinds of pieces pair well with the new item.

---

### Tool 3 -- `create_fit_card`

**Purpose:** Generates a 2-4 sentence Instagram/TikTok-style caption for the thrifted find and its outfit. Calls the Groq LLM at `temperature=1.0` so output varies across runs.

**Inputs:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`. If empty or whitespace-only, returns an error message string without calling the LLM.
- `new_item` (dict): The listing dict for the thrifted item. Used to include the item name, price, and platform naturally in the caption. Must include `title`, `price`, `platform`, `condition`, and `colors`.

**Returns:** A casual, first-person caption string mentioning the item name, price, and platform once each. Captures the specific outfit vibe in concrete terms. Returns a descriptive error message string (not an exception) if `outfit` is empty.

---

## How the Planning Loop Works

The agent runs a linear planning loop with one conditional early exit. Here is the decision logic in `agent.py`:

**Step 1 -- Parse the query.**
The agent uses regex to extract three parameters from the user's natural language query:
- `max_price`: looks for a `$` or number pattern (e.g. "under $30" -> 30.0)
- `size`: looks for "size token" (e.g. "size M" -> "M")
- `description`: the query with price and size mentions stripped out

**Step 2 -- Call `search_listings(description, size, max_price)`.**
Results are stored in `session["search_results"]`.

**Branch point:** If `session["search_results"]` is empty, the agent sets `session["error"]` to a specific actionable message and returns the session immediately. `suggest_outfit` and `create_fit_card` are never called. This is the only branch in the loop.

If results are non-empty, the agent stores `session["selected_item"] = session["search_results"][0]` and continues.

**Step 3 -- Call `suggest_outfit(session["selected_item"], wardrobe)`.**
Result stored in `session["outfit_suggestion"]`. This step always continues -- even an empty wardrobe produces a valid string response, so there is no early exit here.

**Step 4 -- Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`.**
Result stored in `session["fit_card"]`.

**Step 5 -- Return the session dict.** One pass, no retries.

---

## State Management

A `session` dict is created at the start of each `run_agent()` call and passed through the planning loop. It is the single source of truth -- no global state, no re-prompting the user between steps.

- `session["query"]` (str): The original user message, set before any tools are called.
- `session["parsed"]` (dict): Extracted description, size, and max_price from the query.
- `session["search_results"]` (list[dict]): Set after `search_listings` runs. Used for the early-exit check.
- `session["selected_item"]` (dict): Set after non-empty results. This is the listing dict passed into both `suggest_outfit` and `create_fit_card` -- the user never re-enters it.
- `session["wardrobe"]` (dict): Loaded once at the start and passed directly to `suggest_outfit`.
- `session["outfit_suggestion"]` (str): Set after `suggest_outfit` returns. Passed directly into `create_fit_card`.
- `session["fit_card"]` (str): Set after `create_fit_card` returns. This is the final output shown to the user.
- `session["error"]` (str or None): Set only on early exit. If set, `fit_card` and `outfit_suggestion` remain None.

---

## Interaction Walkthrough

**User query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 -- `search_listings` is called**

- **Why:** The user has a shopping intent with style keywords and a price limit. This is always the first tool -- the agent needs actual listings before it can suggest outfits.
- **Input:** `description="vintage graphic tee"`, `size=None`, `max_price=30.0`
- **Output:** The function scans all listings and finds two matches: `lst_002` (Y2K Baby Tee, $18) and `lst_006` (Graphic Tee 2003 Tour Bootleg Style, $24). Both have "vintage" and "graphic tee" in their style tags and are under $30. Returns `[lst_002, lst_006]`.
- The agent stores `session["selected_item"] = results[0]` (the Y2K Baby Tee).

**Step 2 -- `suggest_outfit` is called**

- **Why:** A matching item was found. The agent now needs to show how it fits into the user's wardrobe. This tool is only reached because Step 1 returned results -- if `search_results` had been empty, the agent would have returned early.
- **Input:** `new_item=session["selected_item"]` (the Y2K Baby Tee dict), `wardrobe=get_example_wardrobe()` (10-item wardrobe loaded at session start)
- **Output (actual LLM response):**
  ```
  Outfit 1: Casual Chic -- Pair the Y2K Baby Tee with your Baggy Straight-Leg Jeans
  and Chunky White Sneakers. The pastel colors of the tee complement the dark wash
  of the jeans, and the white sneakers tie in with the white base of the tee.

  Outfit 2: Cottagecore Dream -- Combine the Y2K Baby Tee with your Wide-Leg Khaki
  Trousers and Black Combat Boots. The earthy khaki brings out the soft pink and
  purple hues in the tee, and the combat boots add an edgy counterpoint.
  ```
- Stored in `session["outfit_suggestion"]`.

**Step 3 -- `create_fit_card` is called**

- **Why:** Outfit suggestions exist. The final step is to format everything into a shareable caption.
- **Input:** `outfit=session["outfit_suggestion"]` (the string above), `new_item=session["selected_item"]` (same Y2K Baby Tee dict -- no re-entry)
- **Output (actual LLM response):**
  ```
  I just scored this adorable Y2K Baby Tee for $18 on Depop and I'm obsessed
  with the vintage vibe it's giving me. I paired it with my baggy straight-leg
  jeans and chunky white sneakers for a laid-back, streetwear-inspired look.
  Totally feeling the y2k and cottagecore crossover in this one.
  ```
- Stored in `session["fit_card"]` and returned to the UI.

**Final state of the session dict:**
```python
{
  "query":             "I'm looking for a vintage graphic tee under $30...",
  "parsed":            {"description": "vintage graphic tee", "size": None, "max_price": 30.0},
  "search_results":    [<Y2K Baby Tee dict>, <Graphic Tee dict>],
  "selected_item":     <Y2K Baby Tee dict>,   # same object passed to steps 2 and 3
  "wardrobe":          {"items": [...]},
  "outfit_suggestion": "Outfit 1: Casual Chic -- ...",
  "fit_card":          "I just scored this adorable Y2K Baby Tee...",
  "error":             None
}
```

---

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the filters | Sets `session["error"] = "I couldn't find any listings matching those filters. Try a broader style description, a higher budget, or leave the size open."` and returns early. `suggest_outfit` and `create_fit_card` are never called. |
| `suggest_outfit` | `wardrobe["items"]` is empty (new user with no wardrobe) | Returns a non-empty string with general styling advice -- what kinds of pieces pair well, what vibe it suits, and one concrete styling tip. Does not crash or return an empty string. |
| `create_fit_card` | `outfit` argument is empty or whitespace-only | Returns `"Could not generate a fit card: outfit suggestion was empty. Try running suggest_outfit first and pass its output here."` -- no exception raised. |

### Deliberately triggered failures (terminal output)

**Failure 1 -- `search_listings` returns empty, agent exits early**

```
$ python agent.py

=== No-results path ===

error: I couldn't find any listings matching those filters. Try a broader style
       description, a higher budget, or leave the size open.
fit_card: None
outfit_suggestion: None
```

`suggest_outfit` and `create_fit_card` were never called. The session confirms it: both `fit_card` and `outfit_suggestion` are `None`.

**Failure 2 -- `suggest_outfit` with empty wardrobe**

```
$ python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"

This Y2K Baby Tee is super cute. You can create a laid-back, vintage-inspired look
by pairing it with high-waisted jeans or a flowy skirt. For a more put-together
outfit, throw on a denim jacket or a cardigan to add some depth.

The tee's butterfly print and pastel colors scream cottagecore, so consider pairing
it with earthy tones like brown sandals or sneakers. One concrete styling tip: try
tucking the tee into your bottoms to create a more defined waistline.
```

No crash. General advice returned instead of wardrobe-specific suggestions.

**Failure 3 -- `create_fit_card` with empty outfit string**

```
$ python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"

Could not generate a fit card: outfit suggestion was empty. Try running
suggest_outfit first and pass its output here.
```

No exception. Descriptive error string returned.

---

## Spec Reflection

**One way `planning.md` helped during implementation:**

Writing out the planning loop step-by-step in plain English before touching `agent.py` made the early-exit branch obvious. The spec said explicitly: if `results` is empty, set `session["error"]` and return early -- do not call any further tools. Without that written constraint, it would have been easy to write the loop in a way that called all three tools unconditionally and just passed empty values through. The spec made the branch a deliberate design decision rather than something discovered during debugging.

**One divergence from the spec, and why:**

The `suggest_outfit` and `create_fit_card` tools were specced in `planning.md` to return a dict (with `outfit` and `reasoning` keys). The actual stub signatures in `tools.py` had both returning a plain string. The dict design was cleaner for state tracking, but the stubs were the authoritative interface since `app.py` and `agent.py` were already written around string returns. Adapting to the string return was the right call -- changing the stub signature would have broken the Gradio wiring, and a string is sufficient for the fit card use case.

---

## AI Usage

**Instance 1 -- Implementing `tools.py`**

I gave Claude the Tool 1-3 spec blocks from `planning.md` (parameter names and types, return value descriptions, failure modes) and the `tools.py` stub file, and asked it to implement all three functions. Before running the generated code, I reviewed it against the spec: I confirmed `search_listings` applied all three filters independently and handled `None` inputs, that `suggest_outfit` branched on `wardrobe["items"]` being empty, and that `create_fit_card` guarded against empty strings before making the LLM call. I overrode the return type for `suggest_outfit` and `create_fit_card` from dict to str to match the actual stub signatures, which differed from my planning.md spec.

**Instance 2 -- Implementing `agent.py`**

I gave Claude the Planning Loop and State Management sections from `planning.md` and the Architecture ASCII diagram, and asked it to implement `run_agent()`. I reviewed the generated code for three things: (1) whether it branched on `search_results` being empty rather than calling all tools unconditionally, (2) whether state passed via the session dict rather than local variables, and (3) whether the regex parsing covered the query formats shown in the example queries in `app.py`. I revised the price regex to also match bare numbers without a `$` sign (e.g. "under 30"), and I added the description-cleaning step (stripping price and size tokens from the description before passing it to `search_listings`) which the generated code had omitted.
