; File-select palette overlay: JP and US differ in four CGRAM rows (5, 7, 9,
; 11). Runs the stock US load, then overlays those four rows from
; USFS_Palette (a US-ROM palette slice placed right after this routine). The
; file-select's one JSL repoints here directly, so this label stays
; unprefixed (no EN_).
;
; Row 5 looks unneeded at a glance: the file-select loads dungeon set $06
; (byte-identical between US and JP) while this row's overlay data is set
; $03. But removing it was tested and it turned the wooden file-select
; borders the wrong color, so the runtime load is more involved than that
; static read suggests -- keep all four rows.
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
