"""Cyclops — wearable AI note-taker enclosure. Blender-native.

Three aesthetic variants:
  eye    cyclops iris groove around screen (default)
  fin    grip ridges on sides
  manta  pure smooth, no accents

Run:  VARIANT=eye blender --background --python blender_generate.py

Output: .blend + STLs in cad/ and cad/stl/
"""

import os, math
import bpy  # noqa: E402

# ── HW ref ───────────────────────────────────────────────
WALL = 1.8
SCREEN_GLASS = 28.0

# body outer (after bevel these round inward ~4mm per face)
BODY_L = 42
BODY_W = 36
BODY_H = 14

FLOOR_T = 2.2
POCKET_H = BODY_H - FLOOR_T - 1.0

BTN_D = 6.0; BTN_Y = [-6, 0, 6]
USB_W, USB_H = 9.0, 4.5; MIC_D = 3.0

BEVEL_R = 4.0


def clean():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)


def cube(sx, sy, sz, name='Cube'):
    """Axis-aligned box, total size = sx × sy × sz, centered at origin."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object; o.name = name
    o.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    return o


def cyl(d, h, name='Cyl'):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, depth=h, radius=d/2)
    o = bpy.context.active_object; o.name = name
    return o


def apply_mod(obj, name):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=name)


def sub(target, cutter):
    m = target.modifiers.new('B_DIFF', 'BOOLEAN')
    m.operation = 'DIFFERENCE'; m.object = cutter
    apply_mod(target, 'B_DIFF')
    bpy.data.objects.remove(cutter, do_unlink=True)


def union(target, other):
    m = target.modifiers.new('B_UNION', 'BOOLEAN')
    m.operation = 'UNION'; m.object = other
    apply_mod(target, 'B_UNION')
    bpy.data.objects.remove(other, do_unlink=True)


def add_bevel(obj, r, segs=5):
    m = obj.modifiers.new('B', 'BEVEL')
    m.width = r; m.segments = segs
    m.limit_method = 'ANGLE'; m.angle_limit = math.radians(30)
    apply_mod(obj, 'B')


def shade_smooth(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()


def assign_mat(obj, color, rough=0.4, metal=0.0, name='Mat'):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    b = mat.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = color
        b.inputs['Roughness'].default_value = rough
        b.inputs['Metallic'].default_value = metal
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


# ═══════════════════════════════════════════════════════════
#  BODY
# ═══════════════════════════════════════════════════════════
def build_body(variant):
    # ── rounded outer shell ──
    body = cube(BODY_L, BODY_W, BODY_H, 'Body')
    add_bevel(body, BEVEL_R)

    # ergonomic taper (narrower at bottom)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    for v in body.data.vertices:
        if v.co.z < -0.3 * BODY_H:
            v.select = True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.transform.resize(value=(0.88, 0.88, 1.0), orient_type='LOCAL')
    bpy.ops.object.mode_set(mode='OBJECT')

    # ── hollow interior ──
    pocket = cube(BODY_L - 2*WALL, BODY_W - 2*WALL, POCKET_H, 'Pocket')
    pocket.location.z = FLOOR_T + POCKET_H / 2
    sub(body, pocket)

    # ── screen well ──
    recess = cube(SCREEN_GLASS, SCREEN_GLASS, 1.8, 'Recess')
    recess.location.z = BODY_H / 2 - 0.5
    sub(body, recess)

    # ── USB-C port ──
    usb = cube(2.5, USB_W, USB_H, 'USB')
    usb.location = (-BODY_L / 2, 0, FLOOR_T / 2 + 0.3)
    sub(body, usb)

    # ── tactile buttons ──
    for i, y in enumerate(BTN_Y):
        btn = cyl(BTN_D, 5.0, f'Btn{i}')
        btn.location = (BODY_L / 2, y, FLOOR_T + 0.5)
        sub(body, btn)

    # ── microphone port ──
    mic = cyl(MIC_D, WALL + 2, 'Mic')
    mic.location = (0, -BODY_W / 2, BODY_H * 0.45)
    mic.rotation_euler.x = math.radians(90)
    sub(body, mic)

    # ── lanyard loop ──
    bpy.ops.mesh.primitive_torus_add(
        major_radius=4.5, minor_radius=2.0,
        major_segments=32, minor_segments=12,
        location=(-BODY_L, 0, BODY_H / 2 - 2)
    )
    loop = bpy.context.active_object; loop.name = 'LanyardLoop'
    shade_smooth(loop)
    bridge = cube(3.5, 6.0, 3.0, 'LoopBridge')
    bridge.location = (-BODY_L / 2 + 2, 0, BODY_H / 2 - 2)
    union(body, bridge)
    union(body, loop)

    # ── variant-specific ──
    if variant == 'eye':
        iris = cyl(SCREEN_GLASS + 3, 0.6, 'Iris')
        iris.location.z = BODY_H / 2
        sub(body, iris)
    elif variant == 'fin':
        for sx in [-1, 1]:
            for sy in [-1, 1]:
                f = cube(2.0, 5.0, 3.0, f'Fin{sx}{sy}')
                f.location = (sx * BODY_L / 2 * 0.72,
                              sy * BODY_W / 2 * 0.72,
                              BODY_H * 0.4)
                union(body, f)

    shade_smooth(body)
    return body


# ═══════════════════════════════════════════════════════════
#  LID  (screen bezel frame)
# ═══════════════════════════════════════════════════════════
def build_lid(_variant):
    lw, lh, lt = SCREEN_GLASS + 5, SCREEN_GLASS + 5, 2.5
    lid = cube(lw, lh, lt, 'Lid')
    add_bevel(lid, 2.0)
    win = cube(SCREEN_GLASS - 1.5, SCREEN_GLASS - 1.5, lt + 1, 'Win')
    win.location.z = -0.5
    sub(lid, win)
    shade_smooth(lid)
    return lid


# ═══════════════════════════════════════════════════════════
def export_stl(obj, path):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.wm.stl_export(
        filepath=path, export_selected_objects=True,
        global_scale=1.0, use_scene_unit=True, ascii_format=False,
    )
    obj.select_set(False)


def main():
    variant = os.environ.get('VARIANT', 'eye')
    do_stl = os.environ.get('EXPORT_STL', '1') == '1'
    out = os.path.dirname(os.path.abspath(__file__))

    clean()
    body = build_body(variant)
    lid = build_lid(variant)
    lid.location = (BODY_L + 8, 0, 0)

    assign_mat(body, (0.12, 0.12, 0.14, 1), rough=0.5, name='Body')
    assign_mat(lid,  (0.20, 0.20, 0.22, 1), rough=0.3, metal=0.03, name='Lid')

    blend_path = os.path.join(out, f'cyclops_{variant}.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f'[cyclops]  {blend_path}')

    if do_stl:
        sd = os.path.join(out, 'stl')
        os.makedirs(sd, exist_ok=True)
        export_stl(body, os.path.join(sd, f'{variant}_body.stl'))
        export_stl(lid,  os.path.join(sd, f'{variant}_lid.stl'))
        print(f'[cyclops]  STL -> {sd}/')

    print(f'[cyclops]  variant={variant}  done')


if __name__ == '__main__':
    main()
