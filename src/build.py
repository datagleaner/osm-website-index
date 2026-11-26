"""Country extract -> SQLite index. Reads only OpenStreetMap tags (nothing else is mixed in: ODbL condition, B627).

Steps: `filter_stream` pipes the Geofabrik download through `osmium tags-filter` (one download at a time, declared
User-Agent), `extract` reads the filtered file with pyosmium and writes the rows, `finish` gzips the SQLite file."""
from __future__ import annotations

import gzip
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from . import tos_refuse
from .names import compact, core_name, fold, is_directory_domain, registered_domain
from .schema import COLUMNS, DDL, SCHEMA_VERSION

UA = "KeencrestIndexBuilder/0.1 (+https://keencrest.dev; datagleaner@gmail.com)"
GEOFABRIK = "https://download.geofabrik.de/"
PATHS = {
    "US": "north-america/us-latest.osm.pbf", "CA": "north-america/canada-latest.osm.pbf",
    "FR": "europe/france-latest.osm.pbf", "DE": "europe/germany-latest.osm.pbf",
    "GB": "europe/great-britain-latest.osm.pbf", "NL": "europe/netherlands-latest.osm.pbf",
    "AU": "australia-oceania/australia-latest.osm.pbf",
}
WEBSITE_KEYS = ("website", "contact:website", "url")
NAME_KEYS = ("name", "official_name", "alt_name", "short_name", "name:en")
CHAIN_KEYS = ("brand", "brand:wikidata", "operator:wikidata")
CATEGORY_KEYS = ("amenity", "shop", "office", "craft", "tourism", "healthcare")
# free site builders and hosting subdomains: the registered domain is shared by thousands of unrelated businesses
SHARED_HOSTS = ("wixsite.com", "business.site", "weebly.com", "blogspot.com", "wordpress.com", "godaddysites.com",
                "square.site", "myshopify.com", "google.com", "goo.gl", "bit.ly", "webs.com", "jimdofree.com",
                "yolasite.com", "sites.google.com", "carrd.co", "linktr.ee", "wa.me", "booksy.com", "opentable.com")


def filter_cmd() -> list[str]:
    return ["osmium", "tags-filter", "-F", "pbf", "-", *(f"nwr/{k}" for k in WEBSITE_KEYS), "-R", "-O", "-o", "{out}"]


def geofabrik_url(country: str, override: str | None = None) -> str:
    url = override or GEOFABRIK + PATHS[country]
    if urlparse(url).hostname != "download.geofabrik.de":
        raise ValueError("extract URL must be on download.geofabrik.de")
    return url


def filter_stream(url: str, out_path: str, client=None) -> dict:
    """Stream one download through osmium tags-filter; nothing but the filtered file touches the disk. Returns the
    response's Last-Modified (the extract's timestamp)."""
    import httpx
    if tos_refuse.refused(url):
        raise RuntimeError(f"{url} is refused by tos_refuse")
    cmd = [c.replace("{out}", out_path) for c in filter_cmd()]
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(60.0, read=300.0), follow_redirects=True, event_hooks=tos_refuse.httpx_hooks_sync())
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    last = None
    try:
        with client.stream("GET", url, headers={"User-Agent": UA}) as r:
            r.raise_for_status()
            last = r.headers.get("last-modified")
            for chunk in r.iter_bytes(1 << 20):
                proc.stdin.write(chunk)
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(f"osmium tags-filter failed: {err[-300:]}")
    except BaseException:
        proc.kill()
        raise
    finally:
        if own:
            client.close()
    return {"lastModified": last}


def norm_site(value: str, name: str = "") -> tuple[str, str] | None:
    """(https://host/, registered domain) for a usable company website, else None."""
    v = (value or "").strip().split(";")[0].strip()
    if not v or " " in v:
        return None
    u = v if "://" in v else "https://" + v
    try:
        host = (urlparse(u).hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    d = registered_domain(host)
    if not d or tos_refuse.refused(host) or d in SHARED_HOSTS or host.endswith(SHARED_HOSTS):
        return None
    if is_directory_domain(d, name):
        return None
    return f"https://{host}/", d


def norm_postcode(v: str | None) -> str | None:
    p = re.sub(r"[^0-9A-Z]", "", (v or "").upper())
    return p or None


def rows_for(tags: dict, osm_type: str, osm_id: int, country: str, lat=None, lon=None) -> list[tuple]:
    """Index rows for one OSM object (one per distinct normalised name), [] when it is dropped."""
    if any(tags.get(k) for k in CHAIN_KEYS):
        return []
    name = (tags.get("name") or "").strip()
    if not name:
        return []
    site = None
    for k in WEBSITE_KEYS:
        if tags.get(k):
            site = norm_site(tags[k], name)
            if site:
                break
    if not site:
        return []
    city = fold(tags.get("addr:city") or "") or None
    post = norm_postcode(tags.get("addr:postcode"))
    cat = next((f"{k}={tags[k]}" for k in CATEGORY_KEYS if tags.get(k)), None)
    names, seen = [], set()
    for k in NAME_KEYS:
        for part in (tags.get(k) or "").split(";"):
            part = part.strip()
            n = compact(core_name(part)) if part else ""
            if len(n) >= 2 and n not in seen:
                seen.add(n)
                names.append((n, part))
    return [(n, name, site[0], site[1], city, post, country, lat, lon, osm_type, osm_id, cat) for n, _ in names]


def extract(pbf_path: str, db_path: str, country: str, meta: dict | None = None) -> int:
    """Read a (filtered or full) .osm.pbf/.osm and write the SQLite index. Returns the row count."""
    import osmium
    Path(db_path).unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.executescript(DDL)
    n = 0
    batch: list[tuple] = []
    fp = osmium.FileProcessor(pbf_path).with_filter(osmium.filter.KeyFilter(*WEBSITE_KEYS))
    for o in fp:
        tags = {t.k: t.v for t in o.tags}
        if isinstance(o, osmium.osm.Node):
            typ, lat, lon = "n", o.location.lat, o.location.lon
        elif isinstance(o, osmium.osm.Way):
            typ, lat, lon = "w", None, None
        else:
            typ, lat, lon = "r", None, None
        batch += rows_for(tags, typ, o.id, country, lat, lon)
        if len(batch) >= 50_000:
            db.executemany(f"INSERT INTO poi VALUES ({','.join('?' * len(COLUMNS))})", batch)
            n += len(batch)
            batch = []
    if batch:
        db.executemany(f"INSERT INTO poi VALUES ({','.join('?' * len(COLUMNS))})", batch)
        n += len(batch)
    db.execute("INSERT INTO meta VALUES ('schema', ?)", (str(SCHEMA_VERSION),))
    db.execute("INSERT INTO meta VALUES ('country', ?)", (country,))
    for k, v in (meta or {}).items():
        db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, str(v)))
    db.commit()
    db.execute("VACUUM")
    db.close()
    return n


def gzip_file(src: str, dst: str) -> int:
    with open(src, "rb") as f, gzip.open(dst, "wb", compresslevel=9) as g:
        shutil.copyfileobj(f, g)
    return Path(dst).stat().st_size
