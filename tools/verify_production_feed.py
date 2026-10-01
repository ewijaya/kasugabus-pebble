#!/usr/bin/env python3
"""Observe production HTTPS through the installed PBW worker and native Emery.

Never installs a PBW, substitutes JavaScript, sends AppMessages, changes
preferences, or selects an alternate feed. Requires auto checks off, a Home
default point and an already restored baseline. The live feed must have one
current release and no upcoming release for this focused acceptance check.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
URL = "https://ewijaya.github.io/kasugabus-pebble/timetables/manifest.json"
UUID = "d7ba77b0-d528-4cc8-b35c-7052798152c9"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def read_https(url, maximum):
    require(url.startswith("https://ewijaya.github.io/kasugabus-pebble/timetables/"), "Unexpected production URL")
    request = Request(url, headers={"Accept-Encoding": "identity", "User-Agent": "KasugaBus-production-verifier/1"})
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        require(response.status == 200 and response.geturl() == url, "Production response redirected or is not HTTP 200")
        raw = response.read(maximum + 1)
        require(len(raw) <= maximum, "Production response exceeds its byte bound")
        headers = {key.lower(): value for key, value in response.headers.items() if key.lower() in ("content-type", "content-length", "cache-control", "access-control-allow-origin", "etag", "last-modified")}
    return raw, {"url": url, "bytes": len(raw), "sha256": sha(raw), "headers": headers}


def live_snapshot(version):
    raw, manifest_proof = read_https(URL, 8192)
    feed = json.loads(raw)
    require(feed.get("upcoming") is None and feed["current"]["version"] == version, "This focused check requires the expected current version and no upcoming feed")
    release = feed["current"]
    payload, payload_proof = read_https(release["url"], 32768)
    require(len(payload) == release["bytes"] and sha(payload) == release["sha256"] and zlib.crc32(payload) & 0xffffffff == release["crc32"], "Live payload length/SHA-256/CRC32 mismatch")
    # Independent preflight uses exactly the shipped manifest/binary parsers.
    # These validators do not perform the emulator download or transfer.
    script = "const fs=require('fs'),c=require('./src/pkjs/feed-config'),m=require('./src/pkjs/manifest'),b=require('./src/pkjs/binary');const x=JSON.parse(fs.readFileSync(0,'utf8'));if(c.manifestUrl!==x.url)throw Error('Wrong configured feed');m.validate(x.feed,c,Date.now());b.validate(x.payload,c,x.feed.current);"
    subprocess.run(["node", "-e", script], cwd=ROOT, input=json.dumps({"url": URL, "feed": feed, "payload": list(payload)}), text=True, check=True, timeout=30, capture_output=True)
    return release, {"manifest": manifest_proof, "payload": payload_proof}


def inspect_artifact(path, expected):
    raw = path.read_bytes()
    require(sha(raw) == expected, "PBW differs from the explicitly expected SHA-256")
    with zipfile.ZipFile(path) as archive:
        info = json.loads(archive.read("appinfo.json"))
        require(info["uuid"] == UUID and info["targetPlatforms"] == ["emery"], "Expected KasugaBus Emery artifact")
        require(URL in archive.read("pebble-js-app.js").decode("utf-8"), "Expected production URL is not in the frozen PBW worker")
    return {"sha256": expected, "bytes": len(raw), "version": info["versionLabel"]}


class TransferProof:
    """Bounded reconstruction of observed phone pushes plus native ACKs."""
    def __init__(self, release):
        self.release, self.request, self.session = release, None, None
        self.parts, self.acked, self.sent = {}, set(), 0
        self.begin_acked = self.commit_sent = self.committed = False
        self.success_stamp = None

    def watch(self, message):
        kind = message.get("0")
        if kind == 3 and message.get("7") == 1:
            require(self.request is None, "More than one native manual CHECK")
            self.request = message["8"]
        if kind != 8 or message.get("1") != self.session:
            return
        status, phase, sequence = message.get("7"), message.get("13"), message.get("2")
        if status == 1:
            return # Actual bounded production sender decides the retry.
        if phase == 5:
            require(status == 0 and sequence == 0, "Native BEGIN rejected")
            self.begin_acked = True
        elif phase == 6:
            require(status == 0 and sequence in self.parts, "Native CHUNK rejected or not observed")
            self.acked.add(sequence)
        elif phase == 7:
            require(status == 3 and sequence == 65535 and self.commit_sent, "Native COMMIT did not install current data")
            self.committed = True
        else:
            raise ValueError("Native ACK omitted or changed its phase FLAGS")

    def phone(self, message):
        kind = message.get("0")
        if kind == 4 and message.get("8") == self.request and self.request is not None:
            require(message.get("7") not in (4, 5, 6, 7), "Shipped worker reported feed failure/incompatibility STATUS=" + str(message.get("7")) + " REQUEST=" + str(self.request))
            if message.get("7") == 3:
                require(self.committed, "Feed success arrived without native commit proof")
                stamp = message.get("9")
                require(type(stamp) is int and 0 < stamp <= int(time.time()) + 300, "Invalid shipped-worker success timestamp")
                self.success_stamp = stamp
        if kind == 5:
            require(self.request is not None and message.get("8") == self.request, "BEGIN lacks the actual native manual CHECK request")
            require(message.get("3") == self.release["version"] and message.get("4") == self.release["bytes"] and message.get("5") == self.release["crc32"], "Observed BEGIN differs from live release")
            require(self.session in (None, message.get("1")) and message.get("1"), "Unexpected competing transfer session")
            self.session = message["1"]
        if kind in (6, 7):
            require(self.begin_acked and message.get("1") == self.session, "CHUNK/COMMIT precedes accepted BEGIN or changes session")
            if kind == 6:
                sequence, values = message.get("2"), message.get("6")
                total = math.ceil(self.release["bytes"] / 192)
                require(type(sequence) is int and 0 <= sequence < total and isinstance(values, list) and all(type(v) is int and 0 <= v <= 255 for v in values), "Malformed observed chunk")
                part = bytes(values)
                require(len(part) == min(192, self.release["bytes"] - sequence * 192), "Observed chunk length mismatch")
                require(sequence in self.parts or sequence == len(self.parts), "Observed chunks are not contiguous")
                require(sequence not in self.parts or self.parts[sequence] == part, "Duplicate chunk changed bytes")
                self.parts[sequence] = part
                self.sent += 1
            else:
                raw = b"".join(self.parts[index] for index in range(len(self.parts)))
                require(len(raw) == self.release["bytes"] and sha(raw) == self.release["sha256"] and zlib.crc32(raw) & 0xffffffff == self.release["crc32"], "Actual transferred bytes differ from the live payload")
                require(self.acked == set(self.parts), "COMMIT precedes all native chunk ACKs")
                self.commit_sent = True

    def result(self):
        require(self.committed and self.success_stamp, "Production transfer is incomplete")
        return {"request": self.request, "session": self.session, "version": self.release["version"], "uniqueChunks": len(self.parts), "chunksSent": self.sent, "nativeChunkAcks": len(self.acked), "bytes": self.release["bytes"], "sha256": self.release["sha256"], "crc32": self.release["crc32"], "successStamp": self.success_stamp}


class Emulator:
    def __init__(self, args, proof):
        self.proof, self.events, self.hello, self.latest = proof, queue.Queue(), False, None
        self.process = subprocess.Popen([args.python, str(ROOT / "tools/emu_update_bridge.py"), "--sdk-version", args.sdk_version, "--observe-production", "--expected-pbw", str(args.pbw.resolve())], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        def read():
            for line in self.process.stdout:
                try:
                    self.events.put(json.loads(line))
                except ValueError:
                    self.events.put({"event": "error", "message": "Invalid bridge JSON"})
            self.events.put({"event": "error", "message": "Bridge process ended"})
        threading.Thread(target=read, daemon=True).start()

    def consume(self, event):
        if event.get("event") == "error":
            raise RuntimeError(event["message"])
        if event.get("event") == "phoneappmessage":
            message = event["message"]
            if message.get("0") in (1, 4, 5, 7):
                print("PHONE " + json.dumps({key: value for key, value in message.items() if key != "6"}, sort_keys=True), flush=True)
            if message.get("0") == 1:
                self.hello = True
            self.proof.phone(message)
        if event.get("event") == "appmessage":
            message = event["message"]
            if message.get("0") in (2, 3):
                print("WATCH " + json.dumps({key: value for key, value in message.items() if key != "6"}, sort_keys=True), flush=True)
            self.proof.watch(message)
            if message.get("0") == 2:
                self.latest = message
        if event.get("event") == "watchlog" and event.get("filename") == "main.c" and "Update " in event.get("message", ""):
            print("NATIVE " + event["message"], flush=True)
        if event.get("event") == "phonelog":
            print("PKJS " + event["message"], flush=True)

    def wait(self, predicate, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                event = self.events.get(timeout=max(.001, deadline - time.monotonic()))
            except queue.Empty:
                break
            self.consume(event)
            if predicate(event):
                return event
        raise TimeoutError("Production emulator evidence timed out")

    def command(self, op, **values):
        # There is deliberately no AppMessage-send route in this runner.
        require(op in ("start", "stop", "button", "close"), "Unsupported production verification action")
        self.process.stdin.write(json.dumps(dict(op=op, **values)) + "\n")
        self.process.stdin.flush()

    def restart(self):
        self.command("stop")
        self.wait(lambda e: e.get("kind") == "AppRunStateStop")
        self.hello, self.latest = False, None
        self.command("start")
        self.wait(lambda e: self.hello and self.latest is not None)
        return self.latest

    def button(self, name, **values):
        self.command("button", name=name, **values)
        self.wait(lambda e: e.get("event") == "command" and e.get("op") == "button")

    def close(self):
        if self.process.poll() is None:
            self.command("close")
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)


def verify(args):
    artifact = inspect_artifact(args.pbw, args.sha256)
    release, live = live_snapshot(args.expect_version)
    proof = TransferProof(release)
    emulator = Emulator(args, proof)
    try:
        ready = emulator.wait(lambda e: e.get("event") == "ready")
        require(ready.get("cachedPbwSha256") == artifact["sha256"], "Actual worker cache proof missing")
        before = emulator.restart()
        require(not (before.get("13", 0) & 1), "Turn automatic checks off natively before this manual acceptance check")
        require(before.get("3", 0) < release["version"] and before.get("12", 0) == 0, "Restore bundled data first; production release must be newer and pending fixtures absent")
        prefs = before.get("6", [])
        require(len(prefs) == 80 and (prefs[2] or prefs[3]), "Set a nonzero default point so launch opens Home")
        # Wait for the first frame/click provider after the actual worker STATE.
        time.sleep(.5)
        emulator.button("select", durationMs=800)
        emulator.button("down", repeat=2)
        emulator.button("select")
        emulator.button("select") # Native Data status requests a manual CHECK.
        emulator.wait(lambda e: proof.success_stamp is not None, seconds=120)
        transferred = proof.result()
        after = emulator.restart()
        require(after.get("3") == release["version"] and after.get("12", 0) == 0 and after.get("9") == proof.success_stamp, "Native active version/success timestamp did not persist across restart")
        require(after.get("6") == prefs, "Production check changed preferences")
        return {"schema": 1, "environment": "emulator", "worker": "exact cached PBW pypkjs/XHR", "artifact": artifact, "sdkVersion": ready["sdkVersion"], "live": live, "transfer": transferred, "nativeManualCheck": True, "persisted": {"activeVersion": after["3"], "pendingVersion": after.get("12", 0), "lastSuccess": after["9"]}, "pbwReinstalled": False, "preferencesChanged": False, "limits": ["Emery emulator; not Poco/PT2 physical evidence", "No upcoming production release in this focused check", "Android companion HTTPS/CORS, GPS and seven-day use remain separate"]}
    finally:
        emulator.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbw", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--expect-version", required=True, type=int)
    parser.add_argument("--sdk-version", default="4.33.1")
    parser.add_argument("--python", default=os.environ.get("KASUGABUS_PEBBLE_PYTHON", str(Path.home() / ".local/share/uv/tools/pebble-tool/bin/python")))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "Never overwrite production verification evidence")
    result = verify(args)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print("PASS production HTTPS installed-worker/native transfer + persistence: " + str(args.output))


if __name__ == "__main__":
    main()
