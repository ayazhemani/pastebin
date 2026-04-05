import os
from flask import Flask, request, render_template_string, jsonify
import redis
import secrets

app = Flask(__name__)
db = redis.Redis(host='db', port=6379, decode_responses=True)
expiration = os.environ.get('expiration_secs', None)
max_paste_size = int(os.environ.get('max_paste_size', 512 * 1024))  # 512 KB default
max_pastes_per_ip = int(os.environ.get('max_pastes_per_ip', 24))  # default to 24 pastes per IP per day
app.config['MAX_CONTENT_LENGTH'] = max_paste_size

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Auto-Sync Clipboard</title>
    <style>
        body { font-family: sans-serif; margin: 40px; background: #f8f9fa; max-width: 800px; margin: auto; padding-top: 20px; }
        textarea { width: 100%; padding: 15px; border-radius: 8px; border: 1px solid #ccc; font-family: monospace; font-size: 16px; box-sizing: border-box; resize: vertical; min-height: 300px; }
        .controls { margin-top: 15px; display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
        #status { color: #666; font-size: 0.8em; height: 20px; }
        .button-group { display: flex; gap: 10px; flex-wrap: wrap; }
        .share-section { display: flex; align-items: center; gap: 10px; width: 100%; margin-top: 5px; }
        #shareLinkDisplay { font-family: monospace; background: #eee; padding: 8px; border-radius: 4px; border: 1px solid #ddd; flex-grow: 1; font-size: 0.9em; overflow: hidden; text-overflow: ellipsis; display: none; }
        .btn { padding: 10px 20px; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; transition: background 0.2s; }
        .btn-blue { background: #007bff; }
        .btn-blue:hover { background: #0056b3; }
        .btn-green { background: #28a745; }
        .btn-green:hover { background: #218838; }
    </style>
</head>
<body>
    <h2>📋 Cloud Clipboard</h2>
    
    <textarea id="editor" rows="15" placeholder="Start typing...">{{ content }}</textarea>

    <div class="controls">
        <div id="status">Ready</div>
        <div class="button-group">
            <button id="copyTextBtn" class="btn btn-green" onclick="copyRawText()">📄 Copy Text</button>
            <button id="shareBtn" class="btn btn-blue" onclick="generateAndCopy()">🔗 Generate & Copy Link</button>
        </div>
        <div class="share-section">
            <div id="shareLinkDisplay"></div>
        </div>
    </div>

    <script>
        const editor = document.getElementById('editor');
        const status = document.getElementById('status');
        const shareBtn = document.getElementById('shareBtn');
        const copyTextBtn = document.getElementById('copyTextBtn');
        const shareDisplay = document.getElementById('shareLinkDisplay');
        let timeout = null;

        editor.addEventListener('input', () => {
            status.innerText = 'Typing...';
            shareDisplay.style.display = 'none'; 
            clearTimeout(timeout);
            timeout = setTimeout(autosave, 600);
        });

        async function autosave() {
            if (!editor.value.trim()) return;
            status.innerText = 'Syncing...';
            try {
                await fetch('/autosave', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: new URLSearchParams({'content': editor.value})
                });
                status.innerText = 'Synced to global scratchpad';
            } catch (err) {
                status.innerText = 'Sync failed';
            }
        }

        async function generateAndCopy() {
            status.innerText = 'Generating link...';
            try {
                const response = await fetch('/share', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: new URLSearchParams({'content': editor.value})
                });
                const data = await response.json();
                if (data.status === 'success') {
                    const url = window.location.origin + '/' + data.id;
                    shareDisplay.innerText = url;
                    shareDisplay.style.display = 'block';
                    await navigator.clipboard.writeText(url);
                    flashButton(shareBtn, '✅ Link Copied!');
                }
            } catch (err) {
                status.innerText = 'Failed to generate link';
            }
        }

        async function copyRawText() {
            await navigator.clipboard.writeText(editor.value);
            flashButton(copyTextBtn, '✅ Text Copied!');
        }

        function flashButton(btn, text) {
            const originalText = btn.innerText;
            btn.innerText = text;
            setTimeout(() => { btn.innerText = originalText; }, 2000);
        }
    </script>
</body>
</html>
'''

@app.errorhandler(413)
def too_large(e):
    return jsonify({"status": "error", "message": "Content too large"}), 413

@app.route('/')
def index():
    # Load the latest shared content or the scratchpad
    content = db.get('global_scratchpad') or ""
    return render_template_string(HTML_TEMPLATE, content=content)

@app.route('/autosave', methods=['POST'])
def autosave():
    content = request.form.get('content', '')
    db.set('global_scratchpad', content)
    return jsonify({"status": "success"})

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"status": "error", "message": "Paste limit reached for your IP"}), 429

@app.route('/share', methods=['POST'])
def share():
    content = request.form.get('content', '')
    if not content:
        return jsonify({"status": "error"}), 400

    ip = request.remote_addr
    rate_key = f"rate:{ip}"
    count = db.incr(rate_key)
    if count == 1:
        db.expire(rate_key, 86400)  # reset counter after 24 hours
    if count > max_pastes_per_ip:
        return rate_limited(None)

    paste_id = secrets.token_urlsafe(6)
    db.set(paste_id, content, ex=expiration)
    return jsonify({"status": "success", "id": paste_id})

@app.route('/<paste_id>')
def get_paste(paste_id):
    content = db.get(paste_id)
    if content:
        # Instead of a read-only view, we load the editor with this content
        return render_template_string(HTML_TEMPLATE, content=content)
    return "Paste not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)