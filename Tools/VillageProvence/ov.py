"""Accès aux données ouvertes Overture Maps (S3, sans compte)."""
import os, sys, time
import pyarrow.fs as fs, pyarrow.dataset as ds, pyarrow.compute as pc, pyarrow.parquet as pq

REL = os.environ.get("OVERTURE_RELEASE", "2026-09-23.1")
_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
s3 = fs.S3FileSystem(anonymous=True, region="us-west-2", **({"proxy_options": _proxy} if _proxy else {}))


def dataset(theme, typ):
    return ds.dataset(f"overturemaps-us-west-2/release/{REL}/theme={theme}/type={typ}/", filesystem=s3, format="parquet")


def fetch(theme, typ, bbox, columns=None, out=None):
    t = time.time()
    d = dataset(theme, typ)
    xmin, ymin, xmax, ymax = bbox
    f = (pc.field("bbox", "xmin") < xmax) & (pc.field("bbox", "xmax") > xmin) & (pc.field("bbox", "ymin") < ymax) & (pc.field("bbox", "ymax") > ymin)
    tab = d.to_table(filter=f, columns=columns)
    if out:
        pq.write_table(tab, out)
    print(f"{theme}/{typ}: {tab.num_rows} lignes en {time.time() - t:.0f}s", file=sys.stderr)
    return tab
