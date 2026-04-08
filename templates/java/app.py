from flask import Flask, request, render_template_string
import subprocess

app = Flask(__name__)

code_store = {
    "code": """public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, Java 🚀");
    }
}"""
}

@app.route('/')
def home():
    return render_template_string("""
    <h2>Java Dev Environment 🚀</h2>

    <form method="POST" action="/run">
        <textarea name="code" rows="12" cols="70">{{code}}</textarea><br><br>
        <button type="submit">Run</button>
    </form>

    <pre>{{output}}</pre>
    """, code=code_store["code"], output="")

@app.route('/run', methods=['POST'])
def run():
    code = request.form['code']
    code_store["code"] = code

    with open("Main.java", "w") as f:
        f.write(code)

    try:
        subprocess.run(["javac", "Main.java"], check=True)
        output = subprocess.check_output(["java", "Main"], text=True)
    except Exception as e:
        output = str(e)

    return render_template_string("""
    <h2>Java Dev Environment 🚀</h2>

    <form method="POST" action="/run">
        <textarea name="code" rows="12" cols="70">{{code}}</textarea><br><br>
        <button type="submit">Run</button>
    </form>

    <pre>{{output}}</pre>
    """, code=code_store["code"], output=output)

app.run(host='0.0.0.0', port=8082)
