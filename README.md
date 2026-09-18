# what-plane

Small local HTTP service that returns the nearest aircraft to a configured observer location using [ADS-B Exchange](https://globe.adsbexchange.com/) binCraft data.

Designed to sit between Home Assistant and Google Home:

```
Google Home routine → HA script → what-plane /nearest → TTS response
```

## Quick start

### Docker

Set your observer location in `docker-compose.yml`, then:

```bash
docker compose up --build
curl "http://localhost:1320/nearest"
```

### Local development (uv)

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
OBSERVER_LAT=-41.29 OBSERVER_LNG=174.78 AIRCRAFT_DB_PREFIXES=ZK \
  uv run uvicorn what_plane.main:app --reload --host 0.0.0.0 --port 1320
curl "http://localhost:1320/nearest"
```

## API

### `GET /nearest`

Returns the nearest aircraft to the configured observer location. There are no query parameters; set your site once via environment variables.

Example response:

```json
{
  "found": true,
  "flight": "ZKNAX",
  "registration": "ZK-NAX",
  "type": "C172",
  "type_name": "Cessna 172 Skyhawk",
  "altitude_ft": 1200,
  "distance_km": 3.2,
  "direction": "south-west",
  "summary": "ZKNAX, a Cessna 172 Skyhawk, at 1,200 feet, 3.2 kilometres to the south-west"
}
```

### `GET /health`

Service status and last fetch metadata.

## Home Assistant

```yaml
rest_command:
  what_plane_is_that:
    url: "http://what-plane:1320/nearest"
    method: GET
    timeout: 15

script:
  what_plane_is_that:
    sequence:
      - action: rest_command.what_plane_is_that
        response_variable: plane
      - action: tts.google_translate_say
        target:
          entity_id: media_player.kitchen_speaker
        data:
          message: "{{ plane.summary }}"
```

Expose the script to Google Assistant, then create a Google Home routine that activates it when you say "what plane is that".

## Configuration

| Environment variable | Default |
|---------------------|---------|
| `OBSERVER_LAT` | required |
| `OBSERVER_LNG` | required |
| `NEAREST_RADIUS_KM` | `15` |
| `NEAREST_MAX_ALT_FT` | `15000` |
| `NEAREST_MAX_SEEN_POS_S` | `20` |
| `CACHE_TTL_SECONDS` | `8` |
| `ADSBEXCHANGE_API_URL` | `https://globe.adsbexchange.com/re-api/` |
| `ADSBEXCHANGE_REFERER` | `https://globe.adsbexchange.com/` |
| `HOST` | `0.0.0.0` |
| `PORT` | `1320` |
| `AIRCRAFT_DB_ENABLED` | `true` |
| `AIRCRAFT_DB_PREFIXES` | `ZK` |
| `AIRCRAFT_DB_CACHE_DIR` | `.cache/what-plane` (Docker: `/var/cache/what-plane`) |
| `AIRCRAFT_DB_SOURCE_URL` | tar1090 `aircraft.csv.gz` URL |
| `AIRCRAFT_DB_PATH` | unset (uses fetched cache) |

On startup, what-plane downloads the [tar1090 aircraft database](https://github.com/wiedehopf/tar1090-db), filters it to the comma-separated registration prefixes in `AIRCRAFT_DB_PREFIXES`, and caches the result under `AIRCRAFT_DB_CACHE_DIR`. Docker Compose mounts a volume there so the slice is reused across restarts. Change the prefixes and restart to rebuild the cache.

Example:

```yaml
environment:
  AIRCRAFT_DB_PREFIXES: "ZK,VH"
```

Build a local cache without running the server:

```bash
uv run python scripts/build_aircraft_db_slice.py --prefixes ZK,VH
```

## Development

```bash
uv sync --all-groups
uv run ruff check .
uv run ruff format .
uv run pyright
uv run pytest
```

CI runs linting, formatting, type checking, tests, and a Docker build on every push and pull request. Dependabot opens weekly update PRs for Python, GitHub Actions, and Docker dependencies.

### Commits and releases

Use [Conventional Commits](https://www.conventionalcommits.org/) for every commit merged to `main`. Release-please reads these messages to decide version bumps and generate the changelog.

Format:

```text
<type>(<optional scope>): <short description>
```

Common types:

| Type | When to use | Version bump |
|------|-------------|--------------|
| `feat` | New behaviour or API changes | minor |
| `fix` | Bug fixes | patch |
| `perf` | Performance improvements | patch |
| `docs` | Documentation only | none |
| `chore` | Tooling, deps, CI | none |
| `refactor` | Code changes without behaviour change | none |
| `test` | Test-only changes | none |

Examples:

```text
feat: add aircraft type name lookup from tar1090 db
fix: ignore stale positions older than max_seen_pos_s
chore: bump fastapi to 0.115.6
```

Breaking changes append `!` after the type or add a `BREAKING CHANGE:` footer in the commit body:

```text
feat!: remove lat/lng query parameters from /nearest
```

Releases are automated with [release-please](https://github.com/googleapis/release-please). The release workflow runs only after the CI workflow completes successfully on `main`. As conventional commits land on `main`, release-please opens a release PR that bumps `pyproject.toml` and updates the changelog. Merging that PR runs CI again, then creates the GitHub release and tag.

## Notes

- This is a deliberately local service: configure your observer location once, then call `/nearest` with no parameters.
- ADS-B Exchange's re-api is unofficial. The `Referer` header is required.
- ADS-B Exchange responses are cached for 8 seconds (configurable via `CACHE_TTL_SECONDS`) so repeated `/nearest` calls do not hit upstream on every request.
- "Nearest" uses horizontal distance, recent position, and altitude heuristics. It cannot know which aircraft you are pointing at.
- Aircraft type names come from a cached DB slice keyed by hex id. Unknown aircraft fall back to the ICAO type code (for example `C172`).
