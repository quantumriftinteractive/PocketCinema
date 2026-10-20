# PocketCinema published release records

This is the authoritative index of immutable published version records. Linear
owns current priorities; PROJECT_STATE owns the repository handoff. Consolidation
results supplement these records without rewriting their original test limits.

| Component | Published version | Exact source |
| --- | --- | --- |
| Miyoo client | v1.0.1, CONDITIONAL GO, 2026-10-20 | lightweight tag v1.0.1 → 88ac551177999165caf45ab40251490061f101b2 |
| Windows x64 / macOS arm64 PCServer | v1.0.0, unchanged | annotated tag v1.0.0 → b22ce164d38a33db6f27308b21331d70501a2aae |

## Miyoo client v1.0.1

- [Published release](https://github.com/quantumriftinteractive/PocketCinema/releases/tag/v1.0.1)
- [Release notes](RELEASE_NOTES-v1.0.1.md)
- [30-file manifest](PocketCinema-Miyoo-v1.0.1-manifest.json)
- [Exact package checksum](../../SHA256SUMS-v1.0.1.txt)

ZIP SHA-256:
`3ca28149174d8c03f6358ca17845a93fbe05e1207611b6730ffd60e9e532a1b6`.

The manifest identifies the original maintenance candidate
`137c12602ff6b4e5d445fddf3abf53bed61cf2c1`. Its released UI is byte-identical to
the public tag, but the maintenance branch also contains tests and investigation
history absent from the public snapshot. Preserve both ancestries.

OnionOS 4.3.1-1 video/audio, display handoff and normal Menu exit are physically
confirmed. The release was accepted with full unrestricted host regression,
OnionOS 4.4 beta acceptance, and retained candidate post-playback process/log
evidence outstanding. Later local host results are recorded in
[consolidation evidence](../repository-consolidation-2026-10-20.md); they do not
rewrite the publication record or constitute beta physical acceptance.

This is a client release only. PCServer remains v1.0.0. macOS account-link HTTP
502 remains unresolved; no server diagnostic candidate or fix is claimed shipped.
Player, libraries, helpers, fonts and the 64-item selector retain v1.0.0 assets.

## v1.0.0 platform release

- [Published release](https://github.com/quantumriftinteractive/PocketCinema/releases/tag/v1.0.0)
- [Original release notes](../../RELEASE_NOTES.md)
- [Exact platform/source checksums](../../SHA256SUMS-v1.0.0.txt)
- [Miyoo corresponding-source and provenance records](../../release-sources/miyoo/)

The annotated tag object is `d4e51d5e567c6fd707f26a13b2d19aef6f4de405`;
its peeled commit is `b22ce164d38a33db6f27308b21331d70501a2aae`.
Local, Gitea and GitHub values matched during consolidation. Existing signing
and provenance limitations remain documented; release completion does not mean
Developer ID signing, notarization, or new independent-reproduction acceptance.
