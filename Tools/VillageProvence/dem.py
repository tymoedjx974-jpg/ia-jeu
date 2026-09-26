import sys; sys.path.insert(0,'.')
import numpy as np, tifffile, math
from geo import TF, TB
from scipy.ndimage import map_coordinates
_tiles = {}
def _tile(lat_i, lon_i):
    k=(lat_i,lon_i)
    if k not in _tiles:
        n=f"Copernicus_DSM_COG_10_N{lat_i:02d}_00_E{lon_i:03d}_00_DEM"
        _tiles[k]=tifffile.imread(f"data/{n}.tif").astype(np.float32)
    return _tiles[k]
def sample_lonlat(lon, lat, order=3):
    lon=np.asarray(lon,dtype=np.float64); lat=np.asarray(lat,dtype=np.float64)
    out=np.zeros(lon.shape,dtype=np.float32)
    lat_i=np.floor(lat).astype(int); lon_i=np.floor(lon).astype(int)
    for la,lo in set(zip(lat_i.ravel().tolist(), lon_i.ravel().tolist())):
        t=_tile(la,lo); ny,nx=t.shape
        m=(lat_i==la)&(lon_i==lo)
        # pixel-is-point: pixel centres at lon0 + (i+0.5)/nx ? Copernicus: pixel-is-area, top-left corner = (lo, la+1)
        col=(lon[m]-lo)*nx-0.5; row=(la+1-lat[m])*ny-0.5
        out[m]=map_coordinates(t,[row,col],order=order,mode="nearest")
    return out
def sample_xy(x, y, order=3):
    lon,lat=TB.transform(np.asarray(x,dtype=np.float64), np.asarray(y,dtype=np.float64))
    return sample_lonlat(lon,lat,order)
