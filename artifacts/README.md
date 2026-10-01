# KasugaBus local deliverables

The final tested app is [KasugaBus-1.0.0-emery.pbw](KasugaBus-1.0.0-emery.pbw)
(817,565 bytes), SHA-256
`2bddb0b092d51c7cdab6944c56a11bb377f4a97932643ee37541450bfc8bdb09`.
It includes the selected Neon Express bus icon and is installed on the owner's
Time 2 v4.38.4. The owner confirmed the identical icon on the preceding package. It remains
unpublished and is not approved for release. [SHA256SUMS](SHA256SUMS) also
identifies the dataset, compiled baseline, audits and archived pre-icon PBW.

All [ten icon images](icon-options/index.html), original prompts and the
[selected final asset](icon-options/selected/README.md) are preserved.

Final-artifact evidence:

- [Verification report](../docs/VERIFICATION.md), with PRD coverage and open
  physical/production release checks.
- [Clean build and 113 Python tests](final-workflow-build.log),
  [sealed audit](final-workflow-build-audit.json),
  [native runtime](runtime-workflow-acceptance.log) and
  [exact installation receipt](runtime-workflow-acceptance.log.install.json).
- [Current28/future29/interrupted update](native-update-workflow-acceptance.log)
  without reinstalling, and [launch/button timing](native-profile-workflow-acceptance.json).
- [Native screenshots](screenshots/README.md), including Home, board, details
  and selected/unselected launcher rows.
- [Latest physical installation](physical-workflow-installation.json), which
  is installation evidence, not repeated user QA.
- [Initial listing preview](../docs/releases/listing-preview.html),
  [release procedure](../docs/releasing.md), and authenticated read-only
  [store discovery](store-discovery-final.json): no matching KasugaBus listing.

The owner-confirmed [Neon Express package](KasugaBus-1.0.0-emery-neon-installed.pbw)
remains archived as `4679b90e…`, with its [audit](final-neon-build-audit.json),
[runtime](runtime-neon-acceptance.log), [update checks](native-update-neon-acceptance.log)
and [physical icon confirmation](physical-neon-installation.json).
[Build comparison](workflow-build-comparison.json) shows unchanged application
code, JavaScript and resources; only build metadata/checksum/ZIP timestamps
changed in the final rebuild. Earlier listing captures retain their
[own evidence](store-listing/neon-assets-evidence.json).

Earlier broad acceptance is preserved with its own
[PBW](KasugaBus-1.0.0-emery-before-icon.pbw), SHA-256
`466df8dd233cb2886171eb44fe23f1188fd1b3f68bc1d872249be3262a8dff5b`,
[audit](acceptance-build-audit.json), [build log](final-build-acceptance.log),
[runtime](runtime-acceptance.log), [receipt](runtime-acceptance.log.install.json),
[navigation](native-navigation-acceptance.log),
[offline rollover retry](native-rollover-acceptance-retry.log),
[Restore cancellation](native-restore-acceptance.log),
[actual cancellation markers](native-postreset-acceptance.log), and
[physical navigation confirmation](physical-verification.json).
The [binary comparison](neon-build-comparison.json) establishes identical
native code after the metadata header and identical phone JavaScript.

Other runtime/native logs are retained development history. The initial
`native-rollover-acceptance.log` and `native-update-neon-final*.log` are failed
firmware-stall attempts, not acceptance passes. Diagnostic screenshots are
labelled accordingly. Do not mix artifact digests, timings or physical claims.
`diagnostic-workflow-clean-noop.log` records the SDK clean failure that exposed
stale output. The generated-output cleanup fix and fresh build passed afterward.
