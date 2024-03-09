# paths
TRACKERS_CONFIG_FILEPATH = "src/config/trackers.json"
SHEETS_CONFIG_FILEPATH = "src/config/sheets.json"
LOGGER_CONFIG_FILEPATH = "src/config/logger.json"

SQLITE_DB_ROOT = "data/sqlite"


# async/sleep config
MAX_ASYNC_WORKER = 45
ASYNC_SLEEP_DELAY = 4

MAX_RETRIES = 10
RETRY_SLEEP_DELAY = 4


# headers config
SHARED_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Content-Type": "application/html",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Mode": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
