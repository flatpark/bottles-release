#!/usr/bin/env python3
"""导出产物的 lib/ 与 share/ 子目录清单。

FlatPark 的壳 manifest 里,/app/lib 和 /app/share 必须是真目录(flatpak-builder
构建期要在里面建扩展挂载点,穿不过悬空软链),所以它按子目录粒度软链回 payload,
而那份列表是写死在壳 manifest 里的。这个文件让 FlatPark 侧的 resolve-update.sh
能在刷 pin 时比对——payload 长出新子目录而壳没跟上,就当场报错,而不是等用户
装完发现某个路径是空的。

用法: layout.py <tree> > layout.json
"""
import json
import os
import sys

# 这些必须由 /app 真实持有,不能软链走:
#   lib/i386-linux-gnu  -> Compat.i386 / GL32 / codecs_extra.i386 的挂载点,
#                          且运行时的 /lib/i386-linux-gnu 写死指向它
#   share/{applications,icons,metainfo} -> 壳自带副本,构建期要导出
#   share/{wine,steam}  -> Wine.gecko / Wine.mono / Steam.CompatibilityTool 挂载点
#   share/app-info      -> flatpak-builder 构建期要往 share/app-info/xmls 写自己
#                          编译的 AppStream,悬空软链会让 appstreamcli compose 失败
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
