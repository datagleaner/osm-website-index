import gzip
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import build, main, schema
from tests import fixture


def make(tmp_path, ext="osm.pbf"):
    p = str(tmp_path / f"t.{ext}")
    fixture.write(p)
    db = str(tmp_path / "i.sqlite")
    n = build.extract(p, db, "US", {"lastModified": "x"})
    return db, n


def rows(db, sql="SELECT name_norm, name, website, domain, city, postcode, country, lat, osm_type, osm_id, category FROM poi"):
    return sqlite3.connect(db).execute(sql).fetchall()


def test_extract_pbf_keeps_named_company_sites_only(tmp_path):
    db, n = make(tmp_path)
    got = rows(db)
    assert n == len(got)
    domains = {r[3] for r in got}
    assert domains == {"smiledentalaustin.com", "joesbakery.com", "brasserie-lyon.com", "wayoffice.com"}


def test_alt_names_become_extra_rows_and_use_cdf_normaliser(tmp_path):
    db, _ = make(tmp_path)
    norms = {r[0] for r in rows(db) if r[3] == "smiledentalaustin.com"}
    assert norms == {"smiledentalaustin", "smiledental", "austinsmiles"}
    # legal form stripped by the shared normaliser
    assert "brasserielyon" in {r[0] for r in rows(db)}


def test_fields(tmp_path):
    db, _ = make(tmp_path)
    r = [x for x in rows(db) if x[0] == "smiledentalaustin"][0]
    assert r[2] == "https://www.smiledentalaustin.com/" and r[4] == "austin" and r[5] == "78701"
    assert r[6] == "US" and r[7] == 30.27 and r[8] == "n" and r[9] == 1 and r[10] == "amenity=dentist"
    w = [x for x in rows(db) if x[0] == "wayoffice"][0]
    assert w[8] == "w" and w[7] is None and w[10] == "office=company"


def test_chains_social_nameless_and_builder_hosts_dropped(tmp_path):
    db, _ = make(tmp_path)
    all_names = " ".join(r[1] for r in rows(db))
    for gone in ("Chain Coffee", "Social Salon", "Wix Florist", "No Website Cafe"):
        assert gone not in all_names
    assert not [r for r in rows(db) if r[3] in ("noname.com", "facebook.com")]


def test_xml_input_gives_same_rows(tmp_path):
    p = str(tmp_path / "t.osm")
    fixture.write(p)
    db = str(tmp_path / "x.sqlite")
    n = build.extract(p, db, "US")
    assert n == 6


def test_meta_and_gzip_roundtrip(tmp_path):
    db, _ = make(tmp_path)
    assert dict(sqlite3.connect(db).execute("SELECT k, v FROM meta").fetchall())["schema"] == str(schema.SCHEMA_VERSION)
    gz = str(tmp_path / "i.gz")
    assert build.gzip_file(db, gz) > 0
    Path(tmp_path / "back.sqlite").write_bytes(gzip.open(gz).read())
    assert rows(str(tmp_path / "back.sqlite")) == rows(db)


def test_builder_reads_only_osm_fields():
    src = Path(build.__file__).read_text()
    assert "wikidata.org" not in src and "httpx.get" not in src and "register" not in src.lower().replace("registered", "")


def test_url_must_be_geofabrik():
    assert build.geofabrik_url("DE").startswith("https://download.geofabrik.de/europe/germany")
    try:
        build.geofabrik_url("DE", "https://evil.com/x.pbf")
        assert False
    except ValueError:
        pass


def test_filter_command_is_streaming_tags_filter():
    cmd = build.filter_cmd()
    assert cmd[:3] == ["osmium", "tags-filter", "-F"] and "-R" in cmd and "nwr/website" in cmd and "nwr/contact:website" in cmd


def test_normaliser_identical_to_cdf():
    cdf = Path(__file__).resolve().parents[2] / "company-domain-finder" / "src" / "names.py"
    if not cdf.exists():  # standalone public repo: the sibling Actor is not present
        import pytest
        pytest.skip("company-domain-finder not alongside")
    mine = Path(build.__file__).with_name("names.py")
    assert mine.read_text() == cdf.read_text(), "copy src/names.py from company-domain-finder"


def test_plan_skips_recent_unsupported_and_runs_sequentially():
    now = datetime(2026, 12, 1, tzinfo=timezone.utc)
    man = {"countries": {"DE": {"builtAt": (now - timedelta(days=3)).isoformat()}}}
    p = main.plan({"countries": ["de", "fr", "xx", "FR"]}, man, now)
    assert [(s["country"], s["action"]) for s in p] == [("DE", "skip"), ("FR", "build"), ("XX", "skip")]
    assert main.plan({"countries": ["de"], "force": True}, man, now)[0]["action"] == "build"
    assert main.plan({}, {}, now) == []
