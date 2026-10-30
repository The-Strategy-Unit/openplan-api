# Dataset caching

Dataset downloads cache for **five minutes** by default, with a **128 MiB budget
per Python worker**. CSV, Parquet, and JSON readers share that budget; workers
and instances keep independent caches.

## Configuration

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `OPENPLAN_CACHE_TTL_SECONDS` | `300` | Lifetime after a download completes |
| `OPENPLAN_CACHE_MAX_BYTES` | `134217728` | Retained download bytes per worker (128 MiB) |

Use non-negative integers; setting either value to `0` disables retention.
Set them in local Functions `Values` ([example](../local.settings.example.json))
or Azure application settings. The [deployment script](../infrastructure/create.sh)
accepts the same optional environment variables and passes them through Bicep.

Invalid values fail before deployment commands or cached reads. Health and
documentation do not read cache settings.

## Freshness

- **Expiry:** starts when a download completes; hits do not extend it. The next
  read after expiry downloads again. Expired bytes are removed on cache access.
- **Catalogues:** provider/TPMA responses and identifier validation follow this
  lifetime, so published changes may take that long to appear.
- **Discovery:** release indexes and manifests bypass the cache. Successful
  discovery responses use `Cache-Control: no-store`.
- **Clearing:** changing either setting clears retained entries on the next
  cached read; restarting a worker also clears its cache. Downloads started
  before a clear cannot repopulate it.

## Limits and concurrency

- **Eviction:** least recently used entries are removed to stay within the byte
  budget and a 1,024-entry limit. Oversized blobs are served without retention.
- **Downloads:** concurrent reads of the same blob share one download, even with
  retention disabled; different blobs download in parallel. Storage failures reach
  all waiting callers and are not cached. Failed refreshes return errors.
- **Isolation:** keys include account, container, and blob name. Only immutable
  bytes are cached; JSON objects and Polars frames are created for each caller.

All blobs are downloaded in full. Active downloads, parsed data, responses, and
cache metadata consume memory beyond the retained-byte budget.
