"""
Central configuration for Wiki Explorer.
All tuneable values live here so they can be changed in one place.
"""

# Server
SERVER_HOST: str = "127.0.0.1"
SERVER_PORT: int = 8001

# Wikipedia API
WIKI_API_URL: str = "https://en.wikipedia.org/w/api.php"
WIKI_USER_AGENT: str = "WikiExplorer/1.0 (educational project; palakanand912@gmail.com)"
WIKI_TIMEOUT_SECONDS: int = 10
WIKI_SEARCH_TIMEOUT_SECONDS: int = 5
WIKI_SEARCH_LIMIT: int = 8
WIKI_CATEGORIES_LIMIT: int = 10
WIKI_LINKS_LIMIT: int = 50

# Graph construction
GRAPH_MAX_DEPTH: int = 3
GRAPH_MAX_LINKS_PER_NODE: int = 15
GRAPH_EXPAND_MAX_LINKS: int = 20

# Article caching
ARTICLE_SUMMARY_MAX_CHARS: int = 500

# Client
CLIENT_BASE_URL: str = f"http://{SERVER_HOST}:{SERVER_PORT}"
CLIENT_TIMEOUT_SECONDS: int = 30

# Link namespace prefixes to filter out (navigational, not conceptual)
FILTERED_LINK_PREFIXES: tuple[str, ...] = (
    "Wikipedia:",
    "Help:",
    "Template:",
    "Portal:",
    "File:",
    "Category:",
    "Special:",
)
