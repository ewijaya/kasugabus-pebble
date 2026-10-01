# Implementation milestones

Status recorded on 2026-10-01:

1. Platform foundation verified locally. Storage uses two 208-byte KBD2 directory banks and two 108-byte KBW2 control banks, with legacy compatibility, full payload validation and four ordinary startup metadata reads. The durable CHECK/Restore counter adds no launch write. The final rebuilt PBW passed the clean build/static audit and fresh native timing samples: three launches within 637.32 ms and twelve buttons within 83.76 ms.
2. Validated data and offline engine implemented. The reviewed baseline covers six stop groups, 15 boarding points and 1,411 departures, with operator/direction/route provenance and deterministic JST/calendar selection. Six Hankyu poles have verified coordinates; nine Kintetsu points remain unranked. Source review is due 2026-11-01 and covered service dates end 2026-12-27.
3. Watch and phone integration implemented. Time and Bus, board/details/stops/settings/data status, transactional preferences, one-shot Nearby and validated current/future updates are present. GitHub Pages is selected and configured locally; its prepared feed is not deployed or verified live.
4. The user-selected Neon Express 25×25 transparent dark-bus `MENU_ICON` remains integrated. Fresh rebuilt-PBW acceptance covers host suites, launch/navigation, current/future transfers without reinstall, interrupted/corrupt/incompatible recovery and restart. Fresh native captures show Home, board and details. The rebuilt PBW was physically installed; owner icon confirmation remains tied to the preceding installed Neon package, with no new physical QA claimed.
5. Release tooling now includes durable first-registration intent/App ID, matching-listing adoption, resumable subsequent releases and clean-output recovery. These flows passed isolated tests; actual registration, production publication and broader physical field checks remain open.

The lead owns storage/UI, final native verification and handoff. Assigned agents maintain data validation, the portable engine/codec, and phone/settings/updater/publishing within separate file scopes.

The **1.0.0** candidate is **817,565 bytes**, SHA-256 `2bddb0b092d51c7cdab6944c56a11bb377f4a97932643ee37541450bfc8bdb09`. [Platform evidence](PLATFORM.md) links its sealed native receipt, profile, build and update logs. The [final workflow audit](../artifacts/final-workflow-build-audit.json) records passing launch/navigation/update-transfer checks and 32,400-byte minimum free heap. Build checks passed: 113 Python tests, including 31 release, 32 registration and two cleanup tests, plus 25 phone scenarios, five settings scenarios, five HTTP scenarios and strict C checks. Fresh native updates retained current/future revisions 28/29 after restart, a two-chunk interrupted replacement and rejected corrupt/incompatible/interrupted-HTTP inputs.

The pre-icon `466df8dd…` PBW retains its 29-scenario native suite, including offline future activation, expiry/override cases, preferences and Restore rejecting obsolete requests across restart. Those additional scenarios were not rerun against the new digest. Its [physical verification](../artifacts/physical-verification.json) records readable Home → board → details and Select navigation on PT2 **4.38.4**, Poco F4 **Android 14 build UKQ1.231207.002**, companion **1.14.0.1**. The [installed Neon archive](../artifacts/KasugaBus-1.0.0-emery-neon-installed.pbw), `4679b90e…`, retains the owner's [icon visibility/highlighting confirmation](../artifacts/physical-neon-installation.json). [The workflow comparison](../artifacts/workflow-build-comparison.json) shows identical application code, phone JavaScript and resources; only build metadata/checksum/timestamps changed. [Fresh physical installation](../artifacts/physical-workflow-installation.json) confirms the rebuilt package was installed, without new owner QA or publication approval. Actual GPS, physical settings/recovery/battery behavior, outdoor/glance readability and seven-day use remain unverified. The historical [firmware installation stall](../artifacts/emulator-install-stall-diagnosis.md) occurred before KasugaBus started.

Pages/GitHub remain unpublished. The local project has no initialized Git repository, the intended remote cannot be viewed with current authentication, and [authenticated discovery](../artifacts/store-discovery-final.json) still found no KasugaBus listing. No version bump, commit, registration or publication occurred. All ten original icon concepts and their [gallery](../artifacts/icon-options/index.html) are retained.

Initial state: only user-authored PRD.md and PLAN.md; no Git repository or AGENTS.md. Original PLAN text is preserved, with implementation status appended separately.

## Initial-publication scope accepted

The owner authorized an initial 1.0.0 release with the unperformed physical
and seven-day checks stated as limitations. GitHub source and the dedicated
Pages v2 feed are live, and the owner confirmed a real Poco F4 / Time 2
timetable-only update to v2. See docs/VERIFICATION.md for the exact preceding
PBW and evidence. Final build/freeze, exact physical/listing approval and
publication are the remaining initial-release steps; the full personal-use
milestone is not declared complete.
