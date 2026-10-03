# Registry publication status

This is a source-and-editor repository, not an installable registry release. The draft pointer in `registry/midgard-ascent/mod.json` illustrates the official own-repository schema; it has not been submitted upstream.

The official registry source pointer has `name`, author, description, tags, homepage and `source.github` plus an optional release asset pattern. Version and runtime requirements belong in the actual distributable's manifest, not in the pointer.

The app discovers full GitHub releases. If no matching release asset exists, it can fall back to the tag's source ZIP. This source tree is not a runnable mod, so publishing a full release or registering it now would be misleading. Do not publish the local GRF-derived candidate as a release asset.

Before future registry submission, prepare a distributable whose assets have explicit publication rights, validate its manifest and runtime compatibility, and test it in an isolated game environment. The delivery limits are 50 MB archive, 96 MB unpacked and 2,000 files; unsafe archive paths and links are rejected. Registry submission and release publication are separate future actions.

Contract: [official MOD_REGISTRY.md](https://github.com/Flux159/ragnarokoffline.app/blob/main/docs/MOD_REGISTRY.md). The draft follows the format inspected on 2026-10-03; recheck the contract before submission.
