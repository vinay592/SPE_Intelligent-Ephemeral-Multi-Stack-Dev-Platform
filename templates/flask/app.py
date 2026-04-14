from flask import Flask, request, jsonify
import subprocess
import tempfile

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
    <head>
    <title>Flask IDE</title>

    <style>
        body {
            background: #0f172a;
            color: #e2e8f0;
            font-family: monospace;
            padding: 20px;
        }

        h2 {
            color: #38bdf8;
        }

        textarea {
            width: 100%;
            height: 220px;
            background: #020617;
            color: #00ff9d;
            border: 1px solid #334155;
            padding: 10px;
            border-radius: 8px;
        }

        button {
            margin-top: 10px;
            padding: 10px 15px;
            background: #22c55e;
            border: none;
            color: white;
            border-radius: 6px;
            cursor: pointer;
        }

        .console {
            margin-top: 20px;
            background: #000;
            padding: 15px;
            border-radius: 8px;
            height: 250px;
            overflow-y: auto;
            white-space: pre-wrap;
        }

        .success {
            color: #22c55e;
        }

        .error {
            color: #ef4444;
        }
    </style>

    </head>

    <body>

    <h2>⚡ Flask Dev IDE</h2>

    <textarea id="code">print("Hello Flask 🚀")</textarea>

    <br>
    <button onclick="runCode()">▶ Run Code</button>

    <div class="console" id="output">Ready...</div>

    <script>
    function runCode() {
        const code = document.getElementById("code").value;

        const outputBox = document.getElementById("output");
        outputBox.innerHTML = "⏳ Running...";

        fetch("/run", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({code})
        })
        .then(res => res.json())
        .then(data => {

            if (data.error) {
                outputBox.innerHTML = "<span class='error'>" + data.error + "</span>";
            } else {
                outputBox.innerHTML = "<span class='success'>" + data.output + "</span>";
            }
        });
    }
    </script>

    </body>
    </html>
    """

@app.route('/run', methods=['POST'])
def run():
    code = request.json.get("code")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as f:
        f.write(code.encode())
        filename = f.name

    result = subprocess.run(
        ["python3", filename],
        capture_output=True,
        text=True
    )

    return jsonify({
        "output": result.stdout.strip(),
        "error": result.stderr.strip()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
