"""Builds a tiny synthetic OSM file with pyosmium (no download, no real data)."""
import osmium
from osmium.osm.mutable import Node, Way

NODES = [
    # id, lon, lat, tags
    (1, -97.74, 30.27, {"name": "Smile Dental Austin", "amenity": "dentist", "website": "https://www.smiledentalaustin.com/contact",
                        "addr:city": "Austin", "addr:postcode": "78701", "alt_name": "Smile Dental; Austin Smiles"}),
    (2, -97.75, 30.28, {"name": "Joe's Bakery", "shop": "bakery", "contact:website": "joesbakery.com",
                        "addr:city": "Austin", "addr:postcode": "78702"}),
    (3, -97.76, 30.29, {"name": "Chain Coffee", "amenity": "cafe", "website": "https://chaincoffee.com",
                        "brand": "Chain Coffee", "brand:wikidata": "Q1", "addr:city": "Austin"}),
    (4, -97.77, 30.30, {"name": "Social Salon", "shop": "hairdresser", "website": "https://www.facebook.com/socialsalon",
                        "addr:city": "Austin"}),
    (5, -97.78, 30.31, {"shop": "yes", "website": "https://noname.com"}),
    (6, -97.79, 30.32, {"name": "Wix Florist", "shop": "florist", "website": "https://wixflorist.wixsite.com/shop", "addr:city": "Austin"}),
    (7, -97.80, 30.33, {"name": "No Website Cafe", "amenity": "cafe", "addr:city": "Austin"}),
    (8, -97.81, 30.34, {"name": "Brasserie Lyon GmbH", "amenity": "restaurant", "url": "http://www.brasserie-lyon.com/",
                        "addr:city": "Lyon", "addr:postcode": "69001"}),
]


def write(path: str):
    with osmium.SimpleWriter(path) as w:
        for i, lon, lat, tags in NODES:
            w.add_node(Node(id=i, location=(lon, lat), tags=tags))
        for i in (101, 102, 103):
            w.add_node(Node(id=i, location=(-97.0 + i / 1000, 30.0)))
        w.add_way(Way(id=50, nodes=[101, 102, 103], tags={"name": "Way Office", "office": "company",
                                                          "website": "https://wayoffice.com", "addr:city": "Austin"}))
