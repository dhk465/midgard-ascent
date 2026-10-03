# Midgard Ascent

A configurable wave tower for Ragnarok Offline Renewal, with a browser JSON editor.

The current source contains **20 authored floors, 62 normal waves and two optional trials**. The progression structure supports up to 200 logical floors; floors 21–200 are not authored. The editor has separate English and Korean views. The English view uses English monster names and IDs; the Korean view uses Inven-based names with documented source coverage.

This repository contains source, configuration recipes and the editor. Build the playable candidate locally using your own game GRFs. Game maps, models, textures, sprites, music and prebuilt game archives are not distributed here.

- [English editor](https://dhk465.github.io/midgard-ascent/editor/) / [Korean editor](https://dhk465.github.io/midgard-ascent/editor/?lang=ko): open or load a project, edit waves, then download JSON. It does not compile or install a mod.
- [Local build instructions](docs/BUILD.md).
- [Compatibility and verification](docs/COMPATIBILITY.md).
- [Registry publication status](docs/REGISTRY.md).
- [Sources and asset provenance](NOTICE.md).

The project preserves existing tower map and character progress identifiers. Disable old `ohk` tower variants and settings companions before using a locally built Midgard Ascent candidate in an isolated test environment. They share identifiers and cannot be coactivated.

Local automated checks cover the compiler and editor. In-game behavior, native server parsing, camera appearance and balance are still unverified. Building creates files only; installation and Apply are separate actions.
