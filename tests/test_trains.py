"""Train data: parsers on inline snippets, then the committed KTR1 build."""
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
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

    def _compile_c(self):
        directory = tempfile.TemporaryDirectory(prefix="kasugabus-trains-")
        self.addCleanup(directory.cleanup)
        executable = Path(directory.name) / "test-trains"
        subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", str(ROOT / "src/c/engine.c"),
                        str(ROOT / "src/c/trains.c"), str(ROOT / "tests/test_trains.c"), "-o", str(executable)], check=True)
        return executable

    def _hm(self, minute):
        return f"{minute // 60}:{minute % 60:02}"

    def _expected_next(self, key, ready, target, skip):
        rows = [r for r in self.sections[key] if r[3 + target] and r[0] >= ready]
        if skip >= len(rows):
            return "none"
        minute, kind, destination, *durations = rows[skip]
        return f"{self._hm(minute)}|{self._hm(minute + durations[target])}|{kind}|{destination}"

    def test_c_reader_self_checks(self):
        result = subprocess.run([str(self._compile_c()), str(ROOT / "data/trains.bin")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("self-checks passed", result.stdout)

    def test_c_next_train_matches_the_python_decoder(self):
        networks, directions = ("JR", "Hankyu"), ("Osaka", "Kyoto")
        rng = random.Random(20261021)
        queries, expected = [], []
        for _ in range(600):
            n, d, day = rng.randrange(2), rng.randrange(2), rng.choice((1, 2))
            ready = rng.choice((0, 300, 306, 1469, 1470, 1500)) if rng.random() < 0.2 else rng.randrange(280, 1500)
            target, skip = rng.randrange(2), rng.choice((0, 0, 0, 1, 2, 40, 400))
            queries.append(f"{n} {d} {day} {ready} {target} {skip}")
            expected.append(self._expected_next((networks[n], directions[d], day), ready, target, skip))
        result = subprocess.run([str(self._compile_c()), str(ROOT / "data/trains.bin"), "next"], input="\n".join(queries),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split("\n")[:-1], expected)
        self.assertGreater(sum(1 for e in expected if e != "none"), 250)

    def test_c_connection_matches_the_python_decoder(self):
        networks, directions = ("JR", "Hankyu"), ("Osaka", "Kyoto")
        rng = random.Random(7)
        queries, expected = [], []
        for _ in range(500):
            day, d = rng.choice((1, 2)), rng.randrange(2)
            target = rng.randrange(2) if d else 0
            trip = rng.randrange(330, 1380)
            jr = rng.choice((0, rng.randrange(1, 32)))
            hk = 0 if not jr or rng.random() < 0.15 else jr + rng.choice((5, 6, 8))
            walk = (rng.choice((0, 4, 10)), rng.choice((0, 4, 10)))
            queries.append(f"{day} {d} {target} {trip} {jr} {hk} {walk[0]} {walk[1]}")
            legs = []
            for s, minutes in enumerate((jr, hk)):
                if not minutes:
                    continue
                at = trip + minutes
                line = self._expected_next((networks[s], directions[d], day), at + walk[s], target, 0)
                if line != "none":
                    dep, arr, kind, dest = line.split("|")
                    legs.append((self._arrival(arr), s, f"{s}@{self._hm(at)}:{dep}|{arr}|{kind}|{dest}"))
            legs.sort(key=lambda leg: (leg[0], leg[1]))
            expected.append(" ".join([str(len(legs))] + [leg[2] for leg in legs]))
        result = subprocess.run([str(self._compile_c()), str(ROOT / "data/trains.bin"), "connect"], input="\n".join(queries),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split("\n")[:-1], expected)
        self.assertGreater(sum(1 for e in expected if e.startswith("2")), 100)

    @staticmethod
    def _arrival(text):
        hours, minutes = text.split(":")
        return int(hours) * 60 + int(minutes)

    def test_bundled_resource_is_the_verified_data_file(self):
        self.assertEqual((ROOT / "resources/trains.bin").read_bytes(), self.blob)
        package = json.loads((ROOT / "package.json").read_text())
        media = package["pebble"]["resources"]["media"]
        self.assertEqual([m for m in media if m["name"] == "TRAINS"], [{"type": "raw", "name": "TRAINS", "file": "trains.bin"}])
        # Appended last so existing resource IDs never shift.
        self.assertEqual(media[-1]["name"], "TRAINS")

    def test_header_dates_are_ordered(self):
        self.assertLess(self.decoded["verified"], self.decoded["review_due"])


if __name__ == "__main__":
    unittest.main()
