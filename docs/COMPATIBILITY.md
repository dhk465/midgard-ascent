# Compatibility and verification

Midgard Ascent uses the existing `ohkt01`–`ohkt10` maps, `ohkt_main_clear` character progress and `ohkt_trial_done[0/1]` trial completion slots. Internal `F_OHKC_*` functions and `ohkc_*` NPC/global names remain compatibility identifiers. Public repository, final manifest and output identity use `midgard-ascent`.

Do not activate this mod together with old tower candidates or their settings companions. The final JSON-compiled mod contains its settings in the generated NPC script. Editing JSON requires compiling a new candidate; the website cannot update an installed mod or read app settings automatically. Legacy settings import is a separate local tool.

The local site configuration must explicitly identify app version, Renewal era, NPC encoding and gate/return coordinates. The configured entrance is Prontera `(165, 191)`; verify that location and choose a return position in your isolated test setup. Do not mark evidence confirmations true merely to bypass checks.

The 200-floor capacity is a progression structure. Only floors 1–20 and two optional trials have authored content. Existing monster abilities, native rewards and active-mod overrides are not deliberately replaced by this tower.

Automated source and editor checks are separate from native runtime validation. Game launch, native NPC parsing, sprite animation, effective monster overrides, balance, camera appearance and installation/Apply are **NOT_RUN** for this public preparation. No live account, save or server files are changed by the documented build process.
