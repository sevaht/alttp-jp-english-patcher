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
; extract_english_assets.py).
;
; CLEAN HOOK (replaces the old 4x per-frame USFS_InjectPalette insertions at the module tops):
; the file-select loads its palette from exactly one site -- JSL PaletteLoadForFileSelect at
; $0CCE06, inside ReinitializeFileSelectGraphics -- which ALL four sub-screens (select / copy /
; kill / name) reach (Module01 falls through FileSelect_ReInitSaveFlagsAndGraphics into it;
; Module02-04 call it). Redirecting that one JSL to this wrapper (a byte-neutral operand change)
; runs the stock load and then overlays the four US palettes, ONCE per (re)init instead of every
; frame -- so the ported file-select code stays byte-for-byte the US original and mirrors cleanly.
;
; PaletteLoadForFileSelect writes BOTH palette buffers ($7EC300 compose + $7EC500 NMI-DMA source;
; they are $200 apart), so the overlay writes both too, to survive the ramp-in fade regardless of
; which buffer it reads. CGRAM color N lives at buffer byte 2*N; color 1 of row R is 2*(R*16+1):
;     row 5 -> $A2   row 7 -> $E2   row 9 -> $122   row 11 -> $162   row14.15 -> $1DE

org $278000

USFS_PaletteLoadForFileSelect:
    JSL PaletteLoadForFileSelect    ; stock US load (produces JP palette data for the FS rows)
    PHP                             ; preserve caller's processor mode (M/X flags)
    REP #$30                        ; 16-bit A AND index
    PHB
    PHK
    PLB
    LDX.w #$0000
.row5
    LDA.l USFS_Palette+$00,X
    STA.l $7EC3A2,X                 ; buffer A (compose)
    STA.l $7EC5A2,X                 ; buffer B (NMI DMA source)
    INX
    INX
    CPX.w #$000E
    BNE .row5
    LDX.w #$0000
.row7
    LDA.l USFS_Palette+$0E,X
    STA.l $7EC3E2,X
    STA.l $7EC5E2,X
    INX
    INX
    CPX.w #$000E
    BNE .row7
    LDX.w #$0000
.row9
    LDA.l USFS_Palette+$1C,X
    STA.l $7EC422,X
    STA.l $7EC622,X
    INX
    INX
    CPX.w #$000E
    BNE .row9
    LDX.w #$0000
.row11
    LDA.l USFS_Palette+$2A,X
    STA.l $7EC462,X
    STA.l $7EC662,X
    INX
    INX
    CPX.w #$000E
    BNE .row11
    LDA.w #$0000                    ; row 14 color 15 -> black (US)
    STA.l $7EC4DE
    STA.l $7EC6DE
    PLB
    PLP
    RTL

; Four US file-select palettes (colors 1-7 each), in CGRAM-row order 5, 7, 9, 11.
USFS_Palette:
    incbin "english/usfs_pal.bin"
