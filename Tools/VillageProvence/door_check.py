"""Vérifie la position des vantaux mobiles : une porte fermée et une porte ouverte (rendu extérieur)."""
import sys, pickle, math
sys.path.insert(0, ".")
import numpy as np
import bl, bpy, scene
from modules import MODULE_BUILDERS
B = pickle.load(open("buildings_out.pkl", "rb"))
dr = B["doors"][int(sys.argv[1]) if len(sys.argv) > 1 else 0]
opened = len(sys.argv) > 2 and sys.argv[2] == "ouverte"
c = np.array([dr["x"], dr["y"]])
bl.reset()
R = 30
bbox = (c[0] - R, c[1] - R, c[0] + R, c[1] + R)
scene.terrain_region(*bbox, step=1, name="Terrain")
scene.load_buildings("buildings_out.pkl", bbox)
scene.load_instances(B["inst"], bbox)
leaf = MODULE_BUILDERS[dr["leaf"]]().arrays()
ob = bl.mesh_object("Vantail", leaf, location=(dr["x"], dr["y"], dr["z"]))
ob.scale = (dr["sx"], 1, 1)
ob.rotation_euler[2] = dr["yaw"] + (math.radians(100) if opened else 0.0)
bl.setup_world(sun_elev=35, sun_azim=200, exposure=0.0)
bl.setup_render(960, 720, samples=24)
yaw = dr["yaw"]
u = np.array([math.cos(yaw), math.sin(yaw)])
inw = np.array([-u[1], u[0]])
mid = c + u * 0.45
cam = mid - inw * 3.2 + u * 0.8
bl.camera((cam[0], cam[1], dr["z"] + 1.6), (mid[0], mid[1], dr["z"] + 1.1), lens=24)
bl.render("renders/porte_%s.png" % ("ouverte" if opened else "fermee"))
