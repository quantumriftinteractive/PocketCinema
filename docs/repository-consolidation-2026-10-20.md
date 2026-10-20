# Repository consolidation evidence — 2026-10-20

Scope: user-authorized local history preservation and reconciliation. No feature
implementation, deployment, release, remote write, history rewrite, deletion,
worktree removal, selector rebuild or account-link candidate integration.

## Baseline and preserved history

Canonical repository: `/Users/jdragocy/Quantum Rift Interactive/Projects/MM--PocketStremio`.
Gitea origin remains development authority; GitHub remains publication destination.
Both remote main tips were 2278e25776b0716c33921e19dd85585d454a4619 at audit.
Local main matched them. Two dirty tracked files and 37 untracked files were
individually inventoried and hashed before mutation. All original untracked file
bytes and local recovery backups are retained; generated release folders and the
duplicate hero copy are now precisely ignored, not deleted.

| Preservation | Commit / ref |
| --- | --- |
| Original 64→128 selector experiment only | 0b74301, feature/selector-128 |
| Original PROJECT_STATE metadata edits | bd278b2 |
| Four unique Reddit PNGs | 9c5b140 |
| Original maintenance history | 08fcb7a → c544e2b → 137c126 |
| Maintenance merge | e584acc |
| Exact public release history | 88ac551177999165caf45ab40251490061f101b2, v1.0.1 |
| Public release merge | 860d9ff |
| Documentation/workflow reconciliation | 0f7a48007cc857c34e802a7c8b6d6de2168bc678 |

The source-only selector preservation is an explicit QRI-28 historical exception.
It has no rebuilt matching binary and remains Experimental, unshipped and outside
main. Main source is MAX_ITEMS=64 and its ARM binary matches the accepted baseline.

The public release tag is lightweight and was fetched by its exact ref, not
recreated. v1.0.0 annotated tag and both version checksum files are unchanged.
The published v1.0.1 UI is identical to maintenance 137c126. Its ZIP checksum is
`3ca28149174d8c03f6358ca17845a93fbe05e1207611b6730ffd60e9e532a1b6`;
CRC and all 30 entry hashes, sizes and Unix modes were independently verified.
The local v1.0.0 distribution matches 29/30 entries; only its old UI differs.
Both retained transfer ZIPs match the committed v1.0.0 checksums.

Maintenance includes only one server runtime difference from released v1.0.0:
clarified startup addon-count log text. It is development source, not a new server
package. PCServer account/link behavior is unchanged.

## Account-link candidate recovery

Linear QRI-76 records `/tmp/pocketcinema-account-link-v101`, branch
`investigation/account-link-diagnostics-v101`, and 101 passing source tests.
Neither that path, its /private/tmp equivalent, nor the branch exists here.
Checks covered registered worktrees, local/remote refs, all reflogs, unreachable
commits, bounded project/tmp Git locations, normal Codex worktree locations, and
scoped existing session evidence. Session search found only the current audit
conversation; no candidate patch/source was recovered. Recovery could still be
possible in the originating environment or backups; absence here is not proof
of permanent deletion.

Six unreachable commits were inspected at initial audit. None was the diagnostic
candidate. The historical stash-shaped bafca836 and its parents preserve old
selector/distribution copies; 782e43c and 499cfac are historical feature/checkpoint
commits. A verified local recovery pack preserves these and public 88ac551
without integrating them. No diagnostic branch was fabricated. QRI-76 remains
unresolved, and no diagnostic code was merged.

## Regression impact

| Area | Classification | Verification | Inherited evidence / reason |
| --- | --- | --- | --- |
| Published UI | Identical to released v1.0.1 | Blob equality, existing lifecycle/selection tests, shell checks | 4.3.1-1 physical release observation; no new UI change |
| Server runtime | Startup log wording only from maintenance | Existing server/API/Range suite | Playback/account evidence unchanged; no diagnostic candidate |
| Server tests | Additional maintenance tests, executable fixture | Full existing host suite | No new product semantics |
| Selector main source/binary | Unchanged at 64 | Exact baseline comparisons; experiment ancestry exclusion | Historical device acceptance inherited; no build/physical test needed |
| Artwork and docs | Source preservation and state reconciliation | Hash/content review, links, diff checks | No device/runtime behavior change |
| Release/runtime artifacts | Unchanged | ZIP/manifest/hash/mode checks | Existing player/subtitle/desktop evidence inherited |

## Verification results

- Full existing host suite: **208 tests run in 63.233 seconds, OK (6 skipped)**.
  All 202 executed tests passed; six skips are native Windows-only checks.
  Executed all eleven server.test_* modules by explicit module name on Python
  3.14. This unrestricted local run used real child processes and socket binds.
- Existing server tests exercised /api/status, search, metadata, streams, opaque
  play-session creation and 206 byte-range media responses on ephemeral local
  alternate ports, including the complete offline episode flow.
- All seven scripts/test-miyoo-*.sh checks passed, including renderer runtime,
  subtitle size, Matroska, connection, proxy and library-state checks.
- Server compilation, changed UI shell parsing and diff whitespace checks passed.
  No PowerShell, selector source/binary or runtime assets changed on main.
- Release UI/tag/checksum identity, selector exclusion and original retained file
  hash checks passed. New local documentation links were checked for existence.

This supplies current local host regression evidence for QRI-75; no Linear status
was changed and the published validation record remains immutable. Native Windows
checks, OnionOS 4.4 beta and post-playback physical process/log evidence are not
claimed. No new physical matrix was requested for consolidation.

Raw audit/test logs and recovery copies remain ignored under
`.tmp/consolidation-audit-2026-10-20/`; they must not enter source commits.

## Publication and cleanup boundary

No remote writes are authorized. Required reviewed development refs for later
publication: main, feature/selector-128, maintenance/v1.0.1-stream-diagnostics,
and the exact v1.0.1 tag. The temporary chore/repository-consolidation ref may also
be published as a review/recovery pointer; its commits are retained through main.
No account-link ref exists to publish. v1.0.0 already matches both remotes.

Obtain explicit remote authorization before publication, then fetch and verify
all required tips/tag and update the checkpoint. GitHub main/tag synchronization
requires separately specified approval. Retain the existing maintenance worktree,
all original artifacts and recovery files until independent verification and
separate cleanup authorization. Local-only consolidation is not a cross-machine
handoff.
