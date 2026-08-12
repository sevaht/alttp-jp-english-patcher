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
; FadeLogoIn used).
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

    INC.b $11

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
