org $2C8000

; US file-select / copy / erase / name-entry system (English graft).
; Relocated from bank $0C ($0CCC67-$0CECED) and compacted at $2C8000 under the +1MB mirror scheme.
; bank_00 RunModule dispatch resolves these labels symbolically -> bank $2C. The #_2CXXXX: address
; markers are the real assembled addresses here (not a bank-swap of the $0C offsets).
; The JP $0C original is preserved byte-identical as readable dead code in bank_0C.asm
; (UNREACHABLE_ named labels; #_0CXXXX: address markers).

EN_FileSelect_FairyY:
#_2C8000: db $4A ; File 1
#_2C8001: db $6A ; File 2
#_2C8002: db $8A ; File 3
#_2C8003: db $AF ; Copy  [ENG-FS] US COPY/ERASE row positions
#_2C8004: db $BF ; KILL

;---------------------------------------------------------------------------------------------------

Module01_FileSelect:
EN_Module01_FileSelect:
#_2C8005: STZ.b $E4
#_2C8007: STZ.b $E5
#_2C8009: STZ.b $EA
#_2C800B: STZ.b $EB

#_2C800D: JSL USFS_InjectPalette   ; [ENG-FS] keep US file-select palette in $7EC500

#_2C8011: LDA.b $11
#_2C8013: JSL JumpTableLong
#_2C8017: dl EN_FileSelect_InitializeGFX
#_2C801A: dl EN_FileSelect_ReInitSaveFlagsAndGraphics
#_2C801D: dl EN_FileSelect_UploadFancyBackground   ; [ENG-FS] US green-hex/banner bg step
#_2C8020: dl EN_FileSelect_TriggerStripesAndAdvance
#_2C8023: dl EN_FileSelect_TriggerNameStripesAndAdvance
#_2C8026: dl EN_FileSelect_Main

;===================================================================================================

EN_FileSelect_InitializeGFX:
#_2C8029: JSL EnableForceBlank

#_2C802D: STZ.w $012A
#_2C8030: STZ.w $1F0C

#_2C8033: LDA.b #$0B ; SONG 0B
#_2C8035: STA.w $012C

#_2C8038: INC.b $11

#_2C803A: LDA.b #$02
#_2C803C: STA.w $0AA9

; [ENG-FS] US file-select GFX/palette selection (green-hex bg + wooden banner)
#_2C803F: LDA.b #$06
#_2C8041: STA.w $0AB6
#_2C8044: STA.w $0710

#_2C8047: JSL PaletteLoad_UnderworldSet
#_2C804B: JSL PaletteLoad_OWBG3

#_2C804F: LDA.b #$00
#_2C8051: STA.w $0AB2

#_2C8054: JSL PaletteLoad_HUD

#_2C8058: STZ.w $0202

#_2C805B: LDA.b #$01
#_2C805D: STA.w $0AA4

#_2C8060: LDA.b #$23
#_2C8062: STA.w $0AA1
#_2C8065: LDA.b #$51        ; [ENG-FS] US aux GFX pack
#_2C8067: STA.w $0AA2

#_2C806A: JSL LoadDefaultGraphics
#_2C806E: JSL InitializeTilesets
#_2C8072: JSL LoadFileSelectGraphics
          ; [ENG-GFX] USFS_InjectGraphics removed — US GFX_39 (linoleum) now loads natively

#_2C8076: REP #$30

#_2C8078: STZ.b $00

;---------------------------------------------------------------------------------------------------

.next_file_check
#_2C807A: LDX.b $00

#_2C807C: LDA.l SaveFileCopyOffsets,X
#_2C8080: TAX

#_2C8081: PHX

#_2C8082: LDY.w #$0000
#_2C8085: TYA

.calc_checksum_main
#_2C8086: CLC
#_2C8087: ADC.l $700000,X

#_2C808B: INX
#_2C808C: INX

#_2C808D: INY
#_2C808E: CPY.w #$0280
#_2C8091: BNE .calc_checksum_main

#_2C8093: PLX

#_2C8094: CMP.w #$5A5A
#_2C8097: BEQ .checksum_good

;---------------------------------------------------------------------------------------------------

#_2C8099: PHX

#_2C809A: LDY.w #$0000
#_2C809D: TYA

.calc_checksum_backup
#_2C809E: CLC
#_2C809F: ADC.l $700F00,X

#_2C80A3: INX
#_2C80A4: INX

#_2C80A5: INY
#_2C80A6: CPY.w #$0280
#_2C80A9: BNE .calc_checksum_backup

#_2C80AB: PLX

#_2C80AC: CMP.w #$5A5A
#_2C80AF: BNE .delete_file

;---------------------------------------------------------------------------------------------------

#_2C80B1: LDY.w #$0000

.copy_from_backup
#_2C80B4: LDA.l $700F00,X
#_2C80B8: STA.l $700000,X

#_2C80BC: LDA.l $701000,X
#_2C80C0: STA.l $700100,X

#_2C80C4: LDA.l $701100,X
#_2C80C8: STA.l $700200,X

#_2C80CC: LDA.l $701200,X
#_2C80D0: STA.l $700300,X

#_2C80D4: LDA.l $701300,X
#_2C80D8: STA.l $700400,X

#_2C80DC: INX
#_2C80DD: INX

#_2C80DE: INY
#_2C80DF: CPY.w #$0080
#_2C80E2: BNE .copy_from_backup

;---------------------------------------------------------------------------------------------------

.checksum_good
#_2C80E4: INC.b $00
#_2C80E6: INC.b $00

#_2C80E8: LDX.b $00
#_2C80EA: CPX.w #$0006
#_2C80ED: BNE .next_file_check

;---------------------------------------------------------------------------------------------------

#_2C80EF: LDX.w #$00FE

.clear_next_sprite_prop
#_2C80F2: STZ.w $0D00,X
#_2C80F5: STZ.w $0E00,X
#_2C80F8: STZ.w $0F00,X

#_2C80FB: DEX
#_2C80FC: DEX
#_2C80FD: BPL .clear_next_sprite_prop

#_2C80FF: SEP #$30

#_2C8101: JML DecompressEnemyDamageSubclasses

;---------------------------------------------------------------------------------------------------

.delete_file
#_2C8105: LDY.w #$0000
#_2C8108: TYA

.delete_next
#_2C8109: STA.l $700F00,X
#_2C810D: STA.l $700000,X

#_2C8111: STA.l $701000,X
#_2C8115: STA.l $700100,X

#_2C8119: STA.l $701100,X
#_2C811D: STA.l $700200,X

#_2C8121: STA.l $701200,X
#_2C8125: STA.l $700300,X

#_2C8129: STA.l $701300,X
#_2C812D: STA.l $700400,X

#_2C8131: INX
#_2C8132: INX

#_2C8133: INY
#_2C8134: CPY.w #$0080
#_2C8137: BNE .delete_next

#_2C8139: BRA .checksum_good

;===================================================================================================

EN_FileSelect_ReInitSaveFlagsAndGraphics:
#_2C813B: LDX.b #$05

.clear_next
#_2C813D: STZ.b $BF,X

#_2C813F: DEX
#_2C8140: BPL .clear_next

;===================================================================================================

EN_ReinitializeFileSelectGraphics:
LDA.b #$80
STA.w $0710

JSL EnableForceBlank
JSL EraseTilemaps_bg3
JSL PaletteLoadForFileSelect

INC.b $15
INC.b $11

RTL

;===================================================================================================

EN_FileSelect_TriggerStripesAndAdvance:
#_2C8158: LDA.w $0B9D
#_2C815B: STA.b $C8

.advance_submodule
#_2C815D: INC.b $11

#_2C815F: LDA.b #$06
#_2C8161: STA.b $14

#_2C8163: RTL

;===================================================================================================

#EN_FileSelect_TriggerNameStripesAndAdvance:
#_2C8164: JSR EN_FileSelect_SetUpNamesStripes

#_2C8167: LDA.b #$0F
#_2C8169: STA.b $13

#_2C816B: STZ.w $0710

#_2C816E: BRA .advance_submodule

;===================================================================================================

EN_FileSelect_Main:
#_2C8170: PHB
#_2C8171: PHK
#_2C8172: PLB

#_2C8173: JSL EN_FileSelect_HandleInput

#_2C8177: JMP.w EN_FileSelect_TriggerTheStripes

;===================================================================================================

EN_FileSelect_SetUpNamesStripes:
PHB
PHK
PLB

REP #$10

LDX.w #$00FD

.next
LDA.w EN_FileSelectNamesTilemap-1,X
STA.w $1001,X

DEX
BNE .next

;---------------------------------------------------------------------------------------------------

SEP #$10

PLB

RTS

;===================================================================================================

EN_FileSelect_HandleInput:
LDA.b $C8
CMP.b #$03
BCS .not_on_a_file

STA.w $0B9D

.not_on_a_file
REP #$30

LDX.w #$0000

;---------------------------------------------------------------------------------------------------

.check_next_file
STX.b $00

LDA.l SaveFileCopyOffsets,X
TAX

LDA.l $7003E1,X   ; [ENG-FS] JP save marker is at $3E1 (was US $3E5)
CMP.w #$55AA
BNE .no_name

PHX

LDX.b $00

LDA.w #$0001
STA.b $BF,X

PLX

LDA.w #EN_FileSelect_DrawLink_offset_x
STA.b $04

LDA.w #EN_FileSelect_DrawLink_offset_y
STA.b $02

PHX

JSR EN_FileSelect_DrawLink
JSR EN_FileSelect_DrawDeaths

PLX

JSR EN_FileSelect_CopyNameToStripes

.no_name
LDX.b $00
INX
INX
CPX.w #$0006
BCC .check_next_file

;---------------------------------------------------------------------------------------------------

SEP #$30

LDX.b $C8

LDA.b #$1C
STA.b $00

LDA.w EN_FileSelect_FairyY,X
STA.b $01

JSR EN_FileSelect_DrawFairy

LDY.b #$02

LDA.b $F6
AND.b #$C0

ORA.b $F4
AND.b #$FC
BEQ .exit

AND.b #$2C
BEQ .didnt_change_selection

AND.b #$08
BEQ .pressed_down

;---------------------------------------------------------------------------------------------------

LDA.b #$20 ; SFX3.20
STA.w $012F

DEC.b $C8
BPL .proceed_to_exit

LDA.b #$04
STA.b $C8

BRA .proceed_to_exit

;---------------------------------------------------------------------------------------------------

.pressed_down
LDA.b #$20 ; SFX3.20
STA.w $012F

INC.b $C8

LDA.b $C8
CMP.b #$05
BNE .proceed_to_exit

STZ.b $C8

.proceed_to_exit
BRA .exit

;---------------------------------------------------------------------------------------------------

.didnt_change_selection
LDA.b #$2C ; SFX2.2C
STA.w $012E

LDA.b $C8
CMP.b #$03
BEQ .copy_file
BCS .kill_file

LDA.b $C8
ASL A
TAX

LDA.b $BF,X
BEQ .no_file_there

LDA.b #$F1 ; SONG F1 - fade
STA.w $012C

STZ.b $C9

REP #$20

LDA.l SaveFileCopyOffsets,X
STA.b $00

LDA.b $C8
ASL A
INC A
INC A
STA.l $701FFE

SEP #$20

BRL EN_CopySaveToWRAM

;---------------------------------------------------------------------------------------------------

.no_file_there
STZ.b $C9

LDY.b #$04
BRA .set_module

;---------------------------------------------------------------------------------------------------

.copy_file
LDY.b #$02
BRA .check_for_some_file

.kill_file
LDY.b #$03

.check_for_some_file
LDA.b $BF
ORA.b $C1
ORA.b $C3
BNE .dont_error_beep

LDA.b #$3C ; SFX2.3C
STA.w $012E

BRA .exit

.dont_error_beep
STZ.b $C8

;---------------------------------------------------------------------------------------------------

.set_module
STY.b $10

STZ.b $11
STZ.b $B0

.exit
RTL

;===================================================================================================

CopySaveToWRAM:
EN_CopySaveToWRAM:
#_2C826E: LDX.b #$0F

#_2C8270: LDA.b #$00
#_2C8272: STA.l $001AC0,X
#_2C8276: STA.l $001AE0,X

#_2C827A: LDA.b #$00
#_2C827C: STA.l $001AB0,X
#_2C8280: STA.l $001AD0,X
#_2C8284: STA.l $001AF0,X

#_2C8288: PHB

#_2C8289: LDA.b #$7E
#_2C828B: PHA
#_2C828C: PLB

;---------------------------------------------------------------------------------------------------

#_2C828D: REP #$30

#_2C828F: LDY.w #$0000
#_2C8292: LDX.b $00

.copy_next
#_2C8294: LDA.l $700000,X
#_2C8298: STA.w $7EF000,Y

#_2C829B: LDA.l $700100,X
#_2C829F: STA.w $7EF100,Y

#_2C82A2: LDA.l $700200,X
#_2C82A6: STA.w $7EF200,Y

#_2C82A9: LDA.l $700300,X
#_2C82AD: STA.w $7EF300,Y

#_2C82B0: LDA.l $700400,X
#_2C82B4: STA.w $7EF400,Y

#_2C82B7: INX
#_2C82B8: INX

#_2C82B9: INY
#_2C82BA: INY
#_2C82BB: CPY.w #$0100
#_2C82BE: BNE .copy_next

;---------------------------------------------------------------------------------------------------

#_2C82C0: PLB

#_2C82C1: LDA.w #$0007
#_2C82C4: STA.l $7EC00D
#_2C82C8: STA.l $7EC013

#_2C82CC: LDA.w #$0000
#_2C82CF: STA.l $7EC00F
#_2C82D3: STA.l $7EC015

#_2C82D7: LDA.w #$6040 ; VRAM $C080
#_2C82DA: STA.w $0219

#_2C82DD: LDA.w #$4841
#_2C82E0: STA.w $021D

#_2C82E3: LDA.w #$007F
#_2C82E6: STA.w $021F

#_2C82E9: LDA.w #$FFFF
#_2C82EC: STA.w $0221

;---------------------------------------------------------------------------------------------------

#_2C82EF: SEP #$30

#_2C82F1: LDA.b #$80
#_2C82F3: STA.w $0204

#_2C82F6: LDA.b #$05
#_2C82F8: STA.b $10
#_2C82FA: STZ.b $11

#_2C82FC: STZ.w $010E

#_2C82FF: STZ.w $0710

#_2C8302: STZ.w $0AB2

#_2C8305: RTL

;===================================================================================================

Module02_CopyFile:
EN_Module02_CopyFile:
#_2C8306: STZ.w $0B9D

#_2C8309: JSL USFS_InjectPalette   ; [ENG-FS] keep US file-select palette in $7EC500

#_2C830D: LDA.b $11
#_2C830F: JSL JumpTableLong
#_2C8313: dl EN_ReinitializeFileSelectGraphics
#_2C8316: dl EN_FileSelect_UploadFancyBackground   ; [ENG-FS] US green-hex bg for copy screen
#_2C8319: dl EN_CopyFile_FindFileIndices
#_2C831C: dl EN_CopyFile_ChooseSelection
#_2C831F: dl EN_CopyFile_ChooseTarget
#_2C8322: dl EN_CopyFile_ConfirmSelection

;===================================================================================================

EN_CopyFile_FindFileIndices:
#_2C8325: LDA.b #$07

;===================================================================================================

EN_KILLFile_FindFileIndices:
#_2C8327: STA.b $14

#_2C8329: INC.b $11

#_2C832B: LDA.b #$0F
#_2C832D: STA.b $13

#_2C832F: STZ.w $0710

#_2C8332: LDX.b #$FE

.find_file
#_2C8334: INX
#_2C8335: INX

#_2C8336: LDA.b $BF,X
#_2C8338: BEQ .find_file

;---------------------------------------------------------------------------------------------------

#_2C833A: TXA
#_2C833B: LSR A
#_2C833C: STA.b $C8

#_2C833E: RTL

;===================================================================================================

EN_CopyFile_ChooseSelection:
PHB
PHK
PLB

JSR EN_CopyFile_SelectionAndBlinker

LDA.b $11
CMP.b #$03
BNE EN_FileSelect_TriggerTheStripes

LDA.b $1A
AND.b #$30
BNE EN_FileSelect_TriggerTheStripes

JSR EN_FilePicker_DeleteHeaderStripe

;===================================================================================================

EN_FileSelect_TriggerTheStripes:
#_2C8354: LDA.b #$01
#_2C8356: STA.b $14

#_2C8358: PLB

#_2C8359: RTL

;===================================================================================================

EN_CopyFile_ChooseTarget:
PHB
PHK
PLB

JSR EN_CopyFile_TargetSelectionAndBlink

LDA.b $11
CMP.b #$04
BNE .trigger_stripes

LDA.b $1A
AND.b #$30
BNE EN_FileSelect_TriggerTheStripes

JSR EN_FilePicker_DeleteHeaderStripe

.trigger_stripes
BRA EN_FileSelect_TriggerTheStripes

;===================================================================================================

EN_CopyFile_ConfirmSelection:
PHB
PHK
PLB

JSR EN_CopyFile_HandleConfirmation

JMP.w EN_FileSelect_TriggerTheStripes

;===================================================================================================

pool EN_FilePicker_DeleteHeaderStripe

.offset
dw $0004, $001E

pool off

;---------------------------------------------------------------------------------------------------

EN_FilePicker_DeleteHeaderStripe:
REP #$30

LDX.w #$0002

LDA.w #$00A9

.next_stripe
LDY.w #$000B
STY.b $00

LDY.w .offset,X

.next_byte
STA.w $1002,Y

INY
INY

DEC.b $00
BNE .next_byte

DEX
DEX
BPL .next_stripe

SEP #$30

RTS

;===================================================================================================

EN_CopyFile_FairyHeight:
db $57
db $6F
db $87
db $BF

;===================================================================================================

EN_CopyFile_CopyToMenuStripe:
dw $6761, $0E40 ; VRAM $C2CE | 16 bytes | Fixed horizontal
dw $00A9

dw $8761, $0E40 ; VRAM $C30E | 16 bytes | Fixed horizontal
dw $00A9

dw $C761, $0E40 ; VRAM $C38E | 16 bytes | Fixed horizontal
dw $00A9

dw $E761, $0E40 ; VRAM $C3CE | 16 bytes | Fixed horizontal
dw $00A9

dw $3011, $0100 ; VRAM $2260 | 2 bytes | Horizontal
dw $3583

dw $3111, $1440 ; VRAM $2262 | 22 bytes | Fixed horizontal
dw $3585

dw $3C11, $0100 ; VRAM $2278 | 2 bytes | Horizontal
dw $3584

dw $5011, $0EC0 ; VRAM $22A0 | 16 bytes | Fixed vertical
dw $3586

dw $5C11, $0EC0 ; VRAM $22B8 | 16 bytes | Fixed vertical
dw $3596

dw $5012, $0100 ; VRAM $24A0 | 2 bytes | Horizontal
dw $3593

dw $5112, $1440 ; VRAM $24A2 | 22 bytes | Fixed horizontal
dw $3595

dw $5C12, $0100 ; VRAM $24B8 | 2 bytes | Horizontal
dw $3594

db $FF ; end of stripes data

;===================================================================================================

EN_CopyFile_TargetStripeOffsetAdjuster:
#_2C83EB: db $00 ; File 1
#_2C83EC: db $0C ; File 2

;===================================================================================================

EN_CopyFile_NameStripeBufferOffset:
dw $003C ; File 1
dw $0064 ; File 2
dw $008C ; File 3

;===================================================================================================

EN_CopyFile_SelectionAndBlinker:
REP #$10

LDX.w #$00AC
STX.w $1000

.next_header_stripe
LDA.w EN_CopyFile_HeaderStripe,X
STA.w $1002,X

DEX
BPL .next_header_stripe

;---------------------------------------------------------------------------------------------------

REP #$20

LDX.w #$0000

.next_file_name
STX.b $00

LDA.b $BF,X
AND.w #$0001
BEQ .skip_this_file

LDA.l SaveFileCopyOffsets,X
TXY
TAX

LDA.w EN_CopyFile_NameStripeBufferOffset,Y
TAY

LDA.w #$0004        ; [ENG-FS] JP 4-char names (copy screen source list)
STA.b $02

.next_letter
LDA.l $7003D9,X
CLC
ADC.w #$1800
STA.w $1002,Y

CLC
ADC.w #$0010
STA.w $1016,Y

INX
INX

INY
INY

DEC.b $02
BNE .next_letter

.skip_this_file
LDX.b $00
INX
INX
CPX.w #$0006
BCC .next_file_name

;---------------------------------------------------------------------------------------------------

SEP #$30

LDX.b $C8

LDA.w EN_CopyFile_FairyIndent,X
STA.b $00

LDA.w EN_CopyFile_FairyHeight,X
STA.b $01

JSR EN_FileSelect_DrawFairy

LDA.b $F6
AND.b #$C0

ORA.b $F4
AND.b #$FC
BNE .made_input

BRL .exit

.made_input
AND.b #$2C
BEQ .made_selection

AND.b #$08
BEQ .didnt_press_up

LDX.b $C8
DEX
BMI .select_exit

;---------------------------------------------------------------------------------------------------

.prev_file_check
TXA
ASL A
TAY

LDA.w $00BF,Y
BNE .set_new_selection

DEX
BPL .prev_file_check

.select_exit
LDX.b #$03
BRA .set_new_selection

;---------------------------------------------------------------------------------------------------

.didnt_press_up
LDX.b $C8
INX
CPX.b #$03
BCS .went_too_far

.next_file_check
TXA
ASL A
TAY

LDA.w $00BF,Y
BNE .set_new_selection

INX
CPX.b #$03
BNE .next_file_check

BRA .set_new_selection

.went_too_far
CPX.b #$04
BNE .set_new_selection

LDX.b #$00
BRA .next_file_check

.set_new_selection
LDA.b #$20 ; SFX3.20
STA.w $012F

STX.b $C8
BRA .exit

;---------------------------------------------------------------------------------------------------

.made_selection
LDA.b #$2C ; SFX2.2C
STA.w $012E

LDA.b $C8
CMP.b #$03
BEQ EN_ReturnToFileSelect

;---------------------------------------------------------------------------------------------------

ASL A
STA.b $CC
STZ.b $CD

LDX.b #$49

.next_target_stripe
LDA.w EN_CopyFile_CopyToMenuStripe-1,X
STA.w $1035,X

DEX
BNE .next_target_stripe

;---------------------------------------------------------------------------------------------------

LDX.b $C8
CPX.b #$02
BEQ .selected_file_3

LDA.w EN_CopyFile_TargetStripeOffsetAdjuster,X
TAX

LDA.b #$62
STA.w $1036,X
STA.w $103C,X

LDA.b #$27
STA.w $1037,X

CLC
ADC.b #$20
STA.w $103D,X

.selected_file_3
INC.b $11

BRA .reset_cursor

;===================================================================================================

#EN_ReturnToFileSelect:
LDA.b #$01
STA.b $10

LDA.b #$01
STA.b $11

STZ.b $B0

.reset_cursor
STZ.b $C8

.exit
RTS

;===================================================================================================

EN_CopyFile_ConfirmationStripes:
dw $B461, $0E40 ; VRAM $C368 | 16 bytes | Fixed horizontal
dw $00A9

dw $D461, $0E40 ; VRAM $C3A8 | 16 bytes | Fixed horizontal
dw $00A9

dw $C662, $0D00 ; VRAM $C58C | 14 bytes | Horizontal
dw $1802, $180E, $180F, $1828, $18A9, $180E, $180A

dw $E662, $0D00 ; VRAM $C5CC | 14 bytes | Horizontal
dw $1812, $181E, $181F, $1838, $18A9, $181E, $181A

db $FF ; end of stripes data

;===================================================================================================

EN_CopyFile_TargetFairyX:
db $8C ; 1
db $8C ; 2
db $1C ; Exit

EN_CopyFile_TargetFairyY:
db $67 ; 1
db $7F ; 2
db $BF ; Exit

EN_CopyFile_BufferOffset:
dw $0038
dw $0060

EN_CopyFile_TargetNumerals:
dw $18E7 ; 1
dw $18E8 ; 2
dw $18E9 ; 3

;---------------------------------------------------------------------------------------------------

EN_CopyFile_TargetSelectionAndBlink:
LDA.b #$04
LDX.b #$01

.next_index_setup
CMP.b $CC
BEQ .dont_replace_index

STA.b $CA,X

DEX

.dont_replace_index
DEC A
DEC A
BPL .next_index_setup

;---------------------------------------------------------------------------------------------------

REP #$10

LDX.w #$0084
STX.b $0E

.next_header_stripe
LDA.w EN_CopyFile_TargetHeaderStripes,X
STA.w $1002,X

DEX
BPL .next_header_stripe

;---------------------------------------------------------------------------------------------------

REP #$20

LDX.w #$0000
STX.b $04

.next_filename_stripe
STX.b $00

CPX.b $CC
BEQ .skip_this_file

LDY.b $04

LDA.w EN_CopyFile_BufferOffset,Y
TAY

INC.b $04
INC.b $04

LDA.w EN_CopyFile_TargetNumerals,X
STA.w $1002,Y

CLC
ADC.w #$0010
STA.w $1016,Y

LDA.b $BF,X
BEQ .skip_this_file

LDA.w #$0004        ; [ENG-FS] JP 4-char names (copy screen target list)
STA.b $02

LDA.l SaveFileCopyOffsets,X
TAX

.next_letter
LDA.l $7003D9,X
CLC
ADC.w #$1800
STA.w $1006,Y

CLC
ADC.w #$0010
STA.w $101A,Y

INX
INX

INY
INY

DEC.b $02
BNE .next_letter

.skip_this_file
LDX.b $00
INX
INX
CPX.w #$0006
BCC .next_filename_stripe

;---------------------------------------------------------------------------------------------------

LDX.b $0E
STX.w $1000

SEP #$30

LDX.b $C8

LDA.w EN_CopyFile_TargetFairyX,X
STA.b $00

LDA.w EN_CopyFile_TargetFairyY,X
STA.b $01

JSR EN_FileSelect_DrawFairy

LDA.b $F6
AND.b #$C0

ORA.b $F4
AND.b #$FC
BEQ .exit

AND.b #$2C
BEQ .made_selection

AND.b #$08
BEQ .didnt_press_up

LDX.b $C8
DEX
BPL .select_exit

LDX.b #$02
BRA .select_exit

.didnt_press_up
LDX.b $C8
INX
CPX.b #$03
BCC .select_exit

LDX.b #$00

;---------------------------------------------------------------------------------------------------

.select_exit
LDA.b #$20 ; SFX3.20
STA.w $012F

STX.b $C8
BRA .exit

;---------------------------------------------------------------------------------------------------

.made_selection
LDA.b #$2C ; SFX2.2C
STA.w $012E

LDX.b $C8
CPX.b #$02
BEQ .selecting_exit

LDA.b $CA,X
STA.b $CA
STZ.b $CB

LDX.b #$30

.next_confirm_stripe
LDA.w EN_CopyFile_ConfirmationStripes,X
STA.w $1036,X

DEX
BPL .next_confirm_stripe

LDA.b $C8
BNE .dont_reposition_deleted_name

LDA.b #$62
STA.w $1036
STA.w $103C

LDA.b #$14
STA.w $1037

CLC
ADC.b #$20
STA.w $103D

.dont_reposition_deleted_name
INC.b $11
BRA .reset_selection

;---------------------------------------------------------------------------------------------------

.selecting_exit
JSR EN_ReturnToFileSelect

.reset_selection
STZ.b $C8

.exit
RTS

;===================================================================================================

pool EN_CopyFile_HandleConfirmation

.fairy_y
db $AF ; Yes
db $BF ; No

pool off

;---------------------------------------------------------------------------------------------------

EN_CopyFile_HandleConfirmation:
LDX.b $C8

LDA.b #$1C
STA.b $00

LDA.w .fairy_y,X
STA.b $01

JSR EN_FileSelect_DrawFairy

LDA.b $F6
AND.b #$C0

ORA.b $F4
AND.b #$FC
BEQ .exit

AND.b #$2C
BEQ .made_selection

AND.b #$24
BEQ .select_or_down

LDA.b #$20 ; SFX3.20
STA.w $012F

INC.b $C8

LDA.b $C8
CMP.b #$02
BCC .exit

STZ.b $C8
BRA .exit

;---------------------------------------------------------------------------------------------------

.select_or_down
LDA.b #$20 ; SFX3.20
STA.w $012F

DEC.b $C8
BPL .exit

LDA.b #$01
STA.b $C8
BRA .exit

;---------------------------------------------------------------------------------------------------

.made_selection
LDA.b #$2C ; SFX2.2C
STA.w $012E

LDA.b $C8
BNE .decided_against_it

REP #$30

LDX.b $CA

LDA.l SaveFileCopyOffsets,X
TAY

LDX.b $CC

LDA.l SaveFileCopyOffsets,X
TAX

JSR EN_CopyFile_CopyData

LDX.b $CA

LDA.w #$0001
STA.b $BF,X

SEP #$30

;---------------------------------------------------------------------------------------------------

.decided_against_it
JSR EN_ReturnToFileSelect

STZ.b $C8

.exit
RTS

;===================================================================================================

EN_CopyFile_CopyData:
#_2C8690: SEP #$20

#_2C8692: PHB

#_2C8693: LDA.b #$70
#_2C8695: PHA
#_2C8696: PLB

#_2C8697: REP #$20

#_2C8699: LDA.w #$0080
#_2C869C: STA.b $00

.next
#_2C869E: LDA.w $700000,X
#_2C86A1: STA.w $700000,Y

#_2C86A4: LDA.w $700100,X
#_2C86A7: STA.w $700100,Y

#_2C86AA: LDA.w $700200,X
#_2C86AD: STA.w $700200,Y

#_2C86B0: LDA.w $700300,X
#_2C86B3: STA.w $700300,Y

#_2C86B6: LDA.w $700400,X
#_2C86B9: STA.w $700400,Y

#_2C86BC: INY
#_2C86BD: INY

#_2C86BE: INX
#_2C86BF: INX

#_2C86C0: DEC.b $00
#_2C86C2: BNE .next

;---------------------------------------------------------------------------------------------------

#_2C86C4: SEP #$20 ; !USELESS

#_2C86C6: PLB

#_2C86C7: REP #$20

#_2C86C9: RTS

;===================================================================================================

EN_KILLFile_FairyY:
db $67 ; File 1
db $7F ; File 2
db $97 ; File 3
db $BF ; Exit

;---------------------------------------------------------------------------------------------------

EN_KILL_OK_stripes:
dw $A761, $2440 ; VRAM $C34E | 38 bytes | Fixed horizontal
dw $00A9

dw $C761, $2440 ; VRAM $C38E | 38 bytes | Fixed horizontal
dw $00A9

dw $0762, $2440 ; VRAM $C40E | 38 bytes | Fixed horizontal
dw $00A9

dw $2762, $2440 ; VRAM $C44E | 38 bytes | Fixed horizontal
dw $00A9

dw $C662, $2100 ; VRAM $C58C | 34 bytes | Horizontal
dw $1804, $1821, $1800, $1822, $1804, $18A9, $1823, $1807
dw $18AF, $1822, $18A9, $180F, $180B, $1800, $1828, $1804
dw $1821

dw $E662, $2100 ; VRAM $C5CC | 34 bytes | Horizontal
dw $1814, $1831, $1810, $1832, $1814, $18A9, $1833, $1817
dw $18BF, $1832, $18A9, $181F, $181B, $1810, $1838, $1814
dw $1831

db $FF ; end of stripes data

;===================================================================================================

EN_KILL_OK_FileNameStripesAdjustment:
#_2C8733: db $00 ; File 1
#_2C8734: db $0C ; File 2

;===================================================================================================

Module03_KILLFile:
EN_Module03_KILLFile:
#_2C8735: JSL USFS_InjectPalette   ; [ENG-FS] keep US file-select palette in $7EC500
#_2C8739: LDA.b $11
#_2C873B: JSL JumpTableLong
#_2C873F: dl EN_ReinitializeFileSelectGraphics
#_2C8742: dl EN_FileSelect_UploadFancyBackground   ; [ENG-FS] US green-hex bg for erase screen
#_2C8745: dl EN_KILLFile_SetUp
#_2C8748: dl EN_KILLFile_HandleSelection
#_2C874B: dl EN_KILLFile_HandleConfirmation

;===================================================================================================

EN_KILLFile_SetUp:
#_2C874E: LDA.b #$08

#_2C8750: JMP.w EN_KILLFile_FindFileIndices

;===================================================================================================

EN_KILLFile_HandleSelection:
#_2C8753: PHB
#_2C8754: PHK
#_2C8755: PLB

#_2C8756: LDA.b $C8
#_2C8758: CMP.b #$03
#_2C875A: BCS .selecting_exit

#_2C875C: STA.w $0B9D

.selecting_exit
#_2C875F: JSR EN_KILLFile_ChooseTarget

#_2C8762: JMP.w EN_FileSelect_TriggerTheStripes

;===================================================================================================

EN_KILLFile_HandleConfirmation:
#_2C8765: PHB
#_2C8766: PHK
#_2C8767: PLB

#_2C8768: JSR EN_KILLFile_VerifyDeletion

#_2C876B: JMP.w EN_FileSelect_TriggerTheStripes

;===================================================================================================

EN_KILLFile_ChooseTarget:
REP #$10

LDX.w #$00FD

.next_blankname_stripe
LDA.w EN_KILLFile_BlankNameStripes-1,X
STA.w $1001,X

DEX
BNE .next_blankname_stripe

;---------------------------------------------------------------------------------------------------

REP #$20

LDX.w #$0000

.next_filename_stripe
STX.b $00

LDA.b $BF,X
AND.w #$0001
BEQ .skip_this_file

LDA.l SaveFileCopyOffsets,X
TAX
JSR EN_FileSelect_CopyNameToStripes

.skip_this_file
LDX.b $00
INX
INX
CPX.w #$0006
BCC .next_filename_stripe

;---------------------------------------------------------------------------------------------------

SEP #$30

LDX.b $C8

LDA.w EN_KILLFile_FairyX,X
STA.b $00

LDA.w EN_KILLFile_FairyY,X
STA.b $01

JSR EN_FileSelect_DrawFairy

;---------------------------------------------------------------------------------------------------

LDY.b #$02

LDA.b $F4
AND.b #$20
BNE .pressed_down_or_select

LDA.b $F4
AND.b #$0C
BEQ .check_for_pick

AND.b #$04
BNE .pressed_down_or_select

LDA.b #$20 ; SFX3.20
STA.w $012F

LDY.b #$FE

LDX.b $C8
DEX
BMI .select_exit

.check_prev_file
TXA
ASL A
TAY

LDA.w $00BF,Y
BNE .check_for_pick

DEX
BPL .check_prev_file

;---------------------------------------------------------------------------------------------------

.select_exit
LDX.b #$03
BRA .check_for_pick

;---------------------------------------------------------------------------------------------------

.pressed_down_or_select
LDA.b #$20 ; SFX3.20
STA.w $012F

LDX.b $C8
INX
CPX.b #$03
BCS .not_on_file

.check_next_file
TXA
ASL A
TAY

LDA.w $00BF,Y
BNE .check_for_pick

INX
CPX.b #$03
BNE .check_next_file

BRA .check_for_pick

.not_on_file
CPX.b #$04
BNE .check_for_pick

LDX.b #$00
BRA .check_next_file

;---------------------------------------------------------------------------------------------------

.check_for_pick
STX.b $C8

LDA.b $F6
AND.b #$C0

ORA.b $F4
AND.b #$D0
BEQ .exit

LDA.b #$2C ; SFX2.2C
STA.w $012E

LDA.b $C8
CMP.b #$03
BEQ .picked_exit

LDX.b #$64

.next_ok
LDA.w EN_KILL_OK_stripes,X
STA.w $1002,X

DEX
BPL .next_ok

;---------------------------------------------------------------------------------------------------

INC.b $11

LDX.b $C8
CPX.b #$02
BEQ .no_filename_stripe_adjustment

LDA.w EN_KILL_OK_FileNameStripesAdjustment,X
TAX

LDA.b #$62
STA.w $1002,X
STA.w $1008,X

LDA.b #$67
STA.w $1003,X

CLC
ADC.b #$20
STA.w $1009,X

.no_filename_stripe_adjustment
LDA.b $C8
STA.b $B0

STZ.b $C8
BRA .exit

;---------------------------------------------------------------------------------------------------

.picked_exit
SEP #$30

JSR EN_ReturnToFileSelect

.exit
RTS

;===================================================================================================

pool EN_KILLFile_VerifyDeletion

.fairy_pos_y
db $AF
db $BF

pool off

;---------------------------------------------------------------------------------------------------

EN_KILLFile_VerifyDeletion:
LDA.b $B0
ASL A
STA.b $00

SEP #$30

LDX.b $C8

LDA.b #$1C
STA.b $00

LDA.w .fairy_pos_y,X
STA.b $01

JSR EN_FileSelect_DrawFairy

;---------------------------------------------------------------------------------------------------

LDY.b #$02

LDA.b $F4
AND.b #$2C
BEQ .not_selection_change_input

AND.b #$24
BNE .pressed_select_or_down

DEX
BRA .move_kiss_of_death

.pressed_select_or_down
INX

.move_kiss_of_death
TXA
AND.b #$01
STA.b $C8

LDA.b #$20 ; SFX3.20
STA.w $012F

;---------------------------------------------------------------------------------------------------

.not_selection_change_input
LDA.b $F6
AND.b #$C0

ORA.b $F4
AND.b #$D0
BEQ .exit

LDA.b #$2C ; SFX2.2C
STA.w $012E

LDA.b $C8
BNE .chickened_out

LDA.b #$22 ; SFX3.22
STA.w $012F
STZ.w $012E

REP #$30

LDA.b $B0
AND.w #$00FF
ASL A
TAX

STZ.b $BF,X

LDA.l SaveFileCopyOffsets,X
TAX

;---------------------------------------------------------------------------------------------------

LDY.w #$0000
TYA

.clear_next
STA.l $700000,X
STA.l $700100,X
STA.l $700200,X
STA.l $700300,X
STA.l $700400,X
STA.l $700F00,X
STA.l $701000,X
STA.l $701100,X
STA.l $701200,X
STA.l $701300,X

INX
INX

INY
INY
CPY.w #$0100
BNE .clear_next

;---------------------------------------------------------------------------------------------------

SEP #$30

.chickened_out
JSR EN_ReturnToFileSelect

STZ.b $B0

.exit
RTS

;===================================================================================================

pool EN_FileSelect_CopyNameToStripes

.name_offset
dw $0008
dw $005C
dw $00B0

.hearts_offset
dw $0016
dw $006A
dw $00BE

pool off

;---------------------------------------------------------------------------------------------------

EN_FileSelect_CopyNameToStripes:
PHX

LDY.b $00

LDA.w .name_offset,Y
TAY

LDA.w #$0004        ; [ENG-FS] JP 4-char names (was 6)
STA.b $02

;---------------------------------------------------------------------------------------------------

.next_character
LDA.l $7003D9,X
CLC
ADC.w #$1800
STA.w $1002,Y

CLC
ADC.w #$0010
STA.w $102C,Y

INX
INX

INY
INY

DEC.b $02
BNE .next_character
; [ENG-FS] JP 4-char names (was 6) — see the LDA #$0004 above

;---------------------------------------------------------------------------------------------------

PLX

LDY.w #$0001

LDA.l $70036C,X
AND.w #$00FF
LSR A
LSR A
LSR A
STA.b $02

LDX.b $00

LDY.w .hearts_offset,X
STY.b $04

LDA.w #$0520
LDX.w #$000A

;---------------------------------------------------------------------------------------------------

.next_heart
STA.w $1002,Y

INY
INY

DEX
BNE .same_row

PHA

LDA.b $04
CLC
ADC.w #$002A
TAY

PLA

.same_row
DEC.b $02
BNE .next_heart

RTS

;===================================================================================================

pool EN_FileSelect_DrawLink

.unused
db $01, $06, $0B

.offset_x
db $34

.offset_y
db $43 ; file 1
db $63 ; file 2
db $83 ; file 3

.oam_offset
db $28 ; file 1
db $3C ; file 2
db $50 ; file 3

.sword_gfx
db $85 ; fighter sword
db $A1 ; master sword
db $A1 ; tempered sword
db $A1 ; gold sword

.shield_gfx
db $C4 ; fighter shield
db $CA ; fire shield
db $E0 ; mirror shield

.sword_props
db $72 ; file 1
db $76 ; file 2
db $7A ; file 3

.shield_props
db $32 ; file 1
db $36 ; file 2
db $3A ; file 3

.link_props
db $30 ; file 1
db $34 ; file 2
db $38 ; file 3

pool off

;---------------------------------------------------------------------------------------------------

EN_FileSelect_DrawLink:
REP #$30

LDA.w #$0116
ASL A
STA.w $0100

LDA.b $00
AND.w #$00FF
TAX

LDA.l SaveFileCopyOffsets,X
STA.b $0E

;---------------------------------------------------------------------------------------------------

SEP #$30

LDA.b $00
LSR A
TAY

LDA.w .oam_offset,Y
TAX

LDA.b ($04)
CLC
ADC.b #$0C
STA.w $0800,X
STA.w $0804,X

LDA.b ($02),Y
CLC
ADC.b #$FB
STA.w $0801,X

CLC
ADC.b #$08
STA.w $0805,X

LDA.w .sword_props,Y
STA.w $0803,X
STA.w $0807,X

;---------------------------------------------------------------------------------------------------

PHY
PHX

REP #$10

LDX.b $0E

LDA.l $700359,X

SEP #$10

PLX

TAY
DEY
BPL .have_sword

LDA.b #$F0
STA.w $0801,X
STA.w $0805,X

INY

.have_sword
LDA.w .sword_gfx,Y
STA.w $0802,X

CLC
ADC.b #$10
STA.w $0806,X

;---------------------------------------------------------------------------------------------------

PLY

PHX
TXA

LSR A
LSR A
TAX

LDA.b #$00
STA.w $0A20,X
STA.w $0A21,X

PLA
CLC
ADC.b #$08
TAX

LDA.b ($04)
CLC
ADC.b #$FB
STA.w $0800,X

LDA.b ($02),Y
CLC
ADC.b #$0A
STA.w $0801,X

LDA.w .shield_props,Y
STA.w $0803,X

;---------------------------------------------------------------------------------------------------

PHY
PHX

REP #$10

LDX.b $0E

LDA.l $70035A,X

SEP #$10

PLX

TAY
DEY
BPL .have_shield

LDA.b #$F0
STA.w $0801,X

INY

.have_shield
LDA.w .shield_gfx,Y
STA.w $0802,X

PLY
PHX

TXA
LSR A
LSR A
TAX

LDA.b #$02
STA.w $0A20,X

PLA
CLC
ADC.b #$04
TAX

LDA.b ($04)
STA.w $0800,X
STA.w $0804,X

LDA.b #$00
STA.w $0802,X

LDA.b #$02
STA.w $0806,X

LDA.w .link_props,Y
STA.w $0803,X

ORA.b #$40
STA.w $0807,X

LDA.b ($02),Y
STA.w $0801,X

CLC
ADC.b #$08
STA.w $0805,X

TXA
LSR A
LSR A
TAX

LDA.b #$02
STA.w $0A20,X
STA.w $0A21,X

REP #$30

RTS

;===================================================================================================

pool EN_FileSelect_DrawFairy

.char
db $A8
db $AA

pool off

;---------------------------------------------------------------------------------------------------

EN_FileSelect_DrawFairy:
LDA.b $00
STA.w $0800

LDA.b $01
STA.w $0801

PHX

LDX.b #$00

LDA.b $1A
AND.b #$08
BEQ .frame_0

INX

.frame_0
LDA.w .char,X
STA.w $0802

PLX

LDA.b #$7E
STA.w $0803

LDA.b #$02
STA.w $0A20

;---------------------------------------------------------------------------------------------------

#EN_EXIT_0CD7CA:
RTS

;===================================================================================================

pool EN_FileSelect_DrawDeaths

.digit_char
db $D0 ; 0
db $AC ; 1
db $AD ; 2
db $BC ; 3
db $BD ; 4
db $AE ; 5
db $AF ; 6
db $BE ; 7
db $BF ; 8
db $C0 ; 9

.buffer_offset
db $04 ; ..#
db $10 ; .#.
db $1C ; #..

.digit_position_x
db $0C ; ..#
db $04 ; .#.
db $FC ; #..

pool off

;---------------------------------------------------------------------------------------------------

EN_FileSelect_DrawDeaths:
REP #$30

LDA.b $02
PHA
STA.b $08

LDA.b $04
PHA
STA.b $0A

LDX.b $0E

LDA.l $700401,X   ; [ENG-FS] JP GAMESPLAYED is at $401 (US $405); $FFFF = new game, skip death count
CMP.w #$FFFF

BNE .continue

JMP.w .exit

;---------------------------------------------------------------------------------------------------

.continue
CMP.w #$03E8
BCC .under_1000

LDA.w #$0009
STA.b $02
STA.b $04
STA.b $06

BRA .done_number

.under_1000
LDY.w #$0000

.next_100
CMP.w #$000A
BCC .under_100

SEC
SBC.w #$000A

INY
BRA .next_100


.under_100
STA.b $02
TYA
LDY.w #$0000

.next_10
CMP.w #$000A
BCC .under_10

SEC
SBC.w #$000A
INY

BRA .next_10

.under_10
STA.b $04
STY.b $06

;---------------------------------------------------------------------------------------------------

.done_number
LDX.w #$0004

LDA.b $06
BNE .skip_digit

DEX
DEX

LDA.b $04
BNE .skip_digit

DEX
DEX

.skip_digit
SEP #$30

LDA.b $00
LSR A
TAY

LDA.w .buffer_offset,Y
TAY

;---------------------------------------------------------------------------------------------------

.next_digit
PHX

LDA.b $02,X
TAX

LDA.w .digit_char,X
STA.w $0802,Y

PHY

LDA.b $00
LSR A
TAY

LDA.b ($08),Y
CLC
ADC.b #$10

PLY
STA.w $0801,Y

PLA
PHA

LSR A
TAX

LDA.b ($0A)
CLC
ADC.w .digit_position_x,X
STA.w $0800,Y

LDA.b #$3C
STA.w $0803,Y

PHY

TYA
LSR A
LSR A
TAY

LDA.b #$00
STA.w $0A20,Y

PLY
INY
INY
INY
INY

PLX
DEX
DEX
BPL .next_digit

;---------------------------------------------------------------------------------------------------

REP #$30

.exit
PLA
STA.b $04

PLA
STA.b $02

RTS

;===================================================================================================

Module04_NameFile:
EN_Module04_NameFile:
#_2C8B3E: JSL USFS_InjectPalette   ; [ENG-FS] keep US file-select palette in $7EC500
#_2C8B42: LDA.b $11
#_2C8B44: JSL JumpTableLong
#_2C8B48: dl EN_NameFile_EraseSave
#_2C8B4B: dl EN_NameFile_FillBackground   ; [ENG-FS] US green-hex bg for the name screen
#_2C8B4E: dl EN_NameFile_MakeScreenVisible
#_2C8B51: dl EN_NameFile_DoTheNaming

;===================================================================================================

EN_NameFile_EraseSave:
JSL EN_ReinitializeFileSelectGraphics

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

TAX

;---------------------------------------------------------------------------------------------------

LDY.w #$0000
TYA

.next_clear
STA.l $700000,X
STA.l $700100,X
STA.l $700200,X
STA.l $700300,X
STA.l $700400,X

INX
INX

INY
INY
CPY.w #$0100
BNE .next_clear

;---------------------------------------------------------------------------------------------------

LDX.w $0200

; [ENG-FS] Blank only the JP 4-character name ($3D9-$3DF). The US source blanked six
; words ($3D9-$3E3) for its 6-char name, but in the JP layout $3E1 is the save marker
; (SCHKSML) and $3E3 is GPSEWER (games-played-in-sewer). Writing $00A9 there left GPSEWER
; = $00A9 (169) on every erase, and InitializeSaveFile never clears it, so a fresh file
; showed 169+ "games played" (summed into GAMESPLAYED $401 at the credits). Matches the
; original JP erase, which blanks exactly these four name words and touches nothing past them.
LDA.w #$00A9
STA.l $7003D9,X
STA.l $7003DB,X
STA.l $7003DD,X
STA.l $7003DF,X

SEP #$30

RTL

;===================================================================================================

EN_NameFile_MakeScreenVisible:
LDA.b #$05
JSR EN_Intro_SetStripesAndAdvance

LDA.b #$0F
STA.b $13

STZ.w $0710

RTL

;===================================================================================================
; [ENG-FS] US-only helpers/tables referenced by the grafted US file-select routines but
; absent from the JP disassembly (the two sibling disasms don't share every label):
;  - Intro_SetStripesAndAdvance: US refactored the inline "STA $14 : INC $11" into this helper
;  - CopyFile_FairyIndent / KILLFile_FairyX: per-slot fairy X-indent tables (US split X from Y)
EN_Intro_SetStripesAndAdvance:
STA.b $14
INC.b $11
RTS

EN_CopyFile_FairyIndent:
db $24 ; File 1
db $24 ; File 2
db $24 ; File 3
db $1C ; Exit

EN_KILLFile_FairyX:
db $24 ; File 1
db $24 ; File 2
db $24 ; File 3
db $1C ; Exit

;===================================================================================================

EN_NameFile_CharacterLayout:
db $06, $07, $5F, $09, $59, $59, $1A, $1B
db $1C, $1D, $1E, $1F, $20, $21, $60, $23
db $59, $59, $76, $77, $78, $79, $7A, $59
db $59, $59, $00, $01, $02, $03, $04, $05
db $10, $11, $12, $13, $59, $59, $24, $5F
db $26, $27, $28, $29, $2A, $2B, $2C, $2D
db $59, $59, $7B, $7C, $7D, $7E, $7F, $59
db $59, $59, $0A, $0B, $0C, $0D, $0E, $0F
db $40, $41, $42, $59, $59, $59, $2E, $2F
db $30, $31, $32, $33, $40, $41, $42, $59
db $59, $59, $61, $3F, $45, $46, $59, $59
db $59, $59, $14, $15, $16, $17, $18, $19
db $44, $59, $6F, $6F, $59, $59, $59, $59
db $59, $59, $59, $5A, $44, $59, $6F, $6F
db $59, $59, $5A, $44, $59, $6F, $6F, $59
db $59, $59, $59, $59, $59, $59, $59, $5A

;===================================================================================================

EN_NameFile_CursorPositionX:
dw $01F0, $0000, $0010, $0020
dw $0030, $0040, $0050, $0060
dw $0070, $0080, $0090, $00A0
dw $00B0, $00C0, $00D0, $00E0
dw $00F0, $0100, $0110, $0120
dw $0130, $0140, $0150, $0160
dw $0170, $0180, $0190, $01A0
dw $01B0, $01C0, $01D0, $01E0

EN_NameFile_CursorIndexMovementX:
dw $0001 ; Right
dw $00FF ; Left

EN_NameFile_CursorIndexBoundaryX:
dw $0020 ; Right
dw $00FF ; Left

EN_NameFile_CursorIndexWrapX:
dw $0000 ; Right
dw $001F ; Left

;===================================================================================================

EN_NameFile_CursorPositionY:
db $83, $93, $A3, $B3

EN_NameFile_CursorIndexMovementY:
db $01, $FF

EN_NameFile_CursorIndexBoundaryY:
db $04, $FF

EN_NameFile_CursorStickY:
db $00, $03

EN_NameFile_YtoXIndexOffset:
dw $0000, $0020, $0040, $0060

;===================================================================================================

EN_NameFile_HeartXPosition:
db $1F, $2F, $3F, $4F, $5F, $6F

; (padding removed: NameFile_CursorMovement has no fixed address constraint in bank $2C)
EN_NameFile_CursorMovement:
dw  -1,   1,  -1,   1
dw  -1,   1,  -1,   1
dw  -1,   1,  -1,   1
dw  -1,   1,  -1,   1
dw  -2,   2,  -2,   2
dw  -2,   2,  -2,   2
dw  -4,   4

;===================================================================================================

EN_NameFile_DoTheNaming:
.check_x_scroll
LDY.w $0B13
BEQ .not_busy_scrolling_x

TYA
CMP.b #$31
BEQ .hit_target_scroll_x

CLC
ADC.b #$04
STA.w $0B13

.hit_target_scroll_x
LDA.w $0B10
ASL A
TAX

REP #$20

DEY

LDA.w $0630
CMP.l EN_NameFile_CursorPositionX,X
BNE .not_at_valid_x_position

SEP #$20

LDA.b #$30
STA.w $0B13

LDA.b $F0
AND.b #$03
BNE .had_lr_input

STZ.w $0B13

.had_lr_input
JSR EN_NameFile_CheckForScrollInputX
BRA .check_x_scroll

;---------------------------------------------------------------------------------------------------

.not_at_valid_x_position
REP #$20

LDX.w $0B16
BNE .last_move_left

INY
INY

.last_move_left
LDA.w $0630

TYX

CLC
ADC.l EN_NameFile_CursorMovement,X
AND.w #$01FF
STA.w $0630

SEP #$20

BRA .check_y_scroll

;---------------------------------------------------------------------------------------------------

.not_busy_scrolling_x
JSR EN_NameFile_CheckForScrollInputX

.check_y_scroll
LDA.w $0B14
BEQ .not_busy_scrolling_y

LDX.w $0B15
LDY.b #$02

LDA.w $0B11
CMP.l EN_NameFile_CursorPositionY,X
BNE .not_at_valid_y_position

STZ.w $0B14

JSR EN_NameFile_CheckForScrollInputY
BRA .check_y_scroll

.not_at_valid_y_position
BMI .add_y_scroll

LDY.b #$FE

.add_y_scroll
TYA
CLC
ADC.w $0B11
STA.w $0B11
BRA .done_y

.not_busy_scrolling_y
JSR EN_NameFile_CheckForScrollInputY

;---------------------------------------------------------------------------------------------------

.done_y
LDX.b #$00
TXY
LDA.b #$18
STA.b $00

.next_horizontal_bar_object
LDA.b $00
STA.w $0800,Y

CLC
ADC.b #$08
STA.b $00

LDA.w $0B11
STA.w $0801,Y

LDA.b #$2E
STA.w $0802,Y

LDA.b #$3C
STA.w $0803,Y

STZ.w $0A20,X

INY
INY
INY
INY

INX
CPX.b #$1A
BNE .next_horizontal_bar_object

;---------------------------------------------------------------------------------------------------

PHX

LDX.w $0B12

LDA.l EN_NameFile_HeartXPosition,X
STA.w $0800,Y

LDA.b #$58
STA.w $0801,Y

PLX

LDA.b #$29
STA.w $0802,Y

LDA.b #$0C
STA.w $0803,Y

STZ.w $0A20,X

LDA.w $0B13
ORA.w $0B14
BNE .busy_scrolling

LDA.b $F4
AND.b #$10
BEQ .no_start_press

JMP.w .confirm_name

.no_start_press
LDA.b $F4
AND.b #$C0
BNE .select_item

LDA.b $F6
AND.b #$C0
BNE .select_item

.busy_scrolling
JMP.w .exit

.select_item
LDA.b #$2B ; SFX2.2B
STA.w $012E

REP #$30

LDA.w $0B15
AND.w #$00FF
ASL A
TAX

LDA.l EN_NameFile_YtoXIndexOffset,X
CLC
ADC.w $0B10
AND.w #$00FF
TAX

SEP #$20

LDA.l EN_NameFile_CharacterLayout,X
CMP.b #$5A
BEQ .back_arrow

CMP.b #$44
BEQ .forward_arrow

CMP.b #$6F
BEQ .confirm_name

STA.b $00
STZ.b $01

BRA .written_character

;---------------------------------------------------------------------------------------------------

.back_arrow
LDA.w $0B12
BNE .nonzero

LDA.b #$03        ; [ENG-FS] JP 4-char names: last slot is 3 (was 5 for US 6-char)
STA.w $0B12

BRA .exit

.nonzero
DEC.w $0B12
BRA .exit


.forward_arrow
INC.w $0B12

LDA.w $0B12
CMP.b #$04        ; [ENG-FS] JP 4-char names: wrap after slot 3 (was 6 for US 6-char)
BNE .nowrap

STZ.w $0B12

.nowrap
BRA .exit

;---------------------------------------------------------------------------------------------------

.written_character
REP #$30

AND.w #$000F
STA.b $02

LDA.w $0B12
AND.w #$00FF
ASL A
TAY

CLC
ADC.w $0200
TAX

LDA.b $00
AND.w #$FFF0
ASL A
ORA.b $02
STA.l $7003D9,X

JSR EN_NameFile_DrawSelectedCharacter

BRA .forward_arrow

;---------------------------------------------------------------------------------------------------

.confirm_name
REP #$30

STZ.b $02

.write_name_to_save
LDA.w $0200
CLC
ADC.b $02
TAX

LDA.l $7003D9,X
CMP.w #$00A9
BNE EN_InitializeSaveFile

LDA.b $02
CMP.w #$0006 ; [ENG-FS] JP 4-char name ($3D9-$3DF); was #$000A (US 6-char, walks into $3E1/$3E3)
BEQ .finished

INC A
INC A
STA.b $02
BRA .write_name_to_save


.finished
SEP #$20

LDA.b #$3C ; SFX2.3C
STA.w $012E

.exit
SEP #$30

RTL

;===================================================================================================

EN_InitializeSaveFile:
#_2C8E82: SEP #$30

#_2C8E84: PHB

#_2C8E85: LDA.b #DefaultSaveFileItems>>16
#_2C8E87: PHA
#_2C8E88: PLB

#_2C8E89: REP #$30

#_2C8E8B: LDA.b $C8
#_2C8E8D: ASL A
#_2C8E8E: INC A
#_2C8E8F: INC A
#_2C8E90: STA.l $701FFE

#_2C8E94: TAX

#_2C8E95: LDA.l SaveFileOffsets,X
#_2C8E99: STA.b $00

#_2C8E9B: TAX

;---------------------------------------------------------------------------------------------------

#_2C8E9C: LDA.w #$55AA
#_2C8E9F: STA.l $7003E1,X

; Open the bomb walls for red rang hut and kak restock hut
#_2C8EA3: LDA.w #$F000
#_2C8EA6: STA.l $70020C,X
#_2C8EAA: STA.l $70020E,X

#_2C8EAE: LDA.w #$FFFF
#_2C8EB1: STA.l $700401,X

#_2C8EB5: LDA.w #$001D
#_2C8EB8: STA.b $02

;---------------------------------------------------------------------------------------------------

#_2C8EBA: LDY.w #$003C

#_2C8EBD: CPX.w #$0000
#_2C8EC0: BNE .copy_next

#_2C8EC2: LDA.l Player2JoypadReturn
#_2C8EC6: AND.w #$00FF
#_2C8EC9: CMP.w #$0060 ; RTS
#_2C8ECC: BEQ .copy_next

#_2C8ECE: LDA.l $7003D9
#_2C8ED2: CMP.w #$00AF
#_2C8ED5: BNE .copy_next

#_2C8ED7: LDA.w #$00F0 ; mushroom received
#_2C8EDA: STA.l $700212,X

#_2C8EDE: LDA.w #$1502
#_2C8EE1: STA.l $7003C5,X

#_2C8EE5: LDA.w #$0100
#_2C8EE8: STA.l $7003C7,X

#_2C8EEC: LDY.w #$0000

;---------------------------------------------------------------------------------------------------

.copy_next
#_2C8EEF: LDA.w DefaultSaveFileItems,Y
#_2C8EF2: STA.l $700340,X

#_2C8EF6: INX
#_2C8EF7: INX

#_2C8EF8: INY
#_2C8EF9: INY

#_2C8EFA: DEC.b $02
#_2C8EFC: BPL .copy_next

;---------------------------------------------------------------------------------------------------

#_2C8EFE: LDX.b $00

#_2C8F00: LDY.w #$0000
#_2C8F03: TYA

.build_checksum
#_2C8F04: CLC
#_2C8F05: ADC.l $700000,X

#_2C8F09: INX
#_2C8F0A: INX

#_2C8F0B: INY
#_2C8F0C: CPY.w #$027F
#_2C8F0F: BNE .build_checksum

#_2C8F11: STA.b $02

#_2C8F13: LDX.b $00

#_2C8F15: LDA.w #$5A5A
#_2C8F18: SEC
#_2C8F19: SBC.b $02
#_2C8F1B: STA.l $7004FE,X

;---------------------------------------------------------------------------------------------------

#_2C8F1F: SEP #$30

#_2C8F21: PLB

#_2C8F22: JSR EN_ReturnToFileSelect

#_2C8F25: LDA.b #$FF
#_2C8F27: STA.w $0128

#_2C8F2A: LDA.b #$2C ; SFX2.2C
#_2C8F2C: STA.w $012E

#_2C8F2F: SEP #$30

#_2C8F31: RTL

;===================================================================================================

EN_NameFile_CheckForScrollInputX:
SEP #$30

LDA.b $F0
AND.b #$03
BEQ .exit

INC.w $0B13

DEC A
STA.w $0B16

REP #$30

AND.w #$00FF
ASL A
TAX

LDA.w $0B10
AND.w #$00FF
CLC
ADC.l EN_NameFile_CursorIndexMovementX,X
CMP.l EN_NameFile_CursorIndexBoundaryX,X
BNE .no_wrap

LDA.l EN_NameFile_CursorIndexWrapX,X

.no_wrap
SEP #$30

STA.w $0B10

.exit
SEP #$30

RTS

;===================================================================================================

EN_NameFile_CheckForScrollInputY:
LDA.b $F0
AND.b #$0C
BEQ .no_input

STA.b $02

ASL A
ORA.w $0B15
CMP.b #$10
BEQ .set_input

LDA.b $02
ASL A
ASL A
ORA.w $0B15

LDX.w $0B10

CMP.b #$13
BEQ .set_input

LDA.b $02
LSR A
LSR A

.next
TAX

LDA.w $0B15
CLC
ADC.l EN_NameFile_CursorIndexMovementY-1,X
CMP.l EN_NameFile_CursorIndexBoundaryY-1,X
BNE .no_stick

LDA.l EN_NameFile_CursorStickY-1,X

.no_stick
STA.w $0B15
BRA .not_this_guy

;---------------------------------------------------------------------------------------------------
; Code from the JP versions
;---------------------------------------------------------------------------------------------------
#EN_UNREACHABLE_0CFDF9:
STX.b $01

LDX.w $0B15

LDA.l EN_NameFile_YtoXIndexOffset,X
CLC
ADC.w $0B10
AND.b #$FF
TAX

LDA.l EN_NameFile_CharacterLayout,X
CMP.b #$59
BNE .not_this_guy

LDA.b $01
BRA .next

;---------------------------------------------------------------------------------------------------

.not_this_guy
INC.w $0B14
BRA .set_input

.no_input
STZ.w $00CA

.set_input
LDA.w $0002
STA.w $00CB

RTS

;===================================================================================================

pool EN_NameFile_DrawSelectedCharacter

.vram_position_low
dw $0084
dw $0086
dw $0088
dw $008A
dw $008C
dw $008E

pool off

;---------------------------------------------------------------------------------------------------

EN_NameFile_DrawSelectedCharacter:
PHB
PHK
PLB

LDA.w #$6100 ; VRAM $C200
ORA.w .vram_position_low,Y
XBA
STA.w $1002

XBA
CLC
ADC.w #$0020

XBA
STA.w $1008

LDA.w #$0100
STA.w $1004
STA.w $100A

LDA.l $7003D9,X
ORA.w #$1800
STA.w $1006

CLC
ADC.w #$0010
STA.w $100C

;---------------------------------------------------------------------------------------------------

SEP #$30

LDA.b #$FF
STA.w $100E

LDA.b #$01
STA.b $14

PLB

RTS

;===================================================================================================

IntroLogoTilemap:
EN_IntroLogoTilemap:
#_2C9013: dw $0010, $7E47 ; VRAM $2000 | 1920 bytes | Fixed horizontal
#_2C9017: dw $0976

#_2C9019: dw $A010, $7E43 ; VRAM $2140 | 896 bytes | Fixed horizontal
#_2C901D: dw $0977

#_2C901F: dw $2511, $1700 ; VRAM $224A | 24 bytes | Horizontal
#_2C9023: dw $3900, $3901, $3902, $3903, $3904, $3905, $3906, $3907
#_2C9033: dw $3908, $3909, $390A, $390B

#_2C903B: dw $3911, $0300 ; VRAM $2272 | 4 bytes | Horizontal
#_2C903F: dw $397E, $397F

#_2C9043: dw $4511, $2B00 ; VRAM $228A | 44 bytes | Horizontal
#_2C9047: dw $390C, $390D, $390E, $390F, $3910, $3911, $3912, $3977
#_2C9057: dw $3913, $3914, $3915, $3916, $3977, $3977, $3917, $3918
#_2C9067: dw $3919, $391A, $391B, $391C, $391D, $391E

#_2C9073: dw $6511, $2B00 ; VRAM $22CA | 44 bytes | Horizontal
#_2C9077: dw $391F, $3920, $3921, $3922, $3923, $3924, $3925, $3926
#_2C9087: dw $3927, $3928, $3929, $392A, $392B, $392C, $392D, $392E
#_2C9097: dw $392F, $3930, $3931, $3932, $3933, $3934

#_2C90A3: dw $8511, $2B00 ; VRAM $230A | 44 bytes | Horizontal
#_2C90A7: dw $3935, $3936, $3937, $3938, $3939, $393A, $393B, $393C
#_2C90B7: dw $393D, $393E, $393F, $3940, $3941, $3942, $3943, $3944
#_2C90C7: dw $3945, $3946, $3947, $3948, $3949, $394A

#_2C90D3: dw $A511, $2B00 ; VRAM $234A | 44 bytes | Horizontal
#_2C90D7: dw $394B, $394C, $394D, $394E, $394F, $3950, $3951, $3952
#_2C90E7: dw $3953, $3954, $3955, $3956, $3957, $3958, $3959, $395A
#_2C90F7: dw $395B, $395C, $395D, $395E, $395F, $3960

#_2C9103: dw $C511, $2B00 ; VRAM $238A | 44 bytes | Horizontal
#_2C9107: dw $3977, $3961, $3962, $3963, $3964, $3965, $3966, $3967
#_2C9117: dw $3968, $3969, $396A, $396B, $396C, $396D, $396E, $396F
#_2C9127: dw $3970, $3971, $3972, $3973, $3974, $3975

#_2C9133: db $FF ; end of stripes data

;===================================================================================================

FileSelectTilemap:
EN_FileSelectTilemap:
dw $6560, $1B00 ; VRAM $C0CA | 28 bytes | Horizontal
dw $180F, $180B, $1800, $1828, $1804, $1821, $18A9, $18A9
dw $1822, $1804, $180B, $1804, $1802, $1823

dw $8560, $1B00 ; VRAM $C10A | 28 bytes | Horizontal
dw $181F, $181B, $1810, $1838, $1814, $1831, $18B9, $18B9
dw $1832, $1814, $181B, $1814, $1812, $1833

dw $C662, $1700 ; VRAM $C58C | 24 bytes | Horizontal
dw $1802, $180E, $180F, $1828, $18A9, $18A9, $180F, $180B
dw $1800, $1828, $1804, $1821

dw $E662, $1700 ; VRAM $C5CC | 24 bytes | Horizontal
dw $1812, $181E, $181F, $1838, $18A9, $18A9, $181F, $181B
dw $1810, $1838, $1814, $1831

dw $0663, $1700 ; VRAM $C60C | 24 bytes | Horizontal
dw $1804, $1821, $1800, $1822, $1804, $18A9, $180F, $180B
dw $1800, $1828, $1804, $1821

dw $2663, $1700 ; VRAM $C64C | 24 bytes | Horizontal
dw $1814, $1831, $1810, $1832, $1814, $18A9, $181F, $181B
dw $1810, $1838, $1814, $1831

db $FF ; end of stripes data

;===================================================================================================

EN_FileSelectNamesTilemap:
dw $2961, $2500 ; VRAM $C252 | 38 bytes | Horizontal
dw $18E7, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $4961, $2500 ; VRAM $C292 | 38 bytes | Horizontal
dw $18F7, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $A961, $2500 ; VRAM $C352 | 38 bytes | Horizontal
dw $18E8, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $C961, $2500 ; VRAM $C392 | 38 bytes | Horizontal
dw $18F8, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $2962, $2500 ; VRAM $C452 | 38 bytes | Horizontal
dw $18E9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $4962, $2500 ; VRAM $C492 | 38 bytes | Horizontal
dw $18F9, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

db $FF ; end of stripes data

;===================================================================================================

FileSelectKILLFileTilemap:
EN_FileSelectKILLFileTilemap:
dw $6560, $1700 ; VRAM $C0CA | 24 bytes | Horizontal
dw $1804, $1821, $1800, $1822, $1804, $18A9, $180F, $180B
dw $1800, $1828, $1804, $1821

dw $8560, $1700 ; VRAM $C10A | 24 bytes | Horizontal
dw $1814, $1831, $1810, $1832, $1814, $18A9, $181F, $181B
dw $1810, $1838, $1814, $1831

dw $0461, $2F00 ; VRAM $C208 | 48 bytes | Horizontal
dw $1826, $1807, $18AF, $1802, $1807, $18A9, $180F, $180B
dw $1800, $1828, $1804, $1821, $18A9, $1803, $180E, $18A9
dw $1828, $180E, $1824, $18A9, $1826, $1800, $180D, $1823

dw $2461, $2F00 ; VRAM $C248 | 48 bytes | Horizontal
dw $1836, $1817, $18BF, $1812, $1817, $18A9, $181F, $181B
dw $1810, $1838, $1814, $1831, $18A9, $1813, $181E, $18A9
dw $1838, $181E, $1834, $18A9, $1836, $1810, $181D, $1833

dw $4461, $1300 ; VRAM $C288 | 20 bytes | Horizontal
dw $1823, $180E, $18A9, $1804, $1821, $1800, $1822, $1804
dw $18A9, $186F

dw $6461, $1300 ; VRAM $C2C8 | 20 bytes | Horizontal
dw $1833, $181E, $18A9, $1814, $1831, $1810, $1832, $1814
dw $18A9, $187F

dw $0663, $0700 ; VRAM $C60C | 8 bytes | Horizontal
dw $1820, $1824, $18AF, $1823

dw $2663, $0700 ; VRAM $C64C | 8 bytes | Horizontal
dw $1830, $1834, $18BF, $1833

db $FF ; end of stripes data

;===================================================================================================

EN_KILLFile_BlankNameStripes:
dw $A761, $2500 ; VRAM $C34E | 38 bytes | Horizontal
dw $18E7, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $C761, $2500 ; VRAM $C38E | 38 bytes | Horizontal
dw $18F7, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $0762, $2500 ; VRAM $C40E | 38 bytes | Horizontal
dw $18E8, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $2762, $2500 ; VRAM $C44E | 38 bytes | Horizontal
dw $18F8, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $6762, $2500 ; VRAM $C4CE | 38 bytes | Horizontal
dw $18E9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

dw $8762, $2500 ; VRAM $C50E | 38 bytes | Horizontal
dw $18F9, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18A9

db $FF ; end of stripes data

;===================================================================================================

FileSelectCopyFileTilemap:
EN_FileSelectCopyFileTilemap:
dw $6560, $1700 ; VRAM $C0CA | 24 bytes | Horizontal
dw $1802, $180E, $180F, $1828, $18A9, $18A9, $180F, $180B
dw $1800, $1828, $1804, $1821

dw $8560, $1700 ; VRAM $C10A | 24 bytes | Horizontal
dw $1812, $181E, $181F, $1838, $18A9, $18A9, $181F, $181B
dw $1810, $1838, $1814, $1831

dw $0663, $0700 ; VRAM $C60C | 8 bytes | Horizontal
dw $1820, $1824, $18AF, $1823

dw $2663, $0700 ; VRAM $C64C | 8 bytes | Horizontal
dw $1830, $1834, $18BF, $1833

db $FF ; end of stripes data

;===================================================================================================

EN_CopyFile_HeaderStripe:
dw $0461, $1500 ; VRAM $C208 | 22 bytes | Horizontal
dw $1885, $1826, $1807, $18AF, $1802, $1807, $186F, $1886
dw $18A9, $18A9, $18A9

dw $2461, $1500 ; VRAM $C248 | 22 bytes | Horizontal
dw $1895, $1836, $1817, $18BF, $1812, $1817, $187F, $1896
dw $18A9, $18A9, $18A9

dw $6761, $0F00 ; VRAM $C2CE | 16 bytes | Horizontal
dw $18E7, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

dw $8761, $0F00 ; VRAM $C30E | 16 bytes | Horizontal
dw $18F7, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

dw $C761, $0F00 ; VRAM $C38E | 16 bytes | Horizontal
dw $18E8, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

dw $E761, $0F00 ; VRAM $C3CE | 16 bytes | Horizontal
dw $18F8, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

dw $2762, $0F00 ; VRAM $C44E | 16 bytes | Horizontal
dw $18E9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

dw $4762, $0F00 ; VRAM $C48E | 16 bytes | Horizontal
dw $18F9, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

db $FF ; end of stripes data

;===================================================================================================

EN_CopyFile_TargetHeaderStripes:
dw $5161, $1500 ; VRAM $C2A2 | 22 bytes | Horizontal
dw $1885, $1823, $180E, $18A9, $1826, $1807, $18AF, $1802
dw $1807, $186F, $1886

dw $7161, $1500 ; VRAM $C2E2 | 22 bytes | Horizontal
dw $1895, $1833, $181E, $18B9, $1836, $1817, $18BF, $1812
dw $1817, $187F, $1896

dw $B461, $0F00 ; VRAM $C368 | 16 bytes | Horizontal
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

dw $D461, $0F00 ; VRAM $C3A8 | 16 bytes | Horizontal
dw $18A9, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

dw $1462, $0F00 ; VRAM $C428 | 16 bytes | Horizontal
dw $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

dw $3462, $0F00 ; VRAM $C468 | 16 bytes | Horizontal
dw $18A9, $1891, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9

db $FF ; end of stripes data

;===================================================================================================

NamePlayerTilemap:
EN_NamePlayerTilemap:
dw $A410, $2A40 ; VRAM $2148 | 44 bytes | Fixed horizontal
dw $147F

dw $C410, $2A40 ; VRAM $2188 | 44 bytes | Fixed horizontal
dw $147F

dw $6311, $1040 ; [ENG-FS] WIP box interior fill row 11: 13->9 tiles (6-char box -> 4-char)
dw $147F

dw $8311, $1040 ; [ENG-FS] WIP box interior fill row 12: 13->9 tiles (6-char box -> 4-char)
dw $147F

dw $A311, $1040 ; [ENG-FS] WIP box interior fill row 13: 13->9 tiles (6-char box -> 4-char)
dw $147F

dw $E311, $3240 ; VRAM $23C6 | 52 bytes | Fixed horizontal
dw $147F

dw $0312, $3240 ; VRAM $2406 | 52 bytes | Fixed horizontal
dw $147F

dw $2312, $3240 ; VRAM $2446 | 52 bytes | Fixed horizontal
dw $147F

dw $4312, $3240 ; VRAM $2486 | 52 bytes | Fixed horizontal
dw $147F

dw $6312, $3240 ; VRAM $24C6 | 52 bytes | Fixed horizontal
dw $147F

dw $8312, $3240 ; VRAM $2506 | 52 bytes | Fixed horizontal
dw $147F

dw $A312, $3240 ; VRAM $2546 | 52 bytes | Fixed horizontal
dw $147F

dw $C312, $3240 ; VRAM $2586 | 52 bytes | Fixed horizontal
dw $147F

dw $E312, $3240 ; VRAM $25C6 | 52 bytes | Fixed horizontal
dw $147F

dw $0313, $3240 ; VRAM $2606 | 52 bytes | Fixed horizontal
dw $147F

dw $8210, $3300 ; VRAM $2104 | 52 bytes | Horizontal
dw $1589, $158A, $158B, $158C, $158B, $158C, $158B, $158C
dw $158B, $158C, $158B, $158C, $158B, $158C, $158B, $158C
dw $158B, $158C, $158B, $158C, $158B, $158C, $158B, $158C
dw $558A, $5589

dw $A210, $0300 ; VRAM $2144 | 4 bytes | Horizontal
dw $1599, $159A

dw $BA10, $0300 ; VRAM $2174 | 4 bytes | Horizontal
dw $559A, $5599

dw $C210, $0300 ; VRAM $2184 | 4 bytes | Horizontal
dw $15A9, $15AA

dw $DA10, $0300 ; VRAM $21B4 | 4 bytes | Horizontal
dw $559A, $5599

dw $E210, $3300 ; VRAM $21C4 | 52 bytes | Horizontal
dw $159D, $15AD, $159B, $159C, $159B, $159C, $159B, $159C
dw $159B, $159C, $159B, $159C, $159B, $159C, $159B, $159C
dw $159B, $159C, $159B, $159C, $159B, $159C, $159B, $159C
dw $55AD, $559D

dw $0211, $3300 ; VRAM $2204 | 52 bytes | Horizontal
dw $15AB, $15AC, $15AB, $15AC, $15AB, $15AC, $15AB, $15AC
dw $15AB, $15AC, $15AB, $15AC, $15AB, $15AC, $15AB, $15AC
dw $15AB, $15AC, $15AB, $15AC, $15AB, $15AC, $15AB, $15AC
dw $15AB, $15AC

dw $4211, $1500 ; [ENG-FS] WIP-name box top border 15->11 tiles (6-char box -> 4-char)
dw $1587, $1588, $1587, $1588, $1587, $1588, $1587, $1588
dw $1587, $1588, $1587

dw $6211, $1B80 ; VRAM $22C4 | 28 bytes | Vertical
dw $15AF, $15A7, $15AF, $15A7, $15AF, $15A7, $15AF, $15A7
dw $15AF, $15A7, $15AF, $15A7, $15AF, $15A7

dw $6C11, $0580 ; [ENG-FS] WIP-name box right wall col16 -> col12 (6-char box -> 4-char)
dw $15A8, $15AE, $15A8

dw $C311, $3500 ; VRAM $2386 | 54 bytes | Horizontal
dw $1588, $1598, $1588, $1598, $1588, $1598, $1588, $1598
dw $1588, $1598, $1588, $1598, $1588, $1598, $1588, $1587
dw $1588, $1587, $1588, $1587, $1588, $1587, $1588, $1587
dw $1588, $1587, $1588

dw $FD11, $1380 ; VRAM $23FA | 20 bytes | Vertical
dw $15A8, $15AE, $15A8, $15AE, $15A8, $15AE, $15A8, $15AE
dw $15A8, $15AE

dw $2213, $3700 ; VRAM $2644 | 56 bytes | Horizontal
dw $1597, $1598, $1597, $1598, $1597, $1598, $1597, $1598
dw $1597, $1598, $1597, $1598, $1597, $1598, $1597, $1598
dw $1597, $1598, $1597, $1598, $1597, $1598, $1597, $1598
dw $1597, $1598, $1597, $1598

dw $F011, $12C0 ; VRAM $23E0 | 20 bytes | Fixed vertical
dw $158D

dw $A460, $2B00 ; VRAM $C148 | 44 bytes | Horizontal
dw $18A9, $1821, $1804, $1806, $18AF, $1822, $1823, $1804
dw $1821, $18A9, $18A9, $1828, $180E, $1824, $1821, $18A9
dw $18A9, $180D, $1800, $180C, $1804, $18A9

dw $C460, $2B00 ; VRAM $C188 | 44 bytes | Horizontal
dw $18A9, $1831, $1814, $1816, $18BF, $1832, $1833, $1814
dw $1831, $18A9, $18A9, $1838, $181E, $1834, $1831, $18A9
dw $18A9, $181D, $1810, $181C, $1814, $18A9

dw $0262, $3900 ; VRAM $C404 | 58 bytes | Horizontal
dw $1800, $18A9, $1801, $18A9, $1802, $18A9, $1803, $18A9
dw $1804, $18A9, $1805, $18A9, $1806, $18A9, $1807, $18A9
dw $18AF, $18A9, $1809, $18A9, $18A9, $18A9, $18A9, $18A9
dw $182A, $18A9, $182B, $18A9, $182C

dw $2262, $3900 ; VRAM $C444 | 58 bytes | Horizontal
dw $1810, $18A9, $1811, $18A9, $1812, $18A9, $1813, $18A9
dw $1814, $18A9, $1815, $18A9, $1816, $18A9, $1817, $18A9
dw $18BF, $18A9, $1819, $18A9, $18A9, $18A9, $18A9, $18A9
dw $183A, $18A9, $183B, $18A9, $183C

dw $4262, $3900 ; VRAM $C484 | 58 bytes | Horizontal
dw $180A, $18A9, $180B, $18A9, $180C, $18A9, $180D, $18A9
dw $180E, $18A9, $180F, $18A9, $1820, $18A9, $1821, $18A9
dw $1822, $18A9, $1823, $18A9, $18A9, $18A9, $18A9, $18A9
dw $1844, $18A9, $18AF, $18A9, $1846

dw $6262, $3900 ; VRAM $C4C4 | 58 bytes | Horizontal
dw $181A, $18A9, $181B, $18A9, $181C, $18A9, $181D, $18A9
dw $181E, $18A9, $181F, $18A9, $1830, $18A9, $1831, $18A9
dw $1832, $18A9, $1833, $18A9, $18A9, $18A9, $18A9, $18A9
dw $1854, $18A9, $18BF, $18A9, $1856

dw $8262, $3900 ; VRAM $C504 | 58 bytes | Horizontal
dw $1824, $18A9, $1825, $18A9, $1826, $18A9, $1827, $18A9
dw $1828, $18A9, $1829, $18A9, $1880, $18A9, $1881, $18A9
dw $1882, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $184E, $18A9, $184F, $18A9, $1860

dw $A262, $3900 ; VRAM $C544 | 58 bytes | Horizontal
dw $1834, $18A9, $1835, $18A9, $1836, $18A9, $1837, $18A9
dw $1838, $18A9, $1839, $18A9, $1890, $18A9, $1891, $18A9
dw $1892, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9, $18A9
dw $185E, $18A9, $185F, $18A9, $1870

dw $CC62, $1100 ; VRAM $C598 | 18 bytes | Horizontal
dw $18AA, $18A9, $1884, $18A9, $18A9, $18A9, $1804, $180D
dw $1803

dw $EC62, $1100 ; VRAM $C5D8 | 18 bytes | Horizontal
dw $18BA, $18A9, $1894, $18A9, $18A9, $18A9, $1814, $181D
dw $1813

dw $0066, $3500 ; VRAM $CC00 | 54 bytes | Horizontal
dw $182D, $18A9, $182E, $18A9, $182F, $18A9, $1840, $18A9
dw $1841, $18A9, $18C0, $18A9, $1843, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18E6, $18A9, $18E7, $18A9, $18E8, $18A9
dw $18E9, $18A9, $18EA

dw $2066, $3500 ; VRAM $CC40 | 54 bytes | Horizontal
dw $183D, $18A9, $183E, $18A9, $183F, $18A9, $1850, $18A9
dw $1851, $18A9, $18D0, $18A9, $1853, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18F6, $18A9, $18F7, $18A9, $18F8, $18A9
dw $18F9, $18A9, $18FA

dw $4066, $3500 ; VRAM $CC80 | 54 bytes | Horizontal
dw $1847, $18A9, $1848, $18A9, $1849, $18A9, $184A, $18A9
dw $184B, $18A9, $184C, $18A9, $184D, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18EB, $18A9, $18EC, $18A9, $18ED, $18A9
dw $18EE, $18A9, $18EF

dw $6066, $3500 ; VRAM $CCC0 | 54 bytes | Horizontal
dw $1857, $18A9, $1858, $18A9, $1859, $18A9, $185A, $18A9
dw $185B, $18A9, $185C, $18A9, $185D, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18FB, $18A9, $18FC, $18A9, $18FD, $18A9
dw $18FE, $18A9, $18FF

dw $8066, $3100 ; VRAM $CD00 | 50 bytes | Horizontal
dw $1861, $18A9, $1862, $18A9, $1863, $18A9, $1880, $18A9
dw $1881, $18A9, $1882, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18C1, $18A9, $186F, $18A9, $1885, $18A9
dw $1886

dw $A066, $3100 ; VRAM $CD40 | 50 bytes | Horizontal
dw $1871, $18A9, $1872, $18A9, $1873, $18A9, $1890, $18A9
dw $1891, $18A9, $1892, $18A9, $18A9, $18A9, $18A9, $18A9
dw $18A9, $18A9, $18D1, $18A9, $187F, $18A9, $1895, $18A9
dw $1896

dw $C466, $2D00 ; VRAM $CD88 | 46 bytes | Horizontal
dw $18AA, $18A9, $1884, $18A9, $18A9, $18A9, $1804, $180D
dw $1803, $18A9, $18A9, $18A9, $18A9, $18A9, $18AA, $18A9
dw $1884, $18A9, $18A9, $18A9, $1804, $180D, $1803

dw $E466, $2D00 ; VRAM $CDC8 | 46 bytes | Horizontal
dw $18BA, $18A9, $1894, $18A9, $18A9, $18A9, $1814, $181D
dw $1813, $18A9, $18A9, $18A9, $18A9, $18A9, $18BA, $18A9
dw $1894, $18A9, $18A9, $18A9, $1814, $181D, $1813

db $FF ; end of stripes data

; [ENG-FS] US fancy-background routines + tilemap in NamePlayerTilemap dead pad space

pool EN_FileSelect_UploadLinoleum

.set0
dw $3581, $3582

.set1
dw $3591, $3592

.pointers
dw .set0
dw .set1

pool off

;---------------------------------------------------------------------------------------------------

EN_FileSelect_UploadLinoleum:
LDA.w #$0010 ; VRAM $2000
STA.w $1002

LDA.w #$FF07
STA.w $1004

STZ.b $00

LDX.w #$0000

.next
LDA.b $00
PHA

AND.w #$0020
LSR A
LSR A
LSR A
LSR A
TAY

LDA.w .pointers,Y
STA.b $02

PLA
AND.w #$0001
ASL A
TAY

LDA.b ($02),Y
STA.w $1006,X

INX
INX

INC.b $00

LDA.b $00
CMP.w #$0400
BNE .next

RTS

;===================================================================================================

EN_FileSelect_UploadFancyBackground:
PHB
PHK
PLB

REP #$30

JSR EN_FileSelect_UploadLinoleum

;---------------------------------------------------------------------------------------------------

LDY.w #$00DE

.next
LDA.w EN_FancyBackgroundTileMap,Y
STA.w $1806,Y

INX
INX

DEY
DEY
BPL .next

;---------------------------------------------------------------------------------------------------

LDA.w #$1103 ; VRAM $2206
STA.b $00

LDA.w #$0011
STA.b $02

.next_stripe
LDA.b $00
XBA
STA.w $1006,X

XBA
CLC
ADC.w #$0020
STA.b $00

INX
INX

LDA.w #$3240
STA.w $1006,X

INX
INX

LDA.w #$347F
STA.w $1006,X

INX
INX

DEC.b $02
BPL .next_stripe

;---------------------------------------------------------------------------------------------------

SEP #$20

LDA.b #$FF
STA.w $1006,X

SEP #$10

INC.b $11

JMP.w EN_FileSelect_TriggerTheStripes

;===================================================================================================


EN_NameFile_FillBackground:
PHB
PHK
PLB

REP #$30

JSR EN_FileSelect_UploadLinoleum

LDA.w #$FFFF
STA.w $1006,X

SEP #$30

PLB

LDA.b #$01
JSR EN_Intro_SetStripesAndAdvance

RTL

;---------------------------------------------------------------------------------------------------

EN_FancyBackgroundTileMap:
dw $4210, $2700 ; VRAM $2084 | 40 bytes | Horizontal
dw $3589, $358A, $358B, $358C, $358B, $358C, $358B, $358C
dw $358B, $358C, $358B, $358C, $358B, $358C, $358B, $358C
dw $358B, $358C, $758A, $7589

dw $6210, $0300 ; VRAM $20C4 | 4 bytes | Horizontal
dw $3599, $359A

dw $6410, $1E40 ; VRAM $20C8 | 32 bytes | Fixed horizontal
dw $347F

dw $7410, $0300 ; VRAM $20E8 | 4 bytes | Horizontal
dw $759A, $7599

dw $8210, $0300 ; VRAM $2104 | 4 bytes | Horizontal
dw $35A9, $35AA

dw $8410, $1E40 ; VRAM $2108 | 32 bytes | Fixed horizontal
dw $347F

dw $9410, $0300 ; VRAM $2128 | 4 bytes | Horizontal
dw $75AA, $75A9

dw $A210, $2700 ; VRAM $2144 | 40 bytes | Horizontal
dw $359D, $35AD, $359B, $359C, $359B, $359C, $359B, $359C
dw $359B, $359C, $359B, $359C, $359B, $359C, $359B, $359C
dw $359B, $359C, $75AD, $759D

dw $C210, $2700 ; VRAM $2184 | 40 bytes | Horizontal
dw $35AB, $35AC, $35AB, $35AC, $35AB, $35AC, $35AB, $35AC
dw $35AB, $35AC, $35AB, $35AC, $35AB, $35AC, $35AB, $35AC
dw $35AB, $35AC, $75AB, $75AC

dw $E210, $0100 ; VRAM $21C4 | 2 bytes | Horizontal
dw $3583

dw $E310, $3240 ; VRAM $21C6 | 52 bytes | Fixed horizontal
dw $3585

dw $FD10, $0100 ; VRAM $21FA | 2 bytes | Horizontal
dw $3584

dw $0211, $22C0 ; VRAM $2204 | 36 bytes | Fixed vertical
dw $3586

dw $1D11, $22C0 ; VRAM $223A | 36 bytes | Fixed vertical
dw $3596

dw $4213, $0100 ; VRAM $2684 | 2 bytes | Horizontal
dw $3593

dw $4313, $3240 ; VRAM $2686 | 52 bytes | Fixed horizontal
dw $3595

dw $5D13, $0100 ; VRAM $26BA | 2 bytes | Horizontal
dw $3594

;===================================================================================================
; [ENG-FS] V-IRQ active handler.
; Replaces JP's inline 22-byte block at bank_00 $008205-$00821A: bank_00 reaches us via a single
; JML EN_IRQActiveHandler and we JML back to $00821B (the shared .IRQ_inactive tail) when done --
; no return address on the stack, so no RTL.
; JP hardcoded scanline $38 (56); name-entry mode ($0128=$01) needs $74 (116) so the raster
; split falls below the WIP-name box (BG3 rows 12-13) but above the letter grid (rows 16+),
; keeping the in-progress name left-aligned while the letter grid scrolls horizontally.
; All other IRQ users ($0128=$FF one-shot transitions, etc.) get the JP scanline $38.
; CPU on entry: 8-bit A/X/Y (SEP #$30 set in NMI handler), DBR=$00, direct page=$0000.
;===================================================================================================
EN_IRQActiveHandler:
#_2C9D8B: LDA.w TIMEUP            ; acknowledge V-IRQ (must read to clear IRQ flag)
#_2C9D8E: LDA.w $0128             ; IRQ mode: $01=name-entry, $FF=one-shot transition, $00=off
#_2C9D91: CMP.b #$01
#_2C9D93: BNE .default_split
#_2C9D95: LDA.b #$74              ; name-entry: split below WIP-name box (row 14.5)
#_2C9D97: BRA .store_split
.default_split
#_2C9D99: LDA.b #$38              ; default: JP scanline 56 (above WIP box)
.store_split
#_2C9D9B: STA.w VTIMEL
#_2C9D9E: STZ.w VTIMEH            ; H-IRQ not used; zero H-counter compare
#_2C9DA1: STZ.w HTIMEL
#_2C9DA4: STZ.w HTIMEH
#_2C9DA7: LDA.b #$A1              ; bit7=NMI enable, bit5=V-IRQ enable, bit0=auto-joypad
#_2C9DA9: STA.w NMITIMEN
#_2C9DAC: JML $00821B             ; back to bank_00 .IRQ_inactive (past the displaced block)

;===================================================================================================


