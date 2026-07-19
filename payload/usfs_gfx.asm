; [ENG-FS] US file-select palette fix (ROM-sourced, no emulator).
;
; (The US file-select *graphics* injection that used to live here was removed: the only
; file-select graphic that differed JP<->US was the "linoleum" background, a re-colored floor
; tile = background sheet GFX_39, now repointed to its US version in english/usgfx.asm so the
; game's own tileset loader decompresses it natively. See AGENTS.md §10 / DETAILS.md.)
;
; The file-select composes its CGRAM from the game's own shared palette-load routines
; (PaletteLoad_UnderworldSet / _OWBG3 / _HUD in bank_1B). Almost every row is byte-identical
; JP<->US, so the native loads already produce the correct US colors on the JP ROM. Exactly four
; 7-color palettes differ, plus one stray color:
;     rows 5, 7, 9, 11 (colors 1-7)   and   row 14 color 15 (-> black)
; Rows 5 and 7 are genuinely US-specific palette DATA (row 7 = the wood name-banner). Rows 9 and
; 11 hold the same ROM bytes JP<->US, but the ported US file-select loads a different palette
; index into them than the JP intro left behind, so they still come out wrong.
;
; We reproduce the finished US CGRAM by overlaying just those four US palettes -- ripped straight
; out of the US ROM's PaletteData table (english/usfs_pal.bin, 4*14 bytes, built by
; extract_english_assets.py) -- onto the NMI palette source buffer $7EC500, every frame from the
; file-select / copy / erase / name module tops (the four JSL sites in bank_0C). $7EC500 is the
; buffer bank_00's NMI DMAs to CGRAM; the entry brightness fade freezes it from $7EC300 only
; during ramp-in, so writing $7EC500 directly is what survives across the sub-screens.
;
; CGRAM color N lives at buffer byte 2*N; color 1 of row R is byte 2*(R*16+1):
;     row 5 -> $05A2   row 7 -> $05E2   row 9 -> $0622   row 11 -> $0662   row14.15 -> $06DE

org $278000

USFS_InjectPalette:
    PHP                 ; preserve caller's processor mode (M/X flags)
    REP #$30            ; 16-bit A AND index (module dispatch can enter with 8-bit index)
    PHB
    PHK
    PLB
    LDX.w #$0000
.row5
    LDA.l USFS_Palette+$00,X
    STA.l $7EC5A2,X
    INX
    INX
    CPX.w #$000E
    BNE .row5
    LDX.w #$0000
.row7
    LDA.l USFS_Palette+$0E,X
    STA.l $7EC5E2,X
    INX
    INX
    CPX.w #$000E
    BNE .row7
    LDX.w #$0000
.row9
    LDA.l USFS_Palette+$1C,X
    STA.l $7EC622,X
    INX
    INX
    CPX.w #$000E
    BNE .row9
    LDX.w #$0000
.row11
    LDA.l USFS_Palette+$2A,X
    STA.l $7EC662,X
    INX
    INX
    CPX.w #$000E
    BNE .row11
    LDA.w #$0000        ; row 14 color 15 -> black (US)
    STA.l $7EC6DE
    PLB
    PLP
    RTL

; Four US file-select palettes (colors 1-7 each), in CGRAM-row order 5, 7, 9, 11.
USFS_Palette:
    incbin "english/usfs_pal.bin"
