# API Reference

All endpoints are served by the FastAPI server running on `http://localhost:8001`.
Interactive Swagger docs are available at `http://localhost:8001/docs` while the server is running.

---

## GET /api/search

Search for Wikipedia article titles matching a query string.

### Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `q` | string | no | `""` | Search query. Returns `[]` when blank. |

### Response

A JSON array of up to 8 title strings.

```json
["Black hole", "Black Holes (film)", "Stellar black hole", "Supermassive black hole"]
```

### Errors

| Status | Meaning |
|--------|---------|
| 200 | Always returned, even on Wikipedia API failure (returns `[]`) |

### Example

```bash
curl "http://localhost:8001/api/search?q=black+hole"
```

---

## GET /api/graph

Build a BFS graph starting from an article and following its links up to `depth` hops.

### Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `title` | string | **yes** | — | Root Wikipedia article title |
| `depth` | integer | no | `1` | Hops to follow. Capped at 3. |

### Response

```json
{
  "nodes": [
    {
      "id": "Black hole",
      "summary": "A black hole is a region of spacetime...",
      "categories": ["Astrophysics", "General relativity"],
      "depth": 0
    },
    {
      "id": "Albert Einstein",
      "summary": "Albert Einstein was a German-born physicist...",
      "categories": ["German physicists"],
      "depth": 1
    }
  ],
  "edges": [
    { "source": "Black hole", "target": "Albert Einstein" }
  ]
}
```

### Errors

| Status | Meaning |
|--------|---------|
| 422 | `title` parameter missing |

### Example

```bash
curl "http://localhost:8001/api/graph?title=Black+hole&depth=2"
```

---

## GET /api/expand

Fetch a single article node and its outgoing links. Used to lazily extend an existing graph without rebuilding it from scratch.

### Query Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `title` | string | **yes** | — | Wikipedia article title to expand |

### Response

```json
{
  "node": {
    "id": "Albert Einstein",
    "summary": "Albert Einstein was a German-born physicist...",
    "categories": ["German physicists", "Nobel laureates in Physics"]
  },
  "links": ["Special relativity", "General relativity", "Photoelectric effect"]
}
```

`links` is limited to 20 entries.

### Errors

| Status | Meaning |
|--------|---------|
| 404 | Article not found on Wikipedia |
| 422 | `title` parameter missing |

### Example

```bash
curl "http://localhost:8001/api/expand?title=Albert+Einstein"
```

---

## GET /api/graphs

List all saved graphs, ordered newest first.

### Query Parameters

None.

### Response

```json
[
  { "id": 3, "name": "Physics web", "root": "Black hole", "depth": 2 },
  { "id": 1, "name": "My first graph", "root": "Nikola Tesla", "depth": 1 }
]
```

The heavy `data` field is omitted from this listing. Use `GET /api/graphs/{id}` to retrieve it.

### Errors

| Status | Meaning |
|--------|---------|
| 200 | Always returned; `[]` if no graphs saved |

### Example

```bash
curl "http://localhost:8001/api/graphs"
```

---

## POST /api/graphs

Save a graph to the database.

### Request Body (JSON)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | **yes** | — | Unique name for this graph. Duplicate names overwrite. |
| `root` | string | **yes** | — | Root article title |
| `depth` | integer | no | `1` | Depth used to build the graph |
| `data` | object | no | `{}` | Full `{nodes, edges}` graph object |

### Response

```json
{ "ok": true }
```

### Errors

| Status | Meaning |
|--------|---------|
| 400 | `name` or `root` is missing or empty |

### Example

```bash
curl -X POST "http://localhost:8001/api/graphs" \
  -H "Content-Type: application/json" \
  -d '{"name": "Physics web", "root": "Black hole", "depth": 2, "data": {"nodes": [], "edges": []}}'
```

---

## GET /api/graphs/{id}

Load a single saved graph by its integer ID.

### Path Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id` | integer | **yes** | The graph's database ID |

### Response

```json
{
  "id": 3,
  "name": "Physics web",
  "root": "Black hole",
  "depth": 2,
  "data": {
    "nodes": [
      { "id": "Black hole", "summary": "...", "categories": ["Astrophysics"], "depth": 0 }
    ],
    "edges": []
  }
}
```

`data` is returned as a parsed JSON object, not a string.

### Errors

| Status | Meaning |
|--------|---------|
| 404 | No graph with this ID exists |

### Example

```bash
curl "http://localhost:8001/api/graphs/3"
```
