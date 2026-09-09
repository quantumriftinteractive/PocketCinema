# FFmpeg 2.4.14 PocketCinema source preservation

Recorded 2026-09-09 on Windows. This is a source-preservation input set, not a
new build or approval to redistribute the runtime. The original recovered tree
was only read. No FFplay/selector compilation or Miyoo access occurred.

## Authoritative recovered inputs

Recovery root: `C:\Users\ysocr\MM--PocketStremio`.
Configured tree: `.tmp/ffmpeg-2.4.14` (not a separate Git checkout).
Pristine archive: `.tmp/ffmpeg-2.4.14.tar.xz`, SHA-256
`736567ee95115876d7af7f99f2fa565417c351b748bdc05973618980da1df037`.
An independent read of the [official FFmpeg archive](https://ffmpeg.org/releases/ffmpeg-2.4.14.tar.xz)
matched that hash. `VERSION` and `RELEASE` identify 2.4.14. The archive contains 4,706 regular
files. Every original regular file remains present in the recovered tree;
only the following two have different bytes:

| Final source | SHA-256 |
| --- | --- |
| `ffplay.c` | `b9020d7e8faaa6ade5641994ee3daaf24ede29200a16e34101b9542478553b22` |
| `libavfilter/vf_subtitles.c` | `f3e10bd48ad62088b9949bc819e6fa5fb5994fdeea9dce2374fe1f04f6f7bf42` |

`final.patch` is a byte-preserving unified diff from those pristine archive
members to the final recovered files. SHA-256:
`18d917d32cb0279acc7804849560d33bd7355602c5caa78d001552320b3f5747`.
It is authoritative for this preserved revision; do not apply the seven
historical experiment patches in addition. Historical patch chronology is
unnecessary for recreating these final source bytes.

The patch retains the final subtitle/font-scale, track notice, fontconfig,
native-subtitle suppression, display and aspect changes, including original
legacy identifiers. No cleanup, encoding normalization, or identity rename
was applied during preservation.

## Binary relationship and build observations

The final matching binary was recovered from the original configured build
tree at `.tmp/ffmpeg-2.4.14/ffplay`. Its SHA-256 is
`3a1f0da45dc2d6b44bd211476d9c05457ce7e25dc5050af4258e44f3fdc779e6`.
The retained `ffplay_g` SHA-256 is
`242f763350fb11b54aa3b7181b6e6297e412ddc68724bdbf9a19ad3497b47305`.
Neither binary nor any object/static-library output is copied into this source
set or committed.

The matching binary embeds `Aug 24 2026`, GCC 15.2.1 and
`POCKETCINEMA_SUBTITLE_FONT_SCALE`. Observed local filesystem modification
times: `cmdutils.o` August 24 12:45:06; `config.h` August 24 12:43:41;
`vf_subtitles.c` September 4 17:23:05; its object September 4 17:24:09;
`ffplay.c` September 5 21:58:16; `ffplay.o` September 5 21:58:42;
`ffplay` September 5 21:58:43. These support an incremental-build explanation
for the older embedded date; they are not an independently authenticated build
chronology. The recovered final source and matching output are co-located.
**Bit-for-bit build reproducibility has not been established.**

## Compiler, sysroot and configuration

Compiler: `.tmp/arm-gnu/bin/arm-none-linux-gnueabihf-gcc.exe`.
Actual `--version`: `Arm GNU Toolchain 15.2.Rel1 (Build arm-15.86)`;
`15.2.1 20251203`. Executable SHA-256:
`a5077d9333eb16fcd86075fe699dab79c70c4d3ae1e880d817c6acc066a68202`.
Compiler archive `.tmp/arm-gnu/arm-gnu-toolchain.zip` SHA-256:
`1ae2b1abdae0c37869c92526f5d3533fc7e6d47c242a593f374674d45d0a5152`.

Configured sysroot:
`.tmp/toolchain/mmiyoo/arm-buildroot-linux-gnueabihf/sysroot`.
SDK archive `.tmp/toolchain/toolchain.tar.gz` SHA-256:
`2b39aaf388114cbe773701ed2310a8e8240ff775c4aafdafa4c4859790126581`.
This explicit sysroot overrides the Arm compiler's default
`arm-none-linux-gnueabihf/libc`. SDK library compilation is a separate provenance
chain: libass's ELF comment identifies Arm's 8.2-2018-08 GCC 8.2.1, not 15.2.1.

`configuration/configure-command.txt` preserves the **complete exact command**
from line 1 of `.tmp/ffmpeg-configure.log`, removing only the log's `# ` prefix.
It is also recorded as `FFMPEG_CONFIGURATION` in `configuration/config.mak`.
Both generated configuration files and the pkg-config shim are preserved
byte-for-byte, including the original non-secret local paths. Consult
`manifest.json` for every checksum. The shim SHA-256 is
`5ea1f5f0380b73a946c8b8e08c4019d77079c92b2ccc3f87a7162ef43b44de2b`.
The full configure log hashes to
`eb21be4ba4c9b6d1e830000748264403d2f1f875b5a208e2066b3318c5a90b8c`;
its environment dump is deliberately not copied into Git.

Retained `.tmp/ffplay-*build.log` files show compile/link/copy/strip stages.
No complete historical make-command wrapper was recovered. A future independent
rebuild must deliberately adapt host paths and verify the shell, make, linker,
sysroot and pkg-config behavior; this record does not pretend that configuration
alone establishes an independently reproduced binary.

## Stage and verify, without compiling

From the repository root, with Python 3.11+ and Git available:

```text
python -B scripts/preserve-miyoo-ffmpeg-source.py --archive <verified-ffmpeg-2.4.14.tar.xz> --output <new-directory>
```

The script refuses existing output and incorrect hashes; rejects archive links,
special files and traversal; preserves pristine source/archive and licenses;
applies the final patch with `core.autocrlf=false`; verifies all 4,706 source
files against pristine/final hashes; then adds the preserved shim and provenance.
It never executes configure, make, a compiler or a target binary.
The archive's `LICENSE.md` and four `COPYING.*` files remain in the staged source.
Generated `config.h`/`config.mak` are reference evidence under `provenance`, not
silently installed as a newly configured build.

Verification passed in
`release-sources/miyoo/staging/ffmpeg-2.4.14-pocketcinema-final/`:
both final hashes match and the other 4,704 source files remain pristine.
An initial verification detected Windows Git CRLF conversion and was rejected;
the explicit Git setting above fixed preservation without changing recovered
inputs. This is source reconstruction verification, not a reproduction build.

See [dependency and storage assessment](../PROVENANCE.md) for remaining gates.
