#!/usr/bin/env python3
"""Isolated synthetic loopback feed. Never modifies production data/assets.

Default runs real HTTP phone integration tests. --serve leaves a controlled
feed available for an emulator bridge; Ctrl-C stops it. The test-only HTTP
adapter is injected directly into the Node harness, never production config.
"""
import argparse
import copy
import http.server
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]


def generate(directory, origin):
    script = """
const fs=require('fs'),path=require('path'),fixture=require(process.argv[1]+'/tests/phone-fixture');
const out=process.argv[2],origin=process.argv[3],current=fixture(2),future=fixture(3,'2026-10-03');
fs.writeFileSync(path.join(out,'current.bin'),Buffer.from(current));fs.writeFileSync(path.join(out,'future.bin'),Buffer.from(future));
const feed={schema:1,coverage:'minami-kasugaoka-v1',published:'2026-10-01',current:fixture.release(current,origin+'/current.bin'),upcoming:fixture.release(future,origin+'/future.bin')};
fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify(feed));
const bad=JSON.parse(JSON.stringify(feed));bad.upcoming=null;bad.current.url=origin+'/corrupt.bin';
const corrupt=current.slice();corrupt[150]^=1;fs.writeFileSync(path.join(out,'corrupt.bin'),Buffer.from(corrupt));fs.writeFileSync(path.join(out,'corrupt.json'),JSON.stringify(bad));
const incompatible=JSON.parse(JSON.stringify(feed));incompatible.schema=2;fs.writeFileSync(path.join(out,'incompatible.json'),JSON.stringify(incompatible));
const interrupted=JSON.parse(JSON.stringify(feed));interrupted.upcoming=null;interrupted.current.url=origin+'/interrupted.bin';fs.writeFileSync(path.join(out,'interrupted.json'),JSON.stringify(interrupted));
"""
    subprocess.run(["node", "-e", script, str(ROOT), str(directory), origin], check=True)


def generate_real(directory, origin, current_version, today, future_date):
    from compile_timetable import compile_dataset
    from publish_feed import release_metadata
    baseline = json.loads((ROOT / "data/timetable.json").read_text())
    def payload(version, effective, name):
        doc = copy.deepcopy(baseline)
        doc["release_version"] = version
        doc["effective_from"] = effective
        data = compile_dataset(doc)
        (Path(directory) / name).write_bytes(data)
        return release_metadata(data, origin + "/" + name)
    current = payload(current_version, today, "current.bin")
    future = payload(current_version+1, future_date, "future.bin")
    replacement_current = payload(current_version+2, today, "replacement-current.bin")
    replacement_future = payload(current_version+3, future_date, "replacement-future.bin")
    feed = {"schema": 1, "coverage": baseline["coverage_id"], "published": today,
            "current": current, "upcoming": future, "testOnly": True}
    (Path(directory) / "manifest.json").write_text(json.dumps(feed))
    replacement = dict(feed, current=replacement_current, upcoming=replacement_future)
    (Path(directory) / "replacement.json").write_text(json.dumps(replacement))
    bad = dict(feed, current=dict(replacement_current, url=origin+"/corrupt.bin"), upcoming=None)
    corrupt = bytearray((Path(directory) / "replacement-current.bin").read_bytes())
    corrupt[150] ^= 1
    (Path(directory) / "corrupt.bin").write_bytes(corrupt)
    (Path(directory) / "corrupt.json").write_text(json.dumps(bad))
    (Path(directory) / "incompatible.json").write_text(json.dumps(dict(replacement, schema=2)))
    interrupted = dict(feed, current=dict(replacement_current, url=origin+"/interrupted.bin"), upcoming=None)
    (Path(directory) / "interrupted.json").write_text(json.dumps(interrupted))
    (Path(directory) / "fixture-description.json").write_text(json.dumps({"testOnly": True,
        "source": "Copy of validated baseline; test versions/effective dates are artificial.",
        "currentVersion": current_version, "futureVersion": current_version+1,
        "replacementCurrentVersion": current_version+2, "replacementFutureVersion": current_version+3}))


def serve(directory, port, real_data=False, current_version=2, today="2026-10-01", future_date="2026-10-03"):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path == "/interrupted.bin":
                payload = (Path(directory) / "current.bin").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload[:-20])
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.close_connection = True
                return
            super().do_GET()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    origin = f"http://127.0.0.1:{server.server_port}"
    if real_data:
        generate_real(directory, origin, current_version, today, future_date)
    else:
        generate(directory, origin)
    return server, origin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--real-data", action="store_true", help="Use isolated copies of the validated baseline for emulator transfers")
    parser.add_argument("--current-version", type=int, default=2)
    parser.add_argument("--today", default="2026-10-01")
    parser.add_argument("--future-date", default="2026-10-03")
    args = parser.parse_args()
    if args.directory:
        destination = args.directory.resolve()
        if destination == ROOT or ROOT in destination.parents:
            parser.error("Controlled feed fixtures must be outside the production repository")
    if args.current_version < 1:
        parser.error("Test release version must be positive")
    with tempfile.TemporaryDirectory(prefix="kasugabus-test-feed-") as temporary:
        directory = args.directory or Path(temporary)
        directory.mkdir(parents=True, exist_ok=True)
        server, origin = serve(directory, args.port, args.real_data, args.current_version, args.today, args.future_date)
        print(json.dumps({"testOnly": True, "origin": origin, "manifest": origin+"/manifest.json", "fixtures": str(directory)}), flush=True)
        if args.serve:
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        else:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                subprocess.run(["node", str(ROOT / "tests/run_phone_feed.js"), origin], check=True)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    main()
