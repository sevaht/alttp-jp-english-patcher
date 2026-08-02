#!/usr/bin/env python3
"""Drive Mesen headlessly (Xvfb + Lua) for ACCURATE screenshots — unlike the lenient
snes9x libretro core, Mesen renders/timing-checks like real hardware.

    python3 tools/mesen_runner.py <rom> <out_prefix> <total_frames> [every] [a-b:BUTTON ...]

- every: screenshot every N frames (0 = only explicit + final)
- a-b:BUTTON: hold BUTTON on frames a..b (START SELECT A B X Y L R UP DOWN LEFT RIGHT)
- SRM=path env: copy a battery save in as the ROM's .srm before running
Outputs <prefix>_<frame>.png (+ _final.png) in the prefix's dir.

The Mesen binary is located (in order): $MESEN env var, then ./tools/mesen/Mesen, else the
MesenCE Linux build is downloaded/extracted into ./tools/mesen/. Mesen (the Linux zip) is
portable — its data (settings.json, Saves/) live beside the binary.
"""
import os, sys, subprocess, shutil, re, json, urllib.request, zipfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
MESEN_DIR = os.path.join(TOOLS, "mesen")
MESEN_VERSION = "2.2.1"
MESEN_URL = ("https://github.com/nesdev-org/MesenCE/releases/download/"
             f"{MESEN_VERSION}/Mesen_{MESEN_VERSION}_Linux_x64.zip")

def find_mesen():
    """Return the Mesen binary path: $MESEN, else tools/mesen/Mesen, else download it."""
    env = os.environ.get("MESEN")
    if env:
        if not os.path.isfile(env): sys.exit(f"MESEN={env!r} is not a file")
        return env
    local = os.path.join(MESEN_DIR, "Mesen")
    if os.path.isfile(local):
        return local
    print(f"Mesen not found; downloading MesenCE {MESEN_VERSION} into {MESEN_DIR}/ ...")
    os.makedirs(MESEN_DIR, exist_ok=True)
    zpath = os.path.join(MESEN_DIR, "mesen.zip")
    try:
        urllib.request.urlretrieve(MESEN_URL, zpath)
        with zipfile.ZipFile(zpath) as z: z.extractall(MESEN_DIR)
        os.remove(zpath)
    except Exception as e:
        sys.exit(f"could not download Mesen ({e}).\n"
                 f"  Download {MESEN_URL}\n"
                 f"  and extract it into {MESEN_DIR}/ (so {local} exists), or set MESEN=/path/to/Mesen")
    if not os.path.isfile(local):
        sys.exit(f"Mesen binary not found at {local} after extracting the zip")
    os.chmod(local, 0o755)
    return local

def ensure_mesen_settings(mesen_bin):
    """Mesen is portable (data beside the binary). The Lua drive script uses io.open and long
    runs need a raised timeout, so make sure both are enabled in settings.json. Returns the
    data dir (where Saves/ lives)."""
    data_dir = os.path.dirname(mesen_bin)
    sj = os.path.join(data_dir, "settings.json")
    d = {}
    if os.path.isfile(sj):
        try: d = json.load(open(sj, encoding="utf-8-sig"))
        except Exception: d = {}
    d.setdefault("Debug", {}).setdefault("ScriptWindow", {})
    d["Debug"]["ScriptWindow"]["AllowIoOsAccess"] = True
    d["Debug"]["ScriptWindow"]["ScriptTimeout"] = 600
    with open(sj, "w", encoding="utf-8-sig") as f:  # Mesen writes settings.json with a BOM
        json.dump(d, f)
    return data_dir

# setInput doesn't register in this headless Mesen build, so inject into ALttP's joypad
# WRAM instead: JOY1A(ALL=$F0,NEW=$F4) bits BYsSudlr, JOY1B(ALL=$F2,NEW=$F6) bits AXLR.
# byte: 0 -> $F0/$F4 (A-group), 1 -> $F2/$F6 (B-group).
BTN = {
    "B":(0,0x80), "Y":(0,0x40), "SELECT":(0,0x20), "START":(0,0x10),
    "UP":(0,0x08), "DOWN":(0,0x04), "LEFT":(0,0x02), "RIGHT":(0,0x01),
    "A":(1,0x80), "X":(1,0x40), "L":(1,0x20), "R":(1,0x10),
}

def main():
    rom, pfx, total = sys.argv[1], os.path.abspath(sys.argv[2]), int(sys.argv[3])
    every = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else 0
    holds = []
    for tok in sys.argv[(5 if every else 4):]:
        m = re.match(r"(\d+)-(\d+):(\w+)$", tok)
        if m:
            byte, bit = BTN[m.group(3).upper()]
            holds.append((int(m.group(1)), int(m.group(2)), byte, bit))
    rom = os.path.abspath(rom)
    outdir = os.path.dirname(pfx) or "."
    os.makedirs(outdir, exist_ok=True)

    mesen = find_mesen()
    data_dir = ensure_mesen_settings(mesen)

    # optional battery save: Mesen loads/writes <rom_basename>.srm in <mesen data dir>/Saves/
    srm = os.environ.get("SRM")
    mesen_saves = os.path.join(data_dir, "Saves")
    romsrm = os.path.join(mesen_saves, os.path.splitext(os.path.basename(rom))[0] + ".srm")
    cleanup = []
    if srm:
        os.makedirs(mesen_saves, exist_ok=True)
        shutil.copy(srm, romsrm)  # overwrite Mesen's battery for this rom

    holds_lua = ",".join(f"{{{a},{b},{byte},{bit}}}" for a,b,byte,bit in holds)
    shots_lua = ""
    if every:
        shots_lua = f"if frame % {every} == 0 then shot(frame) end"
    # Inject input by writing ALttP's joypad WRAM in startFrame (after the NMI auto-read):
    # ALL($F0/$F2) every held frame; NEW($F4/$F6) only on the first frame (clean single press).
    lua = f"""
local frame = 0
local holds = {{{holds_lua}}}
local function shot(n)
  local buf = emu.getScreenBuffer(); local sz = emu.getScreenSize()
  local f = io.open("{pfx}_"..n..".ppm","wb")
  f:write("P6\\n"..sz.width.." "..sz.height.."\\n255\\n")
  local t={{}}; for i=1,#buf do local p=buf[i]; t[i]=string.char((p>>16)&0xFF,(p>>8)&0xFF,p&0xFF) end
  f:write(table.concat(t)); f:close()
end
local ALL = {{0x7E00F0, 0x7E00F2}}
local NEW = {{0x7E00F4, 0x7E00F6}}
local function onFrame()
  frame = frame + 1
  local acc = {{0,0}}; local new = {{0,0}}
  for _,h in ipairs(holds) do
    if frame>=h[1] and frame<=h[2] then
      acc[h[3]+1] = acc[h[3]+1] | h[4]
      if frame==h[1] then new[h[3]+1] = new[h[3]+1] | h[4] end
    end
  end
  for i=1,2 do
    if acc[i] ~= 0 then emu.write(ALL[i], acc[i], emu.memType.snesMemory) end
    if new[i] ~= 0 then emu.write(NEW[i], new[i], emu.memType.snesMemory) end
  end
  {shots_lua}
  if frame >= {total} then shot("final"); emu.stop(0) end
end
emu.addEventCallback(onFrame, emu.eventType.startFrame)
"""
    luapath = os.path.join(outdir, "_drive.lua")
    open(luapath, "w").write(lua)
    subprocess.run(["xvfb-run", "-a", mesen, rom, luapath, "--testRunner"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    for c in cleanup:
        try: os.remove(c)
        except OSError: pass
    # convert PPMs
    for f in os.listdir(outdir):
        if f.startswith(os.path.basename(pfx)+"_") and f.endswith(".ppm"):
            p = os.path.join(outdir, f)
            subprocess.run(["magick", p, p[:-4]+".png"], stderr=subprocess.DEVNULL)
    print("done:", pfx)

if __name__ == "__main__":
    main()
