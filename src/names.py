"""Company-name normalisation, input parsing and domain helpers."""
import re
import unicodedata

import tldextract

# Bundled public-suffix snapshot only: no download at run time.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

LEGAL = {
    "inc", "incorporated", "llc", "l l c", "ltd", "limited", "corp", "corporation", "co", "company", "plc", "gmbh",
    "ag", "sa", "s a", "sas", "sarl", "srl", "spa", "s p a", "bv", "b v", "nv", "n v", "ab", "as", "a s", "asa", "oy",
    "oyj", "aps", "kg", "gmbh co kg", "se", "kk", "k k", "pty", "pte", "sdn bhd", "bhd", "tbk", "pt", "lp", "llp",
    "group", "holding", "holdings", "the", "sl", "s l", "sro", "s r o", "zoo", "sp z o o", "spolka", "ltda",
    "kgaa", "cie", "and co", "and cie", "co kg", "and co kg", "and co kgaa", "ohg", "ug", "sas u", "gk",
    "cv", "sa de cv", "pvt", "private", "jsc", "ojsc", "pjsc", "ooo", "kft", "zrt", "doo", "d o o", "ehf",
}
# Words kept for matching but not enough on their own to identify a company.
GENERIC = {"and", "of", "de", "la", "le", "der", "die", "das", "und", "et", "y", "e", "for", "international",
           "global", "technologies", "technology", "tech", "solutions", "services", "systems", "software", "labs",
           "studio", "studios", "digital", "media", "consulting", "partners", "ventures", "capital", "industries",
           "enterprises", "worldwide", "bank", "foods", "food", "motors", "electronics", "energy", "inc"}
CJK_LEGAL = ["株式会社", "有限会社", "合同会社", "股份有限公司", "有限公司", "集团", "集團", "公司", "주식회사", "(주)", "㈜"]

COUNTRY_ALIASES = {
    "us": "US", "usa": "US", "united states": "US", "united states of america": "US", "america": "US",
    "uk": "GB", "gb": "GB", "united kingdom": "GB", "great britain": "GB", "england": "GB", "scotland": "GB",
    "de": "DE", "germany": "DE", "deutschland": "DE", "fr": "FR", "france": "FR", "es": "ES", "spain": "ES",
    "it": "IT", "italy": "IT", "nl": "NL", "netherlands": "NL", "the netherlands": "NL", "holland": "NL",
    "be": "BE", "belgium": "BE", "ch": "CH", "switzerland": "CH", "at": "AT", "austria": "AT", "se": "SE",
    "sweden": "SE", "no": "NO", "norway": "NO", "dk": "DK", "denmark": "DK", "fi": "FI", "finland": "FI",
    "pl": "PL", "poland": "PL", "cz": "CZ", "czechia": "CZ", "czech republic": "CZ", "pt": "PT", "portugal": "PT",
    "ie": "IE", "ireland": "IE", "jp": "JP", "japan": "JP", "tw": "TW", "taiwan": "TW", "cn": "CN", "china": "CN",
    "hk": "HK", "hong kong": "HK", "kr": "KR", "korea": "KR", "south korea": "KR", "in": "IN", "india": "IN",
    "sg": "SG", "singapore": "SG", "id": "ID", "indonesia": "ID", "my": "MY", "malaysia": "MY", "th": "TH",
    "thailand": "TH", "vn": "VN", "vietnam": "VN", "ph": "PH", "philippines": "PH", "au": "AU", "australia": "AU",
    "nz": "NZ", "new zealand": "NZ", "ca": "CA", "canada": "CA", "mx": "MX", "mexico": "MX", "br": "BR",
    "brazil": "BR", "brasil": "BR", "ar": "AR", "argentina": "AR", "cl": "CL", "chile": "CL", "colombia": "CO", "za": "ZA", "south africa": "ZA", "ng": "NG", "nigeria": "NG", "ke": "KE", "kenya": "KE",
    "il": "IL", "israel": "IL", "ae": "AE", "uae": "AE", "united arab emirates": "AE", "tr": "TR", "turkey": "TR",
    "ee": "EE", "estonia": "EE", "lt": "LT", "lithuania": "LT", "lv": "LV", "latvia": "LV", "ro": "RO",
    "romania": "RO", "hu": "HU", "hungary": "HU", "gr": "GR", "greece": "GR", "ua": "UA", "ukraine": "UA",
    "sk": "SK", "slovakia": "SK",
}
COUNTRY_NAMES = {v: k for k, v in COUNTRY_ALIASES.items() if len(k) > 3}
# Country-code domains tried when guessing, by ISO code.
CC_TLDS = {
    "GB": ["co.uk", "uk"], "JP": ["co.jp", "jp"], "TW": ["com.tw", "tw"], "KR": ["co.kr", "kr"], "IN": ["in", "co.in"],
    "BR": ["com.br"], "AU": ["com.au"], "NZ": ["co.nz"], "ZA": ["co.za"], "CN": ["cn", "com.cn"], "HK": ["com.hk", "hk"],
    "SG": ["sg", "com.sg"], "ID": ["co.id", "id"], "MY": ["com.my", "my"], "MX": ["com.mx", "mx"], "AR": ["com.ar"],
    "IL": ["co.il"], "TR": ["com.tr"], "TH": ["co.th"], "PH": ["ph", "com.ph"], "VN": ["vn", "com.vn"],
    "DE": ["de"], "FR": ["fr"], "ES": ["es"], "IT": ["it"], "NL": ["nl"], "BE": ["be"], "CH": ["ch"], "AT": ["at"], "SE": ["se"],
    "NO": ["no"], "DK": ["dk"], "FI": ["fi"], "PL": ["pl"], "CZ": ["cz"], "PT": ["pt"], "IE": ["ie"], "CA": ["ca"],
    "HU": ["hu"], "RO": ["ro"], "GR": ["gr", "com.gr"], "SK": ["sk"], "CL": ["cl"], "CO": ["com.co", "co"],
    "NG": ["com.ng", "ng"], "KE": ["co.ke", "ke"], "AE": ["ae", "co.ae"],
}
# Wikidata item of each country, to check an entity's country (P17) against the hint.
COUNTRY_QIDS = {
    "US": "Q30", "GB": "Q145", "DE": "Q183", "FR": "Q142", "ES": "Q29", "IT": "Q38", "NL": "Q55", "BE": "Q31",
    "CH": "Q39", "AT": "Q40", "SE": "Q34", "NO": "Q20", "DK": "Q35", "FI": "Q33", "PL": "Q36", "CZ": "Q213",
    "PT": "Q45", "IE": "Q27", "JP": "Q17", "TW": "Q865", "CN": "Q148", "HK": "Q8646", "KR": "Q884", "IN": "Q668",
    "SG": "Q334", "ID": "Q252", "MY": "Q833", "TH": "Q869", "VN": "Q881", "PH": "Q928", "AU": "Q408", "NZ": "Q664",
    "CA": "Q16", "MX": "Q96", "BR": "Q155", "AR": "Q414", "CL": "Q298", "CO": "Q739", "ZA": "Q258", "NG": "Q1033",
    "KE": "Q114", "IL": "Q801", "AE": "Q878", "TR": "Q43", "EE": "Q191", "LT": "Q37", "LV": "Q211", "RO": "Q218",
    "HU": "Q28", "GR": "Q41", "UA": "Q212", "SK": "Q214",
}

# Hosts that list or describe companies but are never a company's own site.
NOT_COMPANY_SITES = {
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "tiktok.com",
    "pinterest.com", "reddit.com", "wikipedia.org", "wikidata.org", "wikimedia.org", "crunchbase.com",
    "bloomberg.com", "reuters.com", "zoominfo.com", "dnb.com", "glassdoor.com", "indeed.com", "yelp.com",
    "tripadvisor.com", "trustpilot.com", "amazon.com", "google.com", "bing.com", "duckduckgo.com",
    "yahoo.com", "github.com", "medium.com", "forbes.com", "cbinsights.com", "pitchbook.com", "owler.com",
    "craft.co", "apollo.io", "rocketreach.co", "signalhire.com", "lusha.com", "opencorporates.com",
    "companieshouse.gov.uk", "find-and-update.company-information.service.gov.uk", "northdata.com",
    "northdata.de", "yellowpages.com", "bbb.org", "mapquest.com", "foursquare.com", "manta.com", "kompass.com",
    "europages.com", "macrotrends.net", "marketscreener.com", "finance.yahoo.com", "wsj.com", "ft.com",
    "cnbc.com", "nytimes.com", "theguardian.com", "techcrunch.com", "wellfound.com", "angel.co", "ycombinator.com",
    "producthunt.com", "g2.com", "capterra.com", "getapp.com", "softwareadvice.com", "builtin.com", "comparably.com",
    "ambitionbox.com", "naukri.com", "stockanalysis.com", "companiesmarketcap.com", "britannica.com", "fandom.com",
    "quora.com", "zhihu.com", "baidu.com", "weibo.com", "play.google.com", "apps.apple.com", "wix.com",
    "bizapedia.com", "corporationwiki.com", "buzzfile.com", "datanyze.com", "leadiq.com", "contactout.com",
    "theorg.com", "tracxn.com", "dealroom.co", "f6s.com", "clutch.co", "goodfirms.co", "sortlist.com",
    "glassdoor.co.uk", "glassdoor.de", "kununu.com", "stepstone.de", "xing.com", "wikiwand.com", "dbpedia.org",
    "namepros.com", "godaddy.com", "sedo.com", "dan.com", "afternic.com", "hugedomains.com", "undeveloped.com",
    "domainmarket.com", "brandbucket.com", "squadhelp.com", "atom.com", "uniregistry.com", "buydomains.com",
    "perfectdomain.com", "sav.com", "porkbun.com", "namecheap.com", "parkingcrew.net", "bodis.com",
    "investing.com", "morningstar.com", "nasdaq.com", "nyse.com", "sec.gov", "gov.uk", "europa.eu",
    # Local-business directories, booking platforms, delivery and review marketplaces (B57, 2026-11-01).
    "booksy.com", "fresha.com", "treatwell.co.uk", "treatwell.com", "vagaro.com", "styleseat.com", "schedulicity.com",
    "mindbodyonline.com", "setmore.com", "square.site", "squareup.com", "opentable.com", "resy.com", "yelp.ca",
    "yelp.co.uk", "ubereats.com", "doordash.com", "grubhub.com", "just-eat.co.uk", "deliveroo.co.uk", "zomato.com",
    "skipthedishes.com", "restaurantguru.com", "restaurants-us.com", "beautynailhairsalons.com", "yell.com",
    "thomsonlocal.com", "cylex-uk.co.uk", "cylex.us.com", "hotfrog.com", "hotfrog.co.uk", "nextdoor.com", "angi.com",
    "angieslist.com", "homeadvisor.com", "thumbtack.com", "porch.com", "houzz.com", "trustatrader.com",
    "checkatrade.com", "ratedpeople.com", "mybuilder.com", "bark.com", "192.com", "scoot.co.uk", "tupalo.com",
    "brownbook.net", "chamberofcommerce.com", "showmelocal.com", "merchantcircle.com", "citysearch.com",
    "superpages.com", "whitepages.com", "local.yahoo.com", "yellowpages.ca", "canada411.ca", "restaurantji.com",
    "menupix.com", "allmenus.com", "sirved.com", "wanderlog.com", "tripadvisor.co.uk", "tripadvisor.ca",
    "groupon.com", "fixr.com", "nicelocal.com", "bizjournals.com", "birdeye.com", "alignable.com", "cylex.ca",
    "salonboard.com", "phorest.com", "timely.com", "planity.com", "yelp.com.au", "localsearch.com.au",
    "expertise.com", "threebestrated.com", "threebestrated.ca", "threebestrated.co.uk", "yellowbot.com",
    "ezlocal.com", "mapquest.co.uk", "hub.biz", "dandb.com", "linktr.ee", "business.site", "godaddysites.com",
    "wixsite.com", "weebly.com", "carrd.co", "tumblr.com",
}
# Ordering, hosting and link-in-bio platforms (B607). A business can live on one as a subdomain or path, but the
# registered domain is the platform's, never the business's own: kwickmenu.com was returned for "Little Tokyo
# Express" (B598). Allowed only when the business name is the platform's subdomain (is_company_site(host=...)).
PLATFORM_HOSTS = {
    "kwickmenu.com", "slicelife.com", "toasttab.com", "square.site", "squareup.com", "wixsite.com", "wix.com",
    "godaddysites.com", "business.site", "linktr.ee", "bio.link", "lnk.bio", "beacons.ai", "allmylinks.com",
    "myshopify.com", "shopify.com", "squarespace.com", "webflow.io", "weebly.com", "carrd.co", "wordpress.com",
    "chownow.com", "menufy.com", "clover.com", "order.online", "strikingly.com", "mystrikingly.com", "jimdosite.com",
    "webnode.com", "site123.me", "tumblr.com", "blogspot.com", "doordash.com", "ubereats.com", "grubhub.com",
}
# Non-commercial top-level domains: root.cern is CERN's, not a company called Root (B598).
NON_COMMERCIAL_TLDS = {"int", "cern", "museum", "aero", "mil"}
# Listing words that mark a domain label as a directory unless it carries the company's own distinctive words.
DIRECTORY_LABEL = re.compile(
    r"(directory|listings?|yellowpages|nearme|near-me|findabusiness|localbusiness|bestof|"
    r"(restaurants|salons|plumbers|electricians|contractors|dentists|barbers|businesses|companies)(us|uk|usa|online|hub|guide|list|pages)?$)",
    re.I)
# Two-letter endings that businesses use as ordinary brand domains, not as a country marker.
GENERIC_CCTLD = {"io", "ai", "co", "tv", "me", "ly", "fm", "cc", "ws", "gg", "sh", "to", "so", "ac", "ag", "vc",
                 "gl", "gd", "id", "is", "it", "us", "in", "am", "be", "do", "la", "nu", "pro"}


GOV_LABEL = re.compile(r"(gov$|^(cityof|townof|countyof|villageof)|(^|[a-z])(council|municipal)s?$)", re.I)
GOV_NAME = re.compile(r"\b(city|town|county|village|council|municipal\w*|government|gov|borough|ville|stadt|gemeinde)\b", re.I)


def fold(s: str) -> str:
    """Lowercase, strip accents, '&' -> 'and', every other non-alphanumeric -> space (CJK kept)."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower().replace("&", " and ")
    s = re.sub(r"[’'`]", "", s)
    return re.sub(r"[^\w]+|_", " ", s).strip()


def has_cjk(s: str) -> bool:
    return bool(re.search(r"[぀-ヿ㐀-鿿가-힯]", s or ""))


def core_name(name: str) -> str:
    """'Robert Bosch GmbH' -> 'robert bosch'; 'The Coca-Cola Company' -> 'coca cola'. Legal forms removed."""
    raw = name or ""
    for w in CJK_LEGAL:
        raw = raw.replace(w, " ")
    raw = re.sub(r"\(.*?\)", " ", raw)
    words = fold(raw).split()
    # Strip legal suffixes from the end (multi-word ones first), and a leading 'the'.
    changed = True
    while changed and len(words) > 1:
        changed = False
        for n in (4, 3, 2, 1):
            if len(words) > n and " ".join(words[-n:]) in LEGAL:
                words = words[:-n]
                changed = True
                break
    if len(words) > 1 and words[0] == "the":
        words = words[1:]
    return " ".join(words)


def tokens(name: str) -> list[str]:
    return core_name(name).split()


def distinctive(name: str) -> list[str]:
    toks = tokens(name)
    d = [t for t in toks if t not in GENERIC and len(t) > 1]
    return d or toks


def compact(s: str) -> str:
    return re.sub(r"\s+", "", fold(s))


def slugs(name: str) -> list[str]:
    """Domain labels a company with this name might own, most likely first."""
    toks = tokens(name)
    if not toks or has_cjk(" ".join(toks)):
        return []
    out = ["".join(toks)]
    if len(toks) > 1:
        out.append("-".join(toks))
        dist = distinctive(name)
        if dist and "".join(dist) not in out:
            out.append("".join(dist))
        if len(toks[0]) >= 4 and toks[0] not in GENERIC and toks[0] not in out:
            out.append(toks[0])
    ascii_only = [s for s in out if re.fullmatch(r"[a-z0-9-]{2,63}", s)]
    return ascii_only[:4]


# Words that describe the kind of business, not its brand: dropped when expanding domain-slug variants.
DESCRIPTORS = {
    "cafe", "coffee", "roasters", "roastery", "roasting", "bakery", "bakeries", "tea", "tearooms", "rooms", "room", "house",
    "delicatessen", "deli", "restaurant", "bookstore", "books", "buchhandlung", "distillery", "brewery", "brauerei",
    "weingut", "winery", "kaffeeroesterei", "kaffeerosterei", "stammhaus", "market", "dairy", "doughnut", "chowder",
    "kitchen", "bar", "pub", "shop", "store", "salon", "studio", "bistro", "bakehouse", "patisserie",
}
_TRANSLIT = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss", "æ": "ae", "ø": "oe", "å": "aa"}


def translit(s: str) -> str:
    """German-style transliteration (ä -> ae, ß -> ss), the spelling most domains use."""
    return "".join(_TRANSLIT.get(ch, ch) for ch in s or "")


def slug_variants(name: str) -> list[str]:
    """Extra domain labels beyond slugs(): umlauts and ß spelled out (ae/oe/ue/ss), descriptor words dropped
    ('Bettys Cafe Tea Rooms' -> 'bettys'), a leading 'Dr' dropped, 'and' dropped, possessive 's' dropped."""
    out: list[str] = []
    bases = [name]
    if translit(name) != name:
        bases.insert(0, translit(name))  # 'Kaffeerösterei' -> 'kaffeeroesterei' beats the accent-stripped 'kaffeerosterei'
    for b in bases:
        toks = tokens(b)
        if not toks or has_cjk(" ".join(toks)):
            continue
        cands = ["".join(toks), "".join(t for t in toks if t != "and")]
        brand = [t for t in toks if t not in DESCRIPTORS and t not in ("dr", "and")]
        with_dr = [t for t in toks if t not in DESCRIPTORS and t != "and"]
        if brand and with_dr != brand:
            cands.append("".join(with_dr))  # 'Weingut Dr. Loosen' -> 'drloosen'
        if brand and "delicatessen" in toks:
            cands.append("".join(brand) + "deli")
        if brand and brand != toks:
            cands += ["".join(brand), "-".join(brand)]
            cands.append("".join(brand[:1]))
        elif len(toks) > 1:
            cands.append(toks[0])
        if brand and brand[0].endswith("s") and len(brand[0]) > 4:
            cands.append(brand[0][:-1])  # zingermans -> zingerman
        for c in cands:
            if len(c) >= 4 and c not in out and re.fullmatch(r"[a-z0-9-]{4,63}", c):
                out.append(c)
    return out


# Extra trade words dropped only for the descriptor-drop guess (B467): 'Smile Dental' -> smile.
DD_EXTRA = {"dental", "dentist", "clinic", "salon", "gallery", "boutique", "pharmacy", "gym", "spa", "barbers", "barber"}


def descriptor_drop_slug(name: str) -> str:
    """The bare brand slug of a name that carries a trade descriptor ('Gails Bakery' -> 'gails'; legal forms are already
    gone via core_name), '' when there is no descriptor, nothing is left, or the brand is under 4 letters or not ASCII."""
    toks = tokens(translit(name))
    if not toks or has_cjk(" ".join(toks)):
        return ""
    brand = [t for t in toks if t not in DESCRIPTORS and t not in DD_EXTRA]
    if not brand or brand == toks:
        return ""
    slug = "".join(brand)
    return slug if re.fullmatch(r"[a-z0-9]{4,63}", slug) else ""


def dropped_descriptors(name: str) -> list[str]:
    """Descriptor words (4+ letters) that are in the name: what a page for the full name should also mention."""
    return [t for t in tokens(translit(name)) if (t in DESCRIPTORS or t in DD_EXTRA) and len(t) >= 4]


def brand_name(name: str) -> str:
    """The name without descriptor words ('Brauerei Camba Bavaria' -> 'camba bavaria'); '' when nothing is dropped or
    nothing is left."""
    toks = tokens(translit(name))
    brand = [t for t in toks if t not in DESCRIPTORS]
    return " ".join(brand) if brand and brand != toks else ""


def parse_line(line: str) -> dict:
    """'Bosch, Germany' / 'Bosch | Stuttgart, DE' -> {'name': 'Bosch', 'country': 'DE', 'city': 'Stuttgart'}."""
    line = (line or "").strip()
    out = {"name": line, "country": None, "city": None}
    if "|" in line:
        name, rest = line.split("|", 1)
        out["name"] = name.strip()
        parts = [p.strip() for p in rest.split(",") if p.strip()]
    elif "," in line:
        name, rest = line.rsplit(",", 1)
        # The tail is a place unless it is a legal form or part of the name: 'Procter & Gamble, Co.' and
        # 'Smith, Jones & Partners' stay whole; 'Joe's Pizza, New York' gets city 'New York'.
        tail = fold(rest)
        if (country_code(rest) or (tail and tail not in LEGAL and not re.search(r"\d|&| and ", " " + tail + " ")
                                   and len(tail.split()) <= 3 and name.strip())):
            out["name"] = name.strip()
            parts = [rest.strip()]
        else:
            parts = []
    else:
        parts = []
    for p in parts:
        cc = country_code(p)
        if cc and not out["country"]:
            out["country"] = cc
        elif not out["city"]:
            out["city"] = p
    return out


def country_code(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    v = fold(value)
    if v in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[v]
    return None


def registered_domain(host_or_url: str) -> str | None:
    """'https://www.shop.acme.co.uk/x' -> 'acme.co.uk'."""
    if not host_or_url:
        return None
    ex = _EXTRACT(host_or_url.strip().lower())
    if not ex.domain or not ex.suffix:
        return None
    return f"{ex.domain}.{ex.suffix}"


def domain_label(domain: str) -> str:
    ex = _EXTRACT(domain or "")
    return ex.domain or ""


def is_directory_domain(domain: str | None, name: str = "") -> bool:
    """A domain whose label reads like a listing site and shares no distinctive word with the company."""
    if not domain:
        return False
    label = domain_label(domain)
    if not DIRECTORY_LABEL.search(label):
        return False
    cn = compact(core_name(name))
    flat = label.replace("-", "")
    if cn and (cn in flat or flat in cn):
        return False
    return not any(len(d) >= 3 and d in flat for d in distinctive(name))


def cc_tld(domain: str | None) -> str | None:
    """The domain's country-code TLD as an ISO code ('GB' for .co.uk), None for generic ones."""
    ex = _EXTRACT(domain or "")
    last = (ex.suffix or "").rsplit(".", 1)[-1].lower()
    if len(last) != 2 or last in GENERIC_CCTLD:
        return None
    return "GB" if last == "uk" else last.upper()


def tld_mismatch(domain: str | None, country: str | None) -> bool:
    """True when the query names a country and the domain sits under another country's ccTLD
    (an .ie site for an Austin, US query)."""
    cc = cc_tld(domain)
    return bool(country and cc and cc != country.upper())


def is_company_site(domain: str | None, name: str = "", host: str | None = None) -> bool:
    """False for directories, social networks and news sites, unless the company is that site itself
    (Amazon -> amazon.com, LinkedIn -> linkedin.com). Ordering and hosting platforms are refused unless the
    company is the platform itself or (when `host` is given) its name is the host's subdomain."""
    if not domain:
        return False
    if domain in PLATFORM_HOSTS and domain not in NOT_COMPANY_SITES:
        cn = compact(core_name(name))
        if cn and domain_label(domain) == cn:
            return True
        sub = (host or "").lower().removesuffix(domain).rstrip(".").replace("-", "").replace(".", "")
        return bool(cn) and len(cn) >= 3 and cn in sub
    if _EXTRACT(domain).suffix in NON_COMMERCIAL_TLDS:
        return False
    if domain in NOT_COMPANY_SITES:
        return bool(name) and domain_label(domain) == compact(core_name(name))
    if is_directory_domain(domain, name):
        return False
    # Government, education and generic hosting suffixes are rarely a business's own domain.
    ex = _EXTRACT(domain)
    if GOV_LABEL.search(ex.domain or "") and not GOV_NAME.search(name or ""):
        return False  # lakelandgov.net, cityofx.org: a municipality's site, not a business's
    if ex.suffix in {"gov", "gov.uk", "edu", "mil"} or ex.domain in {"blogspot", "wordpress", "github", "sites"}:
        return False
    return True
