"""
Explore Austrian postal code → Bezirk mapping options.
Tests pgeocode (GeoNames data) against real venue addresses.
"""
import re
import pgeocode

nomi = pgeocode.Nominatim("AT")

# Real PLZ from our venue addresses
test_cases = [
    ("1220", "Wien - Donaustadt"),
    ("1210", "Wien - Floridsdorf"),
    ("1130", "Wien - Hietzing"),
    ("2700", "Wiener Neustadt"),
    ("4600", "Wels"),
    ("8010", "Graz"),
    ("5020", "Salzburg"),
    ("6020", "Innsbruck"),
    ("9020", "Klagenfurt"),
    ("6900", "Bregenz"),
    ("7000", "Eisenstadt"),
    ("3100", "St. Pölten"),
    ("4020", "Linz"),
    ("2460", "Bruckan der Leitha"),  # Bruck/Leitha Bezirk
    ("3430", "Tulln"),
    ("2320", "Schwechat"),
    ("3500", "Krems"),
    ("2170", "Poysdorf / Mistelbach"),
    ("2130", "Mistelbach"),
    ("8200", "Gleisdorf / Graz-Umgebung"),
    ("8700", "Leoben / Murtal"),
    ("9500", "Villach"),
    ("5760", "Saalfelden / Zell am See"),
]

print(f"{'PLZ':<6} {'Expected':<30} {'place_name':<25} {'state_name':<20} {'county_name'}")
print("-" * 110)
for plz, expected in test_cases:
    r = nomi.query_postal_code(plz)
    print(f"{plz:<6} {expected:<30} {str(r.place_name):<25} {str(r.state_name):<20} {r.county_name}")

print()
print("=== All columns returned ===")
r = nomi.query_postal_code("2700")
print(r)
