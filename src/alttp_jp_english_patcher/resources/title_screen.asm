; --us-title-screen: the genuinely novel pieces of the US title screen's
; sword animation. Everything that is just the US ROM's own routines
; (Intro_FadeLogoIn/Intro_PopSubtitleCard/Intro_TrianglesBeforeAttract --
; Module00_Intro_Dispatch below points straight at them now --
; Intro_HandleLogoSword/Intro_InitLogoSword, IntroLogoPaletteFadeIn/
; IntroTitleCardPaletteFadeIn) is pulled by name in title_screen() instead of
; transcribed here; only TitleScreenUS_DrawTriangle's subtype-dispatch logic
; and Module00_Intro_Dispatch's own hybrid table have no ROM original to pull
; from. Every pulled piece lands in this same relocation so all of them get
; EN_-namespaced together, and TitleScreenUS_DrawTriangle's own OAM object
; tables (below) are spliced in from a US pull too, not hand-copied.

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

; [PULLED] .rightside_objects/.leftside_objects (US
; AnimateSceneSprite_DrawTriangle's own pool, priority $1B/$5B) and
; .tf_rightside_objects/.tf_leftside_objects (US
; AnimateSceneSprite_DrawTriforceRoomTriangle's, priority $2B/$6B) are
; spliced in here by title_screen() -- pulled from the US disassembly,
; never transcribed.

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
;
; NOT a whole-routine pull: title_screen() slices just this prefix out of
; US's own Attract_Initialize instead of transcribing it (see there for why
; -- the routine's body diverges again a little further in, in a way this
; build deliberately doesn't want).
TitleScreenUS_AttractInitializePalettes:
    ; [PULLED] US Attract_Initialize's own palette-loading prefix -- spliced in here by title_screen().

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
; Slots 5-7 are the US ROM's own FadeLogoIn/SwordStab/PopSubtitleCard states
; (US restructured JP's 3-state stretch into 4: FadeLogoIn, SwordStab,
; PopSubtitleCard, TrianglesBeforeAttract) -- pulled by name into this same
; relocation in title_screen(), not transcribed here. Slot 10 is genuinely
; free table space for the fourth state (TrianglesBeforeAttract), which used
; to collide with vanilla slot 8; Intro_PopSubtitleCard (slot 7, pulled with
; its own 2 edits -- see title_screen()) jumps straight there when done,
; skipping restored slots 8-9 instead of US's own plain `INC.b $11`.
Module00_Intro_Dispatch:
    JSL JumpTableLong
    dl Intro_InitialInitialization
    dl Intro_InitializeMemory
    dl Intro_InitializeTriforcePolyThread
    dl Intro_HandleAllTriforceAnimations
    dl Intro_HandleAllTriforceAnimations
    dl Intro_FadeLogoIn
    dl Intro_SwordStab
    dl Intro_PopSubtitleCard
    dl Intro_InitializeTriforcePolyThread
    dl Intro_HandleAllTriforceAnimations
    dl Intro_TrianglesBeforeAttract
