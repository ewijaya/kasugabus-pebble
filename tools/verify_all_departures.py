#!/usr/bin/env python3
"""Native All departures fixtures on an already-installed, exact Emery PBW.

Explicit --fixture-relay suppresses SDK worker/geolocation execution, uses only
simulated distance/status replies, then restores/probes the original SDK relay.
Actual timetable bytes and the portable engine provide trip-order evidence.
No PBW build, installation, production feed, or physical-device operation.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time
from verify_emulator import Emulator,ROOT
from verify_accessibility import (artifact_proof,appearance,normalized,await_ui,ui_click,
    choose_row,open_menu,home,capture,scroll_bottom,restore,SIZES,THEMES,sha,native_ui)

UNKNOWN=4294967295
STATUS_NAMES=("success","low accuracy","stale","permission denied","timeout",
              "phone unavailable","outside area","no verified poles","disabled","saved home unset")


class Oracle:
    """Host-only engine compilation; inputs are unchanged real snapshot files."""
    def __init__(self,current,future=None):
        self.current=Path(current).resolve();self.future=Path(future).resolve() if future else None
        self.raw=self.current.read_bytes()
        if not 128<=len(self.raw)<=32768 or self.raw[:4]!=b"KBT1":raise ValueError("Invalid exact timetable input")
        self.version=struct.unpack_from("<I",self.raw,16)[0]
        self.temp=tempfile.TemporaryDirectory(prefix="kasugabus-all-oracle-")
        self.executable=Path(self.temp.name)/"engine-oracle"
        sources=[ROOT/"src/c/engine.c",ROOT/"tests/test_merged.c"]
        subprocess.run(["cc","-std=c99","-Wall","-Wextra","-Werror","-pedantic",*[str(p) for p in sources],"-o",str(self.executable)],check=True,capture_output=True,timeout=20)
        self.query(int(dt.datetime.fromisoformat("2026-10-01T10:05:01+09:00").timestamp()),[],{})
        self.proof={"currentSha256":sha(self.raw),"currentVersion":self.version,"currentBytes":len(self.raw),
                    "engineSha256":sha(sources[0].read_bytes()),"oracleHelperSha256":sha(sources[1].read_bytes())}
        if self.future:
            future_raw=self.future.read_bytes();self.proof["futureSha256"]=sha(future_raw)
            self.proof["futureVersion"]=struct.unpack_from("<I",future_raw,16)[0]
        pool=struct.unpack_from("<I",self.raw,52)[0]
        offset,count=struct.unpack_from("<IH",self.raw,76)
        self.points=[]
        def string(position):
            start=pool+struct.unpack_from("<H",self.raw,position)[0]
            return self.raw[start:self.raw.index(0,start)].decode("utf-8")
        for i in range(count):
            row=offset+i*24
            self.points.append({"id":self.raw[row],"verified":bool(self.raw[row+3]&1),
                                "name":string(row+6),"direction":string(row+10)})

    def query(self,epoch,ids,distances):
        if len(ids)>32 or len(set(ids))!=len(ids):raise ValueError("Invalid oracle selection")
        command=[str(self.executable),str(self.current),str(self.future) if self.future else "-",str(epoch),"-2147483648","255","0"]
        for point in ids:command.extend([str(point),str(distances.get(point,UNKNOWN))])
        result=subprocess.run(command,text=True,capture_output=True,timeout=20)
        if result.returncode:raise RuntimeError("Actual engine rejected the supplied snapshot/query: "+result.stderr[:500])
        rows=[]
        for line in result.stdout.splitlines():
            if line.startswith("T "):
                epoch,day,version,minute,point,pattern,service,kind,override=map(int,line.split()[1:])
                rows.append({"epoch":epoch,"day":day,"version":version,"minute":minute,"point":point,
                             "pattern":pattern,"service":service,"dayType":kind,"override":override})
        return rows

    def close(self):self.temp.cleanup()


class FixtureEmulator(Emulator):
    def __init__(self,**kwargs):
        self.reference_requests=[]
        super().__init__(fixture_relay=True,**kwargs)
    def remember(self,event):
        super().remember(event)
        message=event.get("message",{})
        if event.get("event")=="appmessage" and message.get("0")==14:
            if len(self.reference_requests)>=256:raise RuntimeError("Native fixture exceeded 256 reference requests")
            # Keep only public IDs, not any coordinates or personal state.
            data=message.get("6",[])
            ids=[data[i]+data[i+1]*256 for i in range(0,len(data),10)] if len(data)%10==0 else None
            self.reference_requests.append({"reference":message.get("13"),"request":message.get("8"),
                "version":message.get("3"),"ids":ids,"observedAt":time.monotonic()})


class FixtureClock:
    def __init__(self,emu,text):self.emu,self.text=emu,text;self.reset()
    def reset(self):
        self.epoch=int(dt.datetime.fromisoformat(self.text).timestamp());self.started=time.monotonic()
        self.emu.date(self.text)
    def now(self):return self.epoch+int(time.monotonic()-self.started)
    def advance(self,seconds):
        self.epoch=self.now()+seconds;self.started=time.monotonic()
        self.emu.date(dt.datetime.fromtimestamp(self.epoch,dt.timezone(dt.timedelta(hours=9))).isoformat())


def all_snapshot(emu):
    current=None;complete=False
    for event in emu.observed:
        if event.get("event")!="watchlog":continue
        message=event.get("message","")
        begin=re.search(r"\bAll (loaded|saved) generation(\d+) reference(\d+) count(\d+)\b",message)
        ids=re.search(r"\bAll ids(\d+) (.*)$",message)
        if begin:
            reference,count=int(begin[3]),int(begin[4])
            if reference not in range(3) or not 0<=count<=32:raise AssertionError("Invalid native All preferences diagnostic")
            current={"generation":int(begin[2]),"reference":reference,"count":count,
                     "ids":[None]*count,"observedAt":event.get("observedAt",0)}
            complete=False
        elif ids and current:
            offset=int(ids[1]);values=[] if ids[2]=="empty" else [int(n) for n in ids[2].split()]
            if offset>current["count"] or offset+len(values)>current["count"] or any(not 1<=value<=255 for value in values):raise AssertionError("Native All ID log exceeds its persisted count/ID bounds")
            if not values and (offset or current["count"]):raise AssertionError("Invalid empty native All ID log")
            current["ids"][offset:offset+len(values)]=values
            complete=all(value is not None for value in current["ids"])
            if complete and len(set(current["ids"]))!=current["count"]:raise AssertionError("Duplicate native All boarding IDs")
    return dict(current,ids=current["ids"].copy()) if current and complete else None


def frame_diagnostic(emu,pattern,screen=None):
    """Require a diagnostic after the latest paired draw, not an old frame."""
    end=time.monotonic()+3
    while time.monotonic()<end:
        ui=await_ui(emu,screen)
        for event in reversed(emu.observed):
            if event.get("observedAt",0)<ui["observedAt"]:break
            if event.get("event")=="watchlog":
                match=re.search(pattern,event.get("message",""))
                if match:return match,event.get("observedAt",0)
        emu.wait(lambda e:e.get("event")=="watchlog",max(.01,end-time.monotonic()))
    raise TimeoutError("Fresh native All frame diagnostic missing")


def all_view(emu):
    value,stamp=frame_diagnostic(emu,r"\bAll view reference(\d+) status(\d+) request(\d+) waiting(\d+) selected(\d+) distances(\d+)\b")
    return dict(zip(("reference","status","request","waiting","selected","distances"),map(int,value.groups())),observedAt=stamp)


def last_choice(emu):
    value,_=frame_diagnostic(emu,r"\bAll choice point(\d+) selected([01])\b",21)
    return {"point":int(value[1]),"selected":bool(int(value[2]))}


def focused_trip(emu):
    value,_=frame_diagnostic(emu,r"\bAll trip day(-?\d+) minute(\d+) point(\d+) pattern(\d+) service(\d+) version(\d+)\b",22)
    return dict(zip(("day","minute","point","pattern","service","version"),map(int,value.groups())))


def require_view(emu,**expected):
    await_ui(emu)
    view=all_view(emu)
    if not view or any(view.get(key)!=value for key,value in expected.items()):
        raise AssertionError("Native All view does not match fixture: "+str(expected)+" observed "+str(view))
    return view


def open_reference(emu):
    home(emu);open_menu(emu,0,4);choose_row(emu,4,4);ui_click(emu,"select",20)


def select_reference(emu,reference):
    if reference not in range(4):raise ValueError("Unknown native reference choice")
    open_reference(emu);choose_row(emu,20,reference);ui_click(emu,"select",21)


def choose_point(emu,point,point_count):
    for row in range(4,4+point_count):
        choose_row(emu,21,row)
        value=last_choice(emu)
        if not value:raise AssertionError("Native point choice ID proof missing")
        if value["point"]==point:return value
    raise AssertionError("Native point picker does not contain requested ID "+str(point))


def selection(emu,ids,point_count):
    choose_row(emu,21,3);ui_click(emu,"select",21)
    snapshot=all_snapshot(emu)
    if not snapshot or snapshot["ids"]:raise AssertionError("Native Clear did not save an empty All selection")
    for point in ids:
        choose_point(emu,point,point_count);ui_click(emu,"select",21)
    snapshot=all_snapshot(emu)
    if not snapshot or snapshot["ids"]!=list(ids):raise AssertionError("Native All selection IDs differ")
    return snapshot


def request(emu,reference):
    before=len(emu.reference_requests)
    select_reference(emu,reference)
    emu.drain()
    if len(emu.reference_requests)==before:
        emu.wait(lambda e:e.get("event")=="appmessage" and e.get("message",{}).get("0")==14,5)
    fresh=emu.reference_requests[before:]
    if len(fresh)!=1 or fresh[0]["reference"]!=reference or not fresh[0]["request"]:
        raise AssertionError("Explicit reference lookup must send exactly one matched native request")
    return fresh[0]


def result_message(token,status,clock,distances=None):
    if type(status) is not int or status not in range(10):raise ValueError("Unknown fixture status")
    if token.get("reference") not in (0,1) or any(type(token.get(key)) is not int or not 0<token[key]<=4294967295 for key in ("request","version")) or not isinstance(token.get("ids"),list) or len(token["ids"])>255:
        raise ValueError("Invalid native reference request token")
    message={"TYPE":15,"FLAGS":token["reference"],"REQUEST":token["request"],"VERSION":token["version"],"STATUS":status}
    if status in (0,1,2):
        stamp=clock.now()-(180 if status==2 else 0)
        if not 0<stamp<=4294967295:raise ValueError("Fixture timestamp outside uint32 bounds")
        message.update(STAMP=stamp,ACCURACY=150 if status==1 else 30)
    if status==0:
        distances=distances or {}
        if not distances or any(type(point) is not int or not 1<=point<=255 or point not in token["ids"] or type(metres) is not int or not 0<=metres<=40075000 for point,metres in distances.items()):
            raise ValueError("Fixture distances must use verified IDs from the native request")
        message["DATA"]=list(b"".join(struct.pack("<HI",point,metres) for point,metres in distances.items()))
    return message


def send(emu,message):
    emu.drain();emu.command("send",message=message)
    emu.wait(lambda e:e.get("event")=="sent",5)
    # STATE requests one redraw, without repeating a selection/refresh action.
    started=time.monotonic();emu.state();await_ui(emu,since=started)


def check_trip(emu,expected):
    actual=focused_trip(emu)
    if not actual or any(actual[key]!=expected[key] for key in actual):
        raise AssertionError("Native merged focused identity differs from the exact engine oracle")
    return actual


def show(emu,clock,oracle,ids,distances):
    choose_row(emu,21,0);ui_click(emu,"select",22)
    rows=oracle.query(clock.now(),ids,distances)
    if not rows:raise AssertionError("Real timetable fixture has no merged rows")
    index=native_ui(emu)["selection"]
    if index!=1:raise AssertionError("Merged board must focus its first real trip")
    check_trip(emu,rows[0])
    return rows


def controlled_packet(original,size=0,theme=0,location=False):
    packet=appearance(original,size,theme)
    packet[1]=(packet[1]&~(1|2|4))|(2 if location else 0)
    packet[2:4]=[1,0]
    packet[5]=6;packet[8:32]=[0]*24
    for index,point in enumerate((3,5,6,9,101,102)):packet[8+2*index:10+2*index]=[point,0]
    return packet


def restore_all(emu,old,point_count):
    select_reference(emu,2)
    selection(emu,old["ids"],point_count)
    if old["reference"]!=2:select_reference(emu,old["reference"])
    snapshot=all_snapshot(emu)
    if snapshot is None or snapshot["reference"]!=old["reference"] or snapshot["ids"]!=old["ids"]:
        raise AssertionError("Original All selection/reference could not be restored")
    return {"originalSelectionRestored":True,"originalReferenceRestored":True,"generation":snapshot["generation"],
            "limits":"Values restored by native UI; journal generation advances, transient distance cache is not restored"}


def scenarios(emu,original,oracle,clock,report):
    ids=[3,5,6,9,101,102];count=len(oracle.points)
    packet=controlled_packet(original)
    emu.settings(packet);emu.restart();clock.reset()
    before=len(emu.reference_requests);select_reference(emu,2)
    selection(emu,[],count);emu.restart();select_reference(emu,2)
    empty=all_snapshot(emu)
    assert empty["ids"]==[] and empty["reference"]==2,"Explicitly empty All selection must survive restart"
    report["checks"].append({"case":"explicit empty selection restart","ids":[],"generation":empty["generation"]})
    selection(emu,ids,count);persisted=all_snapshot(emu)
    emu.restart();select_reference(emu,2)
    assert all_snapshot(emu)["ids"]==ids and all_snapshot(emu)["reference"]==2
    assert len(emu.reference_requests)==before,"Manual/restart must work without requesting location"
    clock.reset();show(emu,clock,oracle,ids,{})
    capture(emu,report["captures"],"manual_offline",22,oracleTrip=focused_trip(emu))
    select_reference(emu,3)
    assert all_snapshot(emu)["ids"]==ids and all_snapshot(emu)["reference"]==2
    assert len(emu.reference_requests)==before,"Use favourites must work offline without location"
    report["checks"].append({"case":"manual/favourites offline + restart","ids":ids,"persistedGeneration":persisted["generation"],"referenceRequests":0})
    # Saving/opening settings and ordinary launch must not start a lookup.
    packet=controlled_packet(original,location=True);nearby_before=emu.location_requests
    emu.settings(packet);emu.restart();open_menu(emu,3,10)
    ui_click(emu,"select",16);ui_click(emu,"back",10)
    emu.settings(packet);assert len(emu.reference_requests)==before
    assert emu.location_requests==nearby_before,"Opening/saving settings must not request Nearby GPS"
    report["checks"].append({"case":"location enabled / startup disabled; settings and restart","referenceRequests":0,"nearbyRequests":0})
    distances={point["id"]:100+(i%2)*100 for i,point in enumerate(oracle.points) if point["verified"]}
    # Request/version/reference mismatch must leave the actual request pending.
    clock.reset();token=request(emu,0)
    if token["version"]!=oracle.version:raise AssertionError("Native dataset differs from oracle input")
    for field,value in (("REQUEST",token["request"]+1),("VERSION",token["version"]+1),("FLAGS",1)):
        wrong=result_message(token,0,clock,distances);wrong[field]=value;send(emu,wrong)
        require_view(emu,reference=0,request=token["request"],waiting=1,distances=0)
        report["checks"].append({"case":"mismatched "+field,"rejected":True})
    send(emu,result_message(token,0,clock,distances));require_view(emu,reference=0,status=0,waiting=0,distances=len(distances))
    show(emu,clock,oracle,ids,distances)
    # Known-vs-unknown and stable unknown ties use real source departures.
    rows=oracle.query(clock.now(),ids,distances)
    service_day=(clock.now()+32400)//86400
    tie=[row for row in rows if row["minute"]==606 and row["day"]==service_day]
    assert [row["point"] for row in tie]==[102,3,9],"Reviewed 10:06 real-source tie is absent"
    for index in range(min(6,len(rows))):
        choose_row(emu,22,index+1);check_trip(emu,rows[index])
    report["checks"].append({"case":"real timetable order against engine","firstSix":rows[:6],"10:06Tie":[102,3,9],
        "limits":"No equal-time pair of two verified poles exists in this source; that case remains portable-engine fixture coverage"})
    # Pick a native point while its lookup is pending, then reorder that row.
    clock.reset();token=request(emu,0);choose_point(emu,101,count)
    original_row=native_ui(emu)["selection"]
    reordered=dict(distances);reordered[101]=999
    send(emu,result_message(token,0,clock,reordered))
    assert last_choice(emu)["point"]==101,"Distance reorder lost the focused boarding point ID"
    report["checks"].append({"case":"focused point identity through rank reorder","point":101,"beforeRow":original_row,"afterRow":native_ui(emu)["selection"]})
    clock.advance(130);require_view(emu,reference=0,status=2)
    show(emu,clock,oracle,ids,{})
    report["checks"].append({"case":"current rank ageing","ageSecondsAtLeast":130,"status":2,"orderMatchesUnknownDistanceOracle":True})
    clock.reset();old_distances=len(distances);token=request(emu,1)
    require_view(emu,reference=1,waiting=1,distances=0)
    send(emu,result_message(token,0,clock,distances));require_view(emu,reference=1,status=0,distances=old_distances)
    clock.advance(130);require_view(emu,reference=1,status=0,distances=old_distances)
    show(emu,clock,oracle,ids,distances)
    report["checks"].append({"case":"saved-home rank does not age after two minutes","ageSecondsAtLeast":130,"status":0,"orderMatchesKnownDistanceOracle":True})
    clock.reset();token=request(emu,1);send(emu,result_message(token,0,clock,distances))
    focused=show(emu,clock,oracle,ids,distances)[0];before_row=native_ui(emu)["selection"]
    before=len(emu.reference_requests);send(emu,{"TYPE":16,"STATUS":0})
    require_view(emu,reference=1,status=2,waiting=0,distances=0);check_trip(emu,focused)
    report["checks"].append({"case":"focused trip identity through rank clear","trip":focused,"beforeRow":before_row,"afterRow":native_ui(emu)["selection"]})
    send(emu,{"TYPE":16,"STATUS":9});require_view(emu,reference=1,status=9,waiting=0,distances=0)
    assert len(emu.reference_requests)==before
    report["checks"].append({"case":"reference switch + saved-home changed/cleared","distancesCleared":True,"extraRequests":0})
    token=request(emu,0)
    send(emu,{"TYPE":15,"FLAGS":0,"REQUEST":token["request"],"VERSION":token["version"],"STATUS":2})
    require_view(emu,reference=0,status=2,waiting=0,distances=0)
    report["checks"].append({"case":"metadata-less stale rejection","status":2,"waiting":False,"notTimeout":True})
    for status in range(8):
        clock.reset();token=request(emu,0);send(emu,result_message(token,status,clock,distances))
        require_view(emu,reference=0,status=status,waiting=0,distances=len(distances) if status==0 else 0)
        capture(emu,report["captures"],"status_%d_%s"%(status,STATUS_NAMES[status].replace(" ","_")),21,fixtureStatus=status)
    token=request(emu,1);send(emu,result_message(token,9,clock));require_view(emu,reference=1,status=9,waiting=0,distances=0)
    emu.settings(controlled_packet(original));before=len(emu.reference_requests)
    for reference in (0,1):
        select_reference(emu,reference);require_view(emu,reference=reference,status=8,waiting=0,distances=0)
    assert len(emu.reference_requests)==before
    report["checks"].append({"case":"all ten native statuses","statuses":list(range(10)),"disabledCurrentAndHomeRequests":0,
        "limits":"Statuses/distances are explicit simulated-phone replies, not actual GPS/permission/phone tests"})
    for size in range(3):
        for theme in range(4):
            tag="size%d_theme%d"%(size,theme);packet=controlled_packet(original,size,theme,True)
            emu.settings(packet);assert emu.restart()["6"]==packet
            select_reference(emu,3)
            assert all_snapshot(emu)["ids"]==ids
            clock.reset();token=request(emu,0);send(emu,result_message(token,0,clock,distances))
            choose_point(emu,101,count)
            capture(emu,report["captures"],tag+"_point_selection",21,nativePoint=101)
            rows=show(emu,clock,oracle,ids,distances)
            long_index=next(i for i,row in enumerate(rows) if row["point"]==101)
            choose_row(emu,22,long_index+1);check_trip(emu,rows[long_index])
            capture(emu,report["captures"],tag+"_merged_identity",22,oracleTrip=rows[long_index])
            scroll_bottom(emu,22);capture(emu,report["captures"],tag+"_merged_scroll",22,oracleTrip=rows[long_index])
            ui_click(emu,"select",2);capture(emu,report["captures"],tag+"_details",2,oracleTrip=rows[long_index])
            ui_click(emu,"back",22)
            token=request(emu,1);send(emu,result_message(token,9,clock))
            require_view(emu,reference=1,status=9,waiting=0,distances=0)
            capture(emu,report["captures"],tag+"_home_unset",21)
            ui_click(emu,"select",23,long=True);capture(emu,report["captures"],tag+"_guidance",23)
            scroll_bottom(emu,23);capture(emu,report["captures"],tag+"_guidance_scroll",23)
            ui_click(emu,"back",21)
            emu.settings(controlled_packet(original,size,theme));select_reference(emu,0)
            capture(emu,report["captures"],tag+"_disabled",21)
            report["checks"].append({"case":"appearance","size":SIZES[size],"theme":THEMES[theme],"prefsPersistedAfterRestart":True})
            print("PASS All departures appearance",SIZES[size],THEMES[theme],flush=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbw",type=Path,required=True);parser.add_argument("--runtime-receipt",type=Path,required=True)
    parser.add_argument("--timetable",type=Path,required=True,help="Exact active native dataset bytes; never a regenerated substitute")
    parser.add_argument("--future-timetable",type=Path)
    parser.add_argument("--output",type=Path,required=True);parser.add_argument("--screenshot-prefix",required=True)
    parser.add_argument("--fixture-relay",action="store_true",required=True,help="Explicit opt-in to native tests with a simulated phone and scoped SDK relay swap")
    parser.add_argument("--allow-all-selection-changes",action="store_true",required=True,help="Controlled emulator only; attempts native restoration of prior All IDs/reference")
    parser.add_argument("--expect-version",default="2.0.0");parser.add_argument("--sdk-version",default="4.33.1")
    parser.add_argument("--clock",default="2026-10-01T10:05:01+09:00");parser.add_argument("--max-seconds",type=int,default=1800)
    args=parser.parse_args(argv)
    proof=artifact_proof(args.pbw,args.runtime_receipt,args.expect_version)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}",args.screenshot_prefix) or not 120<=args.max_seconds<=2400:
        raise ValueError("Use a safe capture prefix and a 120..2400 second bound")
    if dt.datetime.fromisoformat(args.clock).tzinfo is None:raise ValueError("Fixture clock must include its offset")
    if args.output.exists() or any((ROOT/"artifacts/screenshots").glob(args.screenshot_prefix+"_*.png")):
        raise FileExistsError("Never overwrite native evidence")
    oracle=Oracle(args.timetable,args.future_timetable)
    emu=None;original=old_all=None;failure=None
    report={"schema":1,"environment":"native Emery emulator with simulated phone","artifact":proof,"oracle":oracle.proof,
            "status":"failed","captures":[],"checks":[],"clockFixture":args.clock,
            "visualReview":"REQUIRED: inspect native captures for full identity, readable guidance, wrapping, contrast, Japanese and clipping",
            "limits":["No physical device or actual phone/GPS/home-coordinate acceptance","Distance/status fixtures only; every departure is from the supplied exact real binary",
                      "Prior All preferences live in separate journals: restored via native UI when IDs remain available; generations and transient ranks cannot be restored"]}
    try:
        emu=FixtureEmulator(screenshot_prefix=args.screenshot_prefix,expected_pbw=args.pbw,sdk_version=args.sdk_version,deadline=time.monotonic()+args.max_seconds)
        if emu.ready.get("observer")!="native-fixture-relay" or emu.ready.get("cachedPbwSha256")!=proof["sha256"]:
            raise AssertionError("Native fixture requires an exact PBW and an isolated SDK relay")
        state=emu.state();original=state["6"]
        if state["3"]!=oracle.version or state.get("12",0)!=(oracle.proof.get("futureVersion",0)):
            raise AssertionError("Active/pending native datasets differ from the supplied engine oracle snapshots")
        # Read the original independent All journal before temporary ordinary
        # favourites can seed an empty All journal on restart.
        emu.restart()
        old_all=all_snapshot(emu)
        if old_all is None:raise AssertionError("Original All ID/reference readback is missing; no All preferences were changed")
        report["originalAllPreferences"]=old_all
        clock=FixtureClock(emu,args.clock)
        scenarios(emu,original,oracle,clock,report)
        if sha(args.pbw.read_bytes())!=proof["sha256"]:raise AssertionError("PBW changed during native verification")
        report["status"]="native fixture checks passed; visual review required"
    except BaseException as error:
        failure=error;report["error"]=type(error).__name__+": "+str(error)
    finally:
        if emu is not None:
            emu.deadline=None
            if old_all is not None:
                try:
                    emu.settings(controlled_packet(original))
                    report["allRestoration"]=restore_all(emu,old_all,len(oracle.points))
                except Exception as error:
                    report["allRestoration"]={"originalSelectionRestored":False,"originalReferenceRestored":False,"error":str(error)}
            report["restoration"]=restore(emu,original) if original is not None else {"errors":["Original ordinary preferences unavailable"]}
            if original is None:
                try:emu.close()
                except Exception as error:report["restoration"]["errors"].append(str(error))
            report["nativeUiRedrawResyncs"]=emu.ui_resyncs
            report["normalSdkRelayRestored"]=any(e.get("event")=="fixtureRestored" and e.get("normalSdkRelayRestored") is True for e in emu.observed)
        oracle.close();report["finishedAt"]=dt.datetime.now(dt.timezone.utc).isoformat()
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x") as output:json.dump(report,output,indent=2);output.write("\n")
    if failure:raise failure
    if report.get("restoration",{}).get("errors") or not report.get("normalSdkRelayRestored") or old_all is not None and not report.get("allRestoration",{}).get("originalSelectionRestored"):
        raise RuntimeError("Native fixture restoration incomplete; inspect report before further verification")
    print("PASS native All departures fixtures; visual review REQUIRED:",args.output,flush=True)
    return report


if __name__=="__main__":main()
