"""Télécharge les données réelles : Overture Maps (bâtiments, routes, lieux, occupation du sol) et relief Copernicus 30 m."""
import os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ov import fetch

os.makedirs("data", exist_ok=True)
B = (5.15, 43.865, 5.345, 43.945)  # Roussillon, Vaucluse (+ campagne alentour)
fetch("places", "place", (4.90, 43.70, 6.30, 44.25), columns=["id", "geometry", "names", "basic_category", "taxonomy", "confidence", "operating_status"], out="data/places_region.parquet")
for theme, typ, name in (("base", "land_use", "land_use"), ("base", "land_cover", "land_cover"), ("base", "water", "water"), ("base", "infrastructure", "infrastructure"),
                         ("base", "land", "land"), ("transportation", "segment", "segments"), ("buildings", "building", "buildings")):
    fetch(theme, typ, B, out=f"data/{name}.parquet")
for t in ("N43_00_E004_00", "N43_00_E005_00", "N43_00_E006_00", "N44_00_E004_00", "N44_00_E005_00", "N44_00_E006_00"):
    n = f"Copernicus_DSM_COG_10_{t}_DEM"
    dst = f"data/{n}.tif"
    if not os.path.exists(dst):
        print("relief", t)
        urllib.request.urlretrieve(f"https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif", dst)
print("données prêtes")
