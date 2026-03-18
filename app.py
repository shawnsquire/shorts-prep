import subprocess
import tempfile
import uuid
from pathlib import Path

from flask import Flask, request, send_file, jsonify

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB

UPLOAD_DIR = Path(tempfile.gettempdir()) / 'shorts-prep'
UPLOAD_DIR.mkdir(exist_ok=True)

HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shorts Prep</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #0f0f0f; color: #e1e1e1;
    min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; padding: 2rem;
  }
  h1 { font-size: 1.5rem; font-weight: 600; margin-bottom: 0.25rem; color: #fff; }
  .subtitle { font-size: 0.85rem; color: #888; margin-bottom: 2rem; }
  .drop-zone {
    width: 100%; max-width: 480px; border: 2px dashed #333;
    border-radius: 12px; padding: 3rem 2rem; text-align: center;
    cursor: pointer; transition: border-color 0.2s, background 0.2s;
  }
  .drop-zone:hover, .drop-zone.drag-over {
    border-color: #ff4444; background: rgba(255, 68, 68, 0.05);
  }
  .drop-zone.processing { pointer-events: none; border-color: #555; opacity: 0.5; }
  .drop-icon { font-size: 2.5rem; margin-bottom: 0.75rem; opacity: 0.6; }
  .drop-label { font-size: 0.95rem; color: #aaa; }
  .drop-label strong { color: #ff4444; }
  .file-types { font-size: 0.75rem; color: #666; margin-top: 0.5rem; }
  input[type="file"] { display: none; }
  .status {
    width: 100%; max-width: 480px; margin-top: 1.5rem; display: none;
  }
  .status.visible { display: block; }
  .file-name { font-size: 0.85rem; color: #ccc; margin-bottom: 0.75rem; word-break: break-all; }
  .progress-bar {
    width: 100%; height: 4px; background: #222;
    border-radius: 2px; overflow: hidden; margin-bottom: 0.75rem;
  }
  .progress-fill {
    height: 100%; background: #ff4444; width: 0%;
    transition: width 0.3s; border-radius: 2px;
  }
  .progress-fill.indeterminate {
    width: 30%; animation: slide 1.2s infinite ease-in-out;
  }
  @keyframes slide {
    0% { margin-left: 0; } 50% { margin-left: 70%; } 100% { margin-left: 0; }
  }
  .status-text { font-size: 0.8rem; color: #888; }
  .done {
    width: 100%; max-width: 480px; margin-top: 1.5rem;
    display: none; text-align: center;
  }
  .done.visible { display: block; }
  .check { font-size: 2rem; color: #4caf50; margin-bottom: 0.5rem; }
  .done-text { font-size: 0.9rem; color: #aaa; margin-bottom: 1rem; }
  .done-details {
    font-size: 0.75rem; color: #666; margin-bottom: 1.25rem;
    line-height: 1.6; text-align: left; background: #1a1a1a;
    padding: 1rem; border-radius: 8px; font-family: monospace;
  }
  .link-row {
    display: flex; align-items: center; gap: 0.5rem;
    background: #1a1a1a; border-radius: 8px; padding: 0.5rem 0.75rem;
    margin-bottom: 1.25rem; max-width: 480px;
  }
  .link-url {
    flex: 1; font-size: 0.75rem; color: #aaa; font-family: monospace;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    user-select: all;
  }
  .copy-btn {
    background: #333; border: none; color: #ccc; padding: 0.3rem 0.6rem;
    border-radius: 4px; font-size: 0.75rem; cursor: pointer;
    white-space: nowrap; transition: background 0.2s;
  }
  .copy-btn:hover { background: #444; }
  .copy-btn.copied { background: #2e7d32; color: #fff; }
  #qrCode {
    margin-bottom: 1.25rem;
  }
  #qrCode canvas { border-radius: 8px; }
  .phone-hint {
    font-size: 0.7rem; color: #555; margin-bottom: 1rem;
  }
  .btn {
    display: inline-block; padding: 0.6rem 1.5rem; background: #ff4444;
    color: #fff; border: none; border-radius: 6px; font-size: 0.9rem;
    cursor: pointer; transition: background 0.2s;
  }
  .btn:hover { background: #e03030; }
  .btn-secondary {
    background: transparent; border: 1px solid #444;
    color: #aaa; margin-left: 0.5rem;
  }
  .btn-secondary:hover { border-color: #666; color: #ccc; background: transparent; }
  .error-text {
    color: #ff6b6b; font-size: 0.85rem; margin-top: 1rem; display: none;
    max-width: 480px; word-break: break-all;
  }
  .error-text.visible { display: block; }
</style>
</head>
<body>

<h1>Shorts Prep</h1>
<p class="subtitle">Strip DaVinci timecode & fix metadata for YouTube Shorts</p>

<div class="drop-zone" id="dropZone">
  <div class="drop-icon">&#x1F4F9;</div>
  <div class="drop-label">Drop your video here or <strong>browse</strong></div>
  <div class="file-types">.mov .mp4</div>
</div>
<input type="file" id="fileInput" accept=".mov,.mp4,video/quicktime,video/mp4">

<div class="status" id="status">
  <div class="file-name" id="fileName"></div>
  <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
  <div class="status-text" id="statusText"></div>
</div>

<div class="done" id="done">
  <div class="check">&#x2713;</div>
  <div class="done-text">Ready for YouTube Shorts</div>
  <div class="done-details" id="doneDetails"></div>
  <div class="link-row">
    <span class="link-url" id="linkUrl"></span>
    <button class="copy-btn" id="copyBtn">Copy link</button>
  </div>
  <div id="qrCode"></div>
  <div class="phone-hint">Scan QR or paste link on your phone to download directly</div>
  <div>
    <a class="btn" id="downloadBtn" href="#">Download</a>
    <button class="btn btn-secondary" id="resetBtn">Process another</button>
  </div>
</div>

<p class="error-text" id="errorText"></p>

<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const statusDiv = document.getElementById('status');
const fileName = document.getElementById('fileName');
const progressFill = document.getElementById('progressFill');
const statusText = document.getElementById('statusText');
const doneDiv = document.getElementById('done');
const doneDetails = document.getElementById('doneDetails');
const downloadBtn = document.getElementById('downloadBtn');
const resetBtn = document.getElementById('resetBtn');
const errorText = document.getElementById('errorText');
const linkUrl = document.getElementById('linkUrl');
const copyBtn = document.getElementById('copyBtn');
const qrCode = document.getElementById('qrCode');

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files.length) processFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) processFile(fileInput.files[0]);
});

copyBtn.addEventListener('click', () => {
  navigator.clipboard.writeText(linkUrl.textContent).then(() => {
    copyBtn.textContent = 'Copied!';
    copyBtn.classList.add('copied');
    setTimeout(() => { copyBtn.textContent = 'Copy link'; copyBtn.classList.remove('copied'); }, 2000);
  });
});

resetBtn.addEventListener('click', () => {
  doneDiv.classList.remove('visible');
  statusDiv.classList.remove('visible');
  errorText.classList.remove('visible');
  dropZone.classList.remove('processing');
  progressFill.style.width = '0%';
  progressFill.classList.remove('indeterminate');
  fileInput.value = '';
  qrCode.innerHTML = '';
  linkUrl.textContent = '';
  copyBtn.textContent = 'Copy link';
  copyBtn.classList.remove('copied');
});

async function processFile(file) {
  if (!file.name.match(/\\.(mov|mp4)$/i)) {
    showError('Please use a .mov or .mp4 file');
    return;
  }

  errorText.classList.remove('visible');
  doneDiv.classList.remove('visible');
  dropZone.classList.add('processing');
  statusDiv.classList.add('visible');
  fileName.textContent = file.name;

  try {
    // Upload
    statusText.textContent = 'Uploading...';
    progressFill.classList.remove('indeterminate');
    const form = new FormData();
    form.append('file', file);

    const xhr = new XMLHttpRequest();
    const uploadDone = new Promise((resolve, reject) => {
      xhr.upload.addEventListener('progress', e => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          progressFill.style.width = pct + '%';
          statusText.textContent = 'Uploading... ' + pct + '%';
        }
      });
      xhr.addEventListener('load', () => resolve(xhr));
      xhr.addEventListener('error', () => reject(new Error('Upload failed')));
    });

    xhr.open('POST', '/process');
    xhr.send(form);
    await uploadDone;

    if (xhr.status !== 200) {
      const err = JSON.parse(xhr.responseText);
      throw new Error(err.error || 'Processing failed');
    }

    const result = JSON.parse(xhr.responseText);

    // Show results
    const dlPath = '/download/' + result.id;
    const fullUrl = window.location.origin + dlPath;
    doneDetails.textContent = result.summary;
    downloadBtn.href = dlPath;
    downloadBtn.download = result.output_name;
    linkUrl.textContent = fullUrl;

    // QR code
    qrCode.innerHTML = '';
    new QRCode(qrCode, { text: fullUrl, width: 160, height: 160,
      colorDark: '#ffffff', colorLight: '#1a1a1a', correctLevel: QRCode.CorrectLevel.L });

    statusDiv.classList.remove('visible');
    doneDiv.classList.add('visible');
    dropZone.classList.remove('processing');

  } catch (err) {
    showError(err.message);
    dropZone.classList.remove('processing');
    statusDiv.classList.remove('visible');
  }
}

function showError(msg) {
  errorText.textContent = msg;
  errorText.classList.add('visible');
}
</script>
</body>
</html>'''


def probe_streams(path):
    """Return ffprobe stream info as text."""
    r = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries',
         'stream=index,codec_type,codec_name,codec_tag_string',
         '-of', 'compact', path],
        capture_output=True, text=True
    )
    return r.stdout.strip()


@app.route('/')
def index():
    return HTML


@app.route('/process', methods=['POST'])
def process():
    if 'file' not in request.files:
        return jsonify(error='No file uploaded'), 400

    f = request.files['file']
    if not f.filename:
        return jsonify(error='No file selected'), 400

    job_id = uuid.uuid4().hex[:12]
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    input_path = job_dir / f'input{Path(f.filename).suffix}'
    f.save(input_path)

    base_name = Path(f.filename).stem
    output_name = f'{base_name}-shorts.mp4'
    output_path = job_dir / output_name

    # Probe before
    before = probe_streams(str(input_path))

    # Remux: strip timecode, keep only video + audio, fix for YouTube
    result = subprocess.run([
        'ffmpeg', '-y', '-i', str(input_path),
        '-map', '0:v:0', '-map', '0:a:0',
        '-c', 'copy',
        '-movflags', '+faststart',
        str(output_path)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        return jsonify(error=f'ffmpeg failed: {result.stderr[-500:]}'), 500

    # Probe after
    after = probe_streams(str(output_path))

    # Clean up input
    input_path.unlink(missing_ok=True)

    out_size = output_path.stat().st_size

    summary = (
        f"Input:  {f.filename}\n"
        f"Before: {before}\n\n"
        f"Output: {output_name}\n"
        f"After:  {after}\n\n"
        f"Size:   {out_size / 1024 / 1024:.1f} MB"
    )

    return jsonify(id=job_id, output_name=output_name, summary=summary)


@app.route('/download/<job_id>')
def download(job_id):
    job_dir = UPLOAD_DIR / job_id
    if not job_dir.exists():
        return jsonify(error='Not found'), 404
    files = list(job_dir.glob('*-shorts.mp4'))
    if not files:
        return jsonify(error='Output not found'), 404
    return send_file(files[0], as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
