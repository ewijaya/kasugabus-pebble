"""Offline scope tests: no SDK, emulator, network or real repository mutation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_policy import classify, make_policy, required_scenarios, SMOKE, FULL


class PolicyTests(unittest.TestCase):
    def test_ui_vs_transfer(self):
        self.assertEqual(classify(['src/c/ui.c'])['required_scenarios'], SMOKE)
        for path in ['src/c/storage.c', 'src/pkjs/updater.js', 'src/pkjs/protocol.js', 'src/c/main.c', 'new-input']:
            self.assertEqual(classify([path])['required_scenarios'], FULL)
        self.assertEqual(classify(['src/c/ui.c'], True)['required_scenarios'], FULL)

    def test_targeted_checks(self):
        self.assertIn('schedule/calendar/provenance', classify(['src/c/engine.c'])['targeted_checks'])
        self.assertIn('settings/location/persistence', classify(['src/pkjs/settings.js'])['targeted_checks'])

    def test_git_bound_scope_and_version_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
            git('init'); git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'Fixture')
            (root / 'package.json').write_text(json.dumps({'version': '1.0.0', 'dependencies': {}}))
            git('add', '.'); git('commit', '-m', 'fixture')
            self.assertEqual(make_policy(root)['required_scenarios'], FULL)
            git('tag', 'v1.0.0')
            (root / 'package.json').write_text(json.dumps({'version': '1.0.1', 'dependencies': {}}))
            git('add', '.'); git('commit', '-m', 'version')
            policy = make_policy(root)
            self.assertEqual(policy['required_scenarios'], SMOKE)
            report = {'validation_policy': policy, 'source': {'git_commit': git('rev-parse', 'HEAD')}}
            self.assertEqual(required_scenarios(report, {}, root), SMOKE)
            policy['required_scenarios'] = []
            with self.assertRaises(RuntimeError):
                required_scenarios(report, {}, root)
            (root / 'package.json').write_text(json.dumps({'version': '1.0.1', 'dependencies': {'new': '1'}}))
            git('add', '.'); git('commit', '-m', 'dependency')
            self.assertEqual(make_policy(root)['required_scenarios'], FULL)

    def test_legacy_audit_keeps_full_gate(self):
        self.assertEqual(required_scenarios({}, {'required_runtime_scenarios': FULL}), FULL)


if __name__ == '__main__':
    unittest.main()
