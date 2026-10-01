# Implementation milestones

Status recorded on 2026-10-01, after initial publication:

1. Platform foundation verified locally. Storage uses two 208-byte KBD2 directory banks and two 108-byte KBW2 control banks, with legacy compatibility, full payload validation and four ordinary startup metadata reads. The durable CHECK/Restore counter adds no launch write. The published PBW passed its clean build/static and native runtime audits. Earlier development timing on `2bddb0b0…` measured three launches within 637.32 ms and twelve buttons within 83.76 ms; those timing samples were not repeated on the release digest.
2. Validated data and offline engine implemented. The reviewed baseline covers six stop groups, 15 boarding points and 1,411 departures, with operator/direction/route provenance and deterministic JST/calendar selection. Six Hankyu poles have verified coordinates; nine Kintetsu points remain unranked. Source review is due 2026-11-01 and covered service dates end 2026-12-27.
3. Watch and phone integration implemented. Time and Bus, board/details/stops/settings/data status, transactional preferences, one-shot Nearby and validated current/future updates are present. The dedicated GitHub Pages HTTPS feed is live at current v2; the exact release worker completed a native timetable-only v2 update without PBW reinstall, with 127 acknowledged chunks and persistence across restart.
4. The user-selected Neon Express 25×25 transparent dark-bus `MENU_ICON` remains integrated. Published-candidate acceptance covers host suites, native launch/navigation and production v2 transfer/restart. Earlier development runs cover controlled current/future transfers and interrupted/corrupt/incompatible recovery. Release-native captures show Home, board and details. The published PBW was physically installed and approved; owner icon visibility confirmation remains tied to the preceding installed Neon package.
5. Release tooling now includes durable first-registration intent/App ID, matching-listing adoption, resumable subsequent releases and clean-output recovery. These flows passed isolated tests. The owner approved the installed candidate and listing, then the same PBW was registered and published to GitHub and RePebble. Broader physical and seven-day field checks remain open under the accepted initial-release scope.

The lead owns storage/UI, final native verification and handoff. Assigned agents maintain data validation, the portable engine/codec, and phone/settings/updater/publishing within separate file scopes.

## Published initial artifact

Version **1.0.0** is **817,922 bytes**, SHA-256 `233627ffc63e0964bff272c3a56bac11e6f7634992b06cb45143524e2bc5330a`, from source `3110dee` and tag `v1.0.0`. It is available from [GitHub Releases](https://github.com/ewijaya/kasugabus-pebble/releases/tag/v1.0.0) and [RePebble](https://apps.repebble.com/f63e6ed24301414a95909564), App ID `f63e6ed24301414a95909564`. The owner explicitly approved the installed candidate and listing before publication. Both downloads match the frozen digest.

[Publication verification](../artifacts/releases/1.0.0/publication.json) passed for GitHub
(including the downloaded PBW and latest release), Dashboard, the general and
Emery-filtered catalogs, and the canonical public store page/changelog. The
phone's My Apps cache was not observed; the Emery catalog is a proxy for it.

The [release build audit](../artifacts/releases/1.0.0/build-audit.json) and [build log](../artifacts/releases/1.0.0/build.log) record **122 Python tests**, the phone/Clay/controlled-feed suites and strict C checks. The release has 31,428 native bytes, 39,170 static RAM bytes, 30,178 resource bytes and **32,400 bytes** minimum observed free heap. The [real SDK HTTPS transfer proof](../artifacts/releases/1.0.0/production-feed.json) records **127 native chunk acknowledgements**, active v2 and success-timestamp persistence, unchanged preferences and no PBW reinstall. These are emulator observations; broader physical field acceptance remains separate.

## Earlier development acceptance

The preceding **1.0.0 development PBW** is **817,565 bytes**, SHA-256 `2bddb0b092d51c7cdab6944c56a11bb377f4a97932643ee37541450bfc8bdb09`. [Platform evidence](PLATFORM.md) links its sealed native receipt, profile, build and update logs. The [final workflow audit](../artifacts/final-workflow-build-audit.json) records passing launch/navigation/update-transfer checks and 32,400-byte minimum free heap. Build checks passed: 113 Python tests, including 31 release, 32 registration and two cleanup tests, plus 25 phone scenarios, five settings scenarios, five HTTP scenarios and strict C checks. Fresh native updates retained current/future revisions 28/29 after restart, a two-chunk interrupted replacement and rejected corrupt/incompatible/interrupted-HTTP inputs.

The pre-icon `466df8dd…` PBW retains its 29-scenario native suite, including offline future activation, expiry/override cases, preferences and Restore rejecting obsolete requests across restart. Those additional scenarios were not rerun against the new digest. Its [physical verification](../artifacts/physical-verification.json) records readable Home → board → details and Select navigation on PT2 **4.38.4**, Poco F4 **Android 14 build UKQ1.231207.002**, companion **1.14.0.1**. The [local installed Neon archive](../artifacts/KasugaBus-1.0.0-emery-neon-installed.pbw), `4679b90e…`, retains the owner's [icon visibility/highlighting confirmation](../artifacts/physical-neon-installation.json). [The workflow comparison](../artifacts/workflow-build-comparison.json) describes those preceding development packages: identical application code, phone JavaScript and resources, with build metadata/checksum/timestamps changed. The published candidate adds the later phone-side XHR correction; this older comparison does not describe it. [The earlier physical installation](../artifacts/physical-workflow-installation.json) confirms that development package was installed, without new owner QA or publication approval at that stage. Actual GPS, physical settings/recovery/battery behavior, outdoor/glance readability and seven-day use remain unverified. The historical [firmware installation stall](../artifacts/emulator-install-stall-diagnosis.md) occurred before KasugaBus started.

At workflow setup, Git/source/feed publication and registration had not occurred; [the retained discovery](../artifacts/store-discovery-final.json) found no KasugaBus listing then. Subsequent authorized source publication, Pages deployment and initial app publication are recorded above. All ten original icon concepts and their [gallery](../artifacts/icon-options/index.html) remain retained.

Initial state: only user-authored PRD.md and PLAN.md; no Git repository or AGENTS.md. Original PLAN text is preserved, with implementation status appended separately.

## Initial-publication scope accepted

The owner authorized an initial 1.0.0 release with the unperformed physical
and seven-day checks stated as limitations. GitHub source and the dedicated
Pages v2 feed are live, and the owner confirmed a real Poco F4 / Time 2
timetable-only update to v2. See docs/VERIFICATION.md for the exact preceding
PBW and evidence. The release was then built, frozen, installed and explicitly approved with its
listing before publication. The full personal-use milestone is not declared
complete; physical GPS/settings/recovery, outdoor/glance readability, battery
and seven-day use remain outstanding.
