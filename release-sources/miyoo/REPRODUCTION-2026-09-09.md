# FFplay independent reproduction gate

Date: 2026-09-09 (Windows)

## Workspace and inputs

The isolated workspace was
`C:\Users\ysocr\PocketCinema-Miyoo-v1.0.0-reproduction`. Fresh FFmpeg 2.4.14
source was extracted from the verified external archive, and
`release-sources/miyoo/ffmpeg-2.4.14-pocketcinema/final.patch` was applied with
Git `core.autocrlf=false`.

The patched `ffplay.c` hash is
`b9020d7e8faaa6ade5641994ee3daaf24ede29200a16e34101b9542478553b22`; patched
`libavfilter/vf_subtitles.c` is
`f3e10bd48ad62088b9949bc819e6fa5fb5994fdeea9dce2374fe1f04f6f7bf42`. All 4,706
pristine archive members were checked; only those two expected files differed.

## Configure result

The preserved configure command was executed with the recovered Arm GNU
Toolchain 15.2.1 compiler, Miyoo sysroot, include/library paths, and copied
pkg-config shim. The first attempt exposed a shell `PATH` assumption for the
shim; rerunning with only the isolated workspace added to `PATH` reached the
actual dependency probe.

Configure then failed with no generated `config.h` or `config.mak`. The linker
reported that the compiler-provided `libgcc_s.so.1` requires
`pthread_once@GLIBC_2.34`, `pthread_setspecific@GLIBC_2.34`,
`pthread_getspecific@GLIBC_2.34`, and `pthread_key_create@GLIBC_2.34`, which the
recovered Miyoo sysroot does not provide. The failure occurred while probing
libass. No compiler, sysroot, source archive, recovered source tree, or known-good
FFplay binary was changed.

Classification: **D — BUILD FAILED**. No reproduced FFplay size or SHA-256 exists;
the known-good shipped binary remains
`3a1f0da45dc2d6b44bd211476d9c05457ce7e25dc5050af4258e44f3fdc779e6`.

This blocks the independent reproduction gate and leaves final v1 release
approval open. It does not invalidate the corresponding-source or license bundle;
no compiler/sysroot substitution or build workaround was attempted.

## Bounded compatibility investigation

The failing linker command was:

```text
arm-none-linux-gnueabihf-gcc.exe --sysroot=<miyoo-sysroot> -isysroot <miyoo-sysroot> -Wl,--as-needed -Wl,-z,noexecstack -I/usr/include -L/usr/lib -pthread -o <probe> <object> -lass -lfontconfig -lfreetype -lfribidi -lharfbuzz -lexpat -luuid -lglib-2.0 -lpcre -lpng16 -lbz2 -lz -lm -lm -lbz2 -lz -pthread
```

The effective `-L` order was `/usr/lib` from the pkg-config shim, with no
historical sysroot `-L` entry in this failing probe. The compiler's default
search directories select:

`C:\Users\ysocr\MM--PocketStremio\.tmp\arm-gnu\arm-none-linux-gnueabihf\lib\libgcc_s.so.1`

SHA-256:
`13a1a42b29a36b0acd0ccbbb3b932e49734bf59679117577d508090aed970e59`.
It is ELF32 little-endian ARM, needs `libc.so.6`, and requires GLIBC_2.34
pthread symbols.

Recovered candidates were:

| Path family | SHA-256 | GLIBC requirement |
| --- | --- | --- |
| `arm-gnu/arm-none-linux-gnueabihf/lib/libgcc_s.so.1` and its `libc/usr/lib` copy | `13a1a42b29a36b0acd0ccbbb3b932e49734bf59679117577d508090aed970e59` | GLIBC_2.4 and GLIBC_2.34 |
| Miyoo SDK sysroot `lib/` and `usr/lib/` | `c9b53158286d9d29c1b5f8469b7c722f0a74f47209e0eb915042c64f58370b70` | GLIBC_2.4 only |
| recovered prebuilt target toolchain `lib/` and `libc/usr/lib` | `c9b53158286d9d29c1b5f8469b7c722f0a74f47209e0eb915042c64f58370b70` | GLIBC_2.4 only |

All candidates are ELF32 little-endian ARM and need `libc.so.6`. The first pair
belongs to the recovered Arm GNU 15.2.1 compiler archive; the compatible pair is
present in the recovered target SDK/prebuilt inputs.

GCC reports its default sysroot as the compiler's bundled `arm-none-linux-gnueabihf/libc`,
while the explicit `--sysroot` points at the Miyoo SDK. `--print-multi-lib` reports
only `.;`. `-print-file-name=libgcc_s.so.1` returns the bare runtime name, while
the failing linker diagnostic identifies the bundled compiler path above.

The known-good FFplay does **not** have `libgcc_s.so.1` in `DT_NEEDED`; its
interpreter is `/lib/ld-linux-armhf.so.3`, and its highest observed GLIBC symbol
version is GLIBC_2.28. It therefore does not require the incompatible GLIBC_2.34
runtime at execution time.

Historical `config.mak` and the successful configure log preserve this environment:

```text
LDFLAGS=" -L<sysroot>/usr/lib -Wl,-rpath-link,<sysroot>/usr/lib"
```

Successful historical probe/link commands place the sysroot `-L` before the
pkg-config `/usr/lib` entries. Retained historical objects, including `ffplay.o`,
`cmdutils.o`, and `vf_subtitles.o`, contain GCC 15.2.1 comments and do not carry
the GLIBC_2.34 pthread requirement. The incompatibility is therefore a final
compiler-runtime selection problem, not a source/object incompatibility.

Root cause: **B — missing historical link environment**. The smallest supported
next correction is one retry with the exact preserved configure command preceded
by the historical `LDFLAGS` value above. Do not add `-static-libgcc`, substitute a
toolchain, or alter the configure command. That retry has not been executed.

## Controlled configure retry

The preserved patched source was copied to the fresh isolated workspace
`C:\Users\ysocr\PocketCinema-Miyoo-v1.0.0-reproduction-retry-20260909`; the prior
failed workspace and authoritative recovered inputs were left unchanged. The
exact historical linker environment was restored:

```text
LDFLAGS=" -L/c/Users/ysocr/MM--PocketStremio/.tmp/toolchain/mmiyoo/arm-buildroot-linux-gnueabihf/sysroot/usr/lib -Wl,-rpath-link,/c/Users/ysocr/MM--PocketStremio/.tmp/toolchain/mmiyoo/arm-buildroot-linux-gnueabihf/sysroot/usr/lib"
```

The retry used the recovered Arm GNU 15.2.1 compiler, recovered Miyoo sysroot,
and copied `pkg-config-arm.sh` shim. Configure exited with failure at the next
smallest boundary, `freetype2`: the shim returned `-I/usr/include/freetype2`,
and the cross compiler could not find `ft2build.h`. The libass probe passed its
link step with target sysroot `-L` entries first; the prior GLIBC_2.34
`libgcc_s.so.1` failure did not recur. No `config.h` or `config.mak` was
generated, so reproduced hashes are unavailable. Classification: **D - CONFIGURE
STILL FAILS**. No build or deployment is authorized by this result; the next
action requires separately authorized investigation of the historical
freetype/pkg-config include-path environment.

## Bounded FreeType/pkg-config investigation

The recovered FreeType header is at
`<Miyoo-sysroot>/usr/include/freetype2/ft2build.h`, with the required headers
under the same `freetype2` directory. The recovered `.pc` file is
`<Miyoo-sysroot>/usr/lib/pkgconfig/freetype2.pc`, SHA-256
`f1a8d606218ba5265c00da101a56eb41484cf716da312aa21e2f8e0f1dee874f`.
It declares `prefix=/usr`, `includedir=/usr/include`,
`Cflags: -I${includedir}/freetype2`, and `Libs: -L${libdir} -lfreetype`.

The archived reproduction shim (`pkg-config-arm.sh`, SHA-256
`5ea1f5f0380b73a946c8b8e08c4019d77079c92b2ccc3f87a7162ef43b44de2b`) returns
`-I/usr/include/freetype2` and `-L/usr/lib -lfreetype`; it invokes no external
pkg-config and defines no `PKG_CONFIG_SYSROOT_DIR`, `PKG_CONFIG_LIBDIR`, or
path-rewriting behavior. The preserved historical configure log instead shows
sysrooted FreeType flags. The retained `experiments/ffplay/pkg-config-arm.sh`
(commit `3c29d15`) computes the repository sysroot and returns those exact
sysrooted flags. The historical log records no `PKG_CONFIG_SYSROOT_DIR`; its
visible `PKG_CONFIG_PATH` is the host MSYS default.

A standalone compiler include-search probe confirms that `--sysroot` rewrites
standard `/usr/include` search locations but does not rewrite an explicit
`-I/usr/include/freetype2`: that directory resolves to the Git installation and
is ignored. The exact sysrooted include flag finds `ft2build.h`. Historical
FreeType configure evidence uses the sysrooted flag and succeeds.

Root cause: **D - wrong pkg-config file selected**. The retry used the archived
shim with unrooted FreeType output, while historical success used the preserved
sysroot-aware experiment shim. The single supported correction is to invoke the
preserved `experiments/ffplay/pkg-config-arm.sh` behavior for the next configure
retry. No configure retry was run during this investigation.

## Configure reproduction pass with explained differences

A fresh isolated retry workspace was used:
`C:\Users\ysocr\PocketCinema-Miyoo-v1.0.0-reproduction-retry-20260909-sysrootshim`.
The verified patched source hashes remained `ffplay.c`
`b9020d7e8faaa6ade5641994ee3daaf24ede29200a16e34101b9542478553b22` and
`libavfilter/vf_subtitles.c`
`f3e10bd48ad62088b9949bc819e6fa5fb5994fdeea9dce2374fe1f04f6f7bf42`.

Configure used the recovered Arm GNU 15.2.1 compiler, Miyoo sysroot, historical
 target-first `LDFLAGS`, and the preserved sysroot-aware
`experiments/ffplay/pkg-config-arm.sh`. It exited 0. The libass and FreeType
probes passed, and no GLIBC_2.34/libgcc_s failure appeared.

Generated hashes are:

```text
config.h   7356d35833f6a6dfb374b64b0cc785875b2a5abe75ace4e7c0d9cca6ec32e5b0
config.mak b1c220356646b8d6f38156a34b47a32caac555fab4e82aad4871bf279ee05dcb
```

Historical hashes remain `config.h`
`61f378e9fbb713a51f7c43294f543378d8e49137d658c9ccf4b6b58708e129b8` and
`config.mak` `d47e8ddcf95d383ed0d17e662aeac362c98b4ed7df48350f8a7d4d684ae175b1`.
Bounded textual comparison found only workspace/logfile/pkg-config path changes
and the equivalent target-first linker flags appearing twice because the
historical `LDFLAGS` environment and preserved `--extra-ldflags` both contribute
the same entries. No enabled-component or link-library difference was found.
Classification: **B - CONFIGURE PASS WITH EXPLAINED NON-MATERIAL DIFFERENCES**.
No build was run. The independent FFplay build can now be separately authorized.

## Independent FFplay build result

The authorized FFplay-only build ran in
`C:\Users\ysocr\PocketCinema-Miyoo-v1.0.0-reproduction-retry-20260909-sysrootshim`
with `/c/Users/ysocr/MM--PocketStremio/.tmp/make.exe -j4
SHELL="C:/Program Files/Git/usr/bin/sh.exe" ffplay`. The target completed
successfully, linking `ffplay_g`, copying it to `ffplay`, and applying the
preserved strip command:

```text
/c/Users/ysocr/MM--PocketStremio/.tmp/arm-gnu/bin/arm-none-linux-gnueabihf-strip ffplay
```

Pre-strip `ffplay_g`: 3,309,472 bytes,
SHA-256 `724d193128d119de4fc954bc15d632256d600ef8a52a4146573813228844e82f`.
Post-strip candidate `ffplay`: 1,577,704 bytes,
SHA-256 `0898573c1460f5ea36324a1c558d4a163ca76b63fdababf7c66e9e91044af73a`.
Known-good remains 1,577,708 bytes,
SHA-256 `3a1f0da45dc2d6b44bd211476d9c05457ce7e25dc5050af4258e44f3fdc779e6`.

The candidate is not byte-identical. Bounded ELF checks show matching ARM32
interpreter, expected SDL/FreeType/libass/bz2/z/pthread/libc dependencies, no
RPATH/RUNPATH, GLIBC requirements no higher than 2.28, and no `libgcc_s.so.1`
dependency. However, `.text` is 4 bytes larger and 746,293 bytes differ across
the common text range; this is a material executable difference, not metadata or
path-only variation. Classification: **C - MATERIAL UNEXPLAINED BINARY DIFFERENCE**.
The independent reproduction gate remains blocked. No further binary archaeology,
deployment, or selector work was performed.
