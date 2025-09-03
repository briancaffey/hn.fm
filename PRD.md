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
