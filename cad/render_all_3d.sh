#!/usr/bin/env bash
# Re-render all Cyclops variant STLs with 3D-printed effect (centered, colored, FDM texture, shadows)
set -u
STL=~/dev/cyclops/cad/stl
OUT=~/dev/cyclops/cad/renders
mkdir -p "$OUT"

render() {
  local stl="$1" color="$2" name="$3"
  blender-render "$STL/$stl" --color $color --samples 128 --size 1920 1080 \
    --output "$OUT/$name.png" >/dev/null 2>&1
  echo "done: $name ($?)"
}

render arduino_body.stl "0.05 0.20 0.20 1" arduino_body
render eye_body.stl    "0.25 0.15 0.35 1" eye_body
render fin_body.stl    "0.10 0.25 0.40 1" fin_body
render manta_body.stl  "0.15 0.15 0.17 1" manta_body
render pebble_body.stl "0.20 0.22 0.25 1" pebble_body
render pendant_body.stl "0.35 0.25 0.15 1" pendant_body
render pendant_v3_antenna_body.stl "0.35 0.12 0.10 1" pendant_v3_antenna_body
render skeleton_body.stl "0.12 0.12 0.14 1" skeleton_body
render tech_body.stl   "0.10 0.30 0.15 1" tech_body
render v2_body.stl     "0.12 0.18 0.35 1" v2_body
render xiao_body.stl   "0.30 0.15 0.35 1" xiao_body
render xiao_v1_pebble_body.stl "0.35 0.28 0.12 1" xiao_v1_pebble_body
render xiao_v2_leaf_body.stl  "0.12 0.32 0.18 1" xiao_v2_leaf_body
render xiao_v3_gem_body.stl   "0.35 0.10 0.30 1" xiao_v3_gem_body
render xiao_v4_temple_body.stl "0.15 0.22 0.35 1" xiao_v4_temple_body
render arduino_all.stl "0.05 0.20 0.20 1" arduino_all
render v2_all.stl      "0.12 0.18 0.35 1" v2_all
render xiao_all.stl    "0.30 0.15 0.35 1" xiao_all

echo "ALL DONE"
