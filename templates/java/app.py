from flask import Flask, request, jsonify
import subprocess
import tempfile
import os

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <html>
    <head>
        <title>Java IDE</title>

        <style>
            body {
                background: #0f172a;
                color: #e2e8f0;
                font-family: monospace;
                padding: 20px;
            }

            h2 {
                color: #f97316;
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
                background: #f97316;
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

            .success { color: #22c55e; }
            .error { color: #ef4444; }
        </style>
    </head>

    <body>

        <h2>⚡ Java Dev IDE</h2>

        <textarea id="code">
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello Java 🚀");
    }
}
        </textarea>

        <br>
        <button onclick="runCode()">▶ Run Code</button>

        <div class="console" id="output">Ready...</div>

        <script>
            function runCode() {
                const code = document.getElementById("code").value;
                const output = document.getElementById("output");

                output.innerHTML = "⏳ Running...";

                fetch("/run", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({code})
                })
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        output.innerHTML = "<span class='error'>" + data.error + "</span>";
                    } else {
                        output.innerHTML = "<span class='success'>" + data.output + "</span>";
                    }
                });
            }
        </script>

    </body>
    </html>
    '''

@app.route('/run', methods=['POST'])
def run():
    code = request.json.get("code")

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "Main.java")

        with open(file_path, "w") as f:
            f.write(code)

        # Compile
        compile_process = subprocess.run(
            ["javac", file_path],
            capture_output=True,
            text=True
        )

        if compile_process.stderr:
            return jsonify({"error": compile_process.stderr})

        # Run
        run_process = subprocess.run(
            ["java", "-cp", tmpdir, "Main"],
            capture_output=True,
            text=True
        )

        return jsonify({
            "output": run_process.stdout,
            "error": run_process.stderr
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082)
