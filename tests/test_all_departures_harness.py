"""Offline native-fixture guards; never touches an emulator or a real relay."""
import os
import datetime as dt
from pathlib import Path
import queue
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
SDK_PYTHON=Path(os.environ.get("KASUGABUS_PEBBLE_PYTHON",str(Path.home()/".local/share/uv/tools/pebble-tool/bin/python")))
sys.path.insert(0,str(ROOT/"tools"))
import verify_all_departures as all_native
from verify_emulator import Emulator,preferences


class AllHarnessTests(unittest.TestCase):
    def logs(self,*messages):
        return Mock(observed=[{"event":"watchlog","message":value,"observedAt":index+1} for index,value in enumerate(messages)])

    def test_latest_incomplete_preferences_never_reuse_old_selection(self):
        emu=self.logs("All loaded generation1 reference2 count2","All ids0 1 101")
        self.assertEqual(all_native.all_snapshot(emu)["ids"],[1,101])
        emu.observed.append({"event":"watchlog","message":"All saved generation2 reference0 count3"})
        self.assertIsNone(all_native.all_snapshot(emu))
        emu.observed.append({"event":"watchlog","message":"All ids0 1 101 102"})
        self.assertEqual(all_native.all_snapshot(emu)["ids"],[1,101,102])
        empty=self.logs("All saved generation3 reference2 count0","All ids0 empty")
        self.assertEqual(all_native.all_snapshot(empty)["ids"],[])
        for logs in (("All saved generation4 reference9 count0",),
                     ("All saved generation4 reference2 count2","All ids0 1 1"),
                     ("All saved generation4 reference2 count2","All ids1 1 101"),
                     ("All saved generation4 reference2 count1","All ids0 256")):
            with self.assertRaises(AssertionError):all_native.all_snapshot(self.logs(*logs))

    def test_choice_and_trip_proof_must_follow_current_native_draw(self):
        emu=self.logs("UI screen21 heap50000","UI selection4 scroll0 limit0","All choice point101 selected1")
        self.assertEqual(all_native.last_choice(emu)["point"],101)
        emu.observed.extend([{"event":"watchlog","message":"UI screen21 heap50000","observedAt":4},
                             {"event":"watchlog","message":"UI selection5 scroll0 limit0","observedAt":5}])
        emu.wait.side_effect=TimeoutError("fixture missing fresh diagnostic")
        with self.assertRaises(TimeoutError):all_native.last_choice(emu)
        emu.observed.append({"event":"watchlog","message":"All choice point102 selected0","observedAt":6})
        self.assertEqual(all_native.last_choice(emu)["point"],102)
        trip=self.logs("UI screen22 heap50000","UI selection1 scroll0 limit0","All trip day20727 minute606 point102 pattern23 service6 version2")
        self.assertEqual(all_native.focused_trip(trip)["point"],102)

    def test_fixture_reply_bounds_and_verified_id_restriction(self):
        token={"reference":0,"request":1,"version":2,"ids":[101,102]};clock=Mock();clock.now.return_value=1790816701
        reply=all_native.result_message(token,0,clock,{102:200,101:100})
        self.assertEqual(reply["DATA"],[102,0,200,0,0,0,101,0,100,0,0,0])
        self.assertEqual(all_native.result_message(token,2,clock)["STAMP"],1790816521)
        for status in range(3,10):self.assertNotIn("DATA",all_native.result_message(token,status,clock))
        for distances in ({1:100},{101:-1},{101:40075001},{101:True},{}):
            with self.assertRaises(ValueError):all_native.result_message(token,0,clock,distances)
        for key,value in (("reference",2),("request",0),("version",4294967296),("ids",None)):
            with self.assertRaises(ValueError):all_native.result_message(dict(token,**{key:value}),0,clock,{101:100})
        clock.now.return_value=float('nan')
        with self.assertRaises(ValueError):all_native.result_message(token,0,clock,{101:100})

    def test_wrong_artifact_and_capture_namespace_stop_before_emulator(self):
        command=["--pbw","unused.pbw","--runtime-receipt","unused.json","--timetable","unused.bin","--output","unused-report.json","--screenshot-prefix","fixture","--fixture-relay","--allow-all-selection-changes"]
        with patch.object(all_native,"artifact_proof",side_effect=ValueError("wrong receipt")),patch.object(all_native,"FixtureEmulator") as emu,patch.object(all_native,"Oracle") as oracle:
            with self.assertRaises(ValueError):all_native.main(command)
            emu.assert_not_called();oracle.assert_not_called()
        command[command.index("fixture")]="../old-release"
        with patch.object(all_native,"artifact_proof",return_value={}),patch.object(all_native,"FixtureEmulator") as emu,patch.object(all_native,"Oracle") as oracle:
            with self.assertRaises(ValueError):all_native.main(command)
            emu.assert_not_called();oracle.assert_not_called()

    def test_cleanup_ignores_expired_work_deadline_but_waits_for_relay_receipt(self):
        emu=Emulator.__new__(Emulator);emu.deadline=time.monotonic()-1;deadline=emu.deadline
        emu.fixture_relay=True;emu.observed=[];emu.events=queue.Queue();emu.proc=Mock();emu.proc.stdin.closed=False
        emu.events.put({"event":"fixtureRestored","normalSdkRelayRestored":True})
        emu.close()
        emu.proc.stdin.write.assert_called_once_with('{"op": "close"}\n')
        emu.proc.stdin.close.assert_called_once();emu.proc.wait.assert_called_once_with(timeout=55)
        self.assertEqual(emu.deadline,deadline)
        self.assertTrue(emu.observed[-1]["normalSdkRelayRestored"])

    def test_real_snapshot_oracle_known_and_unknown_ties(self):
        path=ROOT/"hosting/public/releases/2-5c7adc806702a76e.bin"
        oracle=all_native.Oracle(path)
        try:
            now=int(dt.datetime.fromisoformat("2026-10-01T10:05:01+09:00").timestamp())
            ids=[3,5,6,9,101,102];day=(now+32400)//86400
            unknown=oracle.query(now,ids,{})
            known=oracle.query(now,ids,{101:100,102:200})
            tie=lambda rows:[r["point"] for r in rows if r["day"]==day and r["minute"]==606]
            self.assertEqual(tie(unknown),[3,9,102]);self.assertEqual(tie(known),[102,3,9])
            self.assertEqual([p["id"] for p in oracle.points if p["verified"]],[101,102,103,104,105,106])
            self.assertEqual(oracle.query(now,[],{}),[])
        finally:oracle.close()


class RelayLifecycleTests(unittest.TestCase):
    @unittest.skipUnless(SDK_PYTHON.is_file() and sys.platform=="darwin","Installed macOS SDK unavailable")
    def test_real_sdk_kernel_argv_roundtrip_retains_spaces_empty_args_and_packages(self):
        # Benign child interpreter only: no emulator/socket/account access.
        script=r'''
import importlib.util,subprocess,sys,json
spec=importlib.util.spec_from_file_location('bridge','tools/emu_update_bridge.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
program='import sys; from libpebble2.services.appmessage import AppMessageService; print("READY",flush=True); sys.stdin.read()'
arguments=[sys.executable,'-c',program,'path with spaces','']
p=subprocess.Popen(arguments,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
try:
 assert p.stdout.readline().strip()=='READY'
 original=b.process_arguments(p.pid)
 assert original[1:]==arguments[1:]
finally:p.stdin.close();p.wait(timeout=5)
q=subprocess.Popen([sys.executable,*original[1:]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
try:
 assert q.stdout.readline().strip()=='READY'
 assert b.process_arguments(q.pid)==original
finally:q.stdin.close();q.wait(timeout=5)
print('PASS real installed SDK interpreter/kernel argv roundtrip and package import')
'''
        result=subprocess.run([str(SDK_PYTHON),"-c",script],cwd=ROOT,text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    @unittest.skipUnless(SDK_PYTHON.is_file(),"Installed pebble-tool Python unavailable")
    def test_fixture_relay_uses_sdk_without_evaluating_worker_and_restores_exact_argv(self):
        script=r'''
import importlib.util,hashlib,json,tempfile,signal,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('bridge','tools/emu_update_bridge.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
events=[];bridge.emit=events.append
arguments=['/SDK path/python','-m','pypkjs','--qemu','localhost:1234','--port','2345','--persist','/SDK data/cache','--oauth','PRIVATE_OFFLINE_TOKEN']
info={'qemu':{'pid':9999,'port':1234,'monitor':3456},'pypkjs':{'pid':100,'port':2345},'version':'4.33.1','sdkVersion':'4.33.1'}
processes={};spawned=[];probes=[]
class FakeProcess:
    def __init__(self,pid,argv):self.pid=pid;self.argv=argv;self.alive=True
    def cmdline(self):return self.argv.copy()
    def terminate(self):self.alive=False
    def wait(self,timeout):assert timeout==5;self.alive=False
    def poll(self):return None if self.alive else 0
def arguments_for(pid):
    if pid not in processes or not processes[pid].alive:raise ProcessLookupError('offline process absent')
    return processes[pid].cmdline()
def stop(pid):
    if pid in processes:processes[pid].alive=False
def spawn(argv,**kw):
    assert kw==dict(stdout=bridge.subprocess.DEVNULL,stderr=bridge.subprocess.DEVNULL,start_new_session=True)
    pid=200 if '--fixture-relay-child' in argv else 300
    result=FakeProcess(pid,arguments if pid==300 else argv);processes[pid]=result;spawned.append(argv.copy());return result
with tempfile.TemporaryDirectory() as folder:
    path=Path(folder)/'metadata.json';cache=Path(folder)/'cached.pbw'
    cache.write_bytes(b'OFFLINE PBW FIXTURE ONLY');digest=hashlib.sha256(cache.read_bytes()).hexdigest()
    def reset():
        events.clear();spawned.clear();probes.clear();processes.clear();processes[100]=FakeProcess(100,arguments)
        path.write_text(json.dumps({'emery':{'4.33.1':{k:v for k,v in info.items() if k!='sdkVersion'}}}))
    native={'preferences':bytes([2]+[0]*79),'version':2,'pending':0}
    with patch.object(bridge,'get_emulator_info_path',return_value=str(path)),patch.object(bridge,'get_all_emulator_info',side_effect=lambda:json.loads(path.read_text())),patch.object(bridge,'process_arguments',side_effect=arguments_for),patch.object(bridge.FixtureRelay,'stop_process',side_effect=stop),patch.object(bridge.FixtureRelay,'disconnect_bluetooth',return_value=None),patch.object(bridge.FixtureRelay,'prime_bluetooth',return_value=None),patch.object(bridge.FixtureRelay,'native_state',return_value=native),patch.object(bridge.subprocess,'Popen',side_effect=spawn):
        reset();before=signal.getsignal(signal.SIGTERM)
        with patch.object(bridge.FixtureRelay,'probe',side_effect=lambda port,proc:probes.append(proc.pid)):
            with bridge.FixtureRelay(info,cache,digest):
                state=json.loads(path.read_text())['emery']['4.33.1']
                assert state['pypkjs']['pid']==200 and state['qemu']==info['qemu']
        assert spawned[-1]==[sys.executable,*arguments[1:]] and probes==[200,300]
        assert json.loads(path.read_text())['emery']['4.33.1']['pypkjs']['pid']==300
        assert events[-1]['normalSdkRelayRestored'] and events[-1]['nativeStateVerified'] and signal.getsignal(signal.SIGTERM)==before
        assert 'PRIVATE_OFFLINE_TOKEN' not in json.dumps(events)
        # A failure after stopping the old relay still restores its exact argv.
        reset()
        def fail_first(port,proc):
            probes.append(proc.pid)
            if proc.pid==200:raise TimeoutError('offline fixture start failed')
        with patch.object(bridge.FixtureRelay,'probe',side_effect=fail_first):
            try:
                with bridge.FixtureRelay(info,cache,digest):raise AssertionError('entry must fail')
            except TimeoutError:pass
            else:raise AssertionError('fixture failure ignored')
        assert spawned[-1]==[sys.executable,*arguments[1:]] and events[-1]['normalSdkRelayRestored']
        # Ordinary interrupt also restores; a failed restore never claims success.
        reset()
        with patch.object(bridge.FixtureRelay,'probe',return_value=None):
            try:
                with bridge.FixtureRelay(info,cache,digest):raise KeyboardInterrupt()
            except KeyboardInterrupt:pass
        assert spawned[-1]==[sys.executable,*arguments[1:]] and events[-1]['normalSdkRelayRestored']
        reset()
        with patch.object(bridge.FixtureRelay,'probe',side_effect=lambda port,proc: (_ for _ in ()).throw(TimeoutError('offline restoration failure')) if proc.pid==300 else None):
            try:
                with bridge.FixtureRelay(info,cache,digest):pass
            except TimeoutError:pass
            else:raise AssertionError('restoration failure ignored')
        assert events[-1]['source']=='fixture-restoration' and not any(e.get('normalSdkRelayRestored') for e in events)
        assert 'PRIVATE_OFFLINE_TOKEN' not in json.dumps(events)
        # Ownership changes must be rejected before a normal relay is spawned.
        reset()
        with patch.object(bridge.FixtureRelay,'probe',return_value=None):
            relay=bridge.FixtureRelay(info,cache,digest);relay.__enter__()
            value=json.loads(path.read_text());value['emery']['4.33.1']['pypkjs']['pid']=999;path.write_text(json.dumps(value))
            try:relay.restore()
            except RuntimeError:pass
            else:raise AssertionError('changed ownership accepted')
        assert len(spawned)==1 and not any(e.get('normalSdkRelayRestored') for e in events)
        # Frontend success cannot hide a dead native backend or mutated prefs.
        for failed in (TimeoutError('native backend absent'),dict(native,preferences=bytes([2,8]+[0]*78)),dict(native,version=3)):
            reset()
            sequence=[native,*([failed]*3 if isinstance(failed,TimeoutError) else [failed])]
            with patch.object(bridge.FixtureRelay,'probe',return_value=None),patch.object(bridge.FixtureRelay,'native_state',side_effect=sequence) as native_probe:
                try:
                    with bridge.FixtureRelay(info,cache,digest):pass
                except (RuntimeError,TimeoutError):pass
                else:raise AssertionError('normal native identity/health failure ignored')
            assert events[-1]['source']=='fixture-restoration' and not any(e.get('normalSdkRelayRestored') for e in events)
            assert 'normal native STATE' in events[-1]['message']
            assert native_probe.call_count==(4 if isinstance(failed,TimeoutError) else 2)
        reset()
        with patch.object(bridge.FixtureRelay,'probe',return_value=None),patch.object(bridge.FixtureRelay,'native_state',side_effect=[native,TimeoutError('transient startup'),native]) as native_probe:
            with bridge.FixtureRelay(info,cache,digest):pass
        assert events[-1]['normalSdkRelayRestored'] and events[-1]['nativeStateAttempts']==2 and events[-1]['nativeStateTransientRetries']==1
        reset()
        with patch.object(bridge.FixtureRelay,'native_state',side_effect=TimeoutError('entry backend absent')):
            try:
                with bridge.FixtureRelay(info,cache,digest):pass
            except TimeoutError:pass
            else:raise AssertionError('entry backend failure ignored')
        assert spawned==[] and processes[100].alive
# Exercise the installed SDK runner class with its network constructor mocked.
from pypkjs.runner.websocket import WebsocketRunner
from pypkjs.javascript.runtime import JSRuntime
def run(runner):
    runner.js=None;runner.running_uuid=None
    runner.start_js(SimpleNamespace(src='throw new Error("must never evaluate")'))
    assert runner.js is None and runner.running_uuid is None
with patch.object(WebsocketRunner,'__init__',return_value=None) as constructor,patch.object(WebsocketRunner,'run',run),patch.object(JSRuntime,'__init__',side_effect=AssertionError('worker must not run')):
    bridge.run_fixture_relay_child('4.33.1',1234,2345)
    assert constructor.call_args.kwargs['persist_dir'].endswith('/4.33.1/emery')
print('PASS SDK relay-only worker suppression, exact in-memory argv restore, entry failure, interrupt, failed probe and metadata preservation')
'''
        result=subprocess.run([str(SDK_PYTHON),"-c",script],cwd=ROOT,text=True,capture_output=True,timeout=25)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=="__main__":unittest.main()
