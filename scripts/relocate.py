#!/usr/bin/env python3
"""Rewrite RUNPATHs that hardcode /app into $ORIGIN-relative ones.

On the FlatPark side this tree does not live at /app: extra-data unpacks it to
/app/extra/bottles. The main binaries — wine, bottles-cli, libvte — carry no
RUNPATH at all and find their libraries through LD_LIBRARY_PATH, so they survive
the move untouched. But the samba libraries bundled with wine hardcode
/app/lib/samba in several hundred RUNPATHs, which breaks once the tree moves.
Rewriting them to be $ORIGIN-relative makes the tree self-consistent wherever it
is unpacked.

Usage: relocate.py <tree>     # tree is the built files/ directory
"""
import os
import subprocess
import sys


def iter_elf(root):
    for dirpath, _, names in os.walk(root):
        for n in names:
            f = os.path.join(dirpath, n)
            if os.path.islink(f) or not os.path.isfile(f):
                continue
            try:
                with open(f, "rb") as fh:
                    if fh.read(4) != b"\x7fELF":
                        continue
            except OSError:
                continue
            yield dirpath, f


def rpath(f):
    r = subprocess.run(["patchelf", "--print-rpath", f], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def main(root):
    root = os.path.abspath(root)
    patched = failed = 0
    for dirpath, f in iter_elf(root):
        rp = rpath(f)
        if not rp or "/app" not in rp:
            continue
        out = []
        for entry in rp.split(":"):
            if entry.startswith("/app/"):
                target = os.path.join(root, entry[len("/app/"):])
                rel = os.path.relpath(target, dirpath)
                out.append("$ORIGIN" if rel == "." else "$ORIGIN/" + rel)
            elif entry.startswith("/run/build"):
                continue  # build-time leftover, drop it
            else:
                out.append(entry)
        r = subprocess.run(["patchelf", "--set-rpath", ":".join(out), f],
                           capture_output=True, text=True)
        if r.returncode:
            failed += 1
            print(f"FAIL {f}: {r.stderr.strip()}", file=sys.stderr)
        else:
            patched += 1

    # Verify: not a single one may remain.
    leftover = [f for _, f in iter_elf(root) if "/app" in rpath(f)]
    print(f"patched={patched} failed={failed} leftover={len(leftover)}")
    for f in leftover[:20]:
        print(f"  LEFTOVER {f}", file=sys.stderr)
    return 1 if (failed or leftover) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
