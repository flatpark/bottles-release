# bottles-release

Prebuilt Bottles artifacts for [FlatPark](https://flatpark.org).

This repository builds the complete Bottles `/app` tree and attaches it to a
GitHub release. FlatPark's `registry/com.usebottles.bottles/` pulls it in as
**extra-data**, so FlatPark's own OSTree repository holds nothing but a shell of
a few dozen kilobytes while the hundred-odd megabytes of payload travel over
GitHub's bandwidth.

The manifest is a fork of
[flathub/com.usebottles.bottles](https://github.com/flathub/com.usebottles.bottles).
**The only change is `runtime-version: '49'` → `'50'`.** GNOME 49 and 50 share
the same freedesktop 25.08 base — the fdo extension versions, Python 3.13 and
`base: org.winehq.Wine//stable-25.08` are all unchanged, and the Platform's `.so`
inventory loses nothing between the two — so nothing else needs touching.

The build recipe is this repository, which satisfies the GPL-3.0 obligation to
offer the corresponding source.

## Artifacts

Every release carries three files:

| File | Contents |
|---|---|
| `bottles-<ver>-x86_64.tar.zst` | the whole `/app` tree; unpacks to a `bottles/` root |
| `bottles-<ver>-x86_64.tar.zst.sha256` | checksum |
| `layout.json` | the `lib/` and `share/` subdirectory listing — see below |

## Why the artifact needs post-processing

On the FlatPark side this tree **does not live at `/app`**. During installation
Flatpak's `apply_extra` can only write to `/app/extra` — `/app` itself is
read-only — and a Flatpak sandbox cannot start a nested bwrap to bind it back.
So the tree ends up at `/app/extra/bottles/`, and two things have to happen
after the build:

**1. Rewrite RUNPATHs** (`scripts/relocate.py`)

wine, bottles-cli and libvte carry no RUNPATH at all; they find their libraries
through `LD_LIBRARY_PATH` and are unaffected by the move. The samba libraries
bundled with wine are the problem: over four hundred of them hardcode
`/app/lib/samba` or `/app/lib32/samba`. The script converts each into an
`$ORIGIN`-relative path, then verifies that not one absolute `/app` RUNPATH
remains and fails the build if any does.

**2. Emit the layout** (`scripts/layout.py`)

In FlatPark's shell manifest, `/app/lib` and `/app/share` **must be real
directories** — flatpak-builder creates extension mount points inside them at
build time and cannot traverse a dangling symlink to do so (it fails with
`Extension ... has invalid merge-dirs`). The shell therefore symlinks back into
the payload one subdirectory at a time, and that list is hardcoded in the shell
manifest. `layout.json` lets FlatPark compare the two when refreshing its pin: if
the payload grows a subdirectory the shell has not caught up with, the refresh
fails right there, rather than shipping a package where some path silently
resolves to nothing.

Directories excluded from that list, because `/app` has to own them:

- `lib/i386-linux-gnu` — mount point for `Compat.i386`, `GL32` and
  `codecs_extra.i386`. This path cannot move: the runtime's
  `/lib/i386-linux-gnu` is a hardcoded symlink to it, and relocating the
  extension yields `/lib/ld-linux.so.2: could not open`, killing all 32-bit
  support.
- `share/{applications,icons,metainfo}` — the shell ships its own copies and
  Flatpak exports them at build time.
- `share/app-info` — flatpak-builder writes its own compiled AppStream into
  `share/app-info/xmls`; a dangling symlink makes `appstreamcli compose` fail.
- `share/{wine,steam}` — wine's own data directory, and the mount point for
  `Steam.CompatibilityTool`.

## Updating

Change the tag in `com.usebottles.bottles.src.yaml` (plus whatever else needs
syncing from upstream) and push to `main` to trigger a build; the workflow also
accepts a manual `workflow_dispatch`. The release tag is derived from the Bottles
version in `src.yaml`.

## Known issues

Under GNOME 50's libadwaita 1.9, Bottles 66.7 emits warnings of this shape:

```
Adwaita-CRITICAL: Trying to add GtkOverlay / AdwBanner / AdwPreferencesPage /
AdwStatusPage as a child to an AdwPreferencePage, but only AdwPreferencesGroup is allowed
```

They are not fatal — the app runs — but the affected pages are worth a visual
check. This is Bottles' own code being caught out by 1.9 tightening its child
validation; it has nothing to do with the relocation here, and it does not appear
under GNOME 49.

The workflow currently pins `runs-on: ubuntu-26.04`. `ubuntu-latest` (24.04)
started hanging indefinitely in `apt-get` after image 20260816.277; switch back
once that is fixed.
