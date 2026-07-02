#!/usr/bin/env python3
"""
================================================================================
CRIMSON CLOAK iSH WRAPPER v3.1
================================================================================
"""

import asyncio, json, os, sys, time, subprocess, threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

try:
    import websockets
    WS_ENABLED = True
except ImportError:
    WS_ENABLED = False

HTTP_PORT = 8088
WS_PORT = 8089
SHARED_DIR = os.path.expanduser("~/shared")
LOG_FILE = os.path.expanduser("~/.argus/wrapper.log")
TUNNEL_CONF = os.path.expanduser("~/.argus/tunnel.conf")
TUNNEL_PID = os.path.expanduser("~/.argus/tunnel.pid")
KEEPALIVE_FILE = os.path.expanduser("~/.argus/.keepalive")
CLIPBOARD_FILE = os.path.expanduser("~/.argus/.clipboard")
WATCHED_DIRS = [SHARED_DIR, os.path.expanduser("~/Downloads")]

for d in [SHARED_DIR, os.path.expanduser("~/.argus")]:
    os.makedirs(d, exist_ok=True)

WS_CLIENTS = set()
TOOL_REGISTRY = []
SYSTEM_STATS = {"started": time.time(), "commands": 0, "bytes_streamed": 0, "clipboard_syncs": 0, "file_events": 0}
LAST_CLIPBOARD = ""
FILE_SNAPSHOTS = {}

SHORTCUTS = {
    "huginn": [
        {"label": "Launch", "cmd": "cd ~/Huginn-Muninn && echo '[Huginn] Ready' && python3 -m http.server 7575 &"},
        {"label": "Recon", "cmd": "echo '[Huginn] Recon armed'"},
        {"label": "DMS", "cmd": "echo '[Huginn] DMS active'"}
    ],
    "omnint": [
        {"label": "Module 1", "cmd": "cd ~/OmnINT && python3 omnint_module1.py"},
        {"label": "Deep Paint", "cmd": "cd ~/OmnINT && python3 omnint.py --mode deep"},
        {"label": "Email", "cmd": "cd ~/OmnINT && python3 omnint.py --mode email"},
        {"label": "Report", "cmd": "cd ~/OmnINT && python3 omnint.py --report"}
    ],
    "daedalus": [
        {"label": "Safety", "cmd": "cd ~/Daedalus && python3 daedalus.py --safety-check"},
        {"label": "Hardware", "cmd": "cd ~/Daedalus && ls -la hardware/"},
        {"label": "Live", "cmd": "cd ~/Daedalus && python3 daedalus.py --safety LIVE"}
    ],
    "argus": [
        {"label": "Quick", "cmd": "cd ~ && python3 argus_eye.py --target 127.0.0.1 --quick"},
        {"label": "Full", "cmd": "cd ~ && python3 argus_eye.py --target 192.168.0.0/24"},
        {"label": "Ports", "cmd": "cd ~ && python3 argus_eye.py --target 127.0.0.1 --ports all"}
    ],
    "neural": [
        {"label": "Status", "cmd": "cd ~/neural-chan && python3 neural_chan.py --status"},
        {"label": "Query", "cmd": "cd ~/neural-chan && python3 neural_chan.py --query"},
        {"label": "Agents", "cmd": "cd ~/neural-chan && python3 neural_chan.py --agents"}
    ],
    "ophelia": [
        {"label": "FP", "cmd": "cd ~/Ophelia && python3 ophelia.py --fp"},
        {"label": "Scan", "cmd": "cd ~/Ophelia && python3 ophelia.py --scan"}
    ],
    "hecate": [
        {"label": "Run", "cmd": "cd ~/Hecate && python3 hecate.py --run"},
        {"label": "Vectors", "cmd": "cd ~/Hecate && python3 hecate.py --vectors"}
    ],
    "midas": [
        {"label": "Shadow", "cmd": "cd ~/MIDAS && python3 midas.py --tool shadowbroker"},
        {"label": "FIX", "cmd": "cd ~/MIDAS && python3 midas.py --tool fixinject"}
    ],
    "synchan": [
        {"label": "OS", "cmd": "cd ~/SynChan && python3 synchan.py"},
        {"label": "Voice", "cmd": "cd ~/SynChan && python3 synchan.py --voice"}
    ],
    "crimson-cloud": [
        {"label": "Connect", "cmd": "cd ~/Crimson-Cloud-Kali-iOS && bash cc-connect"},
        {"label": "Status", "cmd": "echo '[Crimson Cloud] Check tunnel status'"}
    ]
}

def log(msg):
    line = f"{datetime.now().strftime('%H:%M:%S')} | {msg}"
    with open(LOG_FILE, "a") as f2:
        f2.write(line + "\n")
    print(line)

def touch_keepalive():
    with open(KEEPALIVE_FILE, "a") as f2:
        f2.write(f"{time.time()}\n")

def get_clipboard():
    try:
        r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
        return r.stdout if r.returncode == 0 else ""
    except:
        return ""

def set_clipboard(text):
    try:
        subprocess.run(["pbcopy"], input=text, text=True, timeout=2)
        return True
    except:
        return False

def get_sandbox_info():
    info = {
        "cwd": os.getcwd(), "home": os.path.expanduser("~"), "shared": SHARED_DIR,
        "shared_files": os.listdir(SHARED_DIR) if os.path.exists(SHARED_DIR) else [],
        "uid": os.getuid() if hasattr(os, "getuid") else "unknown",
        "pid": os.getpid(), "ppid": os.getppid() if hasattr(os, "getppid") else "unknown",
        "clipboard_preview": get_clipboard()[:100] + "..." if len(get_clipboard()) > 100 else get_clipboard(),
        "env_keys": list(os.environ.keys()),
        "ish_version": os.environ.get("ISH_VERSION", "unknown"),
    }
    try:
        info["uname"] = subprocess.run(["uname", "-a"], capture_output=True, text=True).stdout.strip()
        info["load"] = os.getloadavg() if hasattr(os, "getloadavg") else [0, 0, 0]
        info["df"] = subprocess.run(["df", "-h"], capture_output=True, text=True).stdout.strip()
        info["mem"] = subprocess.run(["free", "-h"], capture_output=True, text=True).stdout.strip()
        info["uptime"] = subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()
    except:
        pass
    return info

def open_url_scheme(url):
    try:
        subprocess.run(["open", url], timeout=3)
        return True
    except:
        return False

def clipboard_sync_loop():
    global LAST_CLIPBOARD
    while True:
        time.sleep(5)
        try:
            current = get_clipboard()
            if current != LAST_CLIPBOARD and current:
                LAST_CLIPBOARD = current
                with open(CLIPBOARD_FILE, "w") as f2:
                    f2.write(current)
                SYSTEM_STATS["clipboard_syncs"] += 1
                if WS_CLIENTS:
                    asyncio.run_coroutine_threadsafe(
                        broadcast(json.dumps({"type": "clipboard_sync", "data": current[:200], "time": time.time()})),
                        asyncio.get_event_loop()
                    )
        except Exception as e:
            log(f"[CLIP] Sync error: {e}")

def file_watcher_loop():
    global FILE_SNAPSHOTS
    while True:
        time.sleep(3)
        try:
            for wdir in WATCHED_DIRS:
                if not os.path.exists(wdir):
                    continue
                current = {}
                for item in os.listdir(wdir):
                    fp = os.path.join(wdir, item)
                    try:
                        current[item] = os.path.getmtime(fp)
                    except:
                        pass
                prev = FILE_SNAPSHOTS.get(wdir, {})
                new_files = [k for k in current if k not in prev]
                modified = [k for k in current if k in prev and current[k] != prev[k]]
                FILE_SNAPSHOTS[wdir] = current
                for f in new_files:
                    SYSTEM_STATS["file_events"] += 1
                    if WS_CLIENTS:
                        asyncio.run_coroutine_threadsafe(
                            broadcast(json.dumps({"type": "file_event", "event": "new", "file": f, "dir": wdir, "time": time.time()})),
                            asyncio.get_event_loop()
                        )
                for f in modified:
                    if WS_CLIENTS:
                        asyncio.run_coroutine_threadsafe(
                            broadcast(json.dumps({"type": "file_event", "event": "modified", "file": f, "dir": wdir, "time": time.time()})),
                            asyncio.get_event_loop()
                        )
        except Exception as e:
            log(f"[WATCH] Error: {e}")

def keepalive_loop():
    while True:
        time.sleep(15)
        touch_keepalive()
        if WS_CLIENTS:
            asyncio.run_coroutine_threadsafe(
                broadcast(json.dumps({"type": "keepalive", "time": time.time(), "stats": SYSTEM_STATS})),
                asyncio.get_event_loop()
            )

def network_monitor_loop():
    while True:
        time.sleep(30)
        try:
            netstat = subprocess.run(["netstat", "-an"], capture_output=True, text=True, timeout=5)
            conns = len([l for l in netstat.stdout.splitlines() if "ESTABLISHED" in l or "LISTEN" in l])
            if WS_CLIENTS:
                asyncio.run_coroutine_threadsafe(
                    broadcast(json.dumps({"type": "network", "connections": conns, "time": time.time()})),
                    asyncio.get_event_loop()
                )
        except:
            pass

async def ws_handler(websocket, path):
    cid = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    log(f"[WS] + {cid}")
    WS_CLIENTS.add(websocket)
    try:
        await websocket.send(json.dumps({"type": "welcome", "client": cid,
                                          "time": time.time(), "tools": len(TOOL_REGISTRY)}))
        async for msg in websocket:
            try:
                data = json.loads(msg)
                await handle_ws_msg(websocket, data)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type": "error", "msg": "bad json"}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        WS_CLIENTS.discard(websocket)
        log(f"[WS] - {cid}")

async def stream_proc(proc, ws):
    while True:
        line = await proc.stdout.readline()
        if not line: break
        txt = line.decode().rstrip()
        SYSTEM_STATS["bytes_streamed"] += len(txt)
        await ws.send(json.dumps({"type": "stream", "s": "out", "d": txt}))
    while True:
        line = await proc.stderr.readline()
        if not line: break
        txt = line.decode().rstrip()
        SYSTEM_STATS["bytes_streamed"] += len(txt)
        await ws.send(json.dumps({"type": "stream", "s": "err", "d": txt}))

async def handle_ws_msg(ws, data):
    t = data.get("type", "unknown")
    SYSTEM_STATS["commands"] += 1
    touch_keepalive()

    if t == "discover":
        reg = refresh_registry()
        await ws.send(json.dumps({"type": "discover", "tools": reg, "count": len(reg)}))

    elif t == "exec":
        cmd = data.get("cmd", "")
        if not cmd:
            await ws.send(json.dumps({"type": "exec", "error": "no cmd"})); return
        await ws.send(json.dumps({"type": "exec", "status": "started", "cmd": cmd}))
        try:
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await stream_proc(proc, ws)
            await proc.wait()
            await ws.send(json.dumps({"type": "exec_done", "rc": proc.returncode}))
        except Exception as e:
            await ws.send(json.dumps({"type": "exec", "error": str(e)}))

    elif t == "tool_run":
        tid, args = data.get("id", ""), data.get("args", "")
        tool = next((x for x in TOOL_REGISTRY if x.get("id") == tid), None)
        if not tool:
            await ws.send(json.dumps({"type": "tool_run", "error": "not found"})); return
        entry = tool.get("entry", "")
        if not entry or not os.path.exists(entry):
            await ws.send(json.dumps({"type": "tool_run", "error": "entry missing"})); return
        cmd = f"cd {os.path.dirname(entry) or '.'} && python3 {entry} {args}"
        await ws.send(json.dumps({"type": "tool_run", "status": "started", "tool": tid, "cmd": cmd}))
        try:
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await stream_proc(proc, ws)
            await proc.wait()
            await ws.send(json.dumps({"type": "tool_run_done", "rc": proc.returncode, "tool": tid}))
        except Exception as e:
            await ws.send(json.dumps({"type": "tool_run", "error": str(e)}))

    elif t == "shortcut":
        tid, idx = data.get("id", ""), data.get("idx", 0)
        tool = next((x for x in TOOL_REGISTRY if x.get("id") == tid), None)
        if not tool:
            await ws.send(json.dumps({"type": "shortcut", "error": "not found"})); return
        sc = tool.get("shortcuts", [])
        if idx >= len(sc):
            await ws.send(json.dumps({"type": "shortcut", "error": "bad idx"})); return
        cmd, label = sc[idx].get("cmd", ""), sc[idx].get("label", "unknown")
        await ws.send(json.dumps({"type": "shortcut", "status": "started", "tool": tid, "label": label, "cmd": cmd}))
        try:
            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await stream_proc(proc, ws)
            await proc.wait()
            await ws.send(json.dumps({"type": "shortcut_done", "rc": proc.returncode, "tool": tid, "label": label}))
        except Exception as e:
            await ws.send(json.dumps({"type": "shortcut", "error": str(e)}))

    elif t == "read":
        fname = os.path.basename(data.get("file", ""))
        fpath = os.path.join(SHARED_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath) as f2:
                await ws.send(json.dumps({"type": "read", "file": fname, "content": f2.read()}))
        else:
            await ws.send(json.dumps({"type": "read", "error": "not found"}))

    elif t == "write":
        fname = os.path.basename(data.get("file", "drop.txt"))
        fpath = os.path.join(SHARED_DIR, fname)
        with open(fpath, "w") as f2:
            f2.write(data.get("content", ""))
        await ws.send(json.dumps({"type": "write", "status": "ok", "file": fname}))

    elif t == "clipboard":
        action = data.get("action", "read")
        if action == "read":
            await ws.send(json.dumps({"type": "clipboard", "data": get_clipboard()}))
        elif action == "write":
            ok = set_clipboard(data.get("text", ""))
            await ws.send(json.dumps({"type": "clipboard", "status": "written" if ok else "failed"}))

    elif t == "sandbox":
        await ws.send(json.dumps({"type": "sandbox", "data": get_sandbox_info()}))

    elif t == "files":
        d = os.path.expanduser(data.get("dir", SHARED_DIR))
        if os.path.exists(d):
            items = []
            for item in os.listdir(d):
                fp = os.path.join(d, item)
                items.append({"name": item, "type": "dir" if os.path.isdir(fp) else "file",
                              "size": os.path.getsize(fp) if os.path.isfile(fp) else 0})
            await ws.send(json.dumps({"type": "files", "dir": d, "items": items}))
        else:
            await ws.send(json.dumps({"type": "files", "error": "not found"}))

    elif t == "tunnel":
        host, user = data.get("host"), data.get("user")
        if not host or not user:
            await ws.send(json.dumps({"type": "tunnel", "error": "host/user required"})); return
        rport = data.get("remote_port", 22)
        lbind = data.get("local_bind", 9090)
        cmd = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -R {lbind}:localhost:{HTTP_PORT} {user}@{host} -p {rport} -N -f"
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await ws.send(json.dumps({"type": "tunnel", "status": "initiated"}))

    elif t == "open":
        url = data.get("url", "")
        ok = open_url_scheme(url)
        await ws.send(json.dumps({"type": "open", "status": "opened" if ok else "failed", "url": url}))

    elif t == "info":
        uname = subprocess.run(["uname", "-a"], capture_output=True, text=True)
        await ws.send(json.dumps({"type": "info", "uname": uname.stdout.strip(),
                                   "cwd": os.getcwd(), "shared": SHARED_DIR,
                                   "clients": len(WS_CLIENTS), "stats": SYSTEM_STATS,
                                   "time": time.time()}))

    elif t == "ping":
        await ws.send(json.dumps({"type": "pong", "time": time.time()}))

    else:
        await ws.send(json.dumps({"type": "error", "msg": f"unknown: {t}"}))

async def broadcast(msg):
    if WS_CLIENTS:
        await asyncio.gather(*[c.send(msg) for c in WS_CLIENTS], return_exceptions=True)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Crimson Cloak iSH</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",monospace;background:#08080c;color:#d0d0d8;min-height:100vh}
.header{background:#0f0f14;border-bottom:1px solid #1a1a24;padding:8px 12px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}
.header h1{font-size:14px;color:#dc2626;letter-spacing:2px;text-transform:uppercase}
.status{display:flex;align-items:center;gap:6px;font-size:10px}
.dot{width:7px;height:7px;border-radius:50%;background:#7f1d1d;transition:background .3s}
.dot.on{background:#16a34a}
.btn{background:#991b1b;border:none;color:#e0e0e0;padding:4px 10px;border-radius:3px;font-size:10px;cursor:pointer;transition:all .2s}
.btn:hover{background:#dc2626}
.btn-sm{padding:3px 8px;font-size:9px}
.btn-sec{background:#1e293b;border:1px solid #334155}
.btn-sec:hover{background:#334155}
.btn-dang{background:#7f1d1d}
.btn-dang:hover{background:#991b1b}
.btn-warn{background:#713f12}
.btn-warn:hover{background:#854d0e}
.btn-grn{background:#14532d}
.btn-grn:hover{background:#166534}
.container{max-width:1200px;margin:0 auto;padding:10px}
.toolbar{display:flex;gap:5px;margin-bottom:10px;flex-wrap:wrap}
.tools-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px;margin-bottom:10px}
.tool-card{background:#0f0f14;border:1px solid #1a1a24;border-radius:4px;padding:10px;transition:border-color .2s}
.tool-card:hover{border-color:#dc2626}
.tool-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px}
.tool-name{font-size:12px;font-weight:600;color:#e0e0e0}
.tool-cat{font-size:8px;padding:2px 6px;border-radius:6px;background:#450a0a;color:#f87171}
.tool-desc{font-size:9px;color:#6b7280;margin-bottom:6px;line-height:1.3}
.tool-meta{font-size:8px;color:#4b5563;margin-bottom:6px}
.shortcuts{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:6px}
.sc-btn{background:#0f172a;border:1px solid #1e293b;color:#94a3b8;padding:2px 6px;border-radius:3px;font-size:9px;cursor:pointer;transition:all .2s}
.sc-btn:hover{background:#991b1b;color:#e0e0e0;border-color:#991b1b}
.sc-btn:active{transform:scale(.95)}
.args-row{display:flex;gap:3px;margin-top:4px}
.args-row input{flex:1;background:#08080c;border:1px solid #1a1a24;color:#d0d0d8;padding:4px 6px;border-radius:3px;font-size:10px;font-family:monospace}
.args-row input:focus{outline:none;border-color:#dc2626}
.panels{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}
@media(max-width:768px){.panels{grid-template-columns:1fr}}
.panel{background:#0f0f14;border:1px solid #1a1a24;border-radius:4px;padding:8px}
.panel-title{font-size:10px;color:#f87171;margin-bottom:6px;text-transform:uppercase;letter-spacing:1px}
.terminal{background:#030305;border:1px solid #1a1a24;border-radius:4px;padding:8px;height:240px;overflow-y:auto;font-family:monospace;font-size:10px;line-height:1.4;margin-bottom:8px}
.term-line{padding:1px 0}
.term-out{color:#22c55e}
.term-err{color:#ef4444}
.term-sys{color:#3b82f6}
.term-prompt{color:#fbbf24}
.term-warn{color:#f59e0b}
.term-net{color:#a855f7}
.term-file{color:#06b6d4}
.manual{display:flex;gap:4px;padding-top:8px;border-top:1px solid #1a1a24}
.manual input{flex:1;background:#08080c;border:1px solid #1a1a24;color:#d0d0d8;padding:5px 8px;border-radius:3px;font-size:10px;font-family:monospace}
.manual input:focus{outline:none;border-color:#dc2626}
.file-list{font-family:monospace;font-size:9px;color:#9ca3af;max-height:180px;overflow-y:auto}
.file-item{padding:2px 0;border-bottom:1px solid #1a1a24;display:flex;justify-content:space-between}
.file-item:hover{background:#1a1a24}
.sb-row{display:flex;justify-content:space-between;padding:3px 0;font-size:9px;border-bottom:1px solid #1a1a24}
.sb-row{display:flex;justify-content:space-between;padding:3px 0;font-size:9px;border-bottom:1px solid #1a1a24}
.sb-key{color:#6b7280}
.sb-val{color:#d0d0d8;max-width:55%;overflow:hidden;text-overflow:ellipsis}
.stats-bar{display:flex;gap:12px;padding:6px 0;font-size:9px;color:#6b7280;border-bottom:1px solid #1a1a24;margin-bottom:8px}
.stats-bar span{color:#d0d0d8}
.empty-state{text-align:center;padding:24px;color:#4b5563;font-size:10px}
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:#08080c}
::-webkit-scrollbar-thumb{background:#334155;border-radius:2px}
</style>
</head>
<body>
<div class="header">
<h1>CRIMSON CLOAK iSH</h1>
<div class="status">
<span id="connText">Offline</span>
<div class="dot" id="connDot"></div>
<button class="btn btn-sm" onclick="discover()">DISC</button>
<button class="btn btn-sm btn-sec" onclick="clearTerm()">CLR</button>
<button class="btn btn-sm btn-warn" onclick="getSandbox()">SAND</button>
<button class="btn btn-sm btn-grn" onclick="getFiles()">FILES</button>
<button class="btn btn-sm btn-dang" onclick="abortAll()">KILL</button>
</div>
</div>
<div class="container">
<div class="stats-bar" id="statsBar">Commands: <span id="statCmds">0</span> | Streamed: <span id="statBytes">0</span>B | Clip Syncs: <span id="statClip">0</span> | File Events: <span id="statFiles">0</span></div>
<div class="toolbar">
<button class="btn" onclick="sendCmd('info')">INFO</button>
<button class="btn btn-sec" onclick="sendCmd('ping')">PING</button>
<button class="btn btn-sec" onclick="sendRaw('ls -la')">LS</button>
<button class="btn btn-sec" onclick="sendRaw('whoami')">WHO</button>
<button class="btn btn-sec" onclick="sendRaw('ps aux')">PS</button>
<button class="btn btn-sec" onclick="getClipboard()">CLIP</button>
<button class="btn btn-sec" onclick="startTunnel()">TUNNEL</button>
<button class="btn btn-sec" onclick="openApp('ish://')">iSH</button>
<button class="btn btn-sec" onclick="openApp('shortcuts://')">SHORT</button>
</div>
<div id="toolsArea" class="tools-grid"></div>
<div class="panels">
<div class="panel">
<div class="panel-title">Terminal</div>
<div class="terminal" id="terminal"></div>
<div class="manual">
<input type="text" id="cmdInput" placeholder="Raw command..." onkeydown="if(event.key==='Enter')sendManual()">
<button class="btn" onclick="sendManual()">EXEC</button>
</div>
</div>
<div class="panel">
<div class="panel-title">Sandbox Intel</div>
<div id="sandboxPanel" class="file-list">Click SAND to probe iOS sandbox...</div>
</div>
</div>
<div class="panels">
<div class="panel">
<div class="panel-title">Shared Files</div>
<div id="filesPanel" class="file-list">Click FILES to list...</div>
</div>
<div class="panel">
<div class="panel-title">Live Events</div>
<div id="eventsPanel" class="file-list">Waiting for events...</div>
</div>
</div>
</div>
<script>

const WS_URL='ws://127.0.0.1:8089';
let ws=null, tools=[], active=0, events=[];
const term=document.getElementById('terminal');
const toolsArea=document.getElementById('toolsArea');
const sbPanel=document.getElementById('sandboxPanel');
const filesPanel=document.getElementById('filesPanel');
const eventsPanel=document.getElementById('eventsPanel');
const connDot=document.getElementById('connDot');
const connText=document.getElementById('connText');

function connect(){
  try{
    ws=new WebSocket(WS_URL);
    ws.onopen=()=>{connDot.classList.add('on');connText.textContent='Online';logSys('WS connected');discover();};
    ws.onmessage=(e)=>handleMsg(JSON.parse(e.data));
    ws.onclose=()=>{connDot.classList.remove('on');connText.textContent='Offline';logSys('WS closed, retry 3s...');setTimeout(connect,3000);};
    ws.onerror=(err)=>logSys('WS error: '+err.type);
  }catch(e){logSys('Connect failed: '+e.message);}
}

function handleMsg(data){
  const t=data.type;
  if(t==='welcome'){logSys('Welcome '+data.client+' | Tools:'+data.tools);}
  else if(t==='discover'){tools=data.tools||[];renderTools();logSys('Discovered '+data.count+' tools');}
  else if(t==='exec'&&data.status==='started'){active++;logSys('EXEC: '+data.cmd);}
  else if(t==='tool_run'&&data.status==='started'){active++;logSys('TOOL['+data.tool+'] started');}
  else if(t==='shortcut'&&data.status==='started'){active++;logSys('SC['+data.tool+'/'+data.label+']');}
  else if(t==='stream'){if(data.s==='out')logOut(data.d);else logErr(data.d);}
  else if(t==='exec_done'){active--;logSys('EXEC done RC='+data.rc);}
  else if(t==='tool_run_done'){active--;logSys('TOOL['+data.tool+'] done RC='+data.rc);}
  else if(t==='shortcut_done'){active--;logSys('SC['+data.tool+'/'+data.label+'] done RC='+data.rc);}
  else if(t==='error'){logErr('ERR: '+data.msg);}
  else if(t==='info'){updateStats(data.stats);renderSys(data);}
  else if(t==='pong'){logSys('PONG');}
  else if(t==='sandbox'){renderSandbox(data.data);}
  else if(t==='files'){renderFiles(data);}
  else if(t==='clipboard'){logSys('CLIPBOARD: '+data.data.substring(0,80));}
  else if(t==='clipboard_sync'){addEvent('CLIPBOARD sync: '+data.data.substring(0,60));updateStats({clipboard_syncs:1});}
  else if(t==='file_event'){addEvent('FILE '+data.event+': '+data.file);updateStats({file_events:1});}
  else if(t==='network'){addEvent('NET: '+data.connections+' conns');}
  else if(t==='keepalive'){updateStats(data.stats);}
  else if(t==='read'){if(data.error)logErr('READ err:'+data.error);else logSys('FILE['+data.file+'] '+data.content.length+'b');}
  else if(t==='write'){logSys('WRITE '+data.file);}
  else if(t==='tunnel'){logSys('TUNNEL '+data.status);}
  else if(t==='open'){logSys('OPEN '+data.status+' '+data.url);}
}

function updateStats(s){if(!s)return;const c=document.getElementById('statCmds');const b=document.getElementById('statBytes');const cl=document.getElementById('statClip');const f=document.getElementById('statFiles');if(s.commands)c.textContent=s.commands;if(s.bytes_streamed)b.textContent=s.bytes_streamed;if(s.clipboard_syncs)cl.textContent=parseInt(cl.textContent)+s.clipboard_syncs;if(s.file_events)f.textContent=parseInt(f.textContent)+s.file_events;}

function renderTools(){
  if(!tools.length){toolsArea.innerHTML='<div class="empty-state">No tools. Install or add argus.manifest.</div>';return;}
  toolsArea.innerHTML=tools.map(tool=>{
    const sc=(tool.shortcuts||[]).map((s,i)=>`<button class="sc-btn" onclick="runShortcut('${tool.id}',${i})">${esc(s.label)}</button>`).join('');
    return `<div class="tool-card"><div class="tool-header"><span class="tool-name">${esc(tool.name)}</span><span class="tool-cat">${esc(tool.category||'misc')}</span></div><div class="tool-desc">${esc(tool.description||'')}</div><div class="tool-meta">${tool.source}|${tool.installed?'OK':'MISS'}|${esc(tool.entry||'')}</div><div class="shortcuts">${sc}</div><div class="args-row"><input type="text" id="args-${tool.id}" placeholder="args..."><button class="btn btn-sm" onclick="runTool('${tool.id}')">RUN</button></div></div>`;
  }).join('');
}

function renderSandbox(d){
  let html='';
  for(const[k,v]of Object.entries(d)){
    const val=(typeof v==='object')?JSON.stringify(v).substring(0,150):String(v).substring(0,150);
    html+=`<div class="sb-row"><span class="sb-key">${esc(k)}</span><span class="sb-val">${esc(val)}</span></div>`;
  }
  sbPanel.innerHTML=html||'No data';
}

function renderFiles(d){
  if(d.error){filesPanel.innerHTML='Error: '+esc(d.error);return;}
  let html='<div style="color:#f87171;margin-bottom:4px">'+esc(d.dir)+'</div>';
  for(const item of d.items||[]){
    const icon=item.type==='dir'?'[D]':'[F]';
    const size=item.type==='file'?(item.size+'b'):'';
    html+=`<div class="file-item"><span>${icon} ${esc(item.name)}</span><span>${size}</span></div>`;
  }
  filesPanel.innerHTML=html;
}

function addEvent(msg){
  events.unshift('['+new Date().toLocaleTimeString()+'] '+msg);
  if(events.length>50)events.pop();
  eventsPanel.innerHTML=events.map(e=>`<div class="sb-row"><span class="sb-val">${esc(e)}</span></div>`).join('');
}

function esc(s){if(!s)return'';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function logOut(s){append(s,'term-out');}
function logErr(s){append(s,'term-err');}
function logSys(s){append('['+new Date().toLocaleTimeString()+'] '+s,'term-sys');}
function append(t,c){const d=document.createElement('div');d.className='term-line '+c;d.textContent=t;term.appendChild(d);term.scrollTop=term.scrollHeight;}
function clearTerm(){term.innerHTML='';}

function discover(){if(!ws||ws.readyState!==1){logErr('Not connected');return;}ws.send(JSON.stringify({type:'discover'}));}
function sendCmd(type,extra){if(!ws||ws.readyState!==1){logErr('Not connected');return;}ws.send(JSON.stringify(Object.assign({type:type},extra||{})));}
function sendRaw(cmd){if(!ws||ws.readyState!==1){logErr('Not connected');return;}ws.send(JSON.stringify({type:'exec',cmd:cmd}));}
function sendManual(){const i=document.getElementById('cmdInput');const c=i.value.trim();if(!c)return;append('> '+c,'term-prompt');sendRaw(c);i.value='';}
function runTool(id){const args=document.getElementById('args-'+id)?.value||'';sendCmd('tool_run',{id:id,args:args});}
function runShortcut(id,idx){sendCmd('shortcut',{id:id,idx:idx});}
function getSandbox(){sendCmd('sandbox');}
function getFiles(){sendCmd('files',{dir:'~/shared'});}
function getClipboard(){sendCmd('clipboard',{action:'read'});}
function startTunnel(){sendCmd('tunnel',{host:'192.168.0.80',user:'kali'});}
function openApp(url){sendCmd('open',{url:url});}
function abortAll(){if(active>0){logSys('ABORT '+active+' procs');sendRaw('pkill -f python3');active=0;}else logSys('No active procs');}

connect();
setInterval(()=>{if(ws&&ws.readyState===1)ws.send(JSON.stringify({type:'ping'}));},30000);
</script>
</body>
</html>"""

class HTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log(f"[HTTP] {args[0]}")
    def _send(self, data, ctype="application/json", status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if isinstance(data, str):
            self.wfile.write(data.encode())
        else:
            self.wfile.write(data)
    def _json(self, data, status=200):
        self._send(json.dumps(data, indent=2), "application/json", status)

    def do_GET(self):
        p, q = urlparse(self.path), parse_qs(urlparse(self.path).query)
        if p.path == "/" or p.path == "/index.html":
            self._send(DASHBOARD_HTML, "text/html")
        elif p.path == "/health":
            self._json({"status": "alive", "ws": WS_ENABLED, "clients": len(WS_CLIENTS),
                        "tools": len(TOOL_REGISTRY), "stats": SYSTEM_STATS})
        elif p.path == "/discover":
            self._json({"tools": refresh_registry()})
        elif p.path == "/exec":
            cmd = q.get("cmd", [""])[0]
            if not cmd: self._json({"error": "no cmd"}, 400); return
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                self._json({"cmd": cmd, "rc": r.returncode, "out": r.stdout, "err": r.stderr})
            except Exception as e:
                self._json({"error": str(e)}, 500)
        elif p.path == "/read":
            f = os.path.basename(q.get("file", [""])[0])
            fp = os.path.join(SHARED_DIR, f)
            if os.path.exists(fp):
                with open(fp) as fh: self._json({"file": f, "content": fh.read()})
            else: self._json({"error": "not found"}, 404)
        elif p.path == "/files":
            d = os.path.expanduser(q.get("dir", [SHARED_DIR])[0])
            if os.path.exists(d):
                items = []
                for item in os.listdir(d):
                    fp = os.path.join(d, item)
                    items.append({"name": item, "type": "dir" if os.path.isdir(fp) else "file",
                                  "size": os.path.getsize(fp) if os.path.isfile(fp) else 0})
                self._json({"dir": d, "items": items})
            else: self._json({"error": "not found"}, 404)
        elif p.path == "/sandbox":
            self._json(get_sandbox_info())
        elif p.path == "/clipboard":
            self._json({"clipboard": get_clipboard()})
        elif p.path == "/network":
            try:
                netstat = subprocess.run(["netstat", "-an"], capture_output=True, text=True, timeout=5)
                conns = len([l for l in netstat.stdout.splitlines() if "ESTABLISHED" in l or "LISTEN" in l])
                self._json({"connections": conns})
            except:
                self._json({"error": "netstat failed"})
        else:
            self._json({"error": "unknown"}, 404)
    def do_POST(self):
        p = urlparse(self.path)
        cl = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(cl).decode()
        d = json.loads(body) if body else {}
        if p.path == "/write":
            f = os.path.basename(d.get("file", "drop.txt"))
            fp = os.path.join(SHARED_DIR, f)
            with open(fp, "w") as fh: fh.write(d.get("content", ""))
            self._json({"status": "written", "file": f})
        elif p.path == "/broadcast":
            msg = json.dumps({"type": "broadcast", "payload": d.get("payload", {}), "time": time.time()})
            asyncio.run_coroutine_threadsafe(broadcast(msg), asyncio.get_event_loop())
            self._json({"status": "broadcast", "clients": len(WS_CLIENTS)})
        elif p.path == "/clipboard":
            ok = set_clipboard(d.get("text", ""))
            self._json({"status": "written" if ok else "failed"})
        else:
            self._json({"error": "unknown"}, 404)

def run_http():
    s = HTTPServer(("127.0.0.1", HTTP_PORT), HTTPHandler)
    log(f"[HTTP] http://127.0.0.1:{HTTP_PORT}")
    s.serve_forever()

async def main():
    log("=" * 60)
    log("CRIMSON CLOAK iSH WRAPPER v3.1")
    log("=" * 60)
    refresh_registry()
    auto_tunnel()
    threading.Thread(target=run_http, daemon=True).start()
    threading.Thread(target=keepalive_loop, daemon=True).start()
    threading.Thread(target=clipboard_sync_loop, daemon=True).start()
    threading.Thread(target=file_watcher_loop, daemon=True).start()
    threading.Thread(target=network_monitor_loop, daemon=True).start()
    if WS_ENABLED:
        log(f"[WS] ws://127.0.0.1:{WS_PORT}")
        await websockets.serve(ws_handler, "127.0.0.1", WS_PORT)
        await asyncio.Future()
    else:
        log("[WS] Disabled. HTTP only.")
        while True:
            await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("[!] Shutdown")
