import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_watch", ROOT / "tools/source_watch.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class SourceWatchTests(unittest.TestCase):
    def test_timetable_pages_compare_only_their_times(self):
        old = "<head><title>A</title></head><p>阪大東口</p><td>7:19</td><td>7:31</td>".encode()
        churn = "<head><title>B</title></head><nav>&gt; 時刻表</nav><p>2026.10.2 NEW</p><td>7:19</td><td>7:31</td>".encode()
        changed = "<td>7:19</td><td>7:33</td>".encode()
        self.assertEqual(watch.normalize("hankyu_trip", "html", old), watch.normalize("hankyu_trip", "html", churn))
        self.assertNotEqual(watch.normalize("hankyu_trip", "html", old), watch.normalize("hankyu_trip", "html", changed))

    def test_notice_pages_compare_text_without_stamps_or_dates(self):
        old = b'<link href="a.css?ver=20261001"><li>2026-10-01 Timetable revision</li>'
        same = b'<link href="a.css?ver=20261002"><li>2026-10-02 Timetable revision</li>'
        new = b'<li>2026-10-02 Timetable revision</li><li>Route 22 changes</li>'
        self.assertEqual(watch.normalize("x_notices", "html", old), watch.normalize("x_notices", "html", same))
        self.assertNotEqual(watch.normalize("x_notices", "html", old), watch.normalize("x_notices", "html", new))

    def test_json_ignores_operational_dates_and_files_compare_exactly(self):
        a = b'{"date": "2026-10-01T03:00:00+09:00", "pole": 1}'
        b = b'{"date": "2026-10-02T03:00:00+09:00", "pole": 1}'
        self.assertEqual(watch.normalize("p", "json", a), watch.normalize("p", "json", b))
        self.assertNotEqual(watch.normalize("p", "json", a), watch.normalize("p", "json", a.replace(b"1}", b"2}")))
        self.assertNotEqual(watch.normalize("k", "pdf", b"%PDF-1"), watch.normalize("k", "pdf", b"%PDF-2"))

    def test_report_ranks_timetables_before_notices_and_lists_errors(self):
        results = [{"id": "k", "url": "u", "kind": "pdf", "name": "Weekday", "changed": True, "bytes": 2, "previous_bytes": 1},
                   {"id": "x_notices", "url": "u", "kind": "html", "name": "Notices", "changed": True},
                   {"id": "y", "url": "u", "error": "URLError"}]
        text, files = watch.report(results, "2026-10-01")
        self.assertEqual(files, 1)
        self.assertLess(text.index("Changed timetables"), text.index("Changed notice pages"))
        self.assertIn("`y`: URLError", text)


if __name__ == "__main__":
    unittest.main()
