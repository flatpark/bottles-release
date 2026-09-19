# bottles-release

Prebuilt Bottles artifacts for [FlatPark](https://flatpark.org).

This repository builds the complete Bottles `/app` tree and attaches it to a
GitHub release. FlatPark's `registry/com.usebottles.bottles/` pulls it in as
**extra-data**, so FlatPark's own OSTree repository holds nothing but a shell of
a few dozen kilobytes while the hundred-odd megabytes of payload travel over
GitHub's bandwidth.

The manifest is a fork of
[flathub/com.usebottles.bottles](https://github.com/flathub/com.usebottles.bottles),
which at the time of writing still targets GNOME 50. This fork targets **GNOME 51**
on the freedesktop 26.08 base, which takes three changes beyond the version numbers:

1. **`base: org.winehq.Wine//stable-26.08`.** That base is a new-WoW64 build
   (`--enable-archs=i386,x86_64`): it has no 32-bit unix side at all — no `lib32`,
   no `lib/wine/i386-unix`, no 32-bit krb5/unixodbc/samba — and it declares none of
   the i386 extension points that `stable-25.08` declared. The payload is therefore
   about 50 MB smaller than the GNOME 50 one, and the bundled "system" runner is
   WoW64 rather than a 32-on-32 build. Runners that Bottles downloads at runtime are
   conventional wine builds and still get their 32-bit system libraries from
   `org.freedesktop.Platform.Compat.i386//26.08` and their 32-bit drivers from
   `org.freedesktop.Platform.GL32`, both of which the FlatPark shell mounts.
2. **`org.freedesktop.Platform.GL32` is declared here instead of inherited.** Since
   the 26.08 Wine base no longer declares it, `inherit-extensions` fails the build at
   the very last step with `Can't find inherited extension point`. The declaration is
   copied from the `stable-25.08` Wine manifest, and `cleanup-commands` now creates
   the `lib/i386-linux-gnu/GL` mount point that the base used to create.
3. **The PyPI wheels are regenerated for CPython 3.14** (GNOME 51 ships 3.14, GNOME 50
   shipped 3.13): `req2flatpak.py --target-platforms 314-x86_64`. `yara-python` and
   `pycurl` have no cp314 wheels at the versions Bottles pins, so both come in as
   sdists — they compile offline inside the build sandbox, and `yara-python`'s sdist
   carries the whole of libyara, so it needs nothing from outside. `pycairo` and
   `PyGObject` stay listed as sdists but are never built: the runtime already provides
   them, and `--exists-action=i` against an unversioned requirement leaves them alone.

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

From libadwaita 1.9 onwards (GNOME 50 and later), Bottles emits warnings of this
shape:

```
Adwaita-CRITICAL: Trying to add GtkOverlay / AdwBanner / AdwPreferencesPage /
AdwStatusPage as a child to an AdwPreferencePage, but only AdwPreferencesGroup is allowed
```

They are not fatal — the app runs — but the affected pages are worth a visual
check. This is Bottles' own code being caught out by 1.9 tightening its child
validation; it has nothing to do with the relocation here, and it did not appear
under GNOME 49.

The workflow currently pins `runs-on: ubuntu-26.04`. `ubuntu-latest` (24.04)
started hanging indefinitely in `apt-get` after image 20260816.277; switch back
once that is fixed.
