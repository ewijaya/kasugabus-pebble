# GitHub Pages timetable hosting

The owner-selected dedicated GitHub Pages site is **LIVE** at
`https://ewijaya.github.io/kasugabus-pebble/timetables/manifest.json`.
The first reviewed v1 feed was deployed on 1 October 2026 by
[workflow 36827444799](https://github.com/ewijaya/kasugabus-pebble/actions/runs/36827444799).
The source repository is public, Pages uses the Actions build type with HTTPS,
and the `github-pages` environment permits only branch `main`. No additional
manual reviewer gate was added; deployment itself was explicitly authorized.

[Live HTTP evidence](../artifacts/hosting-v1-http.json) and
[preservation validation](../artifacts/hosting-v1-live-validation.json) confirm
HTTP 200, no redirects, exact SHA-256/CRC/length, JSON/binary MIME types and
`Access-Control-Allow-Origin: *`. Pages supplies `Cache-Control: max-age=600`
for both manifest and payloads. The generic desired header rules are not applied
by Pages; ten-minute caching is accepted for this daily/manual schedule feed,
and may delay visibility of a newly published revision. Payload filenames are
immutable and all prior files remain available. Actual companion transfer and
phone CORS behavior are separate checks.

## What the manual workflow does

`.github/workflows/timetables.yml` has only `workflow_dispatch`. Its default
`publish=false` validates an already prepared `hosting/public` and uploads a
seven-day Pages artifact for inspection. It does not prepare timetables, approve
reconciliation, upload app builds, or deploy PR/push/scheduled artifacts.
Dispatches are restricted to `ewijaya/kasugabus-pebble` on its default branch.
Actions are pinned to the official commit IDs checked on 2026-10-01.

The artifact contains exactly:

```text
index.html
timetables/manifest.json
timetables/inventory.json
timetables/releases/<version>-<sha256-prefix>.bin  # every retained payload
```

The basic index links to the manifest. Review reports, editable source inputs,
operator PDFs, phone settings, app packages, local files and personal information
are excluded by the staging allowlist. Only reviewed timetable binaries carry
stop-pole coordinates. Staging checks the manifest and payload hashes again so
changes after validation fail the run. The artifact uses the static Pages
deployment path; no Jekyll build or `.nojekyll` file is needed. GitHub documents
the artifact format and required Pages job permissions in its
[custom workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

This must be a **dedicated KasugaBus project Pages site**. Deployment publishes
the whole artifact at the project site root; unrelated existing site content
would be replaced. A missing `/timetables/manifest.json` and `/inventory.json`
does not prove that the site root is empty. Before the first deployment, the
owner must inspect the existing site and confirm that it is dedicated to this
feed. The manual first-feed input
`initialize_dedicated_site=true` records that specific confirmation; it is
false by default and is required when both timetable paths return 404.

## Local review and preservation checks

Prepare reviewed immutable files using `tools/publish_feed.py` as described in
the publishing procedure. The local files use the selected Pages URL. The
workflow deliberately fails when `hosting/public` is
missing or incomplete; it never fabricates a publishable feed.

Run the read-only hosting validator and its tests:

```sh
python3 -m unittest discover -s tests -p test_hosting.py
python3 tools/validate_hosting.py hosting/public \
  --base-url https://ewijaya.github.io/kasugabus-pebble/timetables \
  --source data/timetable.json \
  --source-directory hosting/sources
```

Current and upcoming payloads must match their exact `sourceSha256` review report
and the compiler's bytes for that exact JSON input. Compilation is in memory for
comparison; it does not rewrite payloads, manifests or reports. The validator
uses the shipped phone manifest and full binary parsers, the same 8,192-byte
manifest/32,768-byte payload limits, actual JST validation date, filename/version
checks, review dates and departure counts. It emits JSON review evidence on
stdout and changes no feed files. It does not recheck official operator sources
or turn an unreviewed input into an approved release.

Archive the exact JSON input for each retained version under
`hosting/sources/<version>.json`, including any upcoming input not stored in
`data/timetable.json`. Those archives remain outside the Pages artifact. This
lets a default validation run prove all historical payloads locally. If an old
source is unavailable, publication-mode validation may accept that historical
payload only when the existing controlled live inventory pins its exact path,
length and full SHA-256; active current/upcoming releases always need their
source inputs. An archived source or an established live pin is required on
the first deployment too.

For a previously deployed site, add `--check-live`. This performs bounded HTTPS
GETs to the exact manifest/inventory URLs, forbids redirects, and fails on
network errors or one missing file. It never uploads anything. Both files being
404 requires the separate `--allow-first-deployment` confirmation. The live-host check is now recorded above; isolated regression tests still use
mocked reads.

Every prior inventory entry must remain present with unchanged bytes in the
next artifact. The guard rejects effective-date/version downgrades, publication
date downgrades and removal of a still-pending release. A pending correction
needs a higher version at the same activation date: existing watches retain
staged releases, so changing that date cannot safely cancel them through the
current protocol. After a pending release becomes effective, the current entry
must preserve or advance its activation-date/version priority.

Keep all historical payloads and local review reports when preparing the next
feed. For hosts that upload files separately, upload immutable files and the
inventory first and the manifest last, as the publisher describes. Pages uses
a complete site artifact instead: **all retained payloads, the inventory and
the manifest must travel together**. The workflow checks live preservation
before packaging and again after deployment-environment approval. Do not make
an unrelated Pages deployment outside this workflow; doing so can discard its
history guard or overwrite the site.

## Deployment steps

1. Confirm that the repository has a suitable GitHub plan and that the selected
   project Pages site is dedicated to KasugaBus. Public repositories support
   Pages on GitHub Free; private repositories need a supporting paid plan.
   Project sites use the repository path in their default URL.
   [GitHub Pages overview](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
2. Review the default-branch files and candidate public artifact. In repository
   **Settings → Pages**, select **GitHub Actions** as the publishing source.
   Configure the `github-pages` environment to allow only the default branch
   and, when the repository plan supports it, require the owner's review.
   Local configuration has not changed those settings. The deployment job requests
   `pages: write` and `id-token: write`; the validation job has only
   `contents: read`. The configuration action uses `enablement=false`, so it
   cannot create a Pages site automatically.
   [GitHub custom workflow setup](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
3. Check the existing site configuration with the read-only API command below.
   It should report the expected project URL, workflow build type, and no custom
   domain. An administrator can configure a site's `build_type` as `workflow`
   through the Pages API, but that is a separate owner action. The provided
   workflow rejects a different Pages base URL.
   [GitHub Pages REST API](https://docs.github.com/en/rest/pages/pages)

   ```sh
   gh api repos/ewijaya/kasugabus-pebble/pages
   ```

4. Run **Review or publish timetable feed** on the default branch with
   `publish=false`; inspect the `github-pages` artifact. Then, after owner
   approval, run with `publish=true`. Set `initialize_dedicated_site=true` only
   for an approved first feed. Satisfy the environment protection rules. The
   workflow is serialized and never cancels an in-progress deployment.
5. Verify the live HTTP responses before releasing the configured app:
   exact HTTPS URLs with no redirects, HTTP 200, binary length/SHA-256/CRC and
   content types, manifest validation, CORS behavior on the actual companion,
   and cache behavior. `hosting/headers.json` records desired vendor-neutral
   headers; this Pages workflow does **not** apply that file. Pages headers
   must be measured on the actual deployed host and differences recorded.
   Confirm acceptable caching and cross-origin behavior before using this host.
6. Both local feed configurations now contain the selected manifest URL. After
   the live checks, build/test the app and exercise its updater against the
   deployed feed before releasing it. This endpoint change needs a new PBW;
   subsequent timetable-only releases use the same trusted HTTPS origin.

The selected manifest is live at
`https://ewijaya.github.io/kasugabus-pebble/timetables/manifest.json`.

## Local review evidence

On 2026-10-01, all 21 hosting tests passed. They cover exact reviewed-source
binding, full parsing of historical payloads, manifest size limits, missing or
changed history, effective-date priority, pending activation preservation,
redirect/network failures, explicit first-feed approval and artifact exclusions.
The workflow also parsed as YAML with manual-only triggers, both inputs false
by default, restricted token permissions and the named `github-pages`
deployment environment. Repository protection rules remain an owner setup step.

The actual local candidate validated as current v1 with no upcoming release and
an exact reviewed-source proof. Its immutable payload is
`releases/1-cb75a4f850d74c45.bin`, 24,203 bytes, SHA-256
`cb75a4f850d74c45db26f62f569737e0d9346b4817ba502777608ff7a5ed56b8`.
Running the workflow's staging code locally produced exactly the four expected
files: index, manifest, inventory and that payload, with an unchanged manifest
and no symlinks or hard links. Review reports remained outside the artifact.

Those original setup checks used local files and mocked remote reads. The
subsequent authorized live deployment and HTTP checks are recorded above.
Live response headers, Pages permissions and the actual phone's cross-origin
behavior remain checks for an owner-approved deployment.
