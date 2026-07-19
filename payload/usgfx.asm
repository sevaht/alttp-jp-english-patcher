; ============================================================================
; [ENG-GFX] US menu / file-select font graphics sheets
; ----------------------------------------------------------------------------
; The in-game menu / HUD font (and the file-select font) live in VRAM $E000,
; decompressed there by the game's own `LoadDefaultGraphics` from compressed
; sprite sheets `GFX_DC` ($69) and `GFX_DD` ($6A). Those two sheets are the ONLY
; menu/file-select graphics that differ between JP and US (JP kana vs US Latin);
; the box/frame sheets `GFX_D1/D2/DE` are byte-identical JP<->US, so the JP ROM
; already produces them (see AGENTS.md §10).
;
; Rather than capture the decompressed VRAM with an emulator and DMA it back in
; (the old `usmenufont.bin` + `NMIFontHook` path), we follow the disassembly's
; own model: incbin the US sheets in their COMPRESSED form (plain byte slices of
; the US ROM) and let the game's decompressor expand them at runtime. The two
; `GFXSheetPointers` entries `$69`/`$6A` (bank_00) are repointed here, so the
; native `LoadDefaultGraphics` path yields the US font at $E000 for both the item
; menu and the gameplay HUD. (Every HUD tile is byte-identical JP<->US, so the
; HUD is visually unchanged.)
;
; The JP `GFX_DC`/`GFX_DD` data stays in `bank_18` (now pointed at by nothing).
; Overwriting it in place is a separate future initiative.
;
; Source slices (from the US ROM, offsets/sizes per usdasm/graphics.asm):
;   US_GFX_DC : us.sfc[0x0C2F0D .. +0x613]  (GFX_DC, 2bppc)
;   US_GFX_DD : us.sfc[0x0C3520 .. +0x433]  (GFX_DD, 2bppc)
; ============================================================================

org $268000

GFX_DC:
EN_GFX_DC:
    incbin "english/gfx_dc.2bppc"

GFX_DD:
EN_GFX_DD:
    incbin "english/gfx_dd.2bppc"

; [ENG-GFX] The US file-select BACKGROUND ("linoleum") is a re-colored floor tile: it is
; background sheet GFX_39 (tiles 1/2/17/18), which DIFFERS JP<->US. GFX_39 is used only by the
; menu tileset rows $23/$24 (file-select / copy / erase / name) — never by any overworld or
; underworld tileset — so repointing it is menu-only and cannot affect gameplay. The background
; pointer-table entry for GFX_39 (bank_00 `.background_*`) is repointed here; the game's own
; tileset loader then decompresses the US linoleum natively. Compressed byte slice
; us.sfc[0x09C817:+0x351] (GFX_39, 3bppc).
GFX_39:
EN_GFX_39:
    incbin "english/gfx_39.3bppc"
