"""The index file format. company-domain-finder's src/osm_index.py reads it and pins SCHEMA_VERSION and COLUMNS in a test."""
SCHEMA_VERSION = 1
DDL = """
CREATE TABLE poi (
  name_norm TEXT NOT NULL,   -- compact(core_name(x)) of name, official_name, alt_name, short_name, name:en
  name TEXT NOT NULL,
  website TEXT NOT NULL,     -- https://host/
  domain TEXT NOT NULL,      -- registered domain
  city TEXT,                 -- fold(addr:city)
  postcode TEXT,             -- upper-case letters and digits only
  country TEXT NOT NULL,     -- ISO code of the extract
  lat REAL, lon REAL,        -- nodes only
  osm_type TEXT NOT NULL,    -- n, w or r
  osm_id INTEGER NOT NULL,
  category TEXT              -- amenity=dentist, shop=bakery ...
);
CREATE INDEX poi_name_city ON poi(name_norm, city);
CREATE INDEX poi_name_post ON poi(name_norm, postcode);
CREATE INDEX poi_cat_city ON poi(category, city);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
"""
COLUMNS = ["name_norm", "name", "website", "domain", "city", "postcode", "country", "lat", "lon", "osm_type", "osm_id", "category"]
