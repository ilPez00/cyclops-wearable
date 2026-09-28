# Vendor reference geometry — Seeed Studio (XIAO ESP32-S3 Sense)

Downloaded 2026-09-28 from the Seeed Studio wiki page
<https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/> ("Resources" →
"Mechanical Design" for the Sense). These are Seeed's own published design
files, kept here so the case redesign (docs/44) works from the vendor's geometry
instead of guessed numbers.

| File | Origin (files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/) | What it is |
|---|---|---|
| `XIAO_ESP32S3_v1.1_Dimensioning.dxf` | `XIAO_ESP32S3_v1.1_Dimensioning.dxf` | board 2D dimensioned drawing |
| `Sense_TOP.dxf`, `Sense_BOTTOM.dxf` | `TOP.dxf`, `BOTTOM.dxf` | Sense assembly 2D dims (top/bottom) |
| `Sense_ExpBoard_top.dxf`, `Sense_ExpBoard_bot.dxf` | `XIAO_ESP32S3_ExpBoard_v1.0_top.dxf`, `…_bot.dxf` | camera/mic/SD **expansion board** 2D dims |
| `3d/Seeed Studio XIAO-ESP32-S3-Sense.step` | `seeed-studio-xiao-esp32s3-sense-3d_model.zip` | 3D assembly (extracted; the zip itself is git-ignored) |
| `sense-housing-top.stp`, `sense-housing-bottom.stp` | `XIAO-ESP32S3-Sense-housing-design(top).stp`, `…(bottom).stp` | Seeed's own 3D-printable shell |

Caveats that matter (docs/44 §3): each of these files contains **several bodies
or views laid out side by side**, so a plain bounding box measures the sheet, not
a part. Per-body numbers require a real STEP/DXF viewer; the numbers currently in
docs/44 §2 came from a grid-cluster heuristic and are marked accordingly.

Not committed (re-downloadable, 8.8 MB): `sense-3d-model.zip` and its preview
images — see `.gitignore` in this directory.

Re-download (all of them, from a clean checkout):

```bash
B=https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res
curl -sLO "$B/XIAO_ESP32S3_v1.1_Dimensioning.dxf"
curl -sLO "$B/TOP.dxf" -o Sense_TOP.dxf
curl -sLO "$B/BOTTOM.dxf" -o Sense_BOTTOM.dxf
curl -sLO "$B/XIAO_ESP32S3_ExpBoard_v1.0_top.dxf" -o Sense_ExpBoard_top.dxf
curl -sLO "$B/XIAO_ESP32S3_ExpBoard_v1.0_bot.dxf" -o Sense_ExpBoard_bot.dxf
curl -sL "$B/seeed-studio-xiao-esp32s3-sense-3d_model.zip" -o sense-3d-model.zip
mkdir -p 3d && unzip -o sense-3d-model.zip -d 3d
curl -sL "$B/XIAO-ESP32S3-Sense-housing-design(top).stp" -o sense-housing-top.stp
curl -sL "$B/XIAO-ESP32S3-Sense-housing-design(bottom).stp" -o sense-housing-bottom.stp
```
