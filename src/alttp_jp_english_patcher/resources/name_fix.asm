; Module04_NameFile submodule 4: name entry for an already-valid save whose
; name came in blank (an unconvertible JP import -- see save_migration.asm's
; ConvertJP). FileSelect_HandleInput redirects here instead of the normal
; "no file here" path when it finds a valid save with a blank name.
;
; This is NameFile_EraseSave's graphics/cursor setup and $0200 (slot SRAM
; offset) computation, without its two destructive parts: the 0x500-byte SRAM
; wipe, and the blank-name write (the name is already blank, that's how we
; got here). The save is left completely untouched going into the typing
; screen. Advances straight to submodule 1 (the normal fade-in) rather than
; relying on whatever mechanism advances NameFile_EraseSave's own submodule 0
; -- that isn't an instruction in either EraseSave or MakeScreenVisible, so
; it's set explicitly here instead.
;
; On confirm, typing (NameFile_DoTheNaming, unmodified) falls into
; InitializeSaveFile as always; StampNewFileTag there sees the save's $55AA
; marker is already set (it was never erased) and skips straight to the
; checksum recompute, leaving items/deaths/flags untouched.
NameFile_SetupRename:
JSL ReinitializeFileSelectGraphics

LDA.b #$01
STA.w $0128

STZ.w $0B10
STZ.w $0B12
STZ.w $0B15

STZ.w $00CA
STZ.w $00CC

LDA.b #$83
STA.w $0B11

REP #$30

LDA.w #$01F0
STA.w $0630

STZ.b $E4

LDA.b $C8
ASL A
TAX

LDA.l SaveFileCopyOffsets,X
STA.w $0200

SEP #$30

LDA.b #$01              ; submodule 1: NameFile_FillBackground (normal fade-in)
STA.b $11

RTL

; Out-of-line so FileSelect_HandleInput's own inline footprint (see
; edit_check_blank_name) is just a 3-byte JSR -- that routine's pre-existing
; short branches (e.g. its own ".exit"-bound BEQ/BRA) sit mid-routine, before
; this check, and have little headroom to spare. Entered with X = the
; file-select cursor slot * 2 (0/2/4, the JP disassembly's own convention
; here); on return in the "not blank" case, X is restored to that same value
; so FileSelect_HandleInput's unmodified code right after the JSR still
; finds what it expects. Reads the six name words by X rather than Y since
; the 65816 has no absolute-long,Y addressing mode -- only ,X.
FileSelect_NameIsBlankRedirect:
PHP
REP #$30

LDA.l SaveFileCopyOffsets,X
STA.b $00
TAX

LDA.l $7003D5,X
CMP.w #$00A9
BNE .not_blank
LDA.l $7003D7,X
CMP.w #$00A9
BNE .not_blank
LDA.l $7003D9,X
CMP.w #$00A9
BNE .not_blank
LDA.l $7003DB,X
CMP.w #$00A9
BNE .not_blank
LDA.l $7003DD,X
CMP.w #$00A9
BNE .not_blank
LDA.l $7003DF,X
CMP.w #$00A9
BNE .not_blank

; blank confirmed: enter module 4, submodule 4 (NameFile_SetupRename)
; instead of returning to the caller's normal load path. PLP first (while
; still 16-bit) would misalign the 8-bit immediates below, so pop the JSR
; return address by hand (two 8-bit PLAs) after restoring 8-bit mode, then
; RTL -- popping FileSelect_HandleInput's own JSL return address next,
; which is exactly what its own unmodified ".exit: RTL" would have done.
PLP
PLA
PLA

; Both of FileSelect_HandleInput's own exits (load, and .no_file_there)
; STZ $C9 before leaving -- load-bearing, not just cleanup: EraseSave (and
; this routine, copying it) later does `LDA.b $C8` *after* REP #$30, a
; 16-bit read of $C8+$C9 together. A stale nonzero $C9 turns that into a
; huge, wrong table index for SaveFileCopyOffsets.
STZ.b $C9

LDA.b #$04
STA.b $10
STA.b $11
STZ.b $B0

RTL

.not_blank
PLP

LDA.b $C8               ; recompute the caller's X (C8*2) -- clobbered above
ASL A
TAX

RTS
