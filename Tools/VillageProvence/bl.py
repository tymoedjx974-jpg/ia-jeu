"""Aperçu Blender (Cycles) : matériaux PBR, maillages, instances, ciel provençal."""
import os, math
import numpy as np
import bpy
from materials import MATS, TERRAIN_LAYERS

TEXDIR = os.path.abspath("tex")
_img_cache = {}
_mat_cache = {}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _img_cache.clear()
    _mat_cache.clear()


def img(name, noncolor=False):
    key = (name, noncolor)
    if key in _img_cache:
        return _img_cache[key]
    path = os.path.join(TEXDIR, name)
    im = bpy.data.images.load(path, check_existing=True)
    if noncolor:
        im.colorspace_settings.name = "Non-Color"
    _img_cache[key] = im
    return im


def _tex_node(nt, image, x, y, uv=None, interp="Linear"):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = image
    n.interpolation = interp
    n.location = (x, y)
    if uv is not None:
        nt.links.new(uv, n.inputs["Vector"])
    return n


def _dx_normal(nt, ncol_out, x, y, strength=1.0):
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (x, y)
    nt.links.new(ncol_out, sep.inputs["Color"])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    inv.location = (x + 150, y - 60)
    nt.links.new(sep.outputs["Green"], inv.inputs[1])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    comb.location = (x + 300, y)
    nt.links.new(sep.outputs["Red"], comb.inputs["Red"])
    nt.links.new(inv.outputs[0], comb.inputs["Green"])
    nt.links.new(sep.outputs["Blue"], comb.inputs["Blue"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.location = (x + 450, y)
    nm.inputs["Strength"].default_value = strength
    nt.links.new(comb.outputs["Color"], nm.inputs["Color"])
    return nm.outputs["Normal"]


def material(name):
    if name in _mat_cache:
        return _mat_cache[name]
    spec = MATS.get(name, dict(kind="opaque", tex=None))
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (1400, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (1000, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    kind = spec["kind"]
    if kind == "flat":
        bsdf.inputs["Base Color"].default_value = (*spec["color"], 1)
        bsdf.inputs["Roughness"].default_value = spec["rough"]
    elif kind == "glass":
        bsdf.inputs["Base Color"].default_value = (*spec["color"], 1)
        bsdf.inputs["Roughness"].default_value = spec["rough"]
        bsdf.inputs["Specular IOR Level"].default_value = 0.6
    elif kind == "emissive":
        bsdf.inputs["Base Color"].default_value = (0.9, 0.85, 0.7, 1)
        bsdf.inputs["Roughness"].default_value = 0.2
        bsdf.inputs["Emission Color"].default_value = (*spec["color"], 1)
        bsdf.inputs["Emission Strength"].default_value = spec.get("strength", 0.0)
    elif kind == "terrain":
        _terrain_material(nt, bsdf)
    else:
        tex = spec["tex"]
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = "UV"
        uvn.location = (-1200, 0)
        bc = _tex_node(nt, img(f"{tex}_BC.png"), -900, 300, uvn.outputs["UV"])
        nmap = _tex_node(nt, img(f"{tex}_N.png", True), -900, -300, uvn.outputs["UV"])
        orm_path = os.path.join(TEXDIR, f"{tex}_ORM.png")
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        vc.location = (-900, 650)
        inst = nt.nodes.new("ShaderNodeAttribute")
        inst.attribute_type = "INSTANCER"
        inst.attribute_name = "tint_inv"
        inst.location = (-900, 850)
        inv = nt.nodes.new("ShaderNodeMix")
        inv.data_type = "RGBA"
        inv.blend_type = "SUBTRACT"
        inv.inputs["Factor"].default_value = 1.0
        inv.inputs[6].default_value = (1, 1, 1, 1)
        nt.links.new(inst.outputs["Color"], inv.inputs[7])
        inv.location = (-650, 850)
        # la teinte d'instance ne s'applique qu'aux sommets d'alpha 1 (pièces peintes)
        ienable = nt.nodes.new("ShaderNodeMix")
        ienable.data_type = "RGBA"
        ienable.location = (-650, 1000)
        ienable.inputs[6].default_value = (1, 1, 1, 1)
        nt.links.new(vc.outputs["Alpha"], ienable.inputs["Factor"])
        nt.links.new(inv.outputs[2], ienable.inputs[7])
        tint = nt.nodes.new("ShaderNodeMix")
        tint.data_type = "RGBA"
        tint.blend_type = "MULTIPLY"
        tint.inputs["Factor"].default_value = 1.0
        nt.links.new(vc.outputs["Color"], tint.inputs[6])
        nt.links.new(ienable.outputs[2], tint.inputs[7])
        tint.location = (-450, 700)
        if os.path.exists(orm_path):
            orm = _tex_node(nt, img(f"{tex}_ORM.png", True), -900, 0, uvn.outputs["UV"])
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            sep.location = (-600, 0)
            nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
            mask = sep.outputs["Blue"]
            rough = sep.outputs["Green"]
            ao = sep.outputs["Red"]
        else:
            mask = None
            rough = None
            ao = None
        # couleur = BC * mix(1, teinte, masque)
        mixm = nt.nodes.new("ShaderNodeMix")
        mixm.data_type = "RGBA"
        mixm.location = (-250, 500)
        mixm.inputs[6].default_value = (1, 1, 1, 1)
        nt.links.new(tint.outputs[2], mixm.inputs[7])
        if mask is not None and kind not in ("foliage", "masked"):
            nt.links.new(mask, mixm.inputs["Factor"])
        else:
            mixm.inputs["Factor"].default_value = 1.0
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        mul.location = (0, 400)
        nt.links.new(bc.outputs["Color"], mul.inputs[6])
        nt.links.new(mixm.outputs[2], mul.inputs[7])
        col_out = mul.outputs[2]
        if "base_tint" in spec:
            bt = nt.nodes.new("ShaderNodeMix")
            bt.data_type = "RGBA"
            bt.blend_type = "MULTIPLY"
            bt.inputs["Factor"].default_value = 1.0
            bt.inputs[7].default_value = (*spec["base_tint"], 1)
            nt.links.new(col_out, bt.inputs[6])
            col_out = bt.outputs[2]
        if ao is not None:
            aom = nt.nodes.new("ShaderNodeMix")
            aom.data_type = "RGBA"
            aom.blend_type = "MULTIPLY"
            aom.inputs["Factor"].default_value = 0.6
            aom.location = (250, 400)
            nt.links.new(col_out, aom.inputs[6])
            nt.links.new(ao, aom.inputs[7])
            col_out = aom.outputs[2]
        nt.links.new(col_out, bsdf.inputs["Base Color"])
        if rough is not None:
            rs = nt.nodes.new("ShaderNodeMath")
            rs.operation = "MULTIPLY"
            rs.inputs[1].default_value = spec.get("rough_scale", 1.0)
            nt.links.new(rough, rs.inputs[0])
            nt.links.new(rs.outputs[0], bsdf.inputs["Roughness"])
        else:
            bsdf.inputs["Roughness"].default_value = 0.7
        bsdf.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
        nt.links.new(_dx_normal(nt, nmap.outputs["Color"], -600, -300, 1.0), bsdf.inputs["Normal"])
        if kind in ("foliage", "masked"):
            nt.links.new(bc.outputs["Alpha"], bsdf.inputs["Alpha"])
            if kind == "foliage":
                bsdf.inputs["Subsurface Weight"].default_value = 0.0
                bsdf.inputs["Transmission Weight"].default_value = 0.0
                # translucidité douce des feuilles
                tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
                tr.location = (1000, -400)
                nt.links.new(col_out, tr.inputs["Color"])
                mix = nt.nodes.new("ShaderNodeMixShader")
                mix.location = (1200, -100)
                mix.inputs["Fac"].default_value = 0.25
                nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
                nt.links.new(tr.outputs["BSDF"], mix.inputs[2])
                transp = nt.nodes.new("ShaderNodeBsdfTransparent")
                mix2 = nt.nodes.new("ShaderNodeMixShader")
                mix2.location = (1300, -100)
                nt.links.new(bc.outputs["Alpha"], mix2.inputs["Fac"])
                nt.links.new(transp.outputs["BSDF"], mix2.inputs[1])
                nt.links.new(mix.outputs["Shader"], mix2.inputs[2])
                nt.links.new(mix2.outputs["Shader"], out.inputs["Surface"])
                bsdf.inputs["Roughness"].default_value = 0.55
                try:
                    nt.links.remove(bsdf.inputs["Roughness"].links[0])
                except Exception:
                    pass
        if kind == "water":
            bsdf.inputs["Roughness"].default_value = spec["rough"]
            bsdf.inputs["Base Color"].default_value = (*spec["color"], 1)
            for l in list(bsdf.inputs["Base Color"].links):
                nt.links.remove(l)
            for l in list(bsdf.inputs["Roughness"].links):
                nt.links.remove(l)
    _mat_cache[name] = m
    return m


def _terrain_material(nt, bsdf):
    """Mélange de 8 couches pilotées par deux attributs de couleur (W0, W1)."""
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "UV"
    uvn.location = (-2400, 0)
    w0 = nt.nodes.new("ShaderNodeVertexColor")
    w0.layer_name = "W0"
    w0.location = (-2400, 900)
    w1 = nt.nodes.new("ShaderNodeVertexColor")
    w1.layer_name = "W1"
    w1.location = (-2400, 700)
    s0 = nt.nodes.new("ShaderNodeSeparateColor")
    s0.location = (-2200, 900)
    s1 = nt.nodes.new("ShaderNodeSeparateColor")
    s1.location = (-2200, 700)
    nt.links.new(w0.outputs["Color"], s0.inputs["Color"])
    nt.links.new(w1.outputs["Color"], s1.inputs["Color"])
    weights = [s0.outputs["Red"], s0.outputs["Green"], s0.outputs["Blue"], w0.outputs["Alpha"],
               s1.outputs["Red"], s1.outputs["Green"], s1.outputs["Blue"], w1.outputs["Alpha"]]
    # variation macro (casse la répétition)
    mac = nt.nodes.new("ShaderNodeTexNoise")
    mac.inputs["Scale"].default_value = 0.08
    mac.inputs["Detail"].default_value = 3
    mac.location = (-2400, -600)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-2600, -600)
    nt.links.new(tc.outputs["Object"], mac.inputs["Vector"])
    acc_c = acc_r = acc_n = None
    for i, layer in enumerate(TERRAIN_LAYERS):
        y = 1200 - i * 420
        bc = _tex_node(nt, img(f"{layer}_BC.png"), -1900, y, uvn.outputs["UV"])
        orm = _tex_node(nt, img(f"{layer}_ORM.png", True), -1900, y - 140, uvn.outputs["UV"])
        nm = _tex_node(nt, img(f"{layer}_N.png", True), -1900, y - 280, uvn.outputs["UV"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
        wc = nt.nodes.new("ShaderNodeMix")
        wc.data_type = "RGBA"
        wc.blend_type = "MULTIPLY"
        nt.links.new(weights[i], wc.inputs["Factor"])
        wc.inputs[6].default_value = (0, 0, 0, 1)
        nt.links.new(bc.outputs["Color"], wc.inputs[7])
        wc.blend_type = "MIX"
        wr = nt.nodes.new("ShaderNodeMath")
        wr.operation = "MULTIPLY"
        nt.links.new(sep.outputs["Green"], wr.inputs[0])
        nt.links.new(weights[i], wr.inputs[1])
        wn = nt.nodes.new("ShaderNodeMix")
        wn.data_type = "RGBA"
        nt.links.new(weights[i], wn.inputs["Factor"])
        wn.inputs[6].default_value = (0, 0, 0, 1)
        nt.links.new(nm.outputs["Color"], wn.inputs[7])
        if acc_c is None:
            acc_c, acc_r, acc_n = wc.outputs[2], wr.outputs[0], wn.outputs[2]
        else:
            a = nt.nodes.new("ShaderNodeMix")
            a.data_type = "RGBA"
            a.blend_type = "ADD"
            a.inputs["Factor"].default_value = 1.0
            nt.links.new(acc_c, a.inputs[6])
            nt.links.new(wc.outputs[2], a.inputs[7])
            acc_c = a.outputs[2]
            r = nt.nodes.new("ShaderNodeMath")
            r.operation = "ADD"
            nt.links.new(acc_r, r.inputs[0])
            nt.links.new(wr.outputs[0], r.inputs[1])
            acc_r = r.outputs[0]
            nn = nt.nodes.new("ShaderNodeMix")
            nn.data_type = "RGBA"
            nn.blend_type = "ADD"
            nn.inputs["Factor"].default_value = 1.0
            nt.links.new(acc_n, nn.inputs[6])
            nt.links.new(wn.outputs[2], nn.inputs[7])
            acc_n = nn.outputs[2]
    macm = nt.nodes.new("ShaderNodeMapRange")
    macm.inputs["To Min"].default_value = 0.82
    macm.inputs["To Max"].default_value = 1.12
    nt.links.new(mac.outputs["Fac"], macm.inputs["Value"])
    mm = nt.nodes.new("ShaderNodeMix")
    mm.data_type = "RGBA"
    mm.blend_type = "MULTIPLY"
    mm.inputs["Factor"].default_value = 1.0
    nt.links.new(acc_c, mm.inputs[6])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(macm.outputs["Result"], comb.inputs["Red"])
    nt.links.new(macm.outputs["Result"], comb.inputs["Green"])
    nt.links.new(macm.outputs["Result"], comb.inputs["Blue"])
    nt.links.new(comb.outputs["Color"], mm.inputs[7])
    nt.links.new(mm.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(acc_r, bsdf.inputs["Roughness"])
    nt.links.new(_dx_normal(nt, acc_n, -300, -800, 1.0), bsdf.inputs["Normal"])


def mesh_object(name, arrays, collection=None, location=(0, 0, 0), terrain_weights=None):
    """Crée un objet Blender à partir d'un dictionnaire {matériau: {P,N,UV,C,I}}."""
    mats = list(arrays.keys())
    P = np.concatenate([arrays[m]["P"] for m in mats]).astype(np.float32)
    Nn = np.concatenate([arrays[m]["N"] for m in mats]).astype(np.float32)
    UV = np.concatenate([arrays[m]["UV"] for m in mats]).astype(np.float32)
    C = np.concatenate([arrays[m]["C"] for m in mats])
    offs = np.cumsum([0] + [len(arrays[m]["P"]) for m in mats[:-1]])
    I = np.concatenate([arrays[m]["I"] + o for m, o in zip(mats, offs)]).astype(np.int32)
    MI = np.concatenate([np.full(len(arrays[m]["I"]), k, np.int32) for k, m in enumerate(mats)])
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(P))
    me.vertices.foreach_set("co", P.ravel())
    me.loops.add(len(I) * 3)
    me.loops.foreach_set("vertex_index", I.ravel())
    me.polygons.add(len(I))
    me.polygons.foreach_set("loop_start", np.arange(0, len(I) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("material_index", MI)
    me.polygons.foreach_set("use_smooth", np.ones(len(I), bool))
    uvl = me.uv_layers.new(name="UV")
    uv_loop = UV[I.ravel()].copy()
    uv_loop[:, 1] = 1.0 - uv_loop[:, 1]
    uvl.data.foreach_set("uv", uv_loop.ravel())
    ca = me.color_attributes.new("Col", "BYTE_COLOR", "POINT")
    ca.data.foreach_set("color_srgb", (C.astype(np.float32) / 255.0).ravel())
    if terrain_weights is not None:
        for k, wname in enumerate(("W0", "W1")):
            wa = me.color_attributes.new(wname, "FLOAT_COLOR", "POINT")
            wa.data.foreach_set("color", terrain_weights[:, 4 * k:4 * k + 4].astype(np.float32).ravel())
    me.update()
    me.normals_split_custom_set_from_vertices(Nn)
    for m in mats:
        me.materials.append(material(m))
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def instance_points(name, proto_obj, positions, yaws, scales=None, tints=None, collection=None):
    """Instancie un objet prototype sur des points via Geometry Nodes (attribut de teinte par instance)."""
    n = len(positions)
    me = bpy.data.meshes.new(name + "_pts")
    me.vertices.add(n)
    me.vertices.foreach_set("co", np.asarray(positions, np.float32).ravel())
    rot = me.attributes.new("rot", "FLOAT_VECTOR", "POINT")
    r = np.zeros((n, 3), np.float32)
    r[:, 2] = yaws
    rot.data.foreach_set("vector", r.ravel())
    sc = me.attributes.new("scl", "FLOAT_VECTOR", "POINT")
    s = np.ones((n, 3), np.float32) if scales is None else np.asarray(scales, np.float32).reshape(n, -1)
    if s.shape[1] == 1:
        s = np.repeat(s, 3, 1)
    sc.data.foreach_set("vector", s.ravel())
    ti = me.attributes.new("tint_inv", "FLOAT_COLOR", "POINT")
    t = np.ones((n, 4), np.float32)
    if tints is not None:
        t[:, :3] = np.asarray(tints, np.float32)[:, :3]
    lin = np.where(t[:, :3] <= 0.04045, t[:, :3] / 12.92, ((t[:, :3] + 0.055) / 1.055) ** 2.4)
    t[:, :3] = 1.0 - lin
    ti.data.foreach_set("color", t.ravel())
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    mod = ob.modifiers.new("inst", "NODES")
    ng = bpy.data.node_groups.new(name + "_gn", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = ng.nodes.new("NodeGroupInput")
    go = ng.nodes.new("NodeGroupOutput")
    iop = ng.nodes.new("GeometryNodeInstanceOnPoints")
    oi = ng.nodes.new("GeometryNodeObjectInfo")
    oi.inputs["Object"].default_value = proto_obj
    ar = ng.nodes.new("GeometryNodeInputNamedAttribute")
    ar.data_type = "FLOAT_VECTOR"
    ar.inputs["Name"].default_value = "rot"
    asc = ng.nodes.new("GeometryNodeInputNamedAttribute")
    asc.data_type = "FLOAT_VECTOR"
    asc.inputs["Name"].default_value = "scl"
    ng.links.new(gi.outputs[0], iop.inputs["Points"])
    ng.links.new(oi.outputs["Geometry"], iop.inputs["Instance"])
    ng.links.new(ar.outputs["Attribute"], iop.inputs["Rotation"])
    ng.links.new(asc.outputs["Attribute"], iop.inputs["Scale"])
    ng.links.new(iop.outputs["Instances"], go.inputs[0])
    mod.node_group = ng
    proto_obj.hide_render = True
    proto_obj.hide_viewport = True
    return ob


def setup_world(sun_elev=28.0, sun_azim=235.0, strength=1.0, exposure=-0.9):
    sc = bpy.context.scene
    if sc.world is None:
        sc.world = bpy.data.worlds.new("Ciel")
    w = sc.world
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(sun_elev)
    sky.sun_rotation = math.radians(sun_azim)
    sky.altitude = 350.0
    sky.air_density = 1.0
    sky.dust_density = 0.45
    sky.ozone_density = 1.0
    sky.sun_intensity = 1.0
    sky.sun_disc = False
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.42 * strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    # soleil (le ciel Nishita donne déjà la couleur ; lampe pour des ombres nettes)
    sun = bpy.data.lights.new("Soleil", "SUN")
    sun.energy = 4.6 * strength
    sun.angle = math.radians(0.6)
    sun.color = (1.0, 0.9, 0.78)
    so = bpy.data.objects.new("Soleil", sun)
    so.rotation_euler = (math.radians(90 - sun_elev), 0, math.radians(sun_azim + 180 - 90))
    # direction : azimut mesuré depuis le nord, dans le sens horaire
    az = math.radians(sun_azim)
    el = math.radians(sun_elev)
    d = np.array([math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)])
    so.rotation_euler = (0, 0, 0)
    import mathutils
    so.rotation_euler = mathutils.Vector((-d[0], -d[1], -d[2])).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(so)
    # rotation du soleil du ciel Nishita : 0 = soleil vers -Y ; on aligne sur la lampe
    sky.sun_rotation = math.atan2(d[0], -d[1]) if False else math.radians(sun_azim + 180.0)
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    sc.view_settings.exposure = exposure
    return so


def setup_render(w=1280, h=720, samples=64, path="render.png"):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 16
    sc.cycles.use_adaptive_sampling = True
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.filepath = os.path.abspath(path)
    sc.render.image_settings.file_format = "PNG"
    sc.render.threads_mode = "AUTO"


def camera(loc, look_at, lens=28.0, name="Cam"):
    import mathutils
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start = 0.1
    cam.clip_end = 20000
    ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = mathutils.Vector(look_at) - mathutils.Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    return ob


def haze(start=250.0, depth=9000.0, color=(0.62, 0.70, 0.80), amount=0.55):
    """Brume de lointain (perspective aérienne) par composition avec la passe « mist »."""
    sc = bpy.context.scene
    sc.view_layers[0].use_pass_mist = True
    sc.world.mist_settings.start = start
    sc.world.mist_settings.depth = depth
    sc.world.mist_settings.falloff = "QUADRATIC"
    sc.use_nodes = True
    nt = sc.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new("CompositorNodeRLayers")
    mix = nt.nodes.new("CompositorNodeMixRGB")
    mix.blend_type = "MIX"
    mix.inputs[2].default_value = (*color, 1.0)
    mul = nt.nodes.new("CompositorNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = amount
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Mist"], mul.inputs[0])
    nt.links.new(mul.outputs[0], mix.inputs[0])
    nt.links.new(rl.outputs["Image"], mix.inputs[1])
    nt.links.new(mix.outputs[0], comp.inputs["Image"])


def render(path):
    bpy.context.scene.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)
