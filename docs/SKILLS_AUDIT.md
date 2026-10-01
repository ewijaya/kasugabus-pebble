# Project skill audit — 1 October 2026

All four project skills have valid front matter, matching skill/folder names,
working local references and matching `$skill` names in their agent prompts.
The release helpers use KasugaBus's configured UUID, existing RePebble App ID,
Emery target and `ewijaya/kasugabus-pebble` repository.

| Skill | Maintained purpose |
| --- | --- |
| `kasugabus-publish-release` | Coordinates the full release and acceptance review |
| `kasugabus-release` | Plans, freezes, publishes or verifies an exact candidate |
| `kasugabus-appstore` | Maintains the existing listing, with first-registration recovery retained |
| `kasugabus-build-audit` | Tests/builds and binds measured runtime evidence to the PBW |

Read-only `release.py plan --remote --destination github` identifies the
existing v1.0.0 release and saved store listing. The published v1.0.0 candidate
also passed a fresh bounded remote verification during this audit. No new
release was published as part of the audit.

Two future-retry defects were fixed and reviewed:

- Store preservation now saves the original metadata and prior-release
  history before mutation. A retry cannot quietly accept remote damage as a
  new baseline. A failed journal write prevents the upload.
- The installed SDK uploader is wrapped at its HTTP transport boundary so
  authenticated uploads reject redirects. The adapter passes the exact frozen
  PBW and does not modify the installed toolchain.

Focused checks passed: **46 release tests and 32 registration tests**. This
includes the actual installed Pebble uploader with a mocked HTTP transport,
checking all common redirect statuses, a successful response and unchanged
PBW bytes. No live mutation is performed by those tests. The consolidated
suite passed **137 Python tests**, **30 phone scenarios**, **8 Clay checks**,
**5 real-HTTP feed scenarios**, and the portable C suites at this stage.

The toolchain was rechecked locally: Pebble Tool 5.0.40, SDK 4.33.1, Python
3.13.5, Node 26.8.1 and npm 11.19.0. Installed dependencies were reused.
The release workflow still requires a physical installation and approval of
each new PBW; 1.0.0 approval does not approve 2.0.0. Optional artwork changes
have a separate reviewed, hash-bound Dashboard procedure. Future service/API
changes still require checking the installed CLI and official Dashboard
contract, rather than assuming these checks guarantee compatibility forever.

For a future release, use:

> Use $kasugabus-publish-release to prepare and release KasugaBus everywhere.
> Review changes since the previous tag and choose the appropriate version.
> Install one frozen candidate for my physical approval, then publish those
> exact bytes to GitHub and the existing RePebble listing and verify all
> publication surfaces.
