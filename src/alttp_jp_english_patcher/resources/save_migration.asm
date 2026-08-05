; In-place save migrator, packed into the file-select bank and invoked at boot
; (see MigrateAtBoot / apply_base_edits). Any foreign save slot -- a US save,
; or a vanilla Japanese save -- is converted to our 6-word-name-at-$3D5 format
; so it loads and plays. A word at $410 tags ours ($0006); the vanilla erase
; zeroes the whole slot, so a foreign save reads $0000 there. It scans all 6
; slots (3 files x main+backup, $500-strided from $700000). Cheap to re-run:
; only a slot with a $55AA marker but no $410 tag ($3E1 = JP-family / $3E5 =
; US) pays the checksum + convert, once, then it is tagged and skipped. New
; files are tagged in InitializeSaveFile.

; Boot hook: bank_00 InitializeMemoryAndSRAM zeroes each main slot's $3E1 word
; when it isn't the $55AA marker -- which a US save (marker at $3E5) always
; trips, corrupting its checksum before the file-select ever runs. So migrate
; here, BEFORE that check, via relocate_block at $0087EF (see apply_base_edits).
; Y holds the routine's return address.
MigrateAtBoot:                  ; emitted EN_-namespaced -> EN_MigrateAtBoot
PHY
JSR MigrateSaveSlots
PLY
LDA.l $7003E1                   ; displaced instruction from $0087EF (file-1 marker)
JML $0087F3                     ; resume bank_00's per-slot $55AA marker checks

MigrateSaveSlots:
PHP
REP #$30                        ; 16-bit A/X/Y throughout
STZ.b $00                       ; $00 = slot offset (0, $500, ... $1900)
LDX.w #$0006                    ; 6 slots
.next_slot
PHX
JSR MigrateOneSlot              ; migrates the slot at offset $00
LDA.b $00
CLC
ADC.w #$0500
STA.b $00
PLX
DEX
BNE .next_slot
PLP
RTS

MigrateOneSlot:                 ; $00 = slot offset
LDX.b $00
LDA.l $700410,X                ; our-format tag
BNE .done                       ; already ours -> nothing to do
LDA.l $7003E1,X                ; cheap marker check before the costly checksum
CMP.w #$55AA
BEQ .jp                         ; JP-family marker -> vanilla Japanese save
LDA.l $7003E5,X
CMP.w #$55AA
BEQ .us                         ; US marker
RTS                             ; no marker -> empty/unknown slot
.jp
JSR SlotChecksumValid
BCC .done                       ; not a valid save
JSR ConvertJP
BRA .stamp
.us
JSR SlotChecksumValid
BCC .done
JSR ConvertUS
.stamp
JSR StampAndChecksum
.done
RTS

SlotChecksumValid:              ; $00=offset; carry set if slot sums to $5A5A
LDX.b $00
STZ.b $02                       ; running sum
LDY.w #$0280                    ; all 640 words ($000-$4FE)
.sum
LDA.l $700000,X
CLC
ADC.b $02
STA.b $02
INX
INX
DEY
BNE .sum
LDA.b $02
CMP.w #$5A5A
BEQ .valid
CLC
RTS
.valid
SEC
RTS

ConvertUS:                      ; US name+post-name: shift 4 bytes down, $3D9 -> $3D5
LDX.b $00
LDY.w #$0017                    ; 23 words: 6 name + 17 post-name (incl. the marker)
.shift
LDA.l $7003D9,X
STA.l $7003D5,X
INX
INX
DEY
BNE .shift
RTS

; Japanese name: keep it only if every glyph is an uppercase-Latin letter or
; space (the sole characters shared by both fonts), remapped from the JP name
; codes (A-Z = $AA-$C3, space $CC) to ours; else fall back to "Link  ". Reads
; the 4-word JP field at $3D9 and writes our 6-word field at $3D5; writes land
; 4 bytes below the reads and go forward, so each source word is consumed
; before it's overwritten.
ConvertJP:
STZ.b $04                       ; $04 = non-Latin flag (0 = keep the name)
LDX.b $00
LDA.l $7003D9,X                ; JP name word 1
JSR JPWordToOurWord
STA.l $7003D5,X
LDA.l $7003DB,X                ; word 2
JSR JPWordToOurWord
STA.l $7003D7,X
LDA.l $7003DD,X                ; word 3
JSR JPWordToOurWord
STA.l $7003D9,X
LDA.l $7003DF,X                ; word 4
JSR JPWordToOurWord
STA.l $7003DB,X
LDA.w #$00A9                    ; trailing spaces (words 5-6)
STA.l $7003DD,X
STA.l $7003DF,X
LDA.b $04
BNE .link                       ; a non-Latin glyph -> default name instead
RTS
.link                           ; vanilla kana (or any non-Latin) -> "Link  "
LDX.b $00
LDA.w #$000B                    ; L
STA.l $7003D5,X
LDA.w #$00C0                    ; i
STA.l $7003D7,X
LDA.w #$0047                    ; n
STA.l $7003D9,X
LDA.w #$0044                    ; k
STA.l $7003DB,X
LDA.w #$00A9                    ; space
STA.l $7003DD,X
STA.l $7003DF,X                ; space
RTS

; One JP name word -> our name word. Decodes the nibble-spread store
; (code = ((w>>1)&$FFF0)|(w&$0F)); space ($CC) and A-Z ($AA-$C3, with I at our
; $5F) map via JPLatinToWord; anything else sets $04.
JPWordToOurWord:
PHA                             ; W
AND.w #$000F
STA.b $06                       ; low nibble
PLA                             ; W
LSR A
AND.w #$FFF0
ORA.b $06                       ; A = decoded JP code
CMP.w #$00CC                    ; space?
BNE .not_space
LDA.w #$00A9                    ; our space
RTS
.not_space
CMP.w #$00AA                    ; < 'A'?
BCC .not_latin
CMP.w #$00C4                    ; > 'Z'?
BCS .not_latin
SEC
SBC.w #$00AA                    ; k = code - $AA
ASL A                           ; word index
PHX                             ; preserve slot offset (no long,Y form -- index with X)
TAX
LDA.l JPLatinToWord,X
PLX
RTS
.not_latin
LDA.w #$0001
STA.b $04                       ; fall back to the default name
LDA.w #$00A9                    ; placeholder (the .link path overwrites it)
RTS
JPLatinToWord:                  ; our stored word for JP letters A..Z
dw $0000, $0001, $0002, $0003, $0004, $0005, $0006, $0007
dw $00AF, $0009, $000A, $000B, $000C, $000D, $000E, $000F
dw $0020, $0021, $0022, $0023, $0024, $0025, $0026, $0027
dw $0028, $0029

StampAndChecksum:               ; tag ours + recompute SAVEICKSM ($5A5A - sum)
LDX.b $00
LDA.w #$0006
STA.l $700410,X                ; tag = 6-char variant
STZ.b $02
LDX.b $00
LDY.w #$027F                    ; sum $000-$4FC (all but SAVEICKSM)
.sum
LDA.l $700000,X
CLC
ADC.b $02
STA.b $02
INX
INX
DEY
BNE .sum
LDA.w #$5A5A
SEC
SBC.b $02
LDX.b $00
STA.l $7004FE,X
RTS
