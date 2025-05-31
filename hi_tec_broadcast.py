import io
import threading
import time
from flask import Flask, Response, request, jsonify, render_template_string
import cv2
import numpy as np
from PIL import ImageGrab
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import pygetwindow as gw
import pyautogui

app = Flask(__name__)

# --- Windows-only window capture and control ---
def get_window_bbox():
    try:
        win = gw.getWindowsWithTitle("hi_tec")[0]
        return (win.left, win.top, win.right, win.bottom)
    except IndexError:
        return None

def capture_window():
    bbox = get_window_bbox()
    if not bbox:
        return None
    img = ImageGrab.grab(bbox)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def do_keypress(key):
    pyautogui.press(key)

def do_mousemove(x, y):
    pyautogui.moveTo(x, y)

def generate_stream():
    while True:
        frame = capture_window()
        if frame is None:
            time.sleep(1)
            continue
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        time.sleep(0.05)  # ~20 FPS

@app.route('/stream')
def stream():
    return Response(generate_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/command', methods=['POST'])
def command():
    data = request.json
    cmd = data.get('cmd')
    args = data.get('args', {})
    # Example: send keystroke
    if cmd == 'keypress':
        key = args.get('key')
        do_keypress(key)
        return jsonify({'status': 'ok', 'action': 'keypress', 'key': key})
    # Example: move mouse
    elif cmd == 'mousemove':
        x, y = args.get('x'), args.get('y')
        do_mousemove(x, y)
        return jsonify({'status': 'ok', 'action': 'mousemove', 'x': x, 'y': y})
    # Add more commands as needed
    return jsonify({'status': 'error', 'message': 'Unknown command'})

linked_code = "MS13579MS"

@app.route('/link', methods=['POST'])
def link_code():
    global linked_code
    data = request.json
    linked_code = data.get('code')
    return jsonify({'status': 'ok', 'message': 'Code linked successfully.'})

@app.route('/linked_code', methods=['GET'])
def get_linked_code():
    if linked_code is not None:
        return jsonify({'status': 'ok', 'code': linked_code})
    else:
        return jsonify({'status': 'empty', 'code': ''})

EDITOR_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>hi_tec Remote Control</title>
    <style>
        body {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Fira Mono', 'Consolas', 'Monaco', monospace;
            margin: 0;
            padding: 0;
        }
        .container {
            display: flex;
            flex-direction: row;
            max-width: 1200px;
            margin: 40px auto;
            background: #23272e;
            border-radius: 10px;
            box-shadow: 0 4px 24px #000a;
            padding: 0;
            min-height: 600px;
        }
        .editor-side {
            flex: 3;
            padding: 32px 24px 24px 24px;
            display: flex;
            flex-direction: column;
        }
        .editor-label {
            color: #61dafb;
            font-weight: 400;
            margin-bottom: 8px;
            font-size: 1.2rem;
        }
        .code-editor {
            flex: 1;
            background: #181a1b;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 16px;
            color: #d4d4d4;
            font-size: 1.1rem;
            font-family: 'Fira Mono', 'Consolas', 'Monaco', monospace;
            outline: none;
            resize: none;
            width: 100%;
            min-height: 400px;
        }
        .right-side {
            flex: 1;
            background: #181a1b;
            border-left: 1px solid #333;
            border-radius: 0 10px 10px 0;
            padding: 24px 16px 24px 16px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 0;
        }
        .stream-box {
            width: 100%;
            background: #23272e;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 8px;
            margin-bottom: 24px;
            display: flex;
            justify-content: center;
        }
        #stream {
            width: 100%;
            max-width: 240px;
            aspect-ratio: 16/9;
            background: #222;
            border-radius: 4px;
            box-shadow: 0 2px 8px #0007;
        }
        .command-panel {
            width: 100%;
            background: #23272e;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 16px;
        }
        label, select, input, button {
            font-family: inherit;
            font-size: 1rem;
        }
        label {
            color: #9cdcfe;
        }
        input, select {
            background: #23272e;
            color: #d4d4d4;
            border: 1px solid #444;
            border-radius: 4px;
            padding: 6px 10px;
            margin-right: 8px;
        }
        button {
            background: #61dafb;
            color: #23272e;
            border: none;
            border-radius: 4px;
            padding: 6px 18px;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover {
            background: #21a1c4;
        }
        .status {
            margin-top: 12px;
            color: #b5cea8;
        }
        @media (max-width: 900px) {
            .container { flex-direction: column; }
            .right-side, .editor-side { border-radius: 0 0 10px 10px; padding: 12px; }
            #stream { max-width: 100%; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="editor-side">
            <div class="editor-label">Code Write Pad</div>
            <textarea class="code-editor" placeholder="Write your code here..."></textarea>
        </div>
        <div class="right-side">
            <div class="stream-box">
                <img id="stream" src="/stream" alt="hi_tec stream" />
            </div>
            <div class="command-panel">
                <form id="commandForm">
                    <label for="cmd">Command:</label>
                    <select id="cmd" name="cmd">
                        <option value="keypress">Key Press</option>
                        <option value="mousemove">Mouse Move</option>
                    </select>
                    <span id="argsFields">
                        <input type="text" id="keyInput" name="key" placeholder="Key (e.g. enter)" />
                    </span>
                    <button type="submit">Send</button>
                </form>
                <div class="status" id="status"></div>
            </div>
        </div>
    </div>
    <script>
        const cmdSelect = document.getElementById('cmd');
        const argsFields = document.getElementById('argsFields');
        cmdSelect.addEventListener('change', function() {
            argsFields.innerHTML = '';
            if (this.value === 'keypress') {
                argsFields.innerHTML = '<input type="text" id="keyInput" name="key" placeholder="Key (e.g. enter)" />';
            } else if (this.value === 'mousemove') {
                argsFields.innerHTML = '<input type="number" id="xInput" name="x" placeholder="X" style="width:80px;" />' +
                                      '<input type="number" id="yInput" name="y" placeholder="Y" style="width:80px;" />';
            }
        });
        document.getElementById('commandForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const cmd = cmdSelect.value;
            let args = {};
            if (cmd === 'keypress') {
                args.key = document.getElementById('keyInput').value;
            } else if (cmd === 'mousemove') {
                args.x = parseInt(document.getElementById('xInput').value);
                args.y = parseInt(document.getElementById('yInput').value);
            }
            const res = await fetch('/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cmd, args })
            });
            const data = await res.json();
            document.getElementById('status').textContent = data.status === 'ok' ? 'Command sent!' : 'Error: ' + data.message;
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(EDITOR_HTML)

# --- Fix: Use different ports for Flask and custom HTTP server ---
SECRET_CODE = "QWERTYUIOP"
UDP_PORT = 5001
HTTP_PORT = 5002  # Changed from 5000 to 5002 to avoid conflict
FLASK_PORT = 5000  # Add this line to define FLASK_PORT for run_flask()

# 1. UDP Discovery Responder
def udp_discovery_responder():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", UDP_PORT))
    while True:
        data, addr = sock.recvfrom(1024)
        if data.decode().strip() == "DISCOVER_MASTERTEC":
            print(f"Discovery request from {addr}, sending response...")
            sock.sendto(b"MASTERTEC_HERE:OK", addr)

# 2. HTTP Server for /connect and /data
class MasterTecHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        if self.path == "/connect":
            data = json.loads(post_data)
            if data.get("secretCode") == SECRET_CODE:
                print("Android device connected with correct secret code.")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Connected")
            else:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Forbidden")
        elif self.path == "/data":
            print("Received data from Android device:", post_data.decode())
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Data received")
        else:
            self.send_response(404)
            self.end_headers()

def run_http_server():
    server = HTTPServer(('', HTTP_PORT), MasterTecHandler)
    print(f"HTTP server running on port {HTTP_PORT}")
    server.serve_forever()

# --- Fix: Run Flask and custom HTTP server in parallel threads ---
def run_flask():
    app.run(host='0.0.0.0', port=FLASK_PORT, threaded=True)

if __name__ == "__main__":
    print("[Mastertec] Starting UDP discovery responder on port", UDP_PORT)
    udp_thread = threading.Thread(target=udp_discovery_responder, daemon=True)
    udp_thread.start()

    print("[Mastertec] Starting custom HTTP server on port", HTTP_PORT)
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    print("[Mastertec] Starting Flask server on port", FLASK_PORT)
    try:
        run_flask()
    except OSError as e:
        print(f"[Mastertec] ERROR: Could not start Flask server: {e}")
        print("[Mastertec] Shutting down all services.")
        exit(1)
