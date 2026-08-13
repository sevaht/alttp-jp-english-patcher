; --us-title-screen: three Module00_Intro dispatch states, JP's own
; Intro_FadeLogoIn/Intro_PopSubtitleCard/Intro_TrianglesBeforeAttract with the
; US ROM's sword-animation calls spliced back in (US restructured these three
; states' bodies around the sword; JP's originals are left in place, now
; unreferenced -- apply_base_edits repoints the dispatch table here instead of
; editing them in place, since growing them in place would need free space
; the pristine bank doesn't reserve). Intro_HandleLogoSword/Intro_InitLogoSword
; and IntroLogoPaletteFadeIn/IntroTitleCardPaletteFadeIn are the US ROM's
; routines, pulled verbatim (see title_screen()) alongside this file into the
; same relocation so all of them get EN_-namespaced together.

; JP Intro_FadeLogoIn + US's extra Intro_InitLogoSword kickoff (once the fade
; finishes, at frame delay $2A -- JP's own state used $20, US's has to last
; through the new sword-stab state too) and IntroLogoPaletteFadeIn (a real
; call: unlike PopSubtitleCard's tail-JML below, execution comes back here to
; check the fade-done counter it left in $7EC007).
TitleScreenUS_FadeLogoIn:
    JSL Intro_HandleAllTriforceAnimations

    LDA.b $1A
    LSR A
    BCC .exit_a

    JSL IntroLogoPaletteFadeIn

    LDA.l $7EC007
    BNE .dont_advance

    LDA.b #$2A
    STA.b $B0

    INC.b $11

    JSR Intro_InitLogoSword

.exit_a
    RTL

.dont_advance
    CMP.b #$0D
    BNE .exit_b

    LDA.b #$15
    STA.b $1C
    STZ.b $1D

.exit_b
    RTL

; JP Intro_PopSubtitleCard + US's extra Intro_HandleLogoSword upkeep and a
; tail jump to IntroTitleCardPaletteFadeIn (US replaces JP's plain fade-timer
; wait with a real palette unfade, tracked by the same $7EC007 counter
; FadeLogoIn used). Advances to slot 10 (`LDA #$0A / STA $11`), not JP's
; plain `INC.b $11` (which would land on slot 8): see
; Module00_Intro_Dispatch below for why slots 8-9 have to stay vanilla and
; slot 10 is this sequence's real next step now.
TitleScreenUS_PopSubtitleCard:
    JSR Intro_HandleLogoSword

    JSL Intro_HandleAllTriforceAnimations

    LDA.l $7EC007
    BEQ .delay_fade

    LDA.b $1A
    LSR A
    BCC .exit

    ; Tail jump (not JSL): IntroTitleCardPaletteFadeIn's own RTL returns
    ; straight to Module00_Intro's caller, same as the original US ROM.
    JML IntroTitleCardPaletteFadeIn

.delay_fade
    LDA.b $F6
    AND.b #$C0
    ORA.b $F4
    AND.b #$D0
    BEQ .delay_music

    JML FadeMusicAndResetSRAMMirror

.delay_music
    DEC.b $B0
    BNE .exit

    LDA.b #$0A
    STA.b $11

.exit
    RTL

; JP Intro_TrianglesBeforeAttract + US's extra Intro_HandleLogoSword upkeep
; (keeps animating/clearing the sword sprite right up to the module switch).
TitleScreenUS_TrianglesBeforeAttract:
    JSL Intro_HandleAllTriforceAnimations

    STZ.w $1F00
    STZ.w $012A

    JSR Intro_HandleLogoSword

    DEC.b $B0
    BNE .exit

    INC.b $11

    LDA.b #$14
    STA.b $10

    STZ.b $11
    STZ.b $22

.exit
    RTL

; Replaces Intro_LoadAllPalettes_long (bank $02, JP) via relocate_block: that
; wrapper is exactly 4 bytes (JSR Intro_LoadAllPalettes / RTL), matching a
; JML's own footprint, so the swap is byte-neutral -- no growth, no orphan
; bytes. Calls the pulled US Intro_LoadAllPalettes (also pulled into this same
; bank $28 relocation) instead of JP's (see title_screen()'s own comment on
; why that routine's body has to be a whole replacement, not a byte-neutral
; edit). JSR, not JSL: Intro_LoadAllPalettes ends in a bare RTS (same-bank
; return only), so it must be reached with a same-bank call now that it lives
; here alongside this wrapper -- a cross-bank JSL would leave an orphaned
; bank byte on the stack and corrupt every return after it.
TitleScreenUS_LoadAllPalettes:
    JSR Intro_LoadAllPalettes
    RTL

; Replaces AnimateSceneSprite_DrawTriangle (bank $0C, JP) via relocate_block
; (see apply_base_edits): checks the sprite's own subtype ($1E18,X, set once
; at init -- 0 for the title-screen logo triangles, 4/5/6 for the credits'
; triforce-room scene, 7 for the rolling credits triangle) to pick the
; matching OAM-priority pool, since JP's original shared table can't
; simultaneously match the real US ROM's own title screen (priority 1) and
; its separate triforce-room/credits routine, DrawTriforceRoomTriangle
; (priority 2). Reached via a bare JML (relocate_block splices it in at the
; original routine's own address), so its own ending has to restore the
; program bank itself before returning -- see the comment above its RTL-
; replacing tail below for why. PHB/PHK/PLB at entry is this routine's own
; DBR fix (same reasoning as AnimateSceneSprite_DrawCopyright: its pool is
; read through direct-page-indirect addressing, LDA.b ($08),Y, which
; resolves the pool's bank from DBR, not the code's own program bank).
TitleScreenUS_DrawTriangle:
    PHB
    PHK
    PLB

    LDA.b #$10
    STA.b $06
    STZ.b $07

    LDA.w $1E18,X
    CMP.b #$04
    BCS .triforce_room

    CPX.b #$02
    BEQ .decrementing

    LDA.b #.rightside_objects>>0
    STA.b $08
    LDA.b #.rightside_objects>>8
    STA.b $09
    BRA .continue

.decrementing
    LDA.b #.leftside_objects>>0
    STA.b $08
    LDA.b #.leftside_objects>>8
    STA.b $09
    BRA .continue

.triforce_room
    CPX.b #$02
    BEQ .tf_decrementing

    LDA.b #.tf_rightside_objects>>0
    STA.b $08
    LDA.b #.tf_rightside_objects>>8
    STA.b $09
    BRA .continue

.tf_decrementing
    LDA.b #.tf_leftside_objects>>0
    STA.b $08
    LDA.b #.tf_leftside_objects>>8
    STA.b $09

.continue
    JSL AnimateSceneSprite_AddObjectsToOAMBuffer

    PLB
    ; RTS never restores K (the program bank), and this routine is reached
    ; via a bare JML (which set K=$28, not $0C) -- RTS alone would compute
    ; the right 16-bit PC but leave K stuck at $28, running whatever
    ; unrelated bytes live at that PC in bank $28 as code (caught live: a
    ; crash a few frames later, PC ending up at $0003). JML to the
    ; original routine's own now-orphaned RTS, at $0CC6FC -- left intact
    ; in ROM by relocate_block, past its resume address -- restores K
    ; first, so that RTS then correctly consumes the caller's own
    ; JSR-pushed return address and lands back in the right bank.
    JML $0CC6FC

.rightside_objects
    dw   0,   0 : db $80, $1B, $00, $02
    dw  16,   0 : db $82, $1B, $00, $02
    dw  32,   0 : db $84, $1B, $00, $02
    dw  48,   0 : db $86, $1B, $00, $02
    dw   0,  16 : db $A0, $1B, $00, $02
    dw  16,  16 : db $A2, $1B, $00, $02
    dw  32,  16 : db $A4, $1B, $00, $02
    dw  48,  16 : db $A6, $1B, $00, $02
    dw   0,  32 : db $88, $1B, $00, $02
    dw  16,  32 : db $8A, $1B, $00, $02
    dw  32,  32 : db $8C, $1B, $00, $02
    dw  48,  32 : db $8E, $1B, $00, $02
    dw   0,  48 : db $A8, $1B, $00, $02
    dw  16,  48 : db $AA, $1B, $00, $02
    dw  32,  48 : db $AC, $1B, $00, $02
    dw  48,  48 : db $AE, $1B, $00, $02

.leftside_objects
    dw  48,   0 : db $80, $5B, $00, $02
    dw  32,   0 : db $82, $5B, $00, $02
    dw  16,   0 : db $84, $5B, $00, $02
    dw   0,   0 : db $86, $5B, $00, $02
    dw  48,  16 : db $A0, $5B, $00, $02
    dw  32,  16 : db $A2, $5B, $00, $02
    dw  16,  16 : db $A4, $5B, $00, $02
    dw   0,  16 : db $A6, $5B, $00, $02
    dw  48,  32 : db $88, $5B, $00, $02
    dw  32,  32 : db $8A, $5B, $00, $02
    dw  16,  32 : db $8C, $5B, $00, $02
    dw   0,  32 : db $8E, $5B, $00, $02
    dw  48,  48 : db $A8, $5B, $00, $02
    dw  32,  48 : db $AA, $5B, $00, $02
    dw  16,  48 : db $AC, $5B, $00, $02
    dw   0,  48 : db $AE, $5B, $00, $02

.tf_rightside_objects
    dw   0,   0 : db $80, $2B, $00, $02
    dw  16,   0 : db $82, $2B, $00, $02
    dw  32,   0 : db $84, $2B, $00, $02
    dw  48,   0 : db $86, $2B, $00, $02
    dw   0,  16 : db $A0, $2B, $00, $02
    dw  16,  16 : db $A2, $2B, $00, $02
    dw  32,  16 : db $A4, $2B, $00, $02
    dw  48,  16 : db $A6, $2B, $00, $02
    dw   0,  32 : db $88, $2B, $00, $02
    dw  16,  32 : db $8A, $2B, $00, $02
    dw  32,  32 : db $8C, $2B, $00, $02
    dw  48,  32 : db $8E, $2B, $00, $02
    dw   0,  48 : db $A8, $2B, $00, $02
    dw  16,  48 : db $AA, $2B, $00, $02
    dw  32,  48 : db $AC, $2B, $00, $02
    dw  48,  48 : db $AE, $2B, $00, $02

.tf_leftside_objects
    dw  48,   0 : db $80, $6B, $00, $02
    dw  32,   0 : db $82, $6B, $00, $02
    dw  16,   0 : db $84, $6B, $00, $02
    dw   0,   0 : db $86, $6B, $00, $02
    dw  48,  16 : db $A0, $6B, $00, $02
    dw  32,  16 : db $A2, $6B, $00, $02
    dw  16,  16 : db $A4, $6B, $00, $02
    dw   0,  16 : db $A6, $6B, $00, $02
    dw  48,  32 : db $88, $6B, $00, $02
    dw  32,  32 : db $8A, $6B, $00, $02
    dw  16,  32 : db $8C, $6B, $00, $02
    dw   0,  32 : db $8E, $6B, $00, $02
    dw  48,  48 : db $A8, $6B, $00, $02
    dw  32,  48 : db $AA, $6B, $00, $02
    dw  16,  48 : db $AC, $6B, $00, $02
    dw   0,  48 : db $AE, $6B, $00, $02

; Replaces Attract_Initialize's "JSL TransferAttractPlaques" (bank $0C, JP)
; via relocate_block: the real US ROM's own Attract_Initialize sets
; $0AB3=4 and calls PaletteLoad_OWBGMain here too (JP's own version is
; missing both) -- this is what actually (re)loads the attract-mode
; background's own CGRAM rows (e.g. $21-$27) once the title/logo screen's
; own colors (loaded via area 5, see title_screen()) are done with them.
; Without it those rows are left holding whatever Intro_LoadAllPalettes
; last put there, confirmed live: raw, still-unprocessed JP filler (solid
; white). `JSL TransferAttractPlaques` is exactly 4 bytes, matching a
; JML's own footprint: no orphan bytes. This reproduces it (JP's original
; instruction, unchanged) plus the two extra US ones, then rejoins JP's
; own body at JSL PaletteLoad_LinkArmorAndGloves, untouched from there on
; -- none of TransferAttractPlaques/PaletteLoad_HUD/PaletteLoad_OWBGMain
; need a DBR or return-convention fix: JP's own code already reaches all
; three via plain JSL, so they're already RTL-ending and bank-agnostic.
TitleScreenUS_AttractInitializePalettes:
    JSL TransferAttractPlaques

    LDA.b #$04
    STA.w $0AB3

    LDA.b #$01
    STA.w $0AB2
    STZ.w $0AA9

    JSL PaletteLoad_HUD

    LDA.b #$02
    STA.w $0AA9

    JSL PaletteLoad_OWBGMain
    JSL PaletteLoad_HUD

    JML $0CED97

; Module00_Intro's own dispatch (bank $0C, `.run_submodule`): `LDA.b $11 /
; JSL JumpTableLong` reads its target table from JumpTableLong's own return
; address (bank $00, a shared far-jump-table utility used all over the
; game, so it stays put) -- the table has to sit immediately after wherever
; JSL JumpTableLong is called from, so relocating just that one JSL call
; (apply_base_edits) brings a fresh copy of the table here for free,
; growing it from JP's original 10 entries to 11 without touching a single
; byte of bank $0C's own copy (left in place, unreachable, harmless).
;
; Slots 0-4 and 8-9 are untouched vanilla JP (Intro_InitialInitialization /
; Intro_InitializeMemory / Intro_InitializeTriforcePolyThread /
; Intro_HandleAllTriforceAnimations). Slot 8 in particular has to stay
; vanilla: Attract_LoadNewScene's own loop-back-to-title tail (bank $0C,
; unmodified JP) and Save & Quit's own re-intro entry both jump straight
; here with $11=8, expecting JP's original "restart the triforce-forming
; animation" -- the actual title/logo display the player expects to see --
; not sword-animation logic. The original --us-title-screen implementation
; repurposed this slot for the fourth new state on the assumption that it
; was unreachable in normal forward play; it isn't (reached via ordinary
; forward dispatch too, not just those two), and repurposing it both
; corrupted the sword-animation state machine's shared direct-page
; workspace (dispatching through this slot never called
; Intro_InitLogoSword first) and skipped the title/logo display entirely
; on every attract-loop cycle and Save & Quit -- caught live: $CC held
; $2A, outside its valid 0/2/4 range, sending Intro_HandleLogoSword's
; `JMP.w (.vectors,X)` into the weeds and hanging with the screen forced
; black.
;
; Slots 5-7 are the three hand-written US-ified states above, plus the new
; Intro_SwordStab dispatch state in between (US restructured JP's 3-state
; stretch into 4: FadeLogoIn, SwordStab, PopSubtitleCard,
; TrianglesBeforeAttract). Slot 10 is genuinely free table space for the
; fourth state (TrianglesBeforeAttract), which used to collide with
; vanilla slot 8; TitleScreenUS_PopSubtitleCard (slot 7) jumps straight
; there when done, skipping restored slots 8-9 instead of JP's plain
; `INC.b $11`.
Module00_Intro_Dispatch:
    JSL JumpTableLong
    dl Intro_InitialInitialization
    dl Intro_InitializeMemory
    dl Intro_InitializeTriforcePolyThread
    dl Intro_HandleAllTriforceAnimations
    dl Intro_HandleAllTriforceAnimations
    dl TitleScreenUS_FadeLogoIn
    dl Intro_SwordStab
    dl TitleScreenUS_PopSubtitleCard
    dl Intro_InitializeTriforcePolyThread
    dl Intro_HandleAllTriforceAnimations
    dl TitleScreenUS_TrianglesBeforeAttract
