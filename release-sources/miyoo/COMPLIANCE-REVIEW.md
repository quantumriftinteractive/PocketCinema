# Miyoo v1 final compliance sufficiency review

Reviewed 2026-09-09 against the preserved runtime, source metadata, external archive,
and official license guidance. This is a compliance sufficiency assessment, not
legal advice and not a reproduction approval.

## Result

Redistribution is **compliance classification B**: the evidence is sufficient once
the clearly identified public notices and corresponding-source bundle are assembled
and the final artifact audit confirms the measured dynamic-link arrangement. The
SDK's historical provenance remains C, but that is a reproducibility limitation.
The unknown Tokotype export/build path is a provenance limitation only for the exact,
unmodified font bytes.

FFmpeg's official guidance asks distributors to provide the exact corresponding
source, changes, build/configuration explanation, applicable license text, and the
same source alongside the binary distribution. The preserved FFmpeg 2.4.14 archive,
PocketCinema final patch, configure command, licenses, dependency source archives,
package patches, and hashes satisfy that source-identification basis. FFmpeg is
LGPL only when the preserved configuration did not enable GPL/nonfree components;
the release audit must record that check.

The recovered FFplay ELF records the shipped SDL, FreeType, libass, bzip2, and zlib
libraries as `DT_NEEDED` shared objects. This supports the LGPL dynamic-link route:
ship the corresponding modified library sources and license texts, and preserve a
way for users to replace compatible shared libraries. If final packaging discovers
static linkage or a combined work for any LGPL library, add the application object
files and relink instructions required by LGPL 2.1 before release.

## Dependency sufficiency

| Family | License basis | Archived evidence | Remaining release item |
| --- | --- | --- | --- |
| SDL, libass, FriBidi, GLib | LGPL-2.1+ | Exact source archive, Buildroot patches, license text | Notices; dynamic replacement audit |
| FreeType | FTL/GPL-2.0+ dual | Exact source and FTL/GPL texts | Record selected license/use in notices |
| tslib | LGPL-2.1+ library; GPL programs | Exact source and COPYING | Ship library notice; exclude unrelated GPL tools |
| bzip2, zlib, Fontconfig, HarfBuzz, PCRE, Expat, libpng, libffi, libuuid | Permissive/project licenses | Exact source and declared license files | Consolidated notices and attribution |

The package-level A classification establishes exact Buildroot source inputs and
patches. It does not claim those patches were applied by the recovered SDK. That
historical uncertainty does not by itself create a source-distribution obligation.

## Font

The distributed TTF is byte-identical to the identified Stremio Web Git blob and
retains its copyright and OFL 1.1 metadata. It was not modified by PocketCinema.
The OFL requires retaining copyright/license information; the official FAQ states
that Reserved Font Names are not automatic under OFL 1.1 and that a wrapper or
unchanged font does not require a name change. No font source or Tokotype export
pipeline is required to redistribute these exact unmodified bytes. Ship the OFL
text and attribution. The unresolved upstream build/export chain is provenance-only.

## Smallest public compliance bundle

Ship with the Miyoo package:

- `THIRD_PARTY_NOTICES` naming FFmpeg, each bundled library, and Plus Jakarta Sans;
- complete applicable license texts and font attribution/OFL text;
- a source-manifest/hash file and a URL or local pointer to corresponding sources;
- the FFmpeg configure/build instructions and PocketCinema patch identity;
- explicit dynamic-link/replacement instructions and reverse-engineering permission.

Provide separately as the corresponding-source archive:

- exact FFmpeg 2.4.14 source plus final patch;
- the 15 exact dependency archives, 19 Buildroot patches, and package metadata;
- source hashes and provenance notes.

The 1.09 GB archival directory, compiler archive, SDK tarball, recovered FFplay,
raw staging trees, and selector artifacts do not need to ship in the user-facing
runtime package. The compiler/SDK are retained for the independent reproduction
gate and archival backup.

## Gates

Remaining before public redistribution: assemble/review the notices and source
archive, verify the final package's dynamic dependencies and FFmpeg GPL/nonfree
configuration, confirm source links/hashes, and complete the existing artifact and
fresh-install acceptance gates. No FFplay rebuild or Miyoo deployment is implied.

Authoritative references: [FFmpeg legal guidance](https://ffmpeg.org/legal.html),
[LGPL 2.1](https://www.gnu.org/licenses/lgpl-2.1.html),
[official OFL 1.1 text](https://openfontlicense.org/open-font-license-official-text/),
and [OFL FAQ](https://openfontlicense.org/ofl-faq/).
