Great—here’s the **simplified, unambiguous spec** you can hand to an AI coding agent. It covers only: fetch top HN IDs → fetch/store item JSON → list/display. No caching key, no ZSET index, no respx.

---

# 1) Data model

**Pydantic model:**

```python
from typing import List, Optional
from pydantic import BaseModel

class HNItem(BaseModel):
    id: int
    type: Optional[str] = None
    by: Optional[str] = None
    time: Optional[int] = None      # Unix seconds
    url: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = None
    score: Optional[int] = None
    descendants: Optional[int] = None
    kids: Optional[List[int]] = None
```

---

# 2) Storage

**Redis keys (only one pattern):**

* `hnfm:item:{id}` → JSON string of `HNItem`.

**File storage (for each item):**

* `outputs/hn/item/{id}/item.json` (exact JSON we stored in Redis).

---

# 3) Utilities (Python, synchronous)

Use `requests` for HTTP and `redis-py` for Redis.

### 3.1 HTTP (Firebase)

* `get_top_story_ids() -> list[int]`

  * GET `https://hacker-news.firebaseio.com/v0/topstories.json`.
  * Return a Python `list[int]`. No caching.

* `get_item_json_and_store(item_id: int, *, redis_client, outputs_dir: str) -> HNItem`

  * GET `https://hacker-news.firebaseio.com/v0/item/{item_id}.json`.
  * Validate with `HNItem`.
  * `SET hnfm:item:{id}` (serialized JSON).
  * Write `outputs/{id}/item.json`.
  * Return the `HNItem`.

### 3.2 Redis (helpers)

* `exists_item(item_id: int, *, redis_client) -> bool`

  * `EXISTS hnfm:item:{id}` → bool.

* `get_item(item_id: int, *, redis_client) -> HNItem | None`

  * `GET hnfm:item:{id}`; return `HNItem` or `None`.

* `list_item_ids(*, redis_client) -> list[int]`

  * `SCAN` for `hnfm:item:*`, extract `{id}` as `int`, return list of ids.

* `list_items(offset: int, limit: int, *, redis_client) -> list[HNItem]`

  * Get `ids = list_item_ids(...)`.
  * Sort `ids` **descending** (largest id first).
  * Slice with `offset` and `limit`.
  * `MGET` each `hnfm:item:{id}` (or loop `GET`), parse to `HNItem`.
  * Return the list.

*(No ZSET. No `hnfm:top_ids`.)*

---

# 4) Celery task

* `tasks.hn_fetch_item(item_id: int) -> dict`

  * If `exists_item(item_id)` is `True`: return `{"status": "exists", "id": item_id}`.
  * Else call `get_item_json_and_store(...)`.
  * Return `{"status": "fetched", "id": item_id}`.

**Important:** When enqueuing, use `apply_async` (not `.delay`).

---

# 5) API (FastAPI)

All endpoints are synchronous.

### 5.1 Queue top stories

* **Route:** `POST /api/hn/queue-top?limit=50`
* **Behavior:**

  * Call `get_top_story_ids()`.
  * Take the first `limit` ids.
  * For each id, call `hn_fetch_item.apply_async(args=[id])`.
    (We **do not** pre-check Redis here. The task will skip if it already exists.)
* **Response JSON:**

  ```json
  { "queued_count": 50, "ids": [123, 456, ...], "limit": 50 }
  ```

### 5.2 List downloaded items

* **Route:** `GET /api/hn/items?offset=0&limit=50`
* **Behavior:**

  * Call `list_items(offset, limit)`.
* **Response JSON:**

  ```json
  {
    "items": [ HNItem, ... ],
    "pagination": { "offset": 0, "limit": 50, "count": 50 }
  }
  ```

### 5.3 Get one item

* **Route:** `GET /api/hn/items/{item_id}`
* **Behavior:**

  * `get_item(item_id)`; if `None`, return 404 `{ "detail": "Item not found" }`.
  * Else return the `HNItem` JSON.

---

# 6) Tests (pytest)

Use **fakeredis-py** (`cunla/fakeredis-py`) to replace Redis, and **monkeypatch** to stub `requests.get`. Do **not** use respx.

### 6.1 Utilities

**`test_get_top_story_ids_returns_list`**

* Monkeypatch `requests.get` to return `json() -> [1,2,3]`.
* Call `get_top_story_ids()`.
* Assert: result is `[1,2,3]` (type: `list[int]`).

**`test_get_item_json_and_store_saves_redis_and_file`**

* Monkeypatch `requests.get` to return a JSON for one item:

  ```json
  {"id": 1, "type": "story", "time": 1000, "title": "T", "by": "u"}
  ```
* Use `fakeredis.FakeRedis()` and `tmp_path` for `outputs_dir`.
* Call `get_item_json_and_store(1, redis_client=fake, outputs_dir=str(tmp_path))`.
* Assert: `fake.get("hnfm:item:1")` is not `None`.
* Assert: file `tmp_path/"1"/"item.json"` exists and contains `"id": 1`.

**`test_exists_and_get_item_helpers`**

* Seed Redis: `fake.set("hnfm:item:5", '{"id":5}')`.
* Assert: `exists_item(5)` is `True`.
* Assert: `get_item(5)` returns `HNItem(id=5)`.

**`test_list_items_orders_desc_and_paginates`**

* Seed Redis: ids 1, 10, 3.
* Call `list_items(offset=0, limit=2)` → ids `[10,3]`.
* Call `list_items(offset=2, limit=2)` → ids `[1]`.

### 6.2 Celery task

**`test_hn_fetch_item_exists_short_circuits`**

* Seed Redis with item id 7.
* Monkeypatch `requests.get` to raise if called (ensure no HTTP).
* Call `hn_fetch_item(7)` directly (not via worker).
* Assert: `{"status":"exists","id":7}`.

**`test_hn_fetch_item_fetches_when_missing`**

* Empty Redis.
* Monkeypatch `requests.get` to return a valid item JSON `{ "id": 8 }`.
* Call `hn_fetch_item(8)`.
* Assert: Redis has `hnfm:item:8`; result `{"status":"fetched","id":8}`.

### 6.3 API

Use `TestClient` with fakeredis injected into your app’s Redis dependency.

**`test_queue_top_enqueues_apply_async`**

* Monkeypatch `get_top_story_ids` → return `[1,2,3,4,5]`.
* Monkeypatch `tasks.hn_fetch_item.apply_async` to collect `args`.
* POST `/api/hn/queue-top?limit=3`.
* Assert: apply\_async called 3 times with ids `[1,2,3]`.
* Assert response payload matches.

**`test_list_items_endpoint`**

* Seed Redis with two items (ids 2 and 1).
* GET `/api/hn/items?offset=0&limit=2`.
* Assert: items length 2; first item has `id=2`.

**`test_get_single_item_endpoint`**

* Seed id 9; GET `/api/hn/items/9` → 200 with `id=9`.
* GET `/api/hn/items/999999` → 404 with `{ "detail": "Item not found" }`.

---

# 7) Frontend (Nuxt 3)

### 7.1 List page: **`/hn/items`**

* On server-side, fetch `GET /api/hn/items?offset=0&limit=50`.
* Render a simple table with columns: **Title**, **By**, **Score**, **Time**, **ID**.
* Each row:

  * Title links to the external `url` (if present).
  * ID links to `/hn/items/<id>`.
* Add a button **“Queue Top (50)”** that calls `POST /api/hn/queue-top?limit=50`, then refetches the list.

### 7.2 Detail page: **`/hn/items/[id]`**

* On server-side, fetch `GET /api/hn/items/{id}`.
* Show all available fields.
* Back link to `/hn/items`.

---

# 8) Endpoint behavior confirmation

* `POST /api/hn/queue-top?limit=50` **enqueues** the first 50 IDs from top stories using `apply_async`.
* The Celery task itself checks Redis and **exits early** if the item already exists (no error).

---

# 9) Build order (small commits)

1. Model `HNItem`.
2. Redis client + file layout (`outputs/{id}/item.json`).
3. Utilities: `get_top_story_ids`, `get_item_json_and_store`, `exists_item`, `get_item`, `list_item_ids`, `list_items`.
4. Tests for utilities (fakeredis + monkeypatch requests).
5. Celery task `hn_fetch_item` + tests.
6. API routes + tests.
7. Frontend `/hn/items` and `/hn/items/[id]`.

---

# 10) Acceptance checklist

* [ ] `get_top_story_ids()` returns a list of ints from Firebase.
* [ ] `get_item_json_and_store()` saves to **Redis** and **outputs/{id}/item.json**.
* [ ] `POST /api/hn/queue-top?limit=N` enqueues exactly N IDs with `apply_async`.
* [ ] `GET /api/hn/items` returns stored items in **descending id** order with offset/limit.
* [ ] `GET /api/hn/items/{id}` returns 200 if present, 404 if missing.
* [ ] Frontend pages `/hn/items` and `/hn/items/[id]` render correctly.
* [ ] All tests pass with **fakeredis-py** and `requests` monkeypatched.


This is the next step of what wer are going to do: It adds Firecrawl scraping + LLM summary, per-item **runs**, storage in Redis and disk, API, tasks, tests, and two small frontend views. Please implement as specified here:

---

# 1) Data model

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProcessedRun(BaseModel):
    key: str                 # "hnfm:item:{item_id}:run:{run}"
    item_id: int
    run: int
    created_at: datetime
    source_url: str
    content_raw: str         # raw text/markdown from Firecrawl
    content_clean: str       # cleaned text (whitespace/boilerplate removed)
    summary: str             # LLM summary text
```

---

# 2) Redis keys and disk paths

* **Per-run JSON**: `hnfm:item:{item_id}:run:{run}` → serialized `ProcessedRun`.
* **Per-item run sequence counter**: `hnfm:item:{item_id}:run_seq` (INCR to get next run).
* **Per-item run list**: `hnfm:item:{item_id}:runs` (LIST of run ints as strings). On successful save: `LPUSH` the run number.

**Disk:**

```
outputs/hn/item/{item_id}/runs/{run}/processed.json
```

---

# 3) Utilities

Implement these **synchronous** helpers. All file writes must create parent directories as needed.

1. **Run ID**

```python
def next_run_id(item_id: int, *, redis_client) -> int:
    # INCR hnfm:item:{item_id}:run_seq → int
```

2. **Scrape with Firecrawl** (I think we already have logic for this in scraper/content_scraper.py, so please check there first)

```python
def scrape_url_firecrawl(url: str) -> str:
    """
    Use requests.post to your Firecrawl endpoint and return the raw text/markdown.
    If non-200 or empty payload, raise an exception.
    """
```

3. **Clean content** (also please check the content/content_processor.py file for related logic here)

```python
def clean_content(text: str) -> str:
    """
    Simple deterministic cleanup:
    - Strip leading/trailing whitespace
    - Collapse consecutive whitespace/newlines
    Return cleaned string.
    """
```

4. **Summarize with LLM**

```python
def summarize_text_v1(text: str) -> str:
    """
    Use requests.post to your LLM summary endpoint.
    Prompt: 'Summarize the article in 5-7 sentences. Be specific and factual.'
    Return the summary string.
    If non-200 or empty, raise an exception.
    """
```

5. **Save run (Redis + Disk)**

```python
def save_processed_run(pr: ProcessedRun, *, redis_client, outputs_root: str) -> None:
    """
    - SET hnfm:item:{item_id}:run:{run} with JSON(pr)
    - LPUSH hnfm:item:{item_id}:runs the run number
    - Write to outputs/hn/item/{item_id}/runs/{run}/processed.json
    """
```

6. **Get runs for an item**

```python
def list_runs_for_item(item_id: int, *, redis_client, offset: int = 0, limit: int = 20) -> list[int]:
    """
    Use LRANGE on hnfm:item:{item_id}:runs (it's newest-first because we LPUSH).
    Slice with offset/limit and return a list of run ints.
    """
```

7. **Get one run**

```python
def get_run(item_id: int, run: int, *, redis_client) -> Optional[ProcessedRun]:
    """
    GET hnfm:item:{item_id}:run:{run} and parse to ProcessedRun. Return None if missing.
    """
```

---

# 4) Celery task

```python
def process_hn_item_run(item_id: int, run: int) -> dict:
    """
    Steps:
    1) GET hn:item:{item_id} from Redis. If missing → raise.
    2) Parse JSON; read item['url']. If missing → raise.
    3) content_raw = scrape_url_firecrawl(url)
    4) content_clean = clean_content(content_raw)
    5) summary = summarize_text_v1(content_clean)
    6) Build ProcessedRun(...) with created_at=utcnow()
    7) save_processed_run(...)
    8) return {"status": "ok", "item_id": item_id, "run": run}
    """
```

* Use `apply_async(args=[item_id, run])` when enqueueing (see API below).
* Do **not** write anything if an exception occurs (let Celery log the error).

---

# 5) API (FastAPI)

All endpoints are synchronous.

## 5.1 Create and queue a new run

* **Route:** `POST /api/hn/items/{item_id}/runs`
* **Behavior:**

  1. `run = next_run_id(item_id, redis_client=...)`
  2. `process_hn_item_run.apply_async(args=[item_id, run])`
  3. Return `{ "item_id": item_id, "run": run, "status": "queued" }`

## 5.2 List runs for an item

* **Route:** `GET /api/hn/items/{item_id}/runs?offset=0&limit=20`
* **Behavior:**

  1. `run_ids = list_runs_for_item(item_id, offset, limit)`
  2. For each run id, fetch `ProcessedRun` and include only `{run, summary}` in the response list.
* **Response:**

```json
{
  "item_id": 45114175,
  "runs": [
    { "run": 2, "summary": "..." },
    { "run": 1, "summary": "..." }
  ],
  "pagination": { "offset": 0, "limit": 20, "count": 2 }
}
```

## 5.3 Get a single run

* **Route:** `GET /api/hn/items/{item_id}/runs/{run}`
* **Behavior:**

  * Return full `ProcessedRun` JSON.
  * 404 if missing.

---

# 6) Tests (pytest)

Use **fakeredis-py** for Redis and `monkeypatch` to stub network calls (`scrape_url_firecrawl` and `summarize_text_v1`). Do not perform real HTTP.

## 6.1 Utilities

* **`test_next_run_id_increments`**

  * New item: INCR returns 1, then 2.

* **`test_save_processed_run_persists_everywhere`**

  * Build a small `ProcessedRun`.
  * Call `save_processed_run(...)`.
  * Assert Redis `GET hnfm:item:{id}:run:{run}` exists.
  * Assert Redis `LLEN hnfm:item:{id}:runs` increased and `LRANGE` contains the run.
  * Assert file `outputs/hn/item/{id}/runs/{run}/processed.json` exists.

* **`test_list_runs_for_item_newest_first`**

  * Seed `hnfm:item:{id}:runs` with LPUSH 2 then 1.
  * Assert `list_runs_for_item(id)` returns `[2,1]`.

* **`test_get_run_roundtrip`**

  * Seed one run JSON; `get_run` returns `ProcessedRun` with matching fields.

## 6.2 Task

* **`test_process_hn_item_run_happy_path`**

  * Seed `hn:item:{id}` with an item containing a `url`.
  * Monkeypatch `scrape_url_firecrawl` → `"RAW TEXT"`.
  * Monkeypatch `summarize_text_v1` → `"SUMMARY"`.
  * Call task directly: `process_hn_item_run(item_id, run=1)`.
  * Assert Redis run key exists and includes `content_raw="RAW TEXT"`, `summary="SUMMARY"`.
  * Assert run is LPUSHed.

* **`test_process_hn_item_run_missing_item_raises`**

  * No `hn:item:{id}` in Redis.
  * Expect exception; assert no run key written, no LPUSH.

* **`test_process_hn_item_run_missing_url_raises`**

  * Seed item without `url`.
  * Expect exception; assert no run key written, no LPUSH.

## 6.3 API

* **`test_create_and_queue_run`**

  * Monkeypatch `process_hn_item_run.apply_async` to capture args.
  * POST `/api/hn/items/{id}/runs`.
  * Assert response contains `"status":"queued"` and a positive `"run"`.
  * Assert `apply_async` called once with `[id, run]`.

* **`test_list_runs_endpoint`**

  * Seed two run keys and LPUSH runs `[2,1]`.
  * GET `/api/hn/items/{id}/runs`.
  * Assert order `[2,1]`; summaries present.

* **`test_get_single_run_endpoint_200_and_404`**

  * GET existing run → 200 with full `ProcessedRun`.
  * GET non-existing → 404.

---

# 7) Frontend

## 7.1 Item detail page `/hn/items/[id]`

* Add a **Runs** section beneath the existing item fields.
* On server-side, fetch `GET /api/hn/items/{id}/runs?offset=0&limit=20`.
* Render a list (newest first). Each row shows:

  * **Run ID** (e.g., `1`)
  * **Summary** (show first \~200 chars; add “…”, no client options)
  * Link to `/hn/item/{id}/run/{run}`
* Add a button **“Start New Run”** that `POST`s `/api/hn/items/{id}/runs`, then refreshes the runs list.

## 7.2 Run detail page `/hn/item/[id]/run/[run]`

* On server-side, fetch:

  * `GET /api/hn/items/{id}` (basic item info)
  * `GET /api/hn/items/{id}/runs/{run}` (full `ProcessedRun`)
* Render:

  * Item title + link to the original URL.
  * Three collapsible accordions (open/close):

    1. **Raw scraped** → `content_raw`
    2. **Cleaned** → `content_clean`
    3. **Summary** → `summary`
* Add a back link to `/hn/items/{id}`.

---

# 8) Endpoint + storage behavior (confirmation)

* `POST /api/hn/items/{item_id}/runs`:

  * Creates **one** new run id with `INCR`.
  * Enqueues **one** Celery task using `apply_async(args=[item_id, run])`.
* Task:

  * Reads `hn:item:{item_id}`, scrapes, cleans, summarizes.
  * Writes **one** Redis key: `hnfm:item:{item_id}:run:{run}`.
  * LPUSHes `run` into `hnfm:item:{item_id}:runs`.
  * Writes **one** file: `outputs/hn/item/{item_id}/runs/{run}/processed.json`.
* `GET /api/hn/items/{item_id}/runs` returns newest-first runs with `{run, summary}`.
* `GET /api/hn/items/{item_id}/runs/{run}` returns the full `ProcessedRun`.

---

# 9) Build order (sequential)

1. **Models**: `ProcessedRun`.
2. **Redis keys + disk path conventions** (constant helpers).
3. **Utilities**: `next_run_id`, `scrape_url_firecrawl`, `clean_content`, `summarize_text_v1`, `save_processed_run`, `list_runs_for_item`, `get_run`.
4. **Task**: `process_hn_item_run(item_id, run)`.
5. **API**: POST create/queue run; GET list runs; GET single run.
6. **Tests**: utilities → task → API (fakeredis + monkeypatch for network).
7. **Frontend**: update `/hn/items/[id]` to show runs; add `/hn/item/[id]/run/[run]` detail view with accordions.

This completes the “runs v1”: scrape → clean → summarize → store → list → view.

---

Here is the **single, focused plan** to add **Segments** (script-only v1) tied to a specific run. Follow these steps in order.



# 1) Data model

```python
from pydantic import BaseModel
from datetime import datetime

class Segment(BaseModel):
    key: str                      # "hnfm:seg:{item_id}:{run}:{seg}"
    item_id: int
    run: int
    seg: int
    created_at: datetime
    processed_run_key: str        # "hnfm:item:{item_id}:run:{run}"
    script: str                   # full script text (generated by LLM)
```

---

# 2) Redis keys and disk paths

**Redis (strings + list + counter):**

* Per-segment JSON: `hnfm:seg:{item_id}:{run}:{seg}` → serialized `Segment`
* Per-run segment sequence: `hnfm:seg:seq:{item_id}:{run}` (INCR → 1,2,3,…)
* Per-run segment list (newest-first): `hnfm:seg:list:{item_id}:{run}` (LPUSH seg id as string)

**Disk (mirror the keys):**

```
outputs/hn/item/{item_id}/runs/{run}/segments/{seg}/segment.json
```

---

# 3) Utility helpers

Implement these **synchronous** helpers. Create parent dirs before writing files.

```python
def k_seg(item_id: int, run: int, seg: int) -> str:
    return f"hnfm:seg:{item_id}:{run}:{seg}"

def k_seg_seq(item_id: int, run: int) -> str:
    return f"hnfm:seg:seq:{item_id}:{run}"

def k_seg_list(item_id: int, run: int) -> str:
    return f"hnfm:seg:list:{item_id}:{run}"

def seg_dir(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}"
```

### 3.1 Next segment id (atomic)

```python
def next_seg_id(item_id: int, run: int, *, redis_client) -> int:
    return int(redis_client.incr(k_seg_seq(item_id, run)))
```

### 3.2 Generate script (LLM call wrapper) (there may be some existing prompts for generating the script, so please reference that)

* This should use a system prompt and the system prompt should have "Reasoning: high" included to set the reasoning level.
* Please see the `script_generator.py` for complete instructions on what to include for the srcipt.
* I'll add more detailed prompt instructions later, and we will test different versions of the script prompt.

```python
def generate_script_v1(content_clean: str, summary: str) -> str:
    """
    POST to your LLM endpoint.
    Prompt template:
    'Write a concise, energetic script that explains the article clearly.
     Use 2-4 short paragraphs. Avoid fluff. Base it on this cleaned text and summary.
     Cleaned:\n{content_clean}\n\nSummary:\n{summary}'
    Return raw string.
    Raise on non-200 or empty body.
    """
```

### 3.3 Save / get / list / delete

```python
def save_segment(seg_obj: Segment, *, redis_client, outputs_root: str) -> None:
    # SET Redis JSON
    redis_client.set(k_seg(seg_obj.item_id, seg_obj.run, seg_obj.seg), seg_obj.model_dump_json())
    # LPUSH seg id to per-run list
    redis_client.lpush(k_seg_list(seg_obj.item_id, seg_obj.run), str(seg_obj.seg))
    # Write to disk
    d = seg_dir(outputs_root, seg_obj.item_id, seg_obj.run, seg_obj.seg)
    # mkdir -p d
    # write d/segment.json with seg_obj JSON
```

```python
def get_segment(item_id: int, run: int, seg: int, *, redis_client) -> Segment | None:
    # GET hnfm:seg:{item_id}:{run}:{seg}; parse to Segment or return None
```

```python
def list_segments_for_run(item_id: int, run: int, *, redis_client, offset: int = 0, limit: int = 20) -> list[int]:
    # LRANGE k_seg_list(..., ..., ...) offset offset+limit-1
    # cast each to int, return newest-first
```

```python
def delete_segment(item_id: int, run: int, seg: int, *, redis_client, outputs_root: str) -> bool:
    """
    - DEL hnfm:seg:{item_id}:{run}:{seg}
    - LREM k_seg_list(...): remove all occurrences of str(seg)
    - rmtree outputs/hn/item/{item_id}/runs/{run}/segments/{seg}
    - return True if a segment key was deleted, else False
    """
```

---

# 4) Celery task

Single task that generates everything for a segment (v1 = script only).

```python
def generate_segment(item_id: int, run: int, seg: int) -> dict:
    """
    1) Load ProcessedRun from Redis: GET "hnfm:item:{item_id}:run:{run}".
       - If missing → raise.
    2) Extract content_clean and summary.
       - If missing/empty → raise.
    3) script = generate_script_v1(content_clean, summary)
    4) Build Segment(
         key=k_seg(...),
         item_id=item_id, run=run, seg=seg,
         created_at=utcnow(),
         processed_run_key=f"hnfm:item:{item_id}:run:{run}",
         script=script
       )
    5) save_segment(...)
    6) return {"status":"ok","item_id":item_id,"run":run,"seg":seg}
    """
```

Enqueue with `apply_async(args=[item_id, run, seg])`.

---

# 5) API (FastAPI)

All endpoints synchronous. Use your existing Redis client dependency. No query options beyond offset/limit where specified.

## 5.1 Create + queue a segment

* **Route:** `POST /api/hn/items/{item_id}/runs/{run}/segments`
* **Flow:**

  1. `seg = next_seg_id(item_id, run, redis_client=...)`
  2. `generate_segment.apply_async(args=[item_id, run, seg])`
  3. Return:

     ```json
     {"status":"queued","item_id":45114175,"run":1,"seg":1}
     ```

## 5.2 List segments for a run (newest-first)

* **Route:** `GET /api/hn/items/{item_id}/runs/{run}/segments?offset=0&limit=20`
* **Flow:**

  * `seg_ids = list_segments_for_run(...)`
  * For each seg id, `get_segment(...)` and return `{seg, script_preview}` where `script_preview` is the first 200 chars.
* **Response:**

  ```json
  {
    "item_id": 45114175,
    "run": 1,
    "segments": [
      {"seg": 2, "script_preview": "First 200 chars..."},
      {"seg": 1, "script_preview": "First 200 chars..."}
    ],
    "pagination": {"offset":0,"limit":20,"count":2}
  }
  ```

## 5.3 Get a single segment

* **Route:** `GET /api/hn/items/{item_id}/runs/{run}/segments/{seg}`
* **Flow:** `get_segment(...)` → return full `Segment` or 404 `{ "detail": "Segment not found" }`.

## 5.4 Delete a single segment

* **Route:** `DELETE /api/hn/items/{item_id}/runs/{run}/segments/{seg}`
* **Flow:** `ok = delete_segment(...)`

  * If `ok` → `{"status":"deleted","item_id":...,"run":...,"seg":...}`
  * Else 404.

---

# 6) Tests (pytest)

Use **fakeredis-py** for Redis. Monkeypatch the LLM call `generate_script_v1` to a deterministic string. Do not perform real HTTP.

## 6.1 Utilities

* **`test_next_seg_id_increments`**

  * First call returns 1, second returns 2 for same item/run.
* **`test_save_and_get_segment_roundtrip`**

  * Build a `Segment`, save, then get; verify equality and disk file exists at `.../segment.json`.
* **`test_list_segments_for_run_newest_first`**

  * LPUSH seg ids `[3,2,1]`; assert list\_segments returns `[3,2,1]`.
* **`test_delete_segment_removes_everything`**

  * Save a segment + create its folder + file.
  * Call delete; assert Redis key gone, LREM happened, and folder removed.

## 6.2 Task

* **`test_generate_segment_happy_path`**

  * Seed `hnfm:item:{id}:run:{run}` with a valid ProcessedRun JSON containing `content_clean` and `summary`.
  * Monkeypatch `generate_script_v1` → `"SCRIPT_TEXT"`.
  * Call task directly `generate_segment(item_id, run, seg=1)`.
  * Assert: segment key exists; JSON has `script="SCRIPT_TEXT"`; disk file exists.

* **`test_generate_segment_missing_run_raises`**

  * No processed run in Redis → expect exception; assert no segment written.

* **`test_generate_segment_empty_fields_raises`**

  * Processed run present but missing `content_clean` or `summary` → expect exception; assert no segment written.

## 6.3 API

* **`test_create_and_queue_segment`**

  * Monkeypatch `generate_segment.apply_async` to capture args.
  * POST `/api/hn/items/{id}/runs/{run}/segments`.
  * Assert response includes `"status":"queued"` and a positive `"seg"`.
  * Assert `apply_async` called with `[id, run, seg]`.

* **`test_list_segments_endpoint`**

  * Seed two segments; GET list; verify order and `script_preview` fields.

* **`test_get_and_delete_segment_endpoints`**

  * GET existing → 200 with full Segment.
  * DELETE existing → 200 with status deleted; subsequent GET → 404.
  * DELETE non-existing → 404.

---

# 7) Frontend

## 7.1 Run detail page `/hn/item/[id]/run/[runId]`

* Add a **Segments** section **below Runs**:

  * Server-side fetch: `GET /api/hn/items/{id}/runs/{runId}/segments?offset=0&limit=20`
  * Render list (newest-first):

    * Row shows **Seg ID** and a 2-line `script_preview`.
    * Link to segment detail: `/hn/item/{id}/run/{runId}/segment/{segId}`

* Add **“Start New Segment”** button:

  * `POST /api/hn/items/{id}/runs/{runId}/segments` then refetch segments list.

## 7.2 Segment detail page `/hn/item/[id]/run/[runId]/segment/[segId]`

* Create file: `pages/hn/item/run/[runId]/segment/[segId].vue`

  * **Do not** create nested folders to avoid route conflicts.

* Server-side fetch:

  * `GET /api/hn/items/{id}` (basic item info)
  * `GET /api/hn/items/{id}/runs/{runId}/segments/{segId}` (full Segment)

* Render:

  * Header with item title and external link.
  * Accordions:

    1. **Script** (full text)  ← open by default
  * Footer button **Delete Segment**:

    * `DELETE /api/hn/items/{id}/runs/{runId}/segments/{segId}`
    * On success, navigate back to `/hn/item/{id}/run-{runId}` and refresh the segments list.

* Add route param validation (numeric) like you did for the run page.

---

# 8) Build order

1. **Model**: `Segment`.
2. **Keys/paths helpers**.
3. **Utils**: `next_seg_id`, `generate_script_v1`, `save_segment`, `get_segment`, `list_segments_for_run`, `delete_segment`.
4. **Task**: `generate_segment(item_id, run, seg)`.
5. **API**: POST create/queue; GET list; GET one; DELETE one.
6. **Tests**: utils → task → API (fakeredis + monkeypatch LLM).
7. **Frontend**: update run page with Segments list + “Start New Segment”; add segment detail page with accordion + delete.

This adds the **Segment** layer cleanly: you can create, view, list, and delete segments per run, with all data saved in Redis and mirrored to disk.

---

Here’s a **single, unambiguous plan** to add **TTS sections** to a Segment (script-only v1 → narration). It covers models, Redis keys, disk layout, utilities, one Celery task that loops internally, API, tests, and frontend updates.

---

# 1) Data models

### 1.1 Update `Segment` (add audio fields)

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Segment(BaseModel):
    key: str                      # "hnfm:seg:{item_id}:{run}:{seg}"
    item_id: int
    run: int
    seg: int
    created_at: datetime
    processed_run_key: str        # "hnfm:item:{item_id}:run:{run}"
    script: str

    # NEW (audio status)
    sections_total: int = 0
    audio_combined_path: Optional[str] = None  # outputs/.../audio/segment.wav
    audio_ready: bool = False                  # True after stitching succeeds
```

### 1.2 Section metadata

```python
class SegmentSection(BaseModel):
    key: str                      # "hnfm:seg:{item_id}:{run}:{seg}:sec:{section}"
    item_id: int
    run: int
    seg: int
    section: int                  # 1-based
    text: str                     # the exact text used for TTS
    audio_path: Optional[str]     # outputs/.../audio/sections/{section}/audio.wav
    cleaned: bool                 # True if sent through studio-voice
    duration_ms: Optional[int]    # total duration in milliseconds
    created_at: datetime
    updated_at: datetime
```

---

# 2) Redis keys and disk paths

### 2.1 Redis

* **Per-section JSON**: `hnfm:seg:{item_id}:{run}:{seg}:sec:{section}` → serialized `SegmentSection`
* **Per-segment section list** (ordered): `hnfm:seg:{item_id}:{run}:{seg}:sec:list`

  * Use `RPUSH` section numbers as strings **in ascending order** (1..N).
  * Retrieve with `LRANGE` to preserve order.

*(Segment JSON remains at `hnfm:seg:{item_id}:{run}:{seg}` and now includes audio fields.)*

### 2.2 Disk

```
outputs/hn/item/{item_id}/runs/{run}/segments/{seg}/
  segment.json
  audio/
    sections/
      {section}/
        audio.wav           # final (cleaned) audio; overwrite on regen
        meta.json           # serialized SegmentSection
    segment.wav             # stitched combined audio
```

---

# 3) Utilities (synchronous helpers)

Create parent directories before writing any files. On any error, raise and do not write partial metadata.

### 3.1 Key/path helpers

```python
def k_seg(item_id:int, run:int, seg:int) -> str: ...
def k_sec(item_id:int, run:int, seg:int, section:int) -> str:
    return f"hnfm:seg:{item_id}:{run}:{seg}:sec:{section}"
def k_sec_list(item_id:int, run:int, seg:int) -> str:
    return f"hnfm:seg:{item_id}:{run}:{seg}:sec:list"

def seg_root(outputs_root:str, item_id:int, run:int, seg:int) -> str: ...
def sec_dir(outputs_root:str, item_id:int, run:int, seg:int, section:int) -> str:
    return f"{seg_root(outputs_root,item_id,run,seg)}/audio/sections/{section}"
def sec_audio_path(outputs_root:str, item_id:int, run:int, seg:int, section:int) -> str:
    return f"{sec_dir(outputs_root,item_id,run,seg,section)}/audio.wav"
def sec_meta_path(outputs_root:str, item_id:int, run:int, seg:int, section:int) -> str:
    return f"{sec_dir(outputs_root,item_id,run,seg,section)}/meta.json"
def combined_audio_path(outputs_root:str, item_id:int, run:int, seg:int) -> str:
    return f"{seg_root(outputs_root,item_id,run,seg)}/audio/segment.wav"
```

### 3.2 Split script into sections (two lines at a time)

```python
def split_script_into_sections(script: str) -> list[str]:
    """
    - Split by '\n'
    - Trim each line
    - Drop empty lines
    - Group consecutive non-empty lines into chunks of size 2 (last chunk may be size 1)
    - For each chunk, join with '\n' (keep newline between the two lines)
    - Return list[str] in order (indexes become sections 1..N)
    """
```

### 3.3 TTS synthesis (returns path and duration)

```python
def tts_synthesize_to_wav(text: str, out_path: str) -> int:
    """
    - Call your TTS service with `text`.
    - Write resulting WAV bytes to `out_path`.
    - Return duration in milliseconds (compute via 'wave' or similar).
    """
```

### 3.4 Studio-voice cleaning (in-place replace)

```python
def studio_voice_clean_inplace(wav_path: str) -> None:
    """
    - Send `wav_path` to studio-voice service and get cleaned audio back.
    - Overwrite `wav_path` with cleaned audio.
    """
```

### 3.5 Section save/load/list

```python
def save_section_meta(meta: SegmentSection, *, redis_client, outputs_root:str) -> None:
    # SET k_sec(...): JSON(meta)
    # Ensure sec_dir exists
    # Write meta.json to sec_meta_path(...)

def get_section_meta(item_id:int, run:int, seg:int, section:int, *, redis_client) -> SegmentSection | None:
    # GET k_sec(...), parse or None

def list_section_numbers(item_id:int, run:int, seg:int, *, redis_client) -> list[int]:
    # LRANGE k_sec_list(...) 0 -1 -> [ "1", "2", ... ] -> [1,2,...]
```

### 3.6 Stitch sections into one WAV

```python
def stitch_sections_to_wav(section_paths: list[str], out_path: str) -> int:
    """
    - Concatenate all `section_paths` in order into `out_path` (16-bit PCM WAV).
    - Return total duration in ms.
    """
```

### 3.7 Segment audio status update

```python
def update_segment_audio_status(item_id:int, run:int, seg:int, sections_total:int,
                                combined_path:str, ready:bool, *, redis_client) -> None:
    """
    - Load Segment JSON, update fields:
        sections_total, audio_combined_path=combined_path, audio_ready=ready
    - SET Segment back to Redis
    - Overwrite segment.json on disk
    """
```

---

# 4) Celery task (single task; loops internally)

We keep **one** task that either builds **all sections** or **one** specific section, then stitches.

```python
def build_segment_audio(item_id:int, run:int, seg:int, mode:str="all", section:int|None=None, text_override:str|None=None) -> dict:
    """
    1) Load Segment (must exist) and its script.
    2) If mode == "all":
         a) sections_text = split_script_into_sections(segment.script)
         b) For idx, text in enumerate(sections_text, start=1):
               ensure 'idx' is appended to k_sec_list with RPUSH (only once; if already present, skip RPUSH)
               out_wav = sec_audio_path(...)
               duration = tts_synthesize_to_wav(text, out_wav)
               studio_voice_clean_inplace(out_wav)
               meta = SegmentSection(..., text=text, audio_path=out_wav, cleaned=True, duration_ms=duration)
               save_section_meta(meta)
         c) paths = [sec_audio_path(..., section=s) for s in list_section_numbers(...)]
         d) total_ms = stitch_sections_to_wav(paths, combined_audio_path(...))
         e) update_segment_audio_status(..., sections_total=len(paths), combined_path=..., ready=True)
         f) return {"status":"ok","item_id":item_id,"run":run,"seg":seg,"sections":len(paths)}

       If mode == "one":
         a) Require `section` int.
         b) If text_override is None: load existing meta and use meta.text; else use text_override.
         c) out_wav = sec_audio_path(...)
         d) duration = tts_synthesize_to_wav(text, out_wav)
         e) studio_voice_clean_inplace(out_wav)
         f) meta = SegmentSection(..., text=text, audio_path=out_wav, cleaned=True, duration_ms=duration, updated_at=now)
         g) save_section_meta(meta)
         h) paths = [sec_audio_path(..., s) for s in list_section_numbers(...)]
         i) total_ms = stitch_sections_to_wav(paths, combined_audio_path(...))
         j) update_segment_audio_status(..., sections_total=len(paths), combined_path=..., ready=True)
         k) return {"status":"ok","item_id":item_id,"run":run,"seg":seg,"section":section}
    """
```

* Enqueue with `apply_async(args=[item_id, run, seg], kwargs={"mode":"all"})` to build all.
* Enqueue with `apply_async(args=[item_id, run, seg], kwargs={"mode":"one","section":N,"text_override":...})` to regenerate one.

---

# 5) API (FastAPI)

All endpoints are synchronous and enqueue the single task above.

### 5.1 Build or rebuild **all** sections and combined audio

* **POST** `/api/hn/items/{item_id}/runs/{run}/segments/{seg}/audio`
* **Body:** none.
* **Action:** `build_segment_audio.apply_async(args=[item_id, run, seg], kwargs={"mode":"all"})`
* **Response:** `{"status":"queued","item_id":...,"run":...,"seg":...,"mode":"all"}`

### 5.2 Regenerate **one** section (optionally with new text)

* **POST** `/api/hn/items/{item_id}/runs/{run}/segments/{seg}/sections/{section}/audio`
* **Body (optional):** `{ "text": "new text" }`
* **Action:**

  * If body has `text`, pass as `text_override`.
  * `build_segment_audio.apply_async(args=[item_id, run, seg], kwargs={"mode":"one","section":section,"text_override":text_or_None})`
* **Response:** `{"status":"queued","item_id":...,"run":...,"seg":...,"section":section,"mode":"one"}`

### 5.3 List sections with metadata

* **GET** `/api/hn/items/{item_id}/runs/{run}/segments/{seg}/sections`
* **Response:**

```json
{
  "item_id": 45114175,
  "run": 1,
  "seg": 1,
  "sections": [
    {
      "section": 1,
      "text": "line1\nline2",
      "audio_path": "/abs/.../audio/sections/1/audio.wav",
      "cleaned": true,
      "duration_ms": 4321
    },
    ...
  ]
}
```

*(Load numbers via LRANGE, then GET each section’s JSON.)*

---

# 6) Tests (pytest)

Use **fakeredis-py**. Monkeypatch `tts_synthesize_to_wav`, `studio_voice_clean_inplace`, and `stitch_sections_to_wav` to deterministic behaviors. Do not perform real audio work.

### 6.1 Utilities

* **`test_split_script_into_sections_pairs_and_last_single`**

  * Provide 5 non-empty lines; expect sections: 3 chunks (2,2,1).
* **`test_save_get_list_section_meta_roundtrip`**

  * Save a section meta; GET returns equal; LRANGE yields `[1]`; meta.json exists.

### 6.2 Task – build all

* **`test_build_segment_audio_all_happy_path`**

  * Seed a Segment with a script of 3 non-empty lines (→ 2 sections).
  * Monkeypatch:

    * `tts_synthesize_to_wav` → write dummy file and return fixed durations \[1000, 2000].
    * `studio_voice_clean_inplace` → no-op.
    * `stitch_sections_to_wav` → create combined file and return 3000.
  * Call task directly with `mode="all"`.
  * Assert:

    * LRANGE sec\:list → `["1","2"]`
    * Each section key exists; `cleaned=True`; durations set.
    * Segment updated: `sections_total=2`, `audio_ready=True`, and `audio_combined_path` exists on disk.

### 6.3 Task – regenerate one section (with text override)

* **`test_build_segment_audio_one_replaces_section_and_restitches`**

  * Pre-seed two sections’ metas and files.
  * Call task with `mode="one", section=2, text_override="NEW TEXT"`.
  * Assert section 2 meta has `text == "NEW TEXT"` and duration updated.
  * Assert combined audio file exists (re-stitched).

### 6.4 API

* **`test_post_audio_all_queues_task`**

  * Monkeypatch `.apply_async` capture args.
  * POST `/api/.../audio` → response queued; kwargs `mode="all"`.
* **`test_post_audio_one_section_queues_task`**

  * POST `/api/.../sections/2/audio` with body `{ "text": "X" }` → kwargs include `section=2`, `text_override="X"`.
* **`test_get_sections_lists_in_order`**

  * Seed LRANGE as `["1","2"]` and metas; GET returns two entries in order.

---

# 7) Frontend (Nuxt)

### 7.1 Segment detail page: `/hn/item/[id]/run-[runId]-seg-[segId]`

Add a **Narration** section under Script.

* **Server-side fetches:**

  * Already fetches Segment (includes `audio_ready`, `sections_total`, `audio_combined_path`).
  * Fetch sections list: `GET /api/hn/items/{id}/runs/{runId}/segments/{segId}/sections`.

* **UI layout (below Script accordion):**

  1. **Accordion: “Narration Sections” (open by default)**

     * Top-right buttons:

       * **Build All** → `POST /api/.../segments/{segId}/audio`, then refetch sections and segment.
     * For each section (ordered 1..N):

       * Show **Section {n}**
       * `<textarea>` bound to section `text`
       * **Regenerate** button:

         * If text changed, send `{text: <edited>}`; else send no body.
         * POST `/api/.../sections/{n}/audio`
         * On success, refetch sections + segment.
       * **Audio player** using `audio_path` (serve statically from your `/public` or a file-serving endpoint).
       * **Duration** label in seconds (duration\_ms / 1000).
       * **Cleaned** badge if `cleaned` is true.
  2. **Accordion: “Combined Audio”**

     * If `segment.audio_ready` is true:

       * Show **audio player** for `audio_combined_path`.
     * Else show “Not built yet.”

* **Route validation**: keep numeric checks for `id`, `runId`, `segId`.

---

# 8) Build order (sequential)

1. **Model updates**: add audio fields to `Segment`; add `SegmentSection`.
2. **Key/Path helpers** (3.1).
3. **Utilities**: `split_script_into_sections`, `tts_synthesize_to_wav`, `studio_voice_clean_inplace`, section save/get/list, `stitch_sections_to_wav`, `update_segment_audio_status`.
4. **Task**: `build_segment_audio` (modes “all” and “one”).
5. **API**:

   * POST build-all
   * POST regenerate-one
   * GET list sections
6. **Tests**: utilities → task (all / one) → API.
7. **Frontend**: segment page “Narration Sections” accordion + buttons, audio players, combined audio accordion.

This keeps everything **simple and overwrite-friendly**, guarantees **sequential order**, and gives you a clean UI to generate, audit, and redo any section quickly.

---

Here’s a **small, clean, no-ambiguity** addition to integrate **ASR** at the end of your existing `build_segment_audio` task, plus one tiny API and a small frontend change.

---

# 1) Data model change

**Update `Segment`** (script + audio already exist):

```python
class Segment(BaseModel):
    key: str
    item_id: int
    run: int
    seg: int
    created_at: datetime
    processed_run_key: str
    script: str

    sections_total: int = 0
    audio_combined_path: Optional[str] = None
    audio_ready: bool = False

    # NEW: store the ASR JSON file path when available
    asr_json_path: Optional[str] = None
```

No other models change.

---

# 2) Paths and helpers

**Add a single path helper for ASR JSON:**

```python
def asr_json_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    # Keep it simple; store next to combined audio
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}/audio/asr.json"
```

**Add a tiny file helper:**

```python
def write_json(path: str, data: dict) -> None:
    # mkdir -p parent
    # write pretty-printed UTF-8 JSON
```

**Update your existing “save Segment to disk” helper** (whatever you called it) so whenever you modify a `Segment` object (e.g., set `asr_json_path`), you also overwrite `segment.json` on disk and `SET` the Redis key again.

---

# 3) Task change (build\_segment\_audio)

Add the **final ASR step** at the end of the successful “all” and “one” flows. The logic is identical in both cases and runs **after** `audio_combined_path` has been created and `audio_ready` set to `True`.

You already have a comment:

```python
# do ASR processing here!
```

Replace that comment with this logic:

```python
# 1) Preconditions
combined = combined_audio_path(outputs_root, item_id, run, seg)
if not os.path.exists(combined):
    # No combined audio → nothing to do (leave segment.asr_json_path = None)
    return result_dict  # whatever you currently return from the task

# 2) Run ASR
try:
    # Use your existing service classes. Example signatures—adjust to your code.
    asr_service = ASRService()             # existing class
    asr_result: dict = asr_service.transcribe_file(combined)  # returns JSON-serializable dict

    # 3) Persist ASR JSON
    asr_path = asr_json_path(outputs_root, item_id, run, seg)
    write_json(asr_path, asr_result)

    # 4) Update Segment (path only; keep it simple)
    seg_obj = get_segment(item_id, run, seg, redis_client=redis)  # your existing getter
    seg_obj.asr_json_path = asr_path
    save_segment(seg_obj, redis_client=redis, outputs_root=outputs_root)

    # 5) Optionally return a flag (not required)
    result_dict["asr"] = "ok"
except Exception as e:
    # Fail ASR silently: keep task success, frontend will show "not ready" gracefully
    # Log the error if you have logging
    result_dict["asr"] = "error"
```

**Notes**

* Do **not** fail the whole task if ASR fails. Just skip and leave `asr_json_path` as `None`.
* If you also use `AudioProcessor`, you can keep using it internally (e.g., to normalize audio before ASR). Not required here.

---

# 4) API (one small read-only endpoint)

**GET ASR JSON for a segment**

* **Route:** `GET /api/hn/items/{item_id}/runs/{run}/segments/{seg}/asr`
* **Behavior:**

  1. Load `Segment` from Redis.
  2. If `segment.asr_json_path` is missing or the file doesn’t exist → return `404 { "detail": "ASR not ready" }`.
  3. Read the JSON file and return it as:

     ```json
     { "item_id": 45114175, "run": 1, "seg": 1, "asr": { /* raw ASR JSON */ } }
     ```

No POST/DELETE endpoints for ASR now. The ASR runs inside `build_segment_audio`.

---

# 5) Frontend changes (segment detail page)

**Page:** `/hn/item/[id]/run-[runId]-seg-[segId]`

1. Below the **Combined Audio** accordion, add a new accordion **“ASR (Word Timestamps)”**.
2. On server side (or client side if you prefer), **fetch**:

   * `GET /api/hn/items/{id}/runs/{runId}/segments/{segId}` (you already do)
   * `GET /api/hn/items/{id}/runs/{runId}/segments/{segId}/asr`
3. Render logic:

   * If the ASR endpoint returns **200**:

     * Show a small toolbar with a **Refresh** button (re-calls the ASR endpoint).
     * Pretty-print JSON (collapsed by default is fine; or a `<pre>` block).
   * If the ASR endpoint returns **404**:

     * Show a gray “ASR not ready yet” message.
     * Show a **Refresh** button to retry.

**Minimal template sketch (pseudocode):**

```vue
<details class="mb-3">
  <summary>ASR (Word Timestamps)</summary>

  <div class="mb-2">
    <button @click="refreshAsr">Refresh</button>
  </div>

  <div v-if="asrData">
    <pre>{{ JSON.stringify(asrData.asr, null, 2) }}</pre>
  </div>
  <div v-else class="text-gray-500">
    ASR not ready yet.
  </div>
</details>
```

**Data fetch:**

```ts
const { data: asrData, refresh: refreshAsr } = await useFetch(
  `/api/hn/items/${id}/runs/${runId}/segments/${segId}/asr`,
  { key: `asr-${id}-${runId}-${segId}`, server: true }
).catch(() => ({ data: null }))
```

Handle 404 by returning `null` in a `try/catch` or `onResponseError`.

---

# 6) Build order

1. **Model**: add `asr_json_path` to `Segment`.
2. **Paths**: add `asr_json_path(...)` helper + `write_json(...)`.
3. **Task**: add ASR block at the end of `build_segment_audio` (both “all” and “one” flows).
4. **API**: implement `GET /api/hn/items/{item_id}/runs/{run}/segments/{seg}/asr`.
5. **Frontend**: add “ASR (Word Timestamps)” accordion under Combined Audio with fetch + refresh.

---

# 7) Acceptance checklist

* [ ] After `build_segment_audio` completes (successfully stitching audio), ASR runs and writes `audio/asr.json`.
* [ ] `Segment.asr_json_path` is set and persisted to Redis and `segment.json`.
* [ ] `GET /api/.../asr` returns 200 with JSON when available; 404 if not ready.
* [ ] Segment detail page shows an **ASR** accordion; displays JSON or “not ready yet,” with a working **Refresh** button.

This keeps the change **tiny** and **predictable**, leverages your existing task, and makes the ASR output available immediately for future steps (subtitle generation, alignment views, etc.).