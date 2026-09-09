# PocketCinema Miyoo v1 public compliance bundle

This metadata bundle accompanies the Miyoo runtime. The corresponding-source archives are release assets named and hash-pinned in `SOURCE-MANIFEST.json`; the large private archival input directory is not this bundle. The candidate player sets `LD_LIBRARY_PATH` to `experiments/ffplay/lib` before launching FFplay, so the listed shared libraries are replaceable compatible runtime files. Use the supplied corresponding sources and patches for LGPL modifications.

This bundle does not contain the compiler, SDK/sysroot, recovered runtime binaries, selector, account configuration, logs, or device state.
