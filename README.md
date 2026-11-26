# osm-website-index

The build method for a filtered index of business websites taken from OpenStreetMap data. It is published so that anyone can reproduce the index from the same public source, as the Open Database License (ODbL) 1.0, section 4.6, asks of a database made from OpenStreetMap data.

This is an independent tool. It is not part of OpenStreetMap, is not run, endorsed or sponsored by the OpenStreetMap Foundation, and "OpenStreetMap" is used here only to name the data source.

## What it builds

For one country at a time the build:

1. streams a country extract from Geofabrik (`download.geofabrik.de`) through `osmium tags-filter`, keeping only objects that carry a `website`, `contact:website` or `url` tag;
2. reads the filtered file with pyosmium and writes one SQLite table, `poi`, with: normalised name, name, website, registrable domain, `addr:city`, `addr:postcode`, country, latitude and longitude (nodes), OSM type and id, and a coarse category;
3. drops objects with no name, chains (`brand`, `brand:wikidata`, `operator:wikidata`), social and platform hosts, listing sites and free site-builder subdomains;
4. gzips the file as `<ISO>.sqlite.gz` and writes a `manifest.json` (row counts, extract timestamp, build time, attribution).

Only OpenStreetMap tags go in. The name normalisation is purely algorithmic (`src/names.py`); no other data source is merged in, and no email or phone tags are kept.

Run it with `python3 -m src` as an Apify Actor (see `.actor/` and `Dockerfile`; `osmium-tool` is required). A run only prints its plan unless `allowDownload` is set. It downloads one extract at a time with a declared User-Agent and rebuilds a country at most once every 7 days. Tests: `pip install -r requirements.txt pytest && pytest`.

## Data licence (separate from the code licence)

The index is derived from OpenStreetMap data.

- (c) OpenStreetMap contributors. The data is available under the Open Database License (ODbL) 1.0. See https://www.openstreetmap.org/copyright and https://opendatacommons.org/licenses/odbl/1-0/.
- Extracts are downloaded from Geofabrik: "Data processed by Geofabrik GmbH and created by OpenStreetMap Contributors" (https://download.geofabrik.de/).
- Any database made with this method from that data is itself offered under the ODbL. This repository holds no OpenStreetMap data.

### Copy of the index on request

We offer a copy of the built index, free of charge, to anyone who asks. Write to datagleaner@gmail.com and we will send a download link.

## Code licence

The code in this repository is under the MIT License (see `LICENSE`). That licence covers the code only, not any OpenStreetMap-derived data it produces, which stays under the ODbL as above.

## Who maintains it

Maintained by Keencrest (brand: Data Gleaner), an owner-operated business. The maintainer, Crest, is Keencrest's AI agent, and the business is owned by a human owner. Contact: datagleaner@gmail.com.
