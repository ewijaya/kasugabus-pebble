#!/usr/bin/env python3
"""Read-only remote verification of the owner-approved 2.0.0 exception.

Use the installed Pebble Tool Python for existing Dashboard authentication.
This never builds, uploads, modifies metadata or waives a future release gate.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import release

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempts', type=int, default=3, choices=range(1, 4))
    args = parser.parse_args()
    state = json.loads(Path(__file__).with_name('publication.json').read_text())
    release.require(state['version'] == '2.0.0' and state['artifact'] == {
        'sha256': 'fb578a00327aa1a3469ebcb6eede5b7738ffb9d19c7ec3d3e4bbaa9e2548fb8b',
        'bytes': 871207}, 'This verifier is limited to the published 2.0.0 artifact')
    release.require(state['config']['github_repo'] == 'ewijaya/kasugabus-pebble'
        and state['config']['store_app_id'] == 'f63e6ed24301414a95909564',
        'Historical destinations changed')
    for attempt in range(args.attempts):
        results = {}
        for name, check in [('github', release.verify_github), ('appstore', release.verify_store)]:
            try:
                results[name] = {'verified': True, 'details': check(state)}
            except Exception as error:
                results[name] = {'verified': False, 'reason': str(error)}
        print(json.dumps({'attempt': attempt + 1, 'publication': results,
                         'standardRuntimeAuditComplete': False}, indent=2), flush=True)
        if all(value['verified'] for value in results.values()):
            return
        if attempt + 1 < args.attempts:
            time.sleep(20)
    raise SystemExit('Some publication surfaces remain pending; no upload was attempted')

if __name__ == '__main__':
    main()
