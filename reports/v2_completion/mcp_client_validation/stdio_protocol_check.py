"""
Raw JSON-RPC 2.0 over STDIO check of the installed `reponeedle-mcp` server (no MCP SDK client).

Usage:
    python stdio_protocol_check.py <fixture-repo> <evidence.json> [server command ...]

Default server command: the `reponeedle-mcp` console script found on PATH.

Checks: initialize, tools/list, tools/call for all three tools, error handling (path traversal,
empty query, unknown tool), that every stdout line is a JSON-RPC 2.0 message, that diagnostics go to
stderr, clean shutdown when stdin closes, and that the fixture is not modified.
"""

import hashlib
import json
import platform
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"


def snapshot(root: Path) -> dict:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def main() -> int:
    fixture = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2])
    command = sys.argv[3:] or [shutil.which("reponeedle-mcp")]
    results = {"started_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
               "python": sys.version.split()[0], "command": command + ["--repo", "<fixture>"], "checks": []}

    def check(name, ok, detail=None):
        results["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail is not None and not isinstance(detail, (dict, list)) else ""))

    before = snapshot(fixture)
    proc = subprocess.Popen(command + ["--repo", str(fixture)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=str(fixture.parent))
    stdout_lines, stderr_chunks = queue.Queue(), []
    threading.Thread(target=lambda: [stdout_lines.put(l) for l in iter(proc.stdout.readline, b"")], daemon=True).start()
    threading.Thread(target=lambda: [stderr_chunks.append(l) for l in iter(proc.stderr.readline, b"")], daemon=True).start()

    raw_stdout = []

    def send(msg):
        proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        proc.stdin.flush()

    def response(msg_id, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = stdout_lines.get(timeout=0.5)
            except queue.Empty:
                continue
            raw_stdout.append(line)
            msg = json.loads(line)
            if msg.get("id") == msg_id:
                return msg
        raise TimeoutError(f"no response to id {msg_id}")

    def call(msg_id, name, arguments):
        send({"jsonrpc": "2.0", "id": msg_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
        return response(msg_id)

    def payload(resp):
        result = resp.get("result", {})
        if "structuredContent" in result and isinstance(result["structuredContent"], dict):
            sc = result["structuredContent"]
            return sc.get("result", sc)
        return json.loads(result["content"][0]["text"])

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
        "clientInfo": {"name": "raw-stdio-check", "version": "1.0"}}})
    init = response(1)
    info = init["result"]["serverInfo"]
    check("initialize: serverInfo", info.get("name") == "reponeedle" and info.get("version") == "1.2.0", info)
    check("initialize: protocolVersion negotiated", init["result"].get("protocolVersion") == PROTOCOL_VERSION,
          init["result"].get("protocolVersion"))
    check("initialize: tools capability advertised", "tools" in init["result"].get("capabilities", {}))
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = response(2)["result"]["tools"]
    names = sorted(t["name"] for t in tools)
    check("tools/list: exactly the three RepoNeedle tools",
          names == ["reponeedle_change_impact", "reponeedle_inspect", "reponeedle_retrieve"], names)
    results["tools"] = [{"name": t["name"], "required": t["inputSchema"].get("required", []),
                         "properties": sorted(t["inputSchema"].get("properties", {}))} for t in tools]

    insp = payload(call(3, "reponeedle_inspect", {}))
    check("tools/call reponeedle_inspect", insp["status"] == "ready" and insp["indexed_file_count"] == 10,
          f"{insp['indexed_file_count']} files indexed")
    results["inspect"] = {k: insp[k] for k in ("indexed_file_count", "indexed_path_examples", "default_ranker")}
    results["inspect"]["abstention_default_enabled"] = insp["abstention"]["default_enabled"]

    ret = payload(call(4, "reponeedle_retrieve", {
        "query": "Where is the discount applied to the cart total, and which tests cover it?", "budget_tokens": 2000}))
    paths = [f["path"] for f in ret["selected_files"]]
    check("tools/call reponeedle_retrieve: implementation and tests found",
          ret["status"] == "success" and "shopcart/pricing.py" in paths and any(p.startswith("tests/") for p in paths)
          and ret["total_tokens"] <= 2000, paths)
    results["retrieve"] = {"status": ret["status"], "task_type": ret["task_type"], "total_tokens": ret["total_tokens"],
                           "selected_files": paths, "abstention": ret["abstention"]}

    ci = payload(call(5, "reponeedle_change_impact", {"anchor_files": ["shopcart/pricing.py"]}))
    affected = [f["path"] for f in ci["affected_files"]]
    check("tools/call reponeedle_change_impact: dependants of pricing.py",
          ci["status"] == "success" and "shopcart/cart.py" in affected and "shopcart/checkout.py" in affected, affected)
    results["change_impact"] = {"anchor_files": ci["anchor_files"], "affected_files": affected,
                                "explanations": {f["path"]: f["explanation"] for f in ci["affected_files"]}}

    bad = call(6, "reponeedle_change_impact", {"anchor_files": ["../outside.py"]})
    text = json.dumps(bad)
    check("path traversal anchor rejected as a tool error", bad.get("result", {}).get("isError") is True
          and "outside.py" in text and "Traceback" not in text, bad.get("result", {}).get("content", [{}])[0].get("text"))

    # A real (synthetic) file next to the fixture, outside its root: must be refused, not read.
    outside = fixture.parent / "outside_marker.py"
    outside.write_text("OUTSIDE_MARKER = 'must never be returned'\n", encoding="utf-8")
    for msg_id, anchor in ((61, "../outside_marker.py"), (62, str(outside))):
        resp = call(msg_id, "reponeedle_change_impact", {"anchor_files": [anchor]})
        text = json.dumps(resp)
        check(f"existing file outside the root refused ({'relative' if msg_id == 61 else 'absolute'} path)",
              resp.get("result", {}).get("isError") is True and "Security boundary violation" in text
              and "must never be returned" not in text, resp.get("result", {}).get("content", [{}])[0].get("text", "")[:110])
    outside.unlink()

    empty = call(7, "reponeedle_retrieve", {"query": "   "})
    check("empty query rejected as a tool error", empty.get("result", {}).get("isError") is True,
          empty.get("result", {}).get("content", [{}])[0].get("text"))

    unknown = call(8, "no_such_tool", {})
    check("unknown tool rejected", unknown.get("result", {}).get("isError") is True or "error" in unknown,
          unknown.get("error") or unknown.get("result", {}).get("content", [{}])[0].get("text"))

    # Shutdown: closing stdin must end the server cleanly.
    t0 = time.time()
    proc.stdin.close()
    try:
        code = proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        code = "timeout"
    time.sleep(0.3)
    while not stdout_lines.empty():
        raw_stdout.append(stdout_lines.get())
    check("clean shutdown on stdin close", code == 0, f"exit code {code} after {time.time() - t0:.2f}s")

    non_jsonrpc = []
    for line in raw_stdout:
        try:
            msg = json.loads(line)
            if msg.get("jsonrpc") != "2.0":
                non_jsonrpc.append(line[:120])
        except ValueError:
            non_jsonrpc.append(line[:120])
    check("stdout carries only JSON-RPC 2.0 messages", not non_jsonrpc and raw_stdout,
          f"{len(raw_stdout)} lines, {len(non_jsonrpc)} invalid")
    stderr_text = b"".join(stderr_chunks).decode("utf-8", "replace")
    check("diagnostics on stderr", "[reponeedle-mcp] Repository indexed successfully" in stderr_text
          and "Server ready" in stderr_text)
    results["stderr_reponeedle_lines"] = [l for l in stderr_text.splitlines() if l.startswith("[reponeedle-mcp]")]

    after = snapshot(fixture)
    check("read-only: fixture unchanged (no files added, removed or modified)", before == after,
          f"{len(before)} files before, {len(after)} after")

    # Invalid repository path fails safely: exit 1, message on stderr, nothing on stdout.
    missing = str(fixture.parent / "does-not-exist")
    r = subprocess.run(command + ["--repo", missing], capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    check("invalid repository path fails safely", r.returncode == 1 and r.stdout == b""
          and b"does not exist" in r.stderr, f"exit {r.returncode}; stderr: {r.stderr.decode().strip()}")

    results["finished_utc"] = datetime.now(timezone.utc).isoformat()
    results["all_passed"] = all(c["ok"] for c in results["checks"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n{sum(c['ok'] for c in results['checks'])}/{len(results['checks'])} checks passed; evidence: {out_path}")
    return 0 if results["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
