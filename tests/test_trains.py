"""Train data: parsers on inline snippets, then the committed KTR1 build."""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import train_sources as src  # noqa: E402

SPEC = importlib.util.spec_from_file_location("train_build", ROOT / "tools/train_build.py")
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)

JR_LIST = ('<a href="/train-timetable/71011?date=20261020"><div class="mark"></div>'
           '<div class=" departure-time">7:02</div><div class="train-info"><div class="train-name">'
           '<span>普通</span></div><div class="destination" >西明石行</div></div></a>'
           '<a href="/train-timetable/76821?date=20261020"><div class="mark"></div>'
           '<div class=" departure-time legendOrange">7:08</div><div class="train-info"><div class="train-name">'
           '<span class=" legendOrange">A快速（うれしート連結）</span></div><div class="destination" >網干行</div></div></a>')
HANKYU_LIST = ('<a href="/station/timetable.php?stationName=茨木市&amp;SF=4916&amp;TX=1950110-1319-KY5115&amp;DW=0&amp;TM=0616" class="x">'
               '<p class="timetable_min"><span>16</span></p><div class="timetable_att">'
               '<p class="timetable_train_type"><!--wovn-src:［急行］-->［Commuter\n&nbsp;&nbsp;Ltd Exp］</p>'
               '<p class="timetable_station_name"><!--wovn-src:大阪梅田-->Osaka-umeda</p></div></a>')


class ParserTests(unittest.TestCase):
    def test_jr_list_keeps_base_type_and_uses_romaji(self):
        trains = src.parse_jr_list(JR_LIST)
        self.assertEqual([(t["minute"], t["type"], t["destination"]) for t in trains],
                         [(422, "Local", "Nishi-Akashi"), (428, "Rapid", "Aboshi")])
        self.assertEqual(trains[0]["ref"], "/train-timetable/71011?date=20261020")

    def test_hankyu_list_normalizes_whitespace(self):
        (train,) = src.parse_hankyu_list(HANKYU_LIST)
        self.assertEqual((train["minute"], train["type"], train["destination"]), (376, "Commuter Ltd Exp", "Osaka-umeda"))
        self.assertIn("TM=0616", train["ref"])
        self.assertIn("%E8%8C%A8", src.trip_url("Hankyu", train["ref"]))

    def test_service_minutes_run_past_midnight(self):
        self.assertEqual(src.service_minute(0, 24), 24 * 60 + 24)
        self.assertEqual(src.service_minute(5, 6), 306)

    def test_trip_stops_read_arrivals_not_origin_departures(self):
        jr = "<td>茨木</td><td>07:01</td><td>着</td><td>07:02</td><td>発</td><td>大阪</td><td>07:21</td><td>着</td><td>07:22</td><td>発</td><td>高槻</td><td>07:50</td><td>発</td>"
        self.assertEqual(src.parse_trip_stops("JR", jr), {"大阪": 7 * 60 + 21})
        hk = "<p>茨木市</p><p>出発、</p><p>06:16</p><p>大阪梅田(阪急)</p><p>到着、</p><p>06:36</p>"
        self.assertEqual(src.parse_trip_stops("Hankyu", hk), {"大阪梅田(阪急)": 6 * 60 + 36})

    def test_unknown_jr_destination_fails_instead_of_guessing(self):
        with self.assertRaises(KeyError):
            src.parse_jr_list(JR_LIST.replace("網干", "未知"))


@unittest.skipUnless((ROOT / "data/trains.bin").exists(), "train data not built")
class CommittedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (ROOT / "data/trains.bin").read_bytes()
        cls.decoded = BUILD.decode(cls.blob)
        cls.sections = cls.decoded["sections"]

    def test_outputs_match_a_fresh_offline_build(self):
        blob, sections = BUILD.build()
        self.assertEqual(blob, self.blob)
        document = json.dumps(BUILD.readable(sections), ensure_ascii=False, separators=(",", ":")) + "\n"
        self.assertEqual((ROOT / "data/trains.json").read_text(), document)

    def test_all_eight_lists_are_present_and_sorted(self):
        self.assertEqual(len(self.sections), 8)
        for key, rows in self.sections.items():
            minutes = [r[0] for r in rows]
            self.assertEqual(minutes, sorted(minutes), key)
            self.assertGreater(len(rows), 150, key)

    def test_size_fits_a_small_resource(self):
        self.assertLess(len(self.blob), 16 * 1024)

    def test_corruption_is_detected(self):
        damaged = bytearray(self.blob)
        damaged[-3] ^= 0xFF
        with self.assertRaises(ValueError):
            BUILD.decode(bytes(damaged))
        with self.assertRaises(ValueError):
            BUILD.decode(self.blob[:-1])

    def test_osaka_lists_use_one_target_and_kyoto_lists_two(self):
        for (network, direction, day), rows in self.sections.items():
            if direction == "Osaka":
                self.assertTrue(all(r[4] == 0 for r in rows), (network, day))
            else:
                self.assertGreater(sum(1 for r in rows if r[4] > 0), 100, (network, day))

    def test_only_hankyu_trains_for_tengachaya_and_shojaku_miss_umeda(self):
        for day in (1, 2):
            for minute, kind, destination, to_umeda, _ in self.sections[("Hankyu", "Osaka", day)]:
                self.assertEqual(to_umeda == 0, destination in ("Tengachaya", "Shojaku"), (minute, destination))

    def test_durations_are_plausible(self):
        # Observed 2026-10-20: JR Osaka 11-19, Hankyu Umeda 16-34, JR Kyoto 21-37,
        # Hankyu Kawaramachi 25-53; Takatsuki 4-9. Bounds leave a margin.
        limits = {("JR", "Osaka"): (8, 25), ("Hankyu", "Osaka"): (12, 45),
                  ("JR", "Kyoto"): (15, 45), ("Hankyu", "Kyoto"): (20, 65)}
        for (network, direction, day), rows in self.sections.items():
            low, high = limits[(network, direction)]
            for minute, kind, destination, first, second in rows:
                if first:
                    self.assertTrue(low <= first <= high, (network, direction, minute, first))
                if second:
                    self.assertTrue(3 <= second <= 15, (network, direction, minute, second))

    def test_kyoto_trains_missing_a_time_are_the_ones_that_stop_short(self):
        for network, short in (("JR", {"Takatsuki"}), ("Hankyu", {"Takatsuki-shi", "Katsura"})):
            for day in (1, 2):
                for minute, kind, destination, first, second in self.sections[(network, "Kyoto", day)]:
                    self.assertEqual(first == 0, destination in short, (network, minute, destination))

    def test_sources_catalog_hashes_still_match(self):
        BUILD.load_sources()

    def test_a_known_jr_train_matches_its_saved_page(self):
        rows = self.sections[("JR", "Osaka", 1)]
        self.assertEqual(rows[0][0], 5 * 60 + 6)
        page = (ROOT / "data/sources/trains/jr_osaka_weekday.html").read_text(encoding="utf-8")
        self.assertIn('departure-time">5:06', page)

    def test_header_dates_are_ordered(self):
        self.assertLess(self.decoded["verified"], self.decoded["review_due"])


if __name__ == "__main__":
    unittest.main()
