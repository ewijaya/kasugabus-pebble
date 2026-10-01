"""Merged boarding opportunities: independent JSON oracle, no production edits."""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_routes import COMPILER, ROOT, route_fixture

UNKNOWN = 2**32-1
EPOCH = dt.date(1970, 1, 1)


def date_day(value):
    return (dt.date.fromisoformat(value)-EPOCH).days


def fixture():
    doc = route_fixture()
    # Equal absolute time across operators and multiple boarding points.
    for point, pattern, service in [(1, 2, 1), (2, 1, 1), (3, 4, 1), (101, 9, 4)]:
        doc['departures'].append(dict(boarding_point_id=point, pattern_id=pattern, service_id=service, minute=660))
    doc['calendar']['exceptions'].append(dict(date='2026-10-14', operator_id=2, day_type=255))
    return doc


def oracle(doc, future, now, ids, distances, override=None, destination=0):
    day = (now+32400)//86400
    selected = dict(zip(ids, distances))
    today_data = future if future and day >= date_day(future['effective_from']) else doc
    current_operators = {p['id']:p['operator_id'] for p in today_data['boarding_points']}
    for ago in (1,2):
        previous = future if future and day-ago >= date_day(future['effective_from']) else doc
        if max((row['minute'] for row in previous['departures']),default=0) >= ago*1440:
            for point in previous['boarding_points']:
                current_operators.setdefault(point['id'],point['operator_id'])
    rows, blocked = [], set()
    for service_day in range(day-2, day+8):
        current = future if future and service_day >= date_day(future['effective_from']) else doc
        services = {s['id']: s for s in current['services']}
        points = {s['id']: s for s in current['boarding_points']}
        patterns = {s['id']: s for s in current['patterns']}
        operators = {s['id']: s for s in current['operators']}
        for point in ids:
            if point in blocked:
                continue
            if point not in points or points[point]['operator_id'] != current_operators.get(point):
                if service_day >= day:
                    blocked.add(point)
                continue
            op = points[point]['operator_id']
            operator = operators[op]
            within_operator = date_day(operator.get('valid_from',current['valid_from'])) <= service_day <= date_day(operator.get('valid_until',current['valid_until']))
            within_dataset = date_day(current['valid_from']) <= service_day <= date_day(current['valid_until'])
            kind = None if within_operator and within_dataset else 255
            date = (EPOCH + dt.timedelta(days=service_day)).isoformat()
            if kind is None:
                for exception in current['calendar']['exceptions']:
                    if exception['date'] == date and exception['operator_id'] == op:
                        kind = exception['day_type']
            if kind is None:
                if not date_day(current['calendar']['coverage_from']) <= service_day <= date_day(current['calendar']['coverage_until']):
                    kind = 255
                else:
                    weekday = (EPOCH+dt.timedelta(days=service_day)).weekday()
                    holidays = [h if isinstance(h,str) else h['date'] for h in current['calendar']['holidays']]
                    kind = 3 if date in holidays or weekday == 6 else 2 if weekday == 5 else 1
                    declared = operator.get('day_types', sorted({t for s in current['services'] if s['operator_id']==op for t in s['day_types']}))
                    if kind not in declared+operator.get('no_service_day_types',[]):
                        kind = 255
            overridden = bool(override and override[0] == day and service_day == day and within_operator and within_dataset)
            if overridden:
                kind = override[1]
            if kind == 255:
                if service_day >= day:
                    blocked.add(point)
                continue
            for departure in current['departures']:
                service = services[departure['service_id']]
                if departure['boarding_point_id'] != point or kind not in service['day_types']:
                    continue
                if not date_day(service.get('valid_from',operator.get('valid_from',current['valid_from']))) <= service_day <= date_day(service.get('valid_until',operator.get('valid_until',current['valid_until']))):
                    continue
                if destination and destination not in [c['stop_group_id'] for c in patterns[departure['pattern_id']]['downstream_calls']]:
                    continue
                epoch = service_day*86400+departure['minute']*60-32400
                if now >= epoch+60:
                    continue
                rows.append((epoch, service_day, current['release_version'], departure['minute'], point,
                             departure['pattern_id'], departure['service_id'], kind, int(overridden)))
    rows.sort(key=lambda r:(r[0], selected[r[4]], r[1], r[4], r[5], r[6], r[2]))
    return rows[:64]


class MergedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='kasugabus-merged-')
        cls.path = Path(cls.temp.name)
        cls.exe = cls.path/'merged'
        cls.flags = ['cc','-std=c99','-Wall','-Wextra','-Werror','-pedantic']
        cls.sources = [str(ROOT/'src/c/engine.c'), str(ROOT/'tests/test_merged.c')]
        subprocess.run(cls.flags+cls.sources+['-o',str(cls.exe)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_query(self, doc=None, future=None, instant='2026-10-01T10:59:00+09:00', ids=(1,2,3,101), distances=(UNKNOWN,600,600,40), override=None, destination=0, exe=None, tz='Asia/Tokyo'):
        doc = doc or fixture()
        base = self.path/'base.bin'; base.write_bytes(COMPILER.compile_dataset(doc))
        if future:
            future_path = self.path/'future.bin'; future_path.write_bytes(COMPILER.compile_dataset(future))
        now = int(dt.datetime.fromisoformat(instant).timestamp())
        command = [str(exe or self.exe),str(base),str(future_path) if future else '-',str(now),
                   str(override[0] if override else -2147483648), str(override[1] if override else 255),str(destination)]
        for point,distance in zip(ids,distances):
            command += [str(point),str(distance)]
        result = subprocess.run(command, env=dict(os.environ,TZ=tz), text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        lines = result.stdout.splitlines()
        state = tuple(map(int,lines[0].split()[1:]))
        rows = [tuple(map(int,line.split()[1:])) for line in lines[1:]]
        if ids and len(set(ids))==len(ids) and all(i in [p['id'] for p in doc['boarding_points']] for i in ids):
            self.assertEqual(rows,oracle(doc,future,now,ids,distances,override,destination))
        return state,rows

    def test_distance_ties_unknown_and_stable_identity(self):
        _,rows = self.run_query()
        self.assertEqual([r[4] for r in rows[:4]],[101,2,3,1])
        _,rows = self.run_query(distances=(UNKNOWN,)*4)
        self.assertEqual([r[4] for r in rows[:4]],[1,2,3,101])
        _,rows = self.run_query(ids=(101,3,2,1),distances=(40,600,600,UNKNOWN))
        self.assertEqual([r[4] for r in rows[:4]],[101,2,3,1])

    def test_due_minute_and_independent_operator_calendars(self):
        for instant in ('2026-10-01T11:00:59+09:00','2026-10-01T11:01:00+09:00','2026-10-03T00:59:00+09:00',
                        '2026-10-04T00:00:00+09:00','2026-10-12T00:00:00+09:00','2026-11-03T00:00:00+09:00'):
            with self.subTest(instant=instant):self.run_query(instant=instant)
        state,rows=self.run_query(instant='2026-10-14T00:00:00+09:00')
        self.assertTrue(state[4]);self.assertEqual(state[5],date_day('2026-10-14'))
        self.assertTrue(rows);self.assertTrue(all(r[4]!=101 for r in rows))

    def test_override_expires_destination_filter_and_no_service(self):
        self.run_query(instant='2026-10-03T06:00:00+09:00',override=(date_day('2026-10-03'),1))
        self.run_query(instant='2026-10-04T06:00:00+09:00',override=(date_day('2026-10-03'),1))
        self.run_query(destination=3)
        state,rows=self.run_query(instant='2026-10-13T03:00:00+09:00',ids=(1,2),distances=(100,200))
        self.assertTrue(state[2]);self.assertTrue(all(r[1]>date_day('2026-10-13') for r in rows))

    def test_operator_gap_does_not_hide_other_operator_and_service_bounds(self):
        doc=fixture();del doc['operators'][1]['no_service_day_types']
        state,rows=self.run_query(doc,instant='2026-10-03T03:00:00+09:00')
        self.assertTrue(state[4]);self.assertTrue(rows);self.assertTrue(all(r[4]!=101 for r in rows))
        doc=fixture();doc['services'][0].update(valid_from='2026-10-02',valid_until='2026-10-15')
        self.run_query(doc)
        # An explicit operator exception can establish one service date beyond
        # the general public-holiday calendar interval.
        doc=fixture();doc['calendar'].update(coverage_until='2026-10-02',holidays=[])
        doc['calendar']['exceptions'].append(dict(date='2026-10-03',operator_id=1,day_type=2))
        state,rows=self.run_query(doc,instant='2026-10-03T03:00:00+09:00')
        self.assertTrue(rows);self.assertTrue(state[4])

    def test_future_revision_overnight_and_reused_cache(self):
        doc=fixture(); future=copy.deepcopy(doc)
        future.update(release_version=2,effective_from='2026-10-03')
        future['operators'][0]['name_en']='Future fixture '+('x'*400)
        for pattern in future['patterns']:pattern['id']+=40
        for departure in future['departures']:departure['pattern_id']+=40
        for tz in ('UTC','Asia/Tokyo','America/Los_Angeles'):
            _,rows=self.run_query(doc,future,'2026-10-03T00:59:00+09:00',tz=tz)
            self.assertEqual(rows[0][2],1);self.assertTrue(any(r[2]==2 for r in rows))

    def test_empty_invalid_removed_and_unconfirmed_selection(self):
        state,rows=self.run_query(ids=(),distances=());self.assertEqual(state[0],0);self.assertEqual(rows,[])
        state,_=self.run_query(ids=(1,1),distances=(0,0));self.assertEqual(state[0],-2)
        state,rows=self.run_query(ids=(250,),distances=(UNKNOWN,));self.assertEqual(state[0],-1);self.assertTrue(state[4]);self.assertEqual(rows,[])
        doc=fixture();doc['calendar'].update(coverage_until='2026-10-02',holidays=[])
        state,rows=self.run_query(doc,instant='2026-10-03T03:00:00+09:00');self.assertEqual(state[0],-1);self.assertTrue(state[4]);self.assertEqual(rows,[])

    def test_future_removal_preserves_other_boarding_points_and_prior_service_date(self):
        doc=fixture();future=copy.deepcopy(doc)
        future.update(release_version=2,effective_from='2026-10-03')
        future['boarding_points']=[p for p in future['boarding_points'] if p['id']!=2]
        future['departures']=[d for d in future['departures'] if d['boarding_point_id']!=2]
        state,rows=self.run_query(doc,future,'2026-10-02T23:00:00+09:00')
        self.assertTrue(state[4]);self.assertTrue(any(r[4]==2 and r[1]==date_day('2026-10-02') for r in rows))
        self.assertTrue(any(r[2]==2 and r[4]!=2 for r in rows))
        state,rows=self.run_query(doc,future,'2026-10-03T03:00:00+09:00')
        self.assertTrue(state[4]);self.assertTrue(rows);self.assertTrue(all(r[4]!=2 for r in rows))

    def test_removed_point_retains_live_overnight_trip_without_reusing_operator(self):
        doc=fixture();future=copy.deepcopy(doc)
        future.update(release_version=2,effective_from='2026-10-03')
        future['boarding_points']=[p for p in future['boarding_points'] if p['id']!=2]
        future['departures']=[d for d in future['departures'] if d['boarding_point_id']!=2]
        for instant in ('2026-10-03T00:59:00+09:00','2026-10-03T01:05:59+09:00'):
            state,rows=self.run_query(doc,future,instant,ids=(2,),distances=(UNKNOWN,))
            self.assertTrue(state[4]);self.assertEqual(len(rows),1)
            self.assertEqual(rows[0][1:5],(date_day('2026-10-02'),1,1505,2))
        state,rows=self.run_query(doc,future,'2026-10-03T01:06:00+09:00',ids=(2,),distances=(UNKNOWN,))
        self.assertTrue(state[4]);self.assertEqual(rows,[])
        # A retained second-previous service day also survives a removal.
        doc['departures'].append(dict(boarding_point_id=2,pattern_id=1,service_id=1,minute=2945))
        _,rows=self.run_query(doc,future,'2026-10-04T01:05:00+09:00',ids=(2,),distances=(UNKNOWN,))
        self.assertEqual(rows[0][1:5],(date_day('2026-10-02'),1,2945,2))
        # Explicit reassignment in current data must not borrow the old operator.
        reassigned=copy.deepcopy(future)
        replacement=copy.deepcopy(doc['boarding_points'][1]);replacement['operator_id']=2
        reassigned['boarding_points'].append(replacement)
        _,rows=self.run_query(doc,reassigned,'2026-10-03T00:59:00+09:00',ids=(2,),distances=(UNKNOWN,))
        self.assertEqual(rows,[])

    def test_address_and_undefined_sanitizers(self):
        exe=self.path/'merged-sanitized'
        subprocess.run(self.flags+['-fsanitize=address,undefined','-fno-omit-frame-pointer']+self.sources+['-o',str(exe)],check=True,capture_output=True)
        self.run_query(exe=exe)

    def test_all_production_points_weekday_weekend_holiday_and_end_of_coverage(self):
        doc=json.loads((ROOT/'data/timetable.json').read_text())
        ids=tuple(p['id'] for p in doc['boarding_points'])
        # Deliberately unknown distances: read-only comparison with validated
        # source rows, with no pretend reference coordinates in the fixture.
        for instant in ('2026-10-01T10:00:00+09:00','2026-10-03T00:00:00+09:00',
                        '2026-10-04T00:00:00+09:00','2026-10-12T00:00:00+09:00',
                        '2026-12-27T00:00:00+09:00','2026-12-28T00:00:00+09:00'):
            with self.subTest(instant=instant):
                self.run_query(doc,instant=instant,ids=ids,distances=(UNKNOWN,)*len(ids))

if __name__ == '__main__': unittest.main()
