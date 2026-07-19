; english/us_bank00.asm — US bank-$00 code relocated to its +1MB mirror in the 2nd MB
; (US bank $00 -> our bank $20). English claims the canonical name; the JP original in
; bank_00.asm is preserved byte-identical as UNREACHABLE_*, and JSL/JML callers auto-resolve here.

org $20E596
; [ENG-GFX] Uploads TheFont (font.2bpp) to VRAM $E000 — the US form (JP uploaded a $7E2000 VWF buffer).
TransferFontToVRAM:
EN_TransferFontToVRAM:
#_20E596: LDA.b #$02
#_20E598: STA.w OBSEL

#_20E59B: LDA.b #$80
#_20E59D: STA.w VMAIN

#_20E5A0: LDA.b #TheFont>>16
#_20E5A2: STA.b $02

#_20E5A4: REP #$30

#_20E5A6: LDA.w #$7000 ; VRAM $E000
#_20E5A9: STA.w VMADDR

#_20E5AC: LDA.w #TheFont
#_20E5AF: STA.b $00

#_20E5B1: LDX.w #(TheFont_end-TheFont)/2-1

.next
#_20E5B4: LDA.b [$00]
#_20E5B6: STA.w VMDATA

#_20E5B9: INC.b $00
#_20E5BB: INC.b $00

#_20E5BD: DEX
#_20E5BE: BPL .next

#_20E5C0: SEP #$30

#_20E5C2: RTL
