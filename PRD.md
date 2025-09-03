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
