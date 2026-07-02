#!/usr/bin/env python3
"""
================================================================================
CRIMSON CLOAK iSH WRAPPER v3.1 — Maximum Sand Exploitation
Single-file iOS iSH app wrapper — ALL legitimate sandbox tricks
HTTP:8088 | WS:8089 | Auto-Discovery | Auto-Tunnel | Keepalive | Clipboard Sync
File Watcher | Network Monitor | iOS Shortcuts Trigger
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
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(line)

def touch_keepalive():
    with open(KEEPALIVE_FILE, "a") as f:
        f.write(f"{time.time()}\n")

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

def discover_tools():
    tools = []
    home = os.path.expanduser("~")
    sigs = [
        ("Huginn & Muninn", ["~/Huginn-Muninn/index.html","~/Huginn-Muninn/huginn.py"], "Tactical web platform", "recon", "huginn"),
        ("OmnINT", ["~/OmnINT/omnint_module1.py","~/OmnINT/omnint.py"], "OSINT deep-paint engine", "intel", "omnint"),
        ("Daedalus", ["~/Daedalus/daedalus.py","~/Daedalus/hardware/__init__.py"], "Zero-day hardware lab", "exploit", "daedalus"),
        ("Argus Eye", ["~/argus_eye.py","~/Argus-Eye-Repo/argus_eye.py"], "Network scanner", "recon", "argus"),
        ("Neural Chan", ["~/neural-chan/main.py","~/neural-chan/neural_chan.py"], "Multi-agent AI brain", "ai", "neural"),
        ("Crimson Cloud", ["~/Crimson-Cloud-Kali-iOS/install.sh","~/Crimson-Cloud-Kali-iOS/cc-connect"], "Cloud Kali bridge", "cloud", "crimson-cloud"),
        ("SynChan OS", ["~/SynChan/synchan.py","~/synchan_os/main.py"], "Mobile OS interface", "comms", "synchan"),
        ("Ophelia", ["~/ophelia.py","~/Ophelia/ophelia.py"], "Fingerprint engine", "recon", "ophelia"),
        ("Hecate", ["~/Hecate/hecate.py","~/heecate.py"], "OSINT platform", "intel", "hecate"),
        ("MIDAS", ["~/MIDAS/midas.py","~/midas.py"], "Financial red team", "finance", "midas"),
    ]
    for name, paths, desc, cat, tid in sigs:
        entry = next((os.path.expanduser(p) for p in paths if os.path.exists(os.path.expanduser(p))), None)
        if entry:
            tools.append({"id": tid, "name": name, "installed": True, "entry": entry,
                          "description": desc, "category": cat, "source": "signature",
                          "shortcuts": SHORTCUTS.get(tid, [])})
    for root, dirs, files in os.walk(home):
        if root.replace(home, "").count(os.sep) > 3:
            del dirs[:]; continue
        if "argus.manifest" in files:
            try:
                with open(os.path.join(root, "argus.manifest")) as f:
                    m = json.load(f)
                m.update({"installed": True, "source": "manifest",
                           "id": m.get("id", os.path.basename(root).lower()),
                           "shortcuts": m.get("shortcuts", SHORTCUTS.get(m.get("id"), []))})
                tools.append(m)
            except Exception as e:
                log(f"[DISC] Bad manifest: {e}")
    return tools

def refresh_registry():
    global TOOL_REGISTRY
    TOOL_REGISTRY = discover_tools()
    log(f"[DISC] {len(TOOL_REGISTRY)} tools registered")
    return TOOL_REGISTRY

def auto_tunnel():
    if not os.path.exists(TUNNEL_CONF):
        return
    try:
        cfg = {}
        with open(TUNNEL_CONF) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    cfg[k.strip()] = v.strip()
        if cfg.get("AUTO_START", "no").lower() != "yes":
            return
        if os.path.exists(TUNNEL_PID):
            try:
                with open(TUNNEL_PID) as fh:
                    pid = int(fh.read().strip())
                os.kill(pid, 0)
                log("[TUNNEL] Already active")
                return
            except:
                pass
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
    log("CRIMSON CLOAK iSH WRAPPER v3.1 — Maximum Sand Exploitation")
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
        while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: log("[!] Shutdown")
