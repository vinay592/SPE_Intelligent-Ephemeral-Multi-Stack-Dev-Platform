const express = require("express");
const bodyParser = require("body-parser");
const { exec } = require("child_process");
const fs = require("fs");
const path = require("path");

const app = express();
app.use(bodyParser.json());

app.get("/", (req, res) => {
  res.send(`
  <html>
  <head>
    <title>MERN IDE</title>

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

      .success { color: #22c55e; }
      .error { color: #ef4444; }
    </style>

  </head>

  <body>

    <h2>⚡ MERN Dev IDE (Node.js)</h2>

    <textarea id="code">console.log("Hello MERN 🚀")</textarea>

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
          body: JSON.stringify({ code })
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
  `);
});

app.post("/run", (req, res) => {
  const code = req.body.code;

  const filePath = path.join(__dirname, "temp.js");
  fs.writeFileSync(filePath, code);

  exec(`node ${filePath}`, (err, stdout, stderr) => {
    res.json({
      output: stdout.trim(),
      error: stderr.trim()
    });
  });
});

app.listen(3000, "0.0.0.0", () => {
  console.log("MERN IDE running on port 3000");
});
