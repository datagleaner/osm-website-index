"""osm-index-builder entry: one country at a time, filtered, indexed, uploaded to the named KV store with a manifest."""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone

from apify import Actor

from . import build

log = logging.getLogger("osm-index-builder")
STORE = "osm-website-index"


def plan(raw: dict, manifest: dict, now: datetime | None = None) -> list[dict]:
    """What would run, in order: unsupported countries and countries built under 7 days ago are skipped with a reason."""
    now = now or datetime.now(timezone.utc)
    out = []
    for c in dict.fromkeys(str(x).upper() for x in (raw.get("countries") or [])):
        if c not in build.PATHS:
            out.append({"country": c, "action": "skip", "why": "unsupported country"})
            continue
        built = (manifest.get("countries") or {}).get(c, {}).get("builtAt")
        if built and not raw.get("force") and now - datetime.fromisoformat(built) < timedelta(days=7):
            out.append({"country": c, "action": "skip", "why": f"built {built}, under 7 days ago"})
            continue
        out.append({"country": c, "action": "build", "url": build.geofabrik_url(c, raw.get("pbfUrl") if len(raw["countries"]) == 1 else None)})
    return out


async def main():
    async with Actor:
        raw = await Actor.get_input() or {}
        store = await Actor.open_key_value_store(name=raw.get("storeName") or STORE)
        manifest = await store.get_value("manifest.json") or {"countries": {}}
        steps = plan(raw, manifest)
        for s in steps:
            log.info("plan: %s", s)
        if not raw.get("allowDownload"):
            await Actor.set_status_message("dry run: allowDownload is off, nothing downloaded: " + "; ".join(
                f"{s['country']} {s['action']}" for s in steps) if steps else "nothing to do")
            return
        for s in (x for x in steps if x["action"] == "build"):  # sequential: one download at a time
            c = s["country"]
            with tempfile.TemporaryDirectory() as tmp:
                filt, db, gz = (os.path.join(tmp, f) for f in ("f.osm.pbf", "i.sqlite", "i.sqlite.gz"))
                info = build.filter_stream(s["url"], filt)
                rows = build.extract(filt, db, c, {"source": s["url"], "lastModified": info["lastModified"]})
                size = build.gzip_file(db, gz)
                with open(gz, "rb") as f:
                    await store.set_value(f"{c}.sqlite.gz", f.read(), content_type="application/gzip")
            manifest.setdefault("countries", {})[c] = {
                "rows": rows, "gzBytes": size, "source": s["url"], "extractLastModified": info["lastModified"],
                "builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "schema": build.SCHEMA_VERSION,
                "builder": os.environ.get("BUILDER_GIT_SHA", "unknown"),
                "attribution": "Data processed by Geofabrik GmbH and created by OpenStreetMap Contributors; (c) OpenStreetMap contributors, ODbL 1.0, https://www.openstreetmap.org/copyright"}
            await store.set_value("manifest.json", manifest)
            log.info("%s: %d rows, %d bytes gz", c, rows, size)
        await Actor.set_status_message("built: " + ", ".join(s["country"] for s in steps if s["action"] == "build"))
