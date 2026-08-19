# bottles-release

给 [FlatPark](https://flatpark.org) 用的 Bottles 预编译产物。

这里构建 Bottles 的完整 `/app` 树并挂到 GitHub release;FlatPark 侧的
`registry/com.usebottles.bottles/` 用 **extra-data** 从这儿拉。这样 FlatPark 自己的
ostree 仓库里只有一个几十 KB 的壳,几百兆的负载走 GitHub 的带宽。

manifest fork 自 [flathub/com.usebottles.bottles](https://github.com/flathub/com.usebottles.bottles),
改动只有 `runtime-version: '49'` → `'50'`。GNOME 49 和 50 共用 freedesktop 25.08 基座
(fdo 扩展版本、Python 3.13、`base: org.winehq.Wine//stable-25.08` 全不变,Platform 的
`.so` 清单零删除),所以升级不需要动别的。

构建配方即本仓库,满足 GPL-3.0 的源码提供义务。

## 产物

每次 release 挂三个文件:

| 文件 | 说明 |
|---|---|
| `bottles-<ver>-x86_64.tar.zst` | 整棵 `/app` 树,解开后根目录叫 `bottles/` |
| `bottles-<ver>-x86_64.tar.zst.sha256` | 校验和 |
| `layout.json` | `lib/` 与 `share/` 的子目录清单,见下 |

## 为什么产物需要后处理

FlatPark 侧这棵树**不落在 `/app`**。Flatpak 的 `apply_extra` 在安装期只有 `/app/extra`
可写(`/app` 本身只读),沙箱里也起不了嵌套 bwrap 把它 bind 回去,所以树最终待在
`/app/extra/bottles/`。于是构建完要做两件事:

**1. 改写 RUNPATH**(`scripts/relocate.py`)

wine、bottles-cli、libvte 这些主要二进制本来就没有 RUNPATH,靠 `LD_LIBRARY_PATH` 找库,
搬家不受影响。但 wine 捆绑的 samba 有 400 多个库把 `/app/lib/samba`、`/app/lib32/samba`
写死在 RUNPATH 里。脚本把它们逐个换算成 `$ORIGIN` 相对路径,并复核到零残留,
有残留就让 CI 失败。

**2. 导出 layout**(`scripts/layout.py`)

FlatPark 的壳 manifest 里 `/app/lib` 和 `/app/share` **必须是真目录** —— flatpak-builder
在构建期要往里面建扩展挂载点,穿不过悬空软链(会报 `Extension ... has invalid merge-dirs`)。
所以壳是按**子目录**粒度软链回 payload 的,而那份列表写死在壳 manifest 里。
`layout.json` 让 FlatPark 刷 pin 时能比对:payload 长出新子目录而壳没跟上,当场报错,
不至于等用户装完才发现某个路径是空的。

被排除在软链之外、必须由 `/app` 真实持有的目录:

- `lib/i386-linux-gnu` —— `Compat.i386` / `GL32` / `codecs_extra.i386` 的挂载点。
  这个路径动不得:运行时里 `/lib/i386-linux-gnu -> ../../app/lib/i386-linux-gnu`
  是写死的,挪走就 `/lib/ld-linux.so.2: could not open`,32 位全废。
- `share/{applications,icons,metainfo}` —— 壳自带副本,flatpak 构建期要导出它们。
- `share/{wine,steam}` —— `Wine.gecko` / `Wine.mono` / `Steam.CompatibilityTool` 的挂载点。

## 更新

改 `com.usebottles.bottles.src.yaml` 里的 tag(以及需要时同步 upstream 的其它改动),
推到 `main` 即触发构建;也可以在 Actions 里手动 `workflow_dispatch`。
release 的 tag 取自 `src.yaml` 里的 Bottles 版本。

## 已知问题

Bottles 66.7 在 GNOME 50 的 libadwaita 1.9 下会刷这类 CRITICAL:

```
Adwaita-CRITICAL: Trying to add GtkOverlay / AdwBanner / AdwPreferencesPage /
AdwStatusPage as a child to an AdwPreferencePage, but only AdwPreferencesGroup is allowed
```

不致命,应用照跑,但相关页面的渲染值得复验。这是 Bottles 自己的代码在 1.9 收紧
子控件校验后暴露的问题,与本仓库的重定位无关(GNOME 49 下不出现)。
