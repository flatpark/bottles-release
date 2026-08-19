#!/usr/bin/env python3
"""Emit the lib/ and share/ subdirectory listing of the artifact.

In the FlatPark shell manifest, /app/lib and /app/share must be real directories:
flatpak-builder creates extension mount points inside them at build time and
cannot traverse a dangling symlink to do so. The shell therefore symlinks back
into the payload one subdirectory at a time, and that list is hardcoded in the
shell manifest. This file lets FlatPark's resolve-update.sh compare the two when
refreshing the pin — if the payload grows a subdirectory the shell has not caught
up with, the refresh fails right there instead of shipping a package where some
path silently resolves to nothing.

Usage: layout.py <tree> > layout.json
"""
import json
import os
import sys

# These must be owned by /app itself and cannot be symlinked away:
#   lib/i386-linux-gnu  -> mount point for Compat.i386 / GL32 / codecs_extra.i386.
#                          The path is fixed: the runtime's /lib/i386-linux-gnu is
#                          a hardcoded symlink to it.
#   share/{applications,icons,metainfo}
#                       -> the shell ships its own copies; flatpak exports them at
#                          build time.
#   share/{wine,steam}  -> wine's own data directory, and the mount point for
#                          Steam.CompatibilityTool.
#   share/app-info      -> flatpak-builder writes its own compiled AppStream into
#                          share/app-info/xmls at build time; a dangling symlink
#                          makes appstreamcli compose fail.
RESERVED = {"lib": {"i386-linux-gnu"},
            "share": {"applications", "icons", "metainfo", "wine", "steam", "app-info"}}


def subdirs(tree, top):
    d = os.path.join(tree, top)
    if not os.path.isdir(d):
        return []
    return sorted(n for n in os.listdir(d)
                  if os.path.isdir(os.path.join(d, n)) and n not in RESERVED[top])


if __name__ == "__main__":
    tree = sys.argv[1]
    json.dump({"lib": subdirs(tree, "lib"), "share": subdirs(tree, "share")},
              sys.stdout, indent=2)
    print()
