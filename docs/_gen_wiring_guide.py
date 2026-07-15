#!/usr/bin/env python3
"""Generate Cyclops wiring guide as PNG / PDF / SVG from one source of truth.

Covers every documented hardware x screen variant:
  V1  CyclUno      (Arduino Uno)   + I2C SSD1306 128x32  (blue board)   + scrollwheel + 2 btn + 2 LED
  V2  Arduino dev  (Uno/Nano)     + SPI ST7735 128x128  (blue board)    + scrollwheel OR joystick + 2 btn
  V3  XIAO Sense   (wearable)     + I2C SSD1306 128x32  (blue board)   + scrollwheel + 2 btn
  V4  XIAO Sense   (wearable)     + SPI Transparent 1.51" 128x64 (SSD1309) + scrollwheel + 2 btn

Run:  python3 _gen_wiring_guide.py
Out:  cyclops_wiring.svg / cyclops_wiring.pdf / cyclops_wiring.png
      + one PNG per variant (cyclops_vN_*.png)
"""
import cairo, math, os, re

W, H = 1000, 1320          # one variant per page
FONT = "DejaVu Sans"
SCALE = 2                   # default output resolution multiplier (crisp at 2x)
# CyclUno gets an even larger "expanded" poster for print/desk reference
CYCLUNO_EXPAND_SCALE = 3

# ---- colors per signal type ----
C = {
    "i2c": (0.13, 0.55, 0.18),
    "spi": (0.16, 0.36, 0.78),
    "in":  (0.85, 0.45, 0.05),
    "led": (0.78, 0.12, 0.16),
    "pwr": (0.20, 0.20, 0.20),
    "gnd": (0.45, 0.45, 0.45),
    "mic": (0.45, 0.20, 0.60),
    "blk": (0.10, 0.10, 0.10),
}
def rgb(t): return C.get(t, C["blk"])

# ---- data model ----
# mcu_pins: (label, function, type)
# comps: dict name -> {xy:(x,y), pins:[(pinlabel, mcu_target_or_None, type, note)]}
#   mcu_target matches a mcu pin label  -> wire drawn
#   type used for wire color when target None but still wired (rare)
VARIANTS = [
 {
  "tag":"V1", "title":"CyclUno — Arduino Uno dev unit",
  "sub":"I2C SSD1306 128x32 (blue board) · 2 joysticks + 4 buttons · NO encoder/LEDs",
  "mcu":"Arduino Uno / Nano (ATmega328)",
  "mcu_pins":[
    ("A4","OLED SDA (I2C)","i2c"),
    ("A5","OLED SCL (I2C)","i2c"),
    ("5V","OLED VCC","pwr"),
    ("GND","OLED + buttons + joystick GND","gnd"),
    ("A0","J1 VRx (scroll X, analog)","in"),
    ("A1","J1 VRy (scroll Y, analog)","in"),
    ("D2","J1 push = BTN_A (select/REC)","in"),
    ("A2","J2 VRx (analog)","in"),
    ("A3","J2 VRy (analog)","in"),
    ("D3","J2 push = BTN_B (menu/back)","in"),
    ("D4","BTN_B1 (select/REC)","in"),
    ("D5","BTN_B2 (menu/back)","in"),
    ("D6","BTN_B3 (ask agent)","in"),
    ("D7","BTN_B4 (home)","in"),
    ("USB","Serial -> brain @115200","pwr"),
  ],
  "comps":{
    "OLED SSD1306 128x32\\n(I2C, blue board, 0x3C)":{
      "xy":(640,150),
      "pins":[("VCC","5V","pwr",""),("GND","GND","gnd",""),("SDA","A4","i2c",""),("SCL","A5","i2c",""),
              ("RES","","spi","strap pullup->VCC"),("DC","","spi","strap->GND"),("CS","","spi","strap->VCC")]},
    "Joystick 1\\n(primary nav)":{
      "xy":(640,430),
      "pins":[("VRx","A0","in","analog"),("VRy","A1","in","scroll Y / analog"),("SW","D2","in","push = BTN_A"),("+","5V","pwr",""),("GND","GND","gnd","")]},
    "Joystick 2\\n(secondary)":{
      "xy":(640,650),
      "pins":[("VRx","A2","in","analog"),("VRy","A3","in","analog"),("SW","D3","in","push = BTN_B"),("+","5V","pwr",""),("GND","GND","gnd","")]},
    "Button B1\\n(select / REC)":{
      "xy":(640,840),
      "pins":[("SIG","D4","in","active-low"),("GND","GND","gnd","pullup on")]},
    "Button B2\\n(menu / back)":{
      "xy":(640,940),
      "pins":[("SIG","D5","in","active-low"),("GND","GND","gnd","pullup on")]},
    "Button B3\\n(ask agent)":{
      "xy":(640,1030),
      "pins":[("SIG","D6","in","active-low"),("GND","GND","gnd","pullup on")]},
    "Button B4\\n(home)":{
      "xy":(640,1110),
      "pins":[("SIG","D7","in","active-low"),("GND","GND","gnd","pullup on")]},
  },
  "build":"pio run -e cycluno            # compile (~34% flash)\\n"
          "pio run -e cycluno -t upload  # flash (auto-detect port)\\n"
          "python3 demo_cycluno.py       # wired brain demo",
  "notes":"NO rotary encoder / NO LEDs on this build — scroll is the joystick Y axis, select/back\n"
          "are the joystick pushes (or the matching buttons). REC/link state shows on the OLED only.\n"
          "Joysticks: center-locked single step (hold = one move). Same v2 frame protocol as XIAO.\n"
          "J1 = primary nav (scroll + select), J2 = secondary (back/menu). B1..B4 mirror J1/J2 + agent/home.",
 },
 {
  "tag":"V2", "title":"Arduino Uno/Nano dev HUD",
  "sub":"SPI screen (ST7735 128x128 / 128x64 / 128x32, build-selected CS) · scrollwheel OR joystick + 2 buttons",
  "mcu":"Arduino Uno / Nano (ATmega328) — no I2S, HUD-only",
  "mcu_pins":[
    ("D13","SPI SCK","spi"),
    ("D11","SPI MOSI","spi"),
    ("D10","Screen CS (ST7735)","spi"),
    ("D7","Screen CS (128x64)","spi"),
    ("D4","Screen CS (128x32)","spi"),
    ("D9","Screen DC","spi"),
    ("D8","Screen RST","spi"),
    ("D5","BTN_A (pullup)","in"),
    ("D6","BTN_B (pullup)","in"),
    ("D2","Wheel A (INT0)","in"),
    ("D3","Wheel B (INT1)","in"),
    ("D4b","Wheel push (alt 128x32 CS)","in"),
    ("A1","Joy X (analog)","in"),
    ("A2","Joy Y (analog)","in"),
    ("D7b","Joy push (alt 128x64 CS)","in"),
    ("A0","Prox (optional)","in"),
    ("A6","VBAT (divider)","in"),
    ("0/1","TX/RX -> brain @115200","pwr"),
  ],
  "comps":{
    "Screen ST7735 128x128\n(SPI, blue board, 3.3V)":{
      "xy":(640,120),
      "pins":[("VCC","5V","pwr","5V-tolerant"),("GND","GND","gnd",""),("SCK","D13","spi",""),
              ("MOSI","D11","spi",""),("MISO","GND","gnd","nc"),("CS","D10","spi","ST7735"),
              ("DC","D9","spi",""),("RST","D8","spi","")]},
    "Rotary encoder\n(scrollwheel, optional)":{
      "xy":(640,470),
      "pins":[("A","D2","in",""),("B","D3","in",""),("SW","D4b","in","alt CS")]},
    "Joystick\n(optional analog input)":{
      "xy":(640,650),
      "pins":[("X","A1","in",""),("Y","A2","in",""),("SW","D7b","in","alt CS"),
              ("+","5V","pwr",""),("GND","GND","gnd","")]},
    "Button A":{
      "xy":(640,860),
      "pins":[("SIG","D5","in",""),("GND","GND","gnd","pullup")]},
    "Button B":{
      "xy":(640,950),
      "pins":[("SIG","D6","in",""),("GND","GND","gnd","pullup")]},
  },
  "build":"pio run -e arduino_st7735 | arduino_128x64 | arduino_128x32\n"
          "Link: SerialFrameReader / Transport kind=\"serial\" @115200",
  "notes":"Pick ONE role per build: 128x64 CS(D7)=Joy push; 128x32 CS(D4)=Wheel push.\n"
          "Joy Y scrolls like the wheel. Prox>200 -> screen on; idle 30s -> off.\n"
          "No audio here (no I2S) — brain does capture/transcription.",
 },
 {
  "tag":"V3", "title":"XIAO ESP32-S3 Sense — wearable",
  "sub":"I2C SSD1306 128x32 (blue board, 0x3C) · scrollwheel + 2 buttons · onboard mic + SD",
  "mcu":"Seeed XIAO ESP32-S3 Sense (onboard I2S mic + microSD)",
  "mcu_pins":[
    ("D6","OLED SDA (I2C)","i2c"),
    ("D7","OLED SCL (I2C)","i2c"),
    ("3V3","OLED VCC","pwr"),
    ("GND","OLED GND","gnd"),
    ("D0","WHEEL_A (GPIO0, BOOT btn)","in"),
    ("D4","WHEEL_B (GPIO4)","in"),
    ("D3","BTN_A (GPIO3, pullup)","in"),
    ("D5","BTN_B (GPIO5, pullup)","in"),
    ("40/41/42","MIC I2S BCLK/WS/DIN","mic"),
    ("21/7/8/9","SD onboard slot","spi"),
    ("USB-C","5V + data + charge","pwr"),
    ("BAT","Li-Po + (optional)","pwr"),
  ],
  "comps":{
    "OLED SSD1306 128x32\n(I2C, blue board, 0x3C)":{
      "xy":(640,150),
      "pins":[("VCC","3V3","pwr","3.3V"),("GND","GND","gnd",""),("SDA","D6","i2c",""),("SCL","D7","i2c","")]},
    "Rotary encoder\n(scrollwheel)":{
      "xy":(640,440),
      "pins":[("A","D0","in",""),("B","D4","in",""),("SW","D3","in","= BTN_A tap")]},
    "Button B\n(menu / back)":{
      "xy":(640,640),
      "pins":[("SIG","D5","in",""),("GND","GND","gnd","pullup")]},
    "Li-Po (optional)":{
      "xy":(640,760),
      "pins":[("+","BAT","pwr","via protect"),("-","GND","gnd","")]},
  },
  "build":"pio run -e xiao_128x32_i2c -t upload --upload-port /dev/ttyACM0\n"
          "(-DENABLE_RING=1 -DENABLE_IMU=1 for ring/gyro)\n"
          "Screen blank? flip addr 0x3C->0x3D in screens.h",
  "notes":"Don't hold GPIO0 at boot (enters flash mode). Mic/SD are onboard — no wires.\n"
          "Optional I2C IMU shares D6/D7 bus (addr 0x68/0x6A, no clash with 0x3C).\n"
          "Wheel A/B + BTN_A/B are the default control set.",
 },
 {
  "tag":"V4", "title":"XIAO ESP32-S3 Sense — Transparent OLED",
  "sub":"Waveshare 1.51\" Transparent OLED 128x64 (SSD1309) · scrollwheel + 2 buttons",
  "mcu":"Seeed XIAO ESP32-S3 Sense (SPI transparent HUD; I2C variant = D6/D7)",
  "mcu_pins":[
    ("D10","OLED MOSI/DIN","spi"),
    ("D8","OLED SCK/CLK","spi"),
    ("D5","OLED CS (GPIO6)","spi"),
    ("D1","OLED DC (GPIO2)","spi"),
    ("D0","OLED RST (GPIO1)","spi"),
    ("3V3","OLED VCC (EXTVCC boost)","pwr"),
    ("GND","OLED GND","gnd"),
    ("D0w","WHEEL_A (GPIO0)","in"),
    ("D4","WHEEL_B (GPIO4)","in"),
    ("D3","BTN_A (GPIO3, pullup)","in"),
    ("D5b","BTN_B (GPIO5, pullup)","in"),
    ("USB-C","5V + data + charge","pwr"),
  ],
  "comps":{
    "Transparent OLED 1.51\"\n(128x64 SSD1309, SPI)":{
      "xy":(640,150),
      "pins":[("VCC","3V3","pwr","EXTVCC"),("GND","GND","gnd",""),("DIN","D10","spi",""),
              ("CLK","D8","spi",""),("CS","D5","spi",""),("DC","D1","spi",""),("RST","D0","spi","")]},
    "Rotary encoder\n(scrollwheel)":{
      "xy":(640,500),
      "pins":[("A","D0w","in",""),("B","D4","in",""),("SW","D3","in","= BTN_A tap")]},
    "Button B\n(menu / back)":{
      "xy":(640,700),
      "pins":[("SIG","D5b","in",""),("GND","GND","gnd","pullup")]},
  },
  "build":"pio run -e xiao_transparent_151          # SPI\n"
          "pio run -e xiao_transparent_151_i2c     # I2C (move 2 res on module)\n"
          "Boot log: [boot] screen=Transparent 1.51in SSD1309 128x64",
  "notes":"SSD1309=SSD1306-compatible; uses EXTERNALVCC boost, dim(false) for daylight.\n"
          "Unlit pixels stay transparent glass — don't draw 'off' rects.\n"
          "I2C variant frees SPI: SDA->D6, SCL->D7 (no CS/DC/RST wires).",
 },
]

def setup_font(ctx, size, bold=False):
    ctx.select_font_face(FONT, cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)

def text(ctx, x, y, s, size=13, color=(0,0,0), bold=False, align="l"):
    setup_font(ctx, size, bold)
    ctx.set_source_rgb(*color)
    ctx.save(); ctx.translate(x,y)
    if align=="c": ctx.translate(-ctx.text_extents(s).width/2,0)
    elif align=="r": ctx.translate(-ctx.text_extents(s).width,0)
    ctx.move_to(0,0); ctx.text_path(s); ctx.fill(); ctx.restore()

def wrap(s, width):
    out=[]
    for line in s.split("\n"):
        if len(line)<=width: out.append(line); continue
        words=line.split(" "); cur=""
        for w in words:
            if len(cur)+len(w)+1<=width: cur=(cur+" "+w).strip()
            else: out.append(cur); cur=w
        out.append(cur)
    return out

def draw_variant(ctx, v, ox=0, oy=0):
    """Draw one variant at offset (ox,oy)."""
    ctx.save(); ctx.translate(ox,oy)
    # header band
    ctx.set_source_rgb(0.12,0.18,0.30); ctx.rectangle(0,0,W,86); ctx.fill()
    text(ctx, 30, 38, f"{v['tag']}  {v['title']}", 22, (1,1,1), bold=True)
    text(ctx, 30, 66, v["sub"], 13, (0.8,0.85,0.92))
    text(ctx, W-30, 38, "Cyclops wiring", 13, (0.7,0.78,0.9), align="r")

    # ---- MCU box (left) ----
    pin_top = 150; pin_h = 40; pin0 = pin_top
    mcu_x, mcu_w = 60, 250
    mcu_h = pin_h*len(v["mcu_pins"]) + 56
    ctx.set_source_rgb(0.93,0.94,0.97); ctx.rectangle(mcu_x,pin_top-30,mcu_w,mcu_h); ctx.fill()
    ctx.set_source_rgb(0.30,0.34,0.45); ctx.set_line_width(2); ctx.rectangle(mcu_x,pin_top-30,mcu_w,mcu_h); ctx.stroke()
    text(ctx, mcu_x+mcu_w/2, pin_top-8, v["mcu"], 13, (0.15,0.18,0.28), bold=True, align="c")
    # pin rows
    mcu_pin_y={}
    for i,(lab,fn,t) in enumerate(v["mcu_pins"]):
        y = pin_top + 18 + i*pin_h
        mcu_pin_y[lab.split("b")[0]] = y   # base key (strip 'b' suffix)
        # dot + label
        ctx.set_source_rgb(*rgb(t)); ctx.arc(mcu_x+18, y, 5, 0, 2*math.pi); ctx.fill()
        text(ctx, mcu_x+34, y+5, lab, 13, (0.10,0.10,0.10), bold=True)
        text(ctx, mcu_x+34, y+22, fn, 10.5, (0.30,0.32,0.38))
        # stub line to right edge
        ctx.set_source_rgb(*rgb(t)); ctx.set_line_width(2)
        ctx.move_to(mcu_x+mcu_w, y); ctx.line_to(mcu_x+mcu_w+14, y); ctx.stroke()

    # ---- components (right) ----
    comp_pin_y={}
    for name, c in v["comps"].items():
        cx, cy = c["xy"]
        pins = c["pins"]
        cw, ch = 250, 30*len(pins)+34
        ctx.set_source_rgb(0.98,0.96,0.90); ctx.rectangle(cx,cy,cw,ch); ctx.fill()
        ctx.set_source_rgb(0.55,0.45,0.20); ctx.set_line_width(2); ctx.rectangle(cx,cy,cw,ch); ctx.stroke()
        text(ctx, cx+cw/2, cy+20, name, 12.5, (0.35,0.25,0.10), bold=True, align="c")
        comp_pin_y[name]={}
        for j,(plab,target,t,note) in enumerate(pins):
            y = cy+34 + j*30 + 9
            comp_pin_y[name][plab]=y
            # dot on left edge
            if target:
                ctx.set_source_rgb(*rgb(t)); ctx.arc(cx, y, 4.5, 0, 2*math.pi); ctx.fill()
            text(ctx, cx+12, y+4, plab, 12, (0.10,0.10,0.10), bold=True)
            if note:
                text(ctx, cx+60, y+4, note, 9.5, (0.4,0.4,0.45))

    # ---- wires ----
    for name, c in v["comps"].items():
        cx, cy = c["xy"]
        for (plab,target,t,note) in c["pins"]:
            if not target: continue
            key = target.rstrip("b")  # match base mcu key (drop 'b')
            if key not in mcu_pin_y: continue
            y1 = mcu_pin_y[key]; x1 = mcu_x+mcu_w+14
            y2 = comp_pin_y[name][plab]; x2 = cx
            ctx.set_source_rgb(*rgb(t)); ctx.set_line_width(2.4)
            # simple elbow: out, mid, in
            mx = (x1+x2)/2
            ctx.move_to(x1,y1)
            ctx.curve_to(x1+30,y1, x2-30,y2, x2,y2)
            ctx.stroke()
            # wire label (centered on curve-ish midpoint)
            lbl = f"{target}→{plab}" if not target[0].isdigit() else f"{target}"
            if target[:1] in "DAd": lbl = f"{target} → {plab}"
            text(ctx, mx, (y1+y2)/2 - 4, lbl, 10, rgb(t), bold=True, align="c")

    # ---- build + notes footer ----
    fy = pin_top + mcu_h + 24
    ctx.set_source_rgb(0.10,0.10,0.10)
    text(ctx, 60, fy, "$ build / flash", 13, (0.15,0.20,0.45), bold=True)
    for i,line in enumerate(v["build"].split("\n")):
        text(ctx, 70, fy+20+i*17, line, 11.5, (0.18,0.18,0.18), bold=True)
    ny = fy+20+len(v["build"].split("\n"))*17 + 18
    text(ctx, 60, ny, "notes", 13, (0.15,0.30,0.20), bold=True)
    for i,line in enumerate(v["notes"].split("\n")):
        text(ctx, 70, ny+20+i*16, "• "+line, 11, (0.25,0.28,0.28))
    ctx.restore()

def render_pdf(path):
    surface = cairo.PDFSurface(path, W, H)
    ctx = cairo.Context(surface)
    for v in VARIANTS:
        draw_variant(ctx, v)
        ctx.show_page()
    surface.finish()

def render_svg(path):
    surface = cairo.SVGSurface(path, W, H*len(VARIANTS))
    ctx = cairo.Context(surface)
    for i,v in enumerate(VARIANTS):
        draw_variant(ctx, v, 0, i*H)
    surface.finish()

def render_png(path, per_variant_dir=None, scale=SCALE):
    # combined tall PNG (scaled for crisp output)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W*scale), int(H*scale*len(VARIANTS)))
    ctx = cairo.Context(surf)
    ctx.scale(scale, scale)
    ctx.set_source_rgb(1,1,1); ctx.paint()
    for i,v in enumerate(VARIANTS):
        draw_variant(ctx, v, 0, i*H)
    surf.write_to_png(path)
    # per-variant PNGs
    if per_variant_dir:
        for i,v in enumerate(VARIANTS):
            s2 = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W*scale), int(H*scale))
            c2 = cairo.Context(s2); c2.scale(scale, scale)
            c2.set_source_rgb(1,1,1); c2.paint()
            draw_variant(c2, v, 0, 0)
            slug = re.sub(r'[^A-Za-z0-9]+', '_', v['title'].split('—')[0].strip())
            p = os.path.join(per_variant_dir, f"cyclops_{v['tag'].lower()}_{slug}.png")
            s2.write_to_png(p)
            print("  wrote", p)

def render_expanded_cycluno(path, scale=CYCLUNO_EXPAND_SCALE):
    """Dedicated high-res CyclUno (V1) poster for desk/print reference."""
    v = next(x for x in VARIANTS if x["tag"] == "V1")
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W*scale), int(H*scale))
    ctx = cairo.Context(surf)
    ctx.scale(scale, scale)
    ctx.set_source_rgb(1,1,1); ctx.paint()
    draw_variant(ctx, v)
    surf.write_to_png(path)
    print("  wrote", path)

def render_assembly(path, scale=2):
    """Top-down 'finished board' poster for CyclUno V1.
    Every wire is drawn: signal wires curve Uno->comp, power/gnd tap the
    top(5V)/bottom(GND) buses, and the 7-pin OLED straps are shown."""
    W, H = 1500, 1240
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(W*scale), int(H*scale))
    ctx = cairo.Context(surf); ctx.scale(scale, scale)
    ctx.set_source_rgb(0.97,0.97,0.95); ctx.paint()

    text(ctx, 40, 40, "CyclUno V1 — finished assembly (every wire drawn)", 20, (0.12,0.18,0.30), bold=True)
    text(ctx, 40, 64, "Uno (left) -> OLED + 2 joysticks + 4 buttons (right).  Top bar = 5V, bottom bar = GND.", 12, (0.3,0.32,0.4))

    BUS5, BUSG = 110, 1160
    ctx.set_line_width(6)
    ctx.set_source_rgb(*C["pwr"]); ctx.move_to(260,BUS5); ctx.line_to(W-40,BUS5); ctx.stroke()
    ctx.set_source_rgb(*C["gnd"]); ctx.move_to(260,BUSG); ctx.line_to(W-40,BUSG); ctx.stroke()
    text(ctx, 40, BUS5-6, "5V", 13, C["pwr"], bold=True)
    text(ctx, 40, BUSG-6, "GND", 13, C["gnd"], bold=True)

    def wline(x1,y1,x2,y2,col,wd=2.6):
        ctx.set_source_rgb(*col); ctx.set_line_width(wd)
        ctx.move_to(x1,y1); ctx.line_to(x2,y2); ctx.stroke()
    def wcurve(x1,y1,x2,y2,col,wd=2.6):
        ctx.set_source_rgb(*col); ctx.set_line_width(wd)
        ctx.move_to(x1,y1); ctx.curve_to(x1-50,y1, x2+50,y2, x2,y2); ctx.stroke()

    # ---- Uno ----
    ux,uy,uw,uh = 60,150,200,820
    ctx.set_source_rgb(0.93,0.94,0.97); ctx.rectangle(ux,uy,uw,uh); ctx.fill()
    ctx.set_source_rgb(0.30,0.34,0.45); ctx.set_line_width(2); ctx.rectangle(ux,uy,uw,uh); ctx.stroke()
    text(ctx, ux+uw/2, uy+22, "Arduino Uno", 14, (0.15,0.18,0.28), bold=True, align="c")
    uno_pins = [("5V",200,"pwr"),("GND",260,"gnd"),("A0",320,"in"),("A1",370,"in"),
                ("A2",420,"in"),("A3",470,"in"),("A4",520,"i2c"),("A5",570,"i2c"),
                ("D2",640,"in"),("D3",690,"in"),("D4",740,"in"),("D5",790,"in"),
                ("D6",840,"in"),("D7",890,"in")]
    uxr = ux+uw
    uno_y = {}
    for lab,y,t in uno_pins:
        uno_y[lab]=y
        ctx.set_source_rgb(*rgb(t)); ctx.arc(uxr,y,5,0,2*math.pi); ctx.fill()
        text(ctx, uxr+10, y+5, lab, 12, (0.1,0.1,0.1), bold=True)
    text(ctx, ux+uw/2, uy+uh+24, "USB -> host (brain) @115200", 12, (0.15,0.2,0.45), bold=True, align="c")
    # Uno power/gnd to bus
    wline(uxr, uno_y["5V"], uxr, BUS5, rgb("pwr"))
    wline(uxr, uno_y["GND"], uxr, BUSG, rgb("gnd"))

    # ---- components ----
    # comp: (name, x, y, w, h, pins) ; pin=(label, y, type, target, note)
    #   target = Uno pin label | "BUS5" | "BUSG" | ("strap", other_label)
    comps = [
      ("OLED SSD1306 128x32\n(I2C 0x3C)", 900, 150, 250, 250, [
        ("VCC",185,"pwr","BUS5",""),("GND",220,"gnd","BUSG",""),
        ("SDA",255,"i2c","A4",""),("SCL",290,"i2c","A5",""),
        ("RES",335,"spi",("strap","VCC"),"10k"),("DC",370,"spi",("strap","GND"),""),
        ("CS",405,"spi",("strap","VCC"),"") ]),
      ("Joystick 1 (primary)", 900, 500, 250, 180, [
        ("VRx",530,"in","A0",""),("VRy",560,"in","A1",""),("SW",590,"in","D2",""),
        ("+",625,"pwr","BUS5",""),("GND",660,"gnd","BUSG","") ]),
      ("Joystick 2 (secondary)", 900, 730, 250, 180, [
        ("VRx",760,"in","A2",""),("VRy",790,"in","A3",""),("SW",820,"in","D3",""),
        ("+",855,"pwr","BUS5",""),("GND",890,"gnd","BUSG","") ]),
    ]
    # buttons row
    btn_x = [880, 1040, 1200, 1360]; btn_y=950; btn_w=130; btn_h=95
    btn_targets = ["D4","D5","D6","D7"]
    for i,bx in enumerate(btn_x):
        comps.append((f"Button B{i+1}", bx, btn_y, btn_w, btn_h, [
            ("SIG",975,"in",btn_targets[i],""),("GND",1010,"gnd","BUSG","") ]))

    # draw wires first (behind boxes)
    for name,cx,cy,cw,ch,pins in comps:
        for lab,py,t,tgt,note in pins:
            col = rgb(t)
            if isinstance(tgt, tuple) and tgt[0]=="strap":
                # strap to another pin of same comp (drawn later on top)
                continue
            elif tgt=="BUS5":
                wline(cx, py, cx, BUS5, col)
            elif tgt=="BUSG":
                wline(cx, py, cx, BUSG, col)
            else:
                wcurve(cx, py, uxr, uno_y[tgt], col)
    # draw boxes + pin dots + labels
    for name,cx,cy,cw,ch,pins in comps:
        ctx.set_source_rgb(0.98,0.96,0.90); ctx.rectangle(cx,cy,cw,ch); ctx.fill()
        ctx.set_source_rgb(0.55,0.45,0.20); ctx.set_line_width(2); ctx.rectangle(cx,cy,cw,ch); ctx.stroke()
        text(ctx, cx+cw/2, cy+20, name, 12.5, (0.35,0.25,0.10), bold=True, align="c")
        for lab,py,t,tgt,note in pins:
            ctx.set_source_rgb(*rgb(t)); ctx.arc(cx,py,4.5,0,2*math.pi); ctx.fill()
            text(ctx, cx+12, py+4, lab, 12, (0.1,0.1,0.1), bold=True)
            if note: text(ctx, cx+60, py+4, note, 9.5, (0.4,0.4,0.45))
    # draw straps on top (within OLED)
    for name,cx,cy,cw,ch,pins in comps:
        pinmap = {lab:py for lab,py,t,tgt,note in pins}
        for lab,py,t,tgt,note in pins:
            if isinstance(tgt, tuple) and tgt[0]=="strap":
                ty = pinmap.get(tgt[1])
                if ty is None: continue
                ctx.set_source_rgb(*rgb(t)); ctx.set_line_width(2.2)
                ctx.set_dash([5,3]); ctx.move_to(cx,py); ctx.line_to(cx,ty); ctx.stroke(); ctx.set_dash([])
                text(ctx, cx-8, (py+ty)/2, f"{lab}->{tgt[1]}", 9, rgb(t), bold=True, align="r")
    # legend
    lx, ly = 40, 1200
    text(ctx, lx, ly, "legend:", 12, (0.1,0.1,0.1), bold=True)
    for i,(k,c) in enumerate([("i2c",C["i2c"]),("spi",C["spi"]),("in",C["in"]),("pwr",C["pwr"]),("gnd",C["gnd"])]):
        x = lx+60+i*130
        ctx.set_source_rgb(*c); ctx.arc(x, ly-4, 5, 0, 2*math.pi); ctx.fill()
        text(ctx, x+10, ly, k, 11, (0.1,0.1,0.1))
    surf.write_to_png(path)
    print("  wrote", path)

if __name__=="__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    render_pdf(os.path.join(here,"cyclops_wiring.pdf"))
    print("wrote cyclops_wiring.pdf")
    render_svg(os.path.join(here,"cyclops_wiring.svg"))
    print("wrote cyclops_wiring.svg")
    render_png(os.path.join(here,"cyclops_wiring.png"), per_variant_dir=here, scale=SCALE)
    print(f"wrote cyclops_wiring.png (+ per-variant @ {SCALE}x)")
    render_expanded_cycluno(os.path.join(here,"cyclops_v1_CyclUno_EXPANDED.png"), scale=CYCLUNO_EXPAND_SCALE)
    print(f"wrote cyclops_v1_CyclUno_EXPANDED.png (@ {CYCLUNO_EXPAND_SCALE}x)")
    render_assembly(os.path.join(here,"cyclops_v1_CyclUno_ASSEMBLY.png"), scale=2)
    print("wrote cyclops_v1_CyclUno_ASSEMBLY.png")
