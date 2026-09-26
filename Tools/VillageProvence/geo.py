import pyarrow.parquet as pq, shapely, numpy as np, math
from pyproj import Transformer
LON0, LAT0 = 5.2929, 43.9024          # centre du village (Roussillon)
TF = Transformer.from_crs("EPSG:4326", f"+proj=tmerc +lat_0={LAT0} +lon_0={LON0} +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m", always_xy=True)
TB = Transformer.from_crs(f"+proj=tmerc +lat_0={LAT0} +lon_0={LON0} +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m", "EPSG:4326", always_xy=True)
def proj_geom(g):
    return shapely.transform(g, lambda c: np.column_stack(TF.transform(c[:,0], c[:,1])))
def load(name, cols=None):
    rows = pq.read_table(f"data/{name}.parquet", columns=cols).to_pylist()
    for r in rows:
        if "geometry" in r and r["geometry"] is not None:
            r["geom"] = proj_geom(shapely.from_wkb(r["geometry"]))
        st = r.get("source_tags")
        if st is not None and not isinstance(st, dict): r["source_tags"] = dict(st)
    return rows
