#!/bin/bash
# Crimson Cloak iSH Wrapper Installer v3.1
set -e
echo "[+] Crimson Cloak iSH Wrapper Installer"
apk update && apk add python3 py3-pip openssh-client
pip3 install websockets
mkdir -p ~/shared ~/.argus ~/bin ~/Downloads
echo "[*] Downloading wrapper..."
curl -sL "https://raw.githubusercontent.com/synchancybersecurity/Crimson-Cloak-ISH-wrapper-iOS-/main/crimson_cloak_ish.py" -o ~/argus_ish_wrapper.py
chmod +x ~/argus_ish_wrapper.py
if ! grep -q "argus_ish_wrapper.py" ~/.profile 2>/dev/null; then
cat << 'PROFILE_EOF' >> ~/.profile

# === CRIMSON CLOAK iSH WRAPPER AUTO-START ===
if ! pgrep -f "argus_ish_wrapper.py" > /dev/null; then
    mkdir -p ~/.argus ~/shared ~/Downloads
    nohup python3 ~/argus_ish_wrapper.py > ~/.argus/wrapper.log 2>&1 &
    echo "[Crimson Cloak] Started on http://127.0.0.1:8088"
fi
alias cc-log="tail -f ~/.argus/wrapper.log"
alias cc-stop="pkill -f argus_ish_wrapper.py"
alias cc-start="nohup python3 ~/argus_ish_wrapper.py > ~/.argus/wrapper.log 2>&1 &"
alias cc-discover="curl -s http://127.0.0.1:8088/discover | python3 -m json.tool"
alias cc-health="curl -s http://127.0.0.1:8088/health | python3 -m json.tool"
PROFILE_EOF
fi
if [ ! -f ~/.argus/tunnel.conf ]; then
cat << 'TUNNEL_EOF' > ~/.argus/tunnel.conf
REMOTE_HOST=192.168.0.80
REMOTE_USER=kali
REMOTE_PORT=22
LOCAL_HTTP=8088
LOCAL_WS=8089
REMOTE_BIND_HTTP=9090
REMOTE_BIND_WS=9091
AUTO_START=no
TUNNEL_EOF
fi
nohup python3 ~/argus_ish_wrapper.py > ~/.argus/wrapper.log 2>&1 &
sleep 2
echo "[*] Crimson Cloak running at http://127.0.0.1:8088"
curl -s http://127.0.0.1:8088/health | python3 -m json.tool
