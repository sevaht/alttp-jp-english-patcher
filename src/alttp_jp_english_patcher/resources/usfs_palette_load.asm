; File-select palette overlay: JP<->US differ in four CGRAM rows (5, 7, 9,
; 11). This runs the stock US load, then overlays those four rows from
; USFS_Palette (a US-ROM PaletteData slice, incbin'd alongside this in
; file_select_palette()). file_select() repoints the one JSL at it.
;
; NOTE on row 5: statically it looks unneeded -- the file-select drives
; PaletteLoad_UnderworldSet with $0AB6 = #$06 (dungeon set $06, which is
; byte-identical US<->JP), and the overlaid slice ($1BD9AA) is in set $03.
; But dropping it was tested and turned the wooden file-select borders the
; wrong colour, so the runtime CGRAM ends up needing it after all -- the load
; path is more involved than the static read suggests. Keep all four rows.
;
; Read verbatim from this file (an embedded package resource) into an
; Assembly; kept namespace=False (bare, not EN_-prefixed) by generate.py since
; file_select()'s repoint references this exact name.
USFS_PaletteLoadForFileSelect:
    JSL PaletteLoadForFileSelect    ; stock US load (JP palette for FS rows)
    PHP                             ; preserve caller's processor mode (M/X)
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
