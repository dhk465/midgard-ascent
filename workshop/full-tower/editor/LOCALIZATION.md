# Display language and monster identities

The interface uses English. Monster choices show Korean name, English name and numeric ID. Names are presentation only; project monster IDs, counts and combat data are unchanged.

`monster-names.ko.json` covers all 55 monsters in the current authored tower catalog. Names were matched by Aegis identity against the existing local Korean navigation table `navi_mob_krpri.lub`, from the 2026-02-04 compatibility reference. This is not a claim of current live kRO patch parity. The table itself, sprites and other client assets are not included in the website.

The names were extracted locally during development; the private extraction log and original navigation table are not distributed. Table rows pair the Korean display name with the Aegis identity; catalog IDs provide the stable join key. An unknown ID keeps its English label and an explicit missing-Korean-name message.

Examples: 1002 포링 / Poring; 2398 풋내기 포링 / Little Poring; 2404 디노피시스 / Dead Plankton; 2405 그리슬 / Weak Skeleton. Picky IDs1049 and1050 share the Korean display name 픽키; the English label and numeric ID disambiguate them.

Official corroboration for 풋내기 포링: https://ro.gnjoy.com/guide/runemidgarts/popup/monsterview.asp?monsterID=LITTLE_PORING
