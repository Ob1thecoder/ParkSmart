"""
TfNSW Car Park API facility metadata from official documentation.

Each row's first field is the API `facility_id` (string) used in
`GET /v1/carpark?facility=<id>` and in full-list responses — not the TSN.

TSN / transport site numbers are kept in comments for cross-reference.
Warriewood (facility 10): documentation shows a positive latitude; corrected to -33.697777 (NSW).
"""
from __future__ import annotations

# (facility_id, name, lat, lon, suburb, total_spots)
TFNSW_SEED_ROWS: list[tuple[str, str, float, float, str, int]] = [
    # TSN 2155384
    ("1", "Tallawong Station Car Park (Historical Only)", -33.69163, 150.906022, "Tallawong", 1004),
    ("2", "Kellyville Station Car Park (Historical Only)", -33.713514, 150.935304, "Kellyville", 1374),
    ("3", "Bella Vista Station Car Park (Historical Only)", -33.730592, 150.944024, "Bella Vista", 800),
    ("4", "Hills Showground Station Car Park (Historical Only)", -33.72782, 150.987345, "Castle Hill", 600),
    ("5", "Cherrybrook Station Car Park (Historical Only)", -33.736703, 151.031977, "Cherrybrook", 400),
    # TSN 207210
    ("6", "Park&Ride - Gordon Henry St (north)", -33.756009, 151.154528, "Gordon", 213),
    ("7", "Park&Ride - Kiama", -34.672518, 150.854695, "Kiama", 42),
    ("8", "Park&Ride - Gosford", -33.423883, 151.341711, "Gosford", 1057),
    ("9", "Park&Ride - Revesby", -33.95246, 151.014838, "Revesby", 934),
    ("10", "Park&Ride - Warriewood", -33.697777, 151.300667, "Warriewood", 244),
    ("11", "Park&Ride - Narrabeen", -33.713514, 151.297315, "Narrabeen", 46),
    ("12", "Park&Ride - Mona Vale", -33.677276, 151.305146, "Mona Vale", 68),
    ("13", "Park&Ride - Dee Why", -33.752797, 151.286485, "Dee Why", 117),
    ("14", "Park&Ride - West Ryde", -33.807172, 151.090229, "West Ryde", 151),
    ("15", "Park&Ride - Sutherland East Parade", -34.031787, 151.05719, "Sutherland", 373),
    ("16", "Park&Ride - Leppington", -33.9544, 150.8081, "Leppington", 1884),
    ("17", "Park&Ride - Edmondson Park (south)", -33.9693, 150.8587, "Edmondson Park", 1431),
    ("18", "Park&Ride - St Marys", -33.762256, 150.776029, "St Marys", 682),
    ("19", "Park&Ride - Campbelltown Farrow Rd (north)", -34.063835, 150.813929, "Campbelltown", 68),
    ("20", "Park&Ride - Campbelltown Hurley St", -34.063835, 150.813929, "Campbelltown", 118),
    ("21", "Park&Ride - Penrith (at-grade)", -33.750055, 150.696135, "Penrith", 230),
    ("22", "Park&Ride - Penrith (multi-level)", -33.750055, 150.696135, "Penrith", 1144),
    ("23", "Park&Ride - Warwick Farm", -33.91345, 150.935036, "Warwick Farm", 910),
    ("24", "Park&Ride - Schofields", -33.704477, 150.873817, "Schofields", 700),
    ("25", "Park&Ride - Hornsby", -33.702801, 151.098494, "Hornsby", 145),
    ("26", "Park&Ride - Tallawong P1", -33.69163, 150.906022, "Tallawong", 121),
    ("27", "Park&Ride - Tallawong P2", -33.69163, 150.906022, "Tallawong", 455),
    ("28", "Park&Ride - Tallawong P3", -33.69163, 150.906022, "Tallawong", 397),
    ("29", "Park&Ride - Kellyville (north)", -33.713514, 150.935304, "Kellyville", 351),
    ("30", "Park&Ride - Kellyville (south)", -33.713514, 150.935304, "Kellyville", 964),
    ("31", "Park&Ride - Bella Vista", -33.730592, 150.944024, "Bella Vista", 777),
    ("32", "Park&Ride - Hills Showground", -33.72782, 150.987345, "Castle Hill", 584),
    ("33", "Park&Ride - Cherrybrook", -33.736703, 151.031977, "Cherrybrook", 384),
    ("34", "Park&Ride - Lindfield Village Green", -33.775185, 151.169111, "Lindfield", 94),
    ("35", "Park&Ride - Beverly Hills", -33.948849, 151.081692, "Beverly Hills", 200),
    ("36", "Park&Ride - Emu Plains", -33.745527, 150.66987, "Emu Plains", 751),
    ("37", "Park&Ride - Riverwood", -33.952727, 151.050035, "Riverwood", 142),
    ("38", "Park&Ride - North Rocks", -33.765539, 151.014131, "North Rocks", 139),
    ("39", "Park&Ride - Edmondson Park (north)", -33.969123, 150.861594, "Edmondson Park", 917),
    ("486", "Park&Ride - Ashfield", -33.8875506079, 151.125504163, "Ashfield", 225),
    ("487", "Park&Ride - Kogarah", -33.9621493059, 151.132641462, "Kogarah", 259),
    ("488", "Park&Ride - Seven Hills", -33.774430434, 150.936513359, "Seven Hills", 1613),
    ("489", "Park&Ride - Manly Vale (Parent Stop TSN)", -33.786247, 151.26671, "Manly Vale", 142),
    ("490", "Park&Ride - Brookvale", -33.767508, 151.268541, "Brookvale", 246),
]

TFNSW_LEGACY_IDS: dict[str, str] = {
    "6": "tfnsw_gordon",
    "34": "tfnsw_lindfield",
}

TFNSW_LEGACY_NAME_OVERRIDES: dict[str, str] = {
    "6": "Park&Ride - Gordon",
    "34": "Park&Ride - Lindfield",
}

TFNSW_LEGACY_ADDRESS_OVERRIDES: dict[str, str] = {
    "6": "Henry Street, Gordon NSW 2072",
    "34": "Village Green, Lindfield NSW 2070",
}


def slug_address(name: str, suburb: str) -> str:
    return f"{name}, {suburb} NSW"
