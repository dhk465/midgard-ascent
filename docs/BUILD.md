# Local build

Run commands from the repository root. Python 3.10 or newer is required; the compiler uses the standard library. Node.js is only needed for editor tests. No package installation is part of this process. Use Ragnarok Offline 1.4.3 for this build pipeline: its intermediate compiler stage requires app 1.3.4 or newer, and 1.4.3 is the supported inspected site profile. This is build/loader compatibility, not an in-game certification.

1. Copy `workshop/chapter-one/config/site.example.json` to ignored `local/site.json`. Set your actual app version, Renewal era, NPC encoding, gate and return coordinates, and evidence note. Keep confirmations truthful; the example is deliberately incomplete.
2. Supply paths to your own local GRFs. The native importer reads them and writes only under ignored `build/`. Optional BGM input requires both a local baseline table and music directory; no music is downloaded.
3. Build native maps and the full content, then create a JSON project:

```sh
python -X utf8 workshop/chapter-one/tools/build_native_candidate.py --site local/site.json --grf /path/to/your/data.grf --output build/native --profiles workshop/chapter-one/content/field-compact-profiles.json --mod-name midgard-ascent-native
python -X utf8 workshop/full-tower/build.py --assets-from build/native/chapter-one-install-candidate/midgard-ascent-native --site local/site.json --output build/full/midgard-ascent
python -X utf8 workshop/full-tower/json_project.py init --source build/full/midgard-ascent --output local/tower-project.json
```

GRF arguments may be repeated; inspect `--help` before supplying patch archives. Use a new output directory for each build; builders refuse overwrites. Paths containing spaces must be quoted.

4. Open `local/tower-project.json` in the [browser editor](https://dhk465.github.io/midgard-ascent/editor/), download edits and save them locally. Alternatively, the local editor saves the supplied project with validation and backups:

```sh
python -X utf8 workshop/full-tower/editor/server.py --project local/tower-project.json
```

Open the localhost URL printed by the server. Stop it with Ctrl+C. Browser downloads do not automatically overwrite their original file. The website and local editor do not install a game mod.

5. Compile the edited project into a single local candidate:

```sh
python -X utf8 workshop/full-tower/json_project.py build --project local/tower-project.json --source build/full/midgard-ascent --site local/site.json --output build/json/midgard-ascent
```

The final folder and ZIP contain your GRF-derived assets. Keep them private. Intermediate build folders are compiler inputs; the JSON-compiled result is the single-mod candidate. Installation and Apply require a separately prepared isolated game test, not a build command.

For a later edit, compile into another fresh output, such as `build/revision-2/midgard-ascent`. Preserve existing projects and candidates until you have verified the new one.

## Local checks

```sh
python -X utf8 -m unittest discover -s workshop/full-tower/editor -p "test_*.py"
node workshop/full-tower/editor/test_browser_store.js
```

These check editing behavior. They do not validate the native game runtime. See [compatibility](COMPATIBILITY.md).
