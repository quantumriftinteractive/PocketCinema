# Miyoo runtime provenance and preservation assessment

Evidence date: 2026-09-09. M23 remains Next; public redistribution is blocked.
No recovered original was modified, no player/selector was compiled, no runtime
artifact was committed, and no Miyoo/SD-card access occurred.

## Preservation result

[FFmpeg build provenance](ffmpeg-2.4.14-pocketcinema/BUILD-PROVENANCE.md),
`final.patch`, exact configuration and `manifest.json` are the durable small
Git inputs. The host-side source staging script reconstructs the final two
source files byte-for-byte from the hash-pinned pristine archive. The full
staged source/archive is ignored under `staging/`; binaries and objects are
excluded. This is not a newly built player or a complete dependency source set.

## Locally proven SDK evidence

Recovered archive `.tmp/toolchain/toolchain.tar.gz`: 753,300,837 bytes;
SHA-256 `2b39aaf388114cbe773701ed2310a8e8240ff775c4aafdafa4c4859790126581`.
Its 58,589 entries include `mmiyoo/` and `prebuilt/`.
All fifteen library files used by `scripts/deploy-miyoo.ps1` match their archive
members byte-for-byte. Exact library hashes, original paths and deployed names
are in [dependency-binaries.json](dependency-binaries.json). The archive's
`libSDL-1.2.so.0` symlink targets `libSDL-1.2.so.0.11.4`; the deployer copies the
actual file under its runtime SONAME. libuuid comes from `sysroot/lib`, the
other entries from `sysroot/usr/lib`.

`mmiyoo/bin/attr`, `chacl` and `cmake` retain build paths under
`/home/steward/mmiyoo_buildroot/output/build/`, including host-attr-2.5.1,
host-acl-2.3.1 and host-cmake-3.16.9. This is direct evidence of Steward's
Buildroot build environment.

`mmiyoo/etc/meson/cross-compilation.conf` explicitly describes Buildroot/Meson
roles, `/opt/mmiyoo`, the `arm-linux-gnueabihf` external compiler, Cortex-A7,
little-endian ARM/Linux, `-Ofast -g0 -D_FORTIFY_SOURCE=1`, and the matching
`arm-buildroot-linux-gnueabihf/sysroot`. libass's `.comment` section identifies
`GNU Toolchain for the A-profile Architecture 8.2-2018-08 (arm-rel-8.23)` /
`8.2.1 20180802`. The recovered Windows FFplay compiler is separately GCC 15.2.1.

No SDK `.config`, defconfig, package source/hash manifest, Buildroot version
stamp, `legal-info`, relocation script, or complete package sources were found
in the archive or extracted tree. Generic headers mentioning manifests are not
SDK manifests. Installed `.pc`, `.la`, headers and CMake files retain versions,
paths and linkage metadata, but cannot prove the exact applied patch set.

## Authoritative online evidence and its limits

[Steward's Miyoo Mini Plus kernel instructions](https://steward-fu.github.io/website/handheld/miyoo_mini_plus_build_kernel.htm)
explicitly use the `miyoo-mini/toolchain.tar.gz` release asset and its `mmiyoo`
and `prebuilt` directories. The [release API](https://api.github.com/repos/steward-fu/website/releases/tags/miyoo-mini)
records the same 753,300,837-byte asset, created March 1, 2024, with no digest.
This strongly identifies the SDK family and probable download artifact; equal
size is not a cryptographic match. No replacement SDK binary was downloaded.
This is a Steward Miyoo Mini SDK candidate, not proven to be an OnionOS-built
SDK or the distinct `onion_toolchain.tar.gz` release asset. SDK classification: **C**
(family/version strongly corroborated, exact final configuration and patch set
unproven).

[Steward's Parasyte Buildroot instructions](https://steward-fu.github.io/website/handheld/miyoo_mini_parasyte_build_buildroot.htm)
name Buildroot 2021.11, the external Arm 8.2-2018.08 toolchain and `/opt/mmiyoo`.
The published source archive was downloaded for inspection. It is byte-for-byte
identical to [upstream Buildroot 2021.11](https://buildroot.org/downloads/buildroot-2021.11.tar.gz):
7,095,981 bytes, SHA-256
`9b3c372076b5d3de4a1ffb6693a8b94723144fe2d894398bf42d5ddbc73d9911`.
Every source member also matched; no vendor source changes were found in that
published archive. Its recipes match all fifteen installed dependency versions.

The separately published `buildroot-2021.11_config` has SHA-256
`d889c98485b6786bb23e8558af5aa0786a792c25e53739847e9637448c53d577`.
It identifies Buildroot 2021.11 and the external Arm GCC 8 toolchain, but its
`BR2_HOST_DIR="/opt/mini"` differs from the recovered `/opt/mmiyoo`.
Its release upload is January 5, 2025, while SDK files carry 2022 timestamps.
**The exact configuration that produced the recovered SDK is not recovered.**
Buildroot 2021.11 is a strongly corroborated candidate, not an exact locally
proven version/configuration pair. The published source/config must not silently
replace the missing original configuration. Download URLs and hashes are in
[upstream-inputs.json](upstream-inputs.json).

## Dependency classification and source/license inventory

Classification: A = proven stock upstream; B = proven Buildroot-patched;
C = proven Miyoo/Onion-specific patches; D = exact source variant unknown.
All recovered binaries are classified **C**: Buildroot/package versions and candidate
recipes are corroborated, but exact source artifacts and applied patch sets are not
proven. The candidate recipe column shows what
stock Buildroot 2021.11 would apply, not what was proven applied to these bytes.
Zero package patches does not prove A; recipe hooks, global patches, manual
changes and configuration remain possible. No C patch set was established.
The candidate patch filenames and recipe/hash-file checksums are preserved in
[buildroot-package-index.json](buildroot-package-index.json).

Local paths below are relative to
`.tmp/toolchain/mmiyoo/arm-buildroot-linux-gnueabihf/sysroot`.
Header notices are evidence, not a claim of complete package-wide attribution.

| Library/version | Class | Candidate recipe patches | Local license/copyright evidence | Still needed from exact source package |
| --- | --- | --- | --- | --- |
| SDL 1.2.15 | C | 2: DirectFB config, libX11 build | `usr/include/SDL/SDL.h`: LGPL notice | SDL-1.2.15 source, applied patches, full `COPYING` |
| libass 0.15.2 | C | 0 | `usr/include/ass/ass.h`: ISC notice | libass-0.15.2 source and package `COPYING` |
| bzip2 1.0.8 | C | 2: object/build-system changes | `usr/include/bzlib.h`: copyright, reference to LICENSE | bzip2-1.0.8 source/patches, `LICENSE` |
| zlib 1.2.11 | C | 0 (`libzlib`) | `usr/include/zlib.h`: zlib notice | zlib-1.2.11 source, package `README` license |
| Fontconfig 2.13.1 | C | 2: static build/pthread | `usr/include/fontconfig/fontconfig.h`: permission notice | fontconfig-2.13.1 source/patches, `COPYING` |
| FreeType 2.10.4 | C | 0 | `usr/include/freetype2/freetype/freetype.h`: FTL/GPL reference | freetype-2.10.4 source; `docs/LICENSE.TXT`, `docs/FTL.TXT`, `docs/GPLv2.TXT` |
| FriBidi 1.0.10 | C | 0 | `usr/include/fribidi/fribidi.h`: LGPL notice | fribidi-1.0.10 source, `COPYING` |
| HarfBuzz 3.0.0 | C | 1: pthread header detection | `usr/include/harfbuzz/hb.h`: permission notice | harfbuzz-3.0.0 source/patch, aggregate `COPYING` including ucdn |
| GLib 2.68.4 | C | 4: atomic detection, C++ requirement, compiler flag, pkg-config | `usr/include/glib-2.0/glib.h`: LGPL notice | glib-2.68.4 source/patches, `COPYING` |
| PCRE 8.45 | C | 2: compatibility bits, C++ tests | `usr/share/doc/pcre/LICENCE`: full license; `COPYING` only points to it | pcre-8.45 source/patches; preserve recovered `LICENCE` |
| Expat 2.4.1 | C | 0 | `usr/include/expat.h`: MIT notice | expat-2.4.1 source, aggregate `COPYING` |
| libpng 1.6.37 | C | 1: disable pngfix tools | `usr/include/libpng16/png.h`: license text | libpng-1.6.37 source/patch, package `LICENSE` |
| libffi 3.4.2 | C | 3: install location, two MIPS fixes | `usr/include/ffi.h`: MIT notice | libffi-3.4.2 source/patches, package `LICENSE`; ARM applicability assessed later |
| libuuid 2.37.2 | C | 2 util-linux patches, one specifically libuuid | `usr/include/uuid/uuid.h`: BSD notice | util-linux-2.37.2 source/patches, `README.licensing`, `libuuid/COPYING`; assess libuuid separately from util-linux programs |
| tslib 1.22 | C | 0 | `usr/include/tslib.h`: LGPL notice | tslib-1.22 source, `COPYING`; separate library/program terms |

Version evidence is installed `.pc` data except bzip2's header and FreeType's
2.10.4 header macros (`freetype2.pc` reports its separate 23.4.17 numbering).
Authoritative source sites are recorded from the candidate Buildroot recipes:
libsdl.org, libass/libass, sourceware.org/bzip2, zlib.net, fontconfig.org,
Savannah FreeType, fribidi/fribidi, harfbuzz/harfbuzz, GNOME GLib, PCRE/Expat/libpng
project release archives, libffi/libffi, kernel.org util-linux and libts/tslib.
The actual upstream package archives have not been downloaded in this pass.

Sixteen original local license/header evidence files were copied into ignored
`staging/license-evidence/`, preserving their relative paths. Their hashes are
in [license-evidence.json](license-evidence.json). PCRE's actual `LICENCE` corrects
the earlier read-only report's incomplete identification of `COPYING`.
The CMake host tool's bundled zlib copyright is not substituted for the target
zlib license. No license text was invented.

## Plus Jakarta Sans exact-match investigation

Recovered font `.tmp/stremio-web/assets/fonts/PlusJakartaSans.ttf`:
176,408 bytes; SHA-256
`ca8cefd42d9d711cc864703355cb935dc9829e45d7c31f0ab5791cb8f77637c8`.
Embedded metadata: version 2.006, Tokotype, Gumpita Rahayu, copyright 2020
The Plus Jakarta Sans Project Authors, SIL OFL 1.1, and the official Tokotype
repository URL. Local Stremio Web checkout: `1748dc1a3e95f0eb0d171f78aedb536e7df7cd61`.

Only [Tokotype's official repository](https://github.com/tokotype/PlusJakartaSans)
was contacted for font investigation. A separate ignored bare source clone
was inspected across its fetched branches/tags: 153 historical `.ttf` blobs;
none had the recovered file's byte length. All TTF entries in the five published
release ZIPs (1.000, 2.5, 2.6, 2.7, 2.7.1) were also checked; no exact-sized
candidate existed. ZIPs were read in memory, not installed as replacements.
This establishes no exact match in those inspected objects/assets, not absence
from every historical or unpublished upstream build. Version-label similarity
does not establish an exact source relationship.

Official tag 2.6 points to `960fcb9c47ff640ccd643d9c096593137ad8cee3`.
Its [OFL.txt](https://github.com/tokotype/PlusJakartaSans/blob/960fcb9c47ff640ccd643d9c096593137ad8cee3/OFL.txt)
was recovered under `inputs/PlusJakartaSans-2.6-OFL.txt`, SHA-256
`578bfe73675edc639f6aaa6e2e9ac598936bf696f95f034fb7682dca2edc53c7`.
This is authoritative project license material but **not proof that tag 2.6
contains the exact shipped font**. Exact upstream font commit/path and any
intermediate processing remain unresolved. The recovered font was not changed.

## Proposed release structure and retention policy

Recommendation only; no distributable package/source asset was published:

```text
PocketCinema-Miyoo-v1.0.0/
  THIRD_PARTY_NOTICES.md
  licenses/                    # complete attributable texts for shipped components
  source-info/manifest.json    # binary/source hashes, versions, immutable source asset URL
PocketCinema-Miyoo-v1.0.0-source.tar.xz
  ffmpeg/                     # full final source, licenses, final.patch, configure evidence
  dependencies/               # exact corresponding sources, patches, configuration
  BUILD-PROVENANCE.md
```

Keep notices and actual license texts with the binary package. Prefer a complete
source asset beside the binary release over relying solely on third-party links
or an unimplemented written offer. FFmpeg's own [source/configuration guidance](https://ffmpeg.org/legal.html)
supports recording changes/build instructions and hosting matching source with
the binary. Exact dependency obligations and final linkage/relinkability review
remain a release gate; this proposed layout alone does not clear them.

| Material | Long-term policy |
| --- | --- |
| A: first-party patch, configuration, manifests, staging script, evidence | Small focused Git commits, pushed and verified. Preserve raw patch/config bytes through `.gitattributes`. |
| B: pristine FFmpeg and other upstream source archives | Hash-pinned controlled archive storage and eventual source release assets; do not commit whole upstream trees for convenience. |
| C: SDK/Arm compiler and original recovered build tree | Keep originals immutable; maintain separately backed-up, hash-pinned build inputs. The original build tree is historical evidence, not something the source staging script can recreate including objects. |
| D: dependency corresponding source | Preserve exact archives, applied patches, configuration, notices and scripts; publish required corresponding source with release. Stock version matches alone are insufficient. |
| E: generated runtime/source release artifacts | Immutable versioned release assets with checksums after separate validation; no runtime binaries in this metadata commit. |

`inputs/` and `staging/` are ignored, deliberate local analysis/archive copies.
The final source set is `staging/ffmpeg-2.4.14-pocketcinema-final/`.
The initial `staging/ffmpeg-2.4.14-pocketcinema/` is a rejected CRLF-converted
analysis copy, not a release-source input. An earlier successful
`staging/ffmpeg-2.4.14-pocketcinema-verified/` is also retained; use the final set.
Their unique first-party reconstruction work is represented in Git. No external
durable archive destination has been configured or uploaded in this pass.
**Preserving Git metadata is not a backup of the SDK, original build tree or
font.** Off-machine archival of those recovered inputs remains explicitly open.

## Remaining gates and regression impact

1. Recover/attest the exact SDK configuration, vendor patch history and artifact
   digest relationship; obtain matching dependency corresponding source and full
   package-wide notices/licenses. Buildroot 2021.11 is the candidate starting point.
2. Resolve the exact font source/processing chain; retain its complete applicable
   OFL/copyright material without substituting a different font silently.
3. Back up recovered original inputs in controlled external storage and produce
   the final source/notice assets. No release asset is published by this work.
4. Run a separately authorized independent FFplay reproduction build later;
   source patch verification does not establish binary reproducibility.
5. Complete final linkage/license/artifact review and the existing fresh-install
   physical release gate. Current M21/M22 physical evidence remains inherited.

| Changed area | Verification | Inherited evidence / reason |
| --- | --- | --- |
| Source preservation script/metadata | Whole-source patch/hash verification, malformed-input/output-refusal checks, syntax, Git byte preservation | No runtime or deployment changes; all playback/subtitle/controller evidence inherited |
| Provenance and release-gate documentation | Local/archive/source comparisons and authoritative-source review | No product behavior changed; no Apps retest required |

Stop here: no FFplay or selector rebuild, deployment, package publishing, or
Miyoo access belongs to this task.
