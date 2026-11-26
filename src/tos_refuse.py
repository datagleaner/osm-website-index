"""Shared Terms-of-Service host refusal for Actors that fetch user-supplied or crawl-found URLs (B415, 2026-11-02).

CANONICAL COPY. Each Actor that fetches arbitrary hosts (`*` in .actor/hosts.txt) carries an identical copy as
`actors/<name>/src/tos_refuse.py` (Actors are separate Docker builds, so nothing is imported across folders).
scripts/lint_actors.py fails when a copy drifts from this file, when the TOS_REFUSED block below no longer matches
actors/tos_verdicts.tsv, or when a `*` Actor does not ship and import this module. After a new verdict row run
`python3 scripts/tos_refuse.py --sync`: it regenerates the TOS_REFUSED block from the table, then rewrites every copy.

Which hosts are refused (no request at all, the host and every subdomain, on the first URL and on every redirect step):
- TOS_REFUSED: every BANNED, LAWYER and LEGAL-CHECK row of actors/tos_verdicts.tsv (LEGAL-CHECK: Legal first, default no).
- PLATFORMS: social, video, audio and other user-content platforms. Their terms govern other people's content and
  forbid automated download or scraping, so "a host with no row counts as BANNED" applies to them whether or not a
  row exists yet. A platform leaves this list only by a founder decision recorded as a row.
- HELD: hosts an earlier hand-kept list refused whose row has since turned OK. B415 merged four hand lists and let
  no refused host become allowed; the founder may drop a HELD host.
- Any other host with no row (an independent business site, a file on its owner's server or CDN) is the user's own
  pick of a target. It is governed by robots.txt (robots_gate), the active-challenge gate and the honest UA. The
  static lint's "no row = BANNED" covers every host our own code names; applying it to user-named hosts would refuse
  every small-business site (reasoning: ops/reports/2026-11-02-B415.md).
Matching is by host or any parent domain. An OK row on a subdomain does not lift a refused parent (a ban is never
narrower than the host it names), which is how the old hand lists matched too.

Use: `refused(url)` -> (entry, kind) or None before the first request; `httpx_hooks()` / `httpx_hooks_sync()` for the
client's `event_hooks=`, which raise RefusedHost before any request (redirect steps included) goes to a refused host.
"""
from __future__ import annotations

import pathlib
import re
import sys
from urllib.parse import urlparse

try:  # httpx is optional: an Actor without it still gets refused() and the message helpers (B125)
    import httpx
    _BASE = httpx.RequestError
except ImportError:  # pragma: no cover
    httpx = None
    _BASE = Exception

PLATFORMS = (
    # Google / YouTube
    "youtube.com", "youtu.be", "youtube-nocookie.com", "googlevideo.com", "ytimg.com",
    # ByteDance / TikTok / Douyin
    "tiktok.com", "tiktokcdn.com", "tiktokv.com", "tiktokcdn-us.com", "douyin.com", "ixigua.com", "byteimg.com",
    # Vimeo
    "vimeo.com", "vimeocdn.com", "livestream.com",
    # Meta
    "instagram.com", "cdninstagram.com", "facebook.com", "fb.com", "fb.watch", "fbcdn.net", "threads.net",
    # X / Twitter
    "x.com", "twitter.com", "twimg.com", "t.co", "periscope.tv", "pscp.tv",
    # Twitch / Kick
    "twitch.tv", "ttvnw.net", "jtvnw.net", "kick.com",
    # Dailymotion
    "dailymotion.com", "dai.ly", "dmcdn.net", "dm-event.net",
    # Other video hosts and social networks
    "bilibili.com", "bilibili.tv", "b23.tv", "bilivideo.com", "hdslb.com", "rumble.com", "streamable.com",
    "vk.com", "vkvideo.ru", "vk.ru", "ok.ru", "rutube.ru", "youku.com", "iqiyi.com", "iq.com", "kuaishou.com",
    "weibo.com", "weibo.cn", "nicovideo.jp", "nimg.jp", "snapchat.com", "pinterest.com", "pinimg.com",
    "reddit.com", "redd.it", "redditmedia.com", "linkedin.com", "licdn.com", "tumblr.com", "9gag.com", "imgur.com",
    "loom.com", "wistia.com", "wistia.net", "vidyard.com", "brightcove.com", "brightcove.net", "brightcovecdn.com",
    "jwplayer.com", "jwplatform.com", "jwpcdn.com", "sproutvideo.com", "vidio.com", "bitchute.com", "odysee.com",
    "lbry.tv", "peertube.tv", "veoh.com", "metacafe.com", "ted.com", "coub.com", "triller.co", "likee.video",
    "kwai.com", "zhihu.com", "xiaohongshu.com", "xhscdn.com", "douban.com", "acfun.cn", "mgtv.com", "qq.com",
    # Streaming and audio
    "netflix.com", "nflxvideo.net", "hulu.com", "disneyplus.com", "primevideo.com", "max.com", "hbomax.com",
    "peacocktv.com", "paramountplus.com", "crunchyroll.com", "tv.apple.com", "spotify.com", "spotify.link", "scdn.co",
    "soundcloud.com", "archive.org",
    # Adult platforms (terms forbid downloading; never a source)
    "pornhub.com", "xvideos.com", "xhamster.com", "onlyfans.com", "chaturbate.com",
)

HELD = (
    "fmcsa.dot.gov",  # LEGAL-CHECK in video-frame-extractor's hand list until B307's OK row; kept refused for user URLs
)

# --- TOS_REFUSED: generated from actors/tos_verdicts.tsv (BANNED, LAWYER, LEGAL-CHECK) by --sync; do not edit ---
TOS_REFUSED = {
    "acquire.com": "BANNED", "adstransparency.google.com": "LEGAL-CHECK", "airbnb.com": "BANNED",
    "aliexpress.com": "BANNED", "allmylinks.com": "BANNED", "api-krs.ms.gov.pl": "LEGAL-CHECK",
    "api.elections.kalshi.com": "BANNED", "api.kvk.nl": "LEGAL-CHECK", "api.mojeek.com": "LEGAL-CHECK",
    "api.opencorporates.com": "BANNED", "api.search.brave.com": "BANNED", "apps.apple.com": "BANNED",
    "apps.fcc.gov": "LEGAL-CHECK", "archive.org": "BANNED", "ares.gov.cz": "LEGAL-CHECK",
    "autocomplete.clearbit.com": "LEGAL-CHECK", "beacons.ai": "BANNED", "bilibili.com": "BANNED",
    "bing.com": "BANNED", "bio.link": "BANNED", "bolagsverket.se": "LEGAL-CHECK", "campsite.bio": "BANNED",
    "cvrapi.dk": "BANNED", "data.fcc.gov": "LEGAL-CHECK", "data.gov.ie": "LEGAL-CHECK",
    "datacvr.virk.dk": "LEGAL-CHECK", "dol.gov": "LEGAL-CHECK", "douban.com": "BANNED", "duckduckgo.com": "BANNED",
    "espn.com": "BANNED", "eventbrite.com": "BANNED", "expofp.com": "BANNED", "flatfox.ch": "LAWYER",
    "flippa.com": "BANNED", "freelancer.com": "BANNED", "gamma-api.polymarket.com": "BANNED",
    "gelbeseiten.de": "BANNED", "github.com": "BANNED", "herold.at": "BANNED", "homeaffairs.gov.au": "LEGAL-CHECK",
    "hotfrog.co.nz": "BANNED", "hotfrog.co.uk": "BANNED", "hotfrog.com": "BANNED", "hotfrog.com.au": "BANNED",
    "immigration.govt.nz": "LEGAL-CHECK", "justizonline.gv.at": "LEGAL-CHECK", "lennysnewsletter.com": "BANNED",
    "linktr.ee": "BANNED", "lnk.bio": "BANNED", "lu.ma": "BANNED", "luma.com": "BANNED", "myshopify.com": "BANNED",
    "myworkdayjobs.com": "BANNED", "nominatim.openstreetmap.org": "BANNED", "opencorporates.com": "BANNED",
    "overpass-api.de": "BANNED", "patents.google.com": "BANNED", "pinterest.com": "BANNED",
    "pubapi.registry.google": "BANNED", "rdap.centralnic.com": "BANNED", "rdap.denic.de": "BANNED",
    "rdap.gmoregistry.net": "BANNED", "rdap.identitydigital.services": "BANNED", "rdap.nominet.uk": "BANNED",
    "rdap.norid.no": "BANNED", "rdap.publicinterestregistry.org": "BANNED", "rdap.verisign.com": "BANNED",
    "shopify.com": "BANNED", "skool.com": "BANNED", "solo.to": "BANNED", "spc.noaa.gov": "LEGAL-CHECK",
    "steampowered.com": "BANNED", "stock.adobe.com": "BANNED", "substack.com": "BANNED",
    "suggestqueries.google.com": "LEGAL-CHECK", "t.me": "BANNED", "taplink.cc": "BANNED",
    "tennisexplorer.com": "BANNED", "tiktok.com": "BANNED", "tld-rdap.verisign.com": "BANNED", "vimeo.com": "BANNED",
    "weibo.cn": "BANNED", "weibo.com": "BANNED", "willhaben.at": "BANNED", "www.fcc.gov": "LEGAL-CHECK",
    "xiaohongshu.com": "BANNED", "yc-oss.github.io": "BANNED", "ycombinator.com": "BANNED",
    "yellowpages.ca": "BANNED", "yellowpages.com": "BANNED", "youtube.com": "BANNED", "zefix.admin.ch": "LEGAL-CHECK",
}
# --- end TOS_REFUSED ---

TERMS_MSG = ("{host} is not a supported source: its terms do not allow automated access of this kind, so this Actor never "
             "requests it (no request is made, and nothing is charged).")
PLATFORM_MSG = ("{host} is a social, video or content platform whose terms do not allow automated downloading or scraping, "
                "so this Actor never requests it (no request is made, and nothing is charged).")


class RefusedHost(_BASE):
    """Raised by the httpx hooks before a request (first URL or a redirect step) would go to a refused host."""

    def __init__(self, url: str, entry: str, kind: str, request=None):
        self.url, self.entry, self.kind = url, entry, kind
        msg = message(entry, kind)
        if httpx is not None:
            super().__init__(msg, request=request)
        else:  # pragma: no cover
            super().__init__(msg)


def _host(url_or_host: str) -> str:
    s = (url_or_host or "").strip()
    if "://" not in s:
        s = "http://" + s
    try:
        h = urlparse(s).hostname or ""
    except ValueError:
        return ""
    return h.lower().rstrip(".")


def _match(host: str, table) -> str | None:
    for h in table:
        if host == h or host.endswith("." + h):
            return h
    return None


def refused(url_or_host: str) -> tuple[str, str] | None:
    """(entry, kind) when this URL's host (or a bare host/domain) must never be requested, else None.
    kind is the verdict (BANNED, LAWYER, LEGAL-CHECK), "PLATFORM" or "HELD"."""
    host = _host(url_or_host)
    if not host:
        return None
    p = _match(host, PLATFORMS)  # a platform first, so its message names it as one even when it also has a verdict row
    if p:
        return p, "PLATFORM"
    t = _match(host, TOS_REFUSED)
    if t:
        return t, TOS_REFUSED[t]
    h = _match(host, HELD)
    if h:
        return h, "HELD"
    return None


def refused_entry(url_or_host: str) -> str | None:
    r = refused(url_or_host)
    return r[0] if r else None


def message(entry: str, kind: str) -> str:
    return (PLATFORM_MSG if kind == "PLATFORM" else TERMS_MSG).format(host=entry)


def check(url: str, request=None) -> None:
    """Raise RefusedHost when `url` is refused."""
    r = refused(url)
    if r:
        raise RefusedHost(url, r[0], r[1], request=request)


async def _async_hook(request) -> None:
    check(str(request.url), request=request)


def _sync_hook(request) -> None:
    check(str(request.url), request=request)


def httpx_hooks(extra: dict | None = None) -> dict:
    """event_hooks for httpx.AsyncClient: every request, each redirect step included, is checked before it is sent."""
    hooks = {k: list(v) for k, v in (extra or {}).items()}
    hooks.setdefault("request", []).insert(0, _async_hook)
    return hooks


def httpx_hooks_sync(extra: dict | None = None) -> dict:
    """event_hooks for httpx.Client (sync)."""
    hooks = {k: list(v) for k, v in (extra or {}).items()}
    hooks.setdefault("request", []).insert(0, _sync_hook)
    return hooks


# ---- repo-side maintenance (never runs inside an Actor) ----
BLOCK_RX = re.compile(r"(# --- TOS_REFUSED: generated[^\n]*\n)(.*?)(# --- end TOS_REFUSED ---)", re.S)


def tsv_refused(path) -> dict[str, str]:
    """host -> verdict for every BANNED, LAWYER and LEGAL-CHECK row of a tos_verdicts.tsv file."""
    out = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#") or not line.strip():
            continue
        cols = [c.strip() for c in line.split("\t")]
        if len(cols) > 1 and cols[0] and cols[1].upper() in ("BANNED", "LAWYER", "LEGAL-CHECK"):
            out[cols[0].lower()] = cols[1].upper()
    return out


def render_block(table: dict[str, str]) -> str:
    items = [f'"{h}": "{v}",' for h, v in sorted(table.items())]
    lines, cur = [], "   "
    for it in items:
        if len(cur) + 1 + len(it) > 118:
            lines.append(cur)
            cur = "   "
        cur += " " + it
    if items:
        lines.append(cur)
    return "TOS_REFUSED = {\n" + "".join(l + "\n" for l in lines) + "}\n"


def regenerate(text: str, table: dict[str, str]) -> str:
    return BLOCK_RX.sub(lambda m: m.group(1) + render_block(table) + m.group(3), text, count=1)


def stale(root: pathlib.Path | None = None) -> bool:
    """True when this canonical file's TOS_REFUSED block differs from actors/tos_verdicts.tsv (lint FAILs on it)."""
    root = root or pathlib.Path(__file__).resolve().parent.parent
    me = (root / "scripts" / "tos_refuse.py").read_text()
    return regenerate(me, tsv_refused(root / "actors" / "tos_verdicts.tsv")) != me


def sync(root: pathlib.Path | None = None):
    root = root or pathlib.Path(__file__).resolve().parent.parent
    canon = root / "scripts" / "tos_refuse.py"
    me = regenerate(canon.read_text(), tsv_refused(root / "actors" / "tos_verdicts.tsv"))
    canon.write_text(me)
    for p in sorted((root / "actors").glob("*/src/tos_refuse.py")):
        p.write_text(me)
        print("synced", p.relative_to(root))


if __name__ == "__main__":
    if "--sync" in sys.argv:
        sync()
