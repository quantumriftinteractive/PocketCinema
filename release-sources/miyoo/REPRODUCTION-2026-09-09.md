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
