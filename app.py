"""
Blog Optimization Pipeline — Replit Dashboard
Flask web UI to trigger and monitor pipeline.py runs.
"""

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, request

app = Flask(__name__)

# ── State ─────────────────────────────────────────────────────────────────────
_run_lock = threading.Lock()
_is_running = False
_log_queue: queue.Queue = queue.Queue()

WORKSPACE_ROOT = Path(__file__).parent
PIPELINE_CMD = [sys.executable, str(WORKSPACE_ROOT / "execution" / "pipeline.py")]


# ── Queue stats helper ────────────────────────────────────────────────────────

def _get_queue_stats() -> dict:
    """Read Status column from Google Sheet and return counts. Returns '?' on error."""
    try:
        sys.path.insert(0, str(WORKSPACE_ROOT / "execution"))
        from config import load_config
        from sheets_client import SheetsClient

        cfg = load_config()
        sheets = SheetsClient(cfg)
        all_rows = sheets._get_all_rows()
        counts = {"Pending": 0, "Done": 0, "Error": 0, "Total": 0}
        for row in all_rows[1:]:  # skip header
            if len(row) < 17:
                continue
            status = row[16].strip() if len(row) > 16 else ""  # col Q = Status
            counts["Total"] += 1
            if status == "Pending":
                counts["Pending"] += 1
            elif status in ("Awaiting_Review", "Done", "Optimizing"):
                counts["Done"] += 1
            elif status == "Error":
                counts["Error"] += 1
        return counts
    except Exception as e:
        return {"Pending": "?", "Done": "?", "Error": "?", "Total": "?", "fetch_error": str(e)}


# ── Background runner ─────────────────────────────────────────────────────────

def _run_pipeline(limit):
    global _is_running
    cmd = PIPELINE_CMD.copy()
    if limit:
        cmd += ["--limit", str(limit)]

    _log_queue.put(f"[dashboard] Starting: {' '.join(cmd)}\n")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(WORKSPACE_ROOT),
            bufsize=1,
        )
        for line in proc.stdout:
            _log_queue.put(line)
        proc.wait()
        _log_queue.put(f"[dashboard] Process exited with code {proc.returncode}\n")
    except Exception as e:
        _log_queue.put(f"[dashboard] ERROR launching pipeline: {e}\n")
    finally:
        _is_running = False
        _log_queue.put(None)  # sentinel — signals SSE stream to close


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    stats = _get_queue_stats()
    status_label = "Running" if _is_running else "Idle"
    status_color = "#e8a800" if _is_running else "#2ecc71"
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blog Pipeline Dashboard</title>
<style>
  body{{font-family:system-ui,sans-serif;max-width:700px;margin:0 auto;padding:20px;background:#f5f5f5}}
  h1{{font-size:1.4rem;margin-bottom:4px}}
  .subtitle{{color:#666;font-size:.85rem;margin-bottom:20px}}
  .cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
  .card{{background:#fff;border-radius:8px;padding:14px 20px;min-width:100px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
  .card .num{{font-size:2rem;font-weight:700}}
  .card .label{{font-size:.75rem;color:#888;text-transform:uppercase}}
  .status{{display:inline-block;background:{status_color};color:#fff;border-radius:4px;padding:3px 10px;font-size:.85rem;font-weight:600;margin-bottom:16px}}
  .buttons{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px}}
  button{{padding:10px 18px;border:none;border-radius:6px;background:#3b5bdb;color:#fff;font-size:.9rem;cursor:pointer;font-weight:600}}
  button:hover{{background:#2f4ac0}}
  #log{{background:#1a1a2e;color:#a9dc76;font-family:monospace;font-size:.78rem;padding:14px;border-radius:8px;height:340px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}}
</style></head><body>
<h1>Blog Pipeline — Dr. Mitra</h1>
<div class="subtitle">SEO optimization queue dashboard</div>
<div class="cards">
  <div class="card"><div class="num">{stats.get('Pending','?')}</div><div class="label">Pending</div></div>
  <div class="card"><div class="num">{stats.get('Done','?')}</div><div class="label">Done</div></div>
  <div class="card"><div class="num">{stats.get('Error','?')}</div><div class="label">Errors</div></div>
  <div class="card"><div class="num">{stats.get('Total','?')}</div><div class="label">Total</div></div>
</div>
<div class="status">{status_label}</div>
<div class="buttons">
  <button onclick="run(1)">Run 1</button>
  <button onclick="run(5)">Run 5</button>
  <button onclick="run(10)">Run 10</button>
  <button onclick="run(0)">Run All Pending</button>
</div>
<div id="log">Logs will appear here when a run starts...</div>
<script>
const logEl=document.getElementById("log");
let es=null;
function run(n){{
  fetch("/run",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{limit:n||null}})}})
  .then(r=>r.json()).then(d=>{{
    if(d.error){{logEl.textContent="ERROR: "+d.error;return;}}
    logEl.textContent="";
    if(es)es.close();
    es=new EventSource("/stream");
    es.onmessage=e=>{{logEl.textContent+=e.data+"\\n";logEl.scrollTop=logEl.scrollHeight;}};
    es.onerror=()=>{{es.close();es=null;}};
  }});
}}
</script>
</body></html>"""
    return html


@app.route("/run", methods=["POST"])
def start_run():
    global _is_running
    with _run_lock:
        if _is_running:
            return jsonify({"error": "A run is already in progress."}), 409
        data = request.get_json(force=True, silent=True) or {}
        limit = data.get("limit") or None
        _is_running = True
        while not _log_queue.empty():
            try:
                _log_queue.get_nowait()
            except queue.Empty:
                break
        t = threading.Thread(target=_run_pipeline, args=(limit,), daemon=True)
        t.start()
    return jsonify({"started": True, "limit": limit})


@app.route("/stream")
def stream():
    def generate():
        while True:
            try:
                line = _log_queue.get(timeout=30)
                if line is None:
                    yield "data: [RUN COMPLETE]\n\n"
                    break
                yield f"data: {line.rstrip()}\n\n"
            except queue.Empty:
                yield "data: [waiting...]\n\n"
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
