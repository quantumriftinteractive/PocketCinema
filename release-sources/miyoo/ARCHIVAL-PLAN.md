# Miyoo v1 controlled archival plan

This plan records what must be retained outside Git so the recovered Windows
build can be reconstructed without putting large binaries or private working
state into the repository. The authoritative inventory is
`archival-manifest.json`; it is a verifier input, not a release approval.

Create one immutable external directory or object-store prefix named
`PocketCinema-Miyoo-v1.0.0-release-inputs/`, with restricted write access and a
second independent backup. Preserve the following categories:

| Category | Contents | Git policy |
| --- | --- | --- |
| first-party metadata | `release-sources/miyoo/`, final patch, configuration, manifests, verifier | Track the small files already committed. |
| upstream source | pristine FFmpeg archive and later exact dependency source archives | Store externally with immutable hashes; publish corresponding source with the binary if shipped. |
| toolchain/SDK | Arm compiler archive, complete Miyoo SDK tarball, and immutable recovery notes | External controlled archive only; never commit. |
| exact font | recovered `PlusJakartaSans.ttf` plus authoritative copyright/OFL material | External archive until exact upstream artifact/processing provenance is resolved. |
| corresponding source bundle | final FFmpeg source, exact dependency sources, applied patches, package configuration, notices and `SHA256SUMS` | Generate only after dependency provenance is complete; release alongside binaries. |
| generated binaries | FFplay, shared libraries, selector and packaged SD artifacts | Separate versioned release artifacts; never treat them as source provenance. |

At the archival root, create `SHA256SUMS` from the committed manifest and an
`ARCHIVE-README.md` containing the recovery machine, date, source commit, and
whether each item is exact, corroborating, or unresolved. Keep the raw recovered
`.tmp` tree immutable until an independent reproduction gate is finished. Store
the output of the verifier with the archive and record the archive's own digest
in release bookkeeping. Do not use a working checkout as the only backup.

The current manifest intentionally includes the recovered FFplay and font so
their identity cannot be lost, even though they are not eligible for Git. It
does not imply that either is approved for redistribution. The candidate
Buildroot configuration and OFL text are optional corroborating inputs and are
not substitutes for the missing exact SDK configuration or exact font source.

Recommended release source layout after the remaining gaps close:

```text
PocketCinema-Miyoo-v1.0.0-source/
  ffmpeg-2.4.14/                 # exact corresponding source and licenses
  dependencies/                  # exact source archives and applied patches
  licenses/                      # complete notices for shipped components
  source-info/manifest.json
  SHA256SUMS
  BUILD-PROVENANCE.md
```

The next archival action is a controlled copy and hash verification by a human
or release process with access to durable external storage. This repository
does not perform that copy automatically.
