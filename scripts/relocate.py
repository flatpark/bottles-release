#!/usr/bin/env python3
"""把构建产物里指向 /app 的绝对 RUNPATH 改写成 $ORIGIN 相对路径。

FlatPark 侧这棵树不落在 /app,而是被 extra-data 解到 /app/extra/bottles。
wine / bottles-cli / libvte 等主要二进制本来就没有 RUNPATH(靠 LD_LIBRARY_PATH),
但 wine 捆绑的 samba 有几百个库把 /app/lib/samba 写死在 RUNPATH 里,搬家后就断了。
改成 $ORIGIN 相对路径后,这棵树放在哪都能自洽。

用法: relocate.py <tree>     # tree 是构建出来的 files/ 目录
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
                continue  # 构建期残留,丢掉
            else:
                out.append(entry)
        r = subprocess.run(["patchelf", "--set-rpath", ":".join(out), f],
                           capture_output=True, text=True)
        if r.returncode:
            failed += 1
            print(f"FAIL {f}: {r.stderr.strip()}", file=sys.stderr)
        else:
            patched += 1

    # 复核:一个都不能剩
    leftover = [f for _, f in iter_elf(root) if "/app" in rpath(f)]
    print(f"patched={patched} failed={failed} leftover={len(leftover)}")
    for f in leftover[:20]:
        print(f"  LEFTOVER {f}", file=sys.stderr)
    return 1 if (failed or leftover) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
