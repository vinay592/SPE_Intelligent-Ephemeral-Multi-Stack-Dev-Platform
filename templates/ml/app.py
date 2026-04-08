from flask import Flask, request, render_template_string

app = Flask(__name__)

code_store = {"code": "print('Hello ML 🚀')"}

@app.route('/')
def home():
    return render_template_string("""
    <h2>ML Dev Environment 🚀</h2>

    <form method="POST" action="/run">
        <textarea name="code" rows="10" cols="50">{{code}}</textarea><br><br>
        <button type="submit">Run</button>
    </form>

    <pre>{{output}}</pre>
    """, code=code_store["code"], output="")

@app.route('/run', methods=['POST'])
def run():
    code = request.form['code']
    code_store["code"] = code

    try:
        exec(code)
        output = "Executed successfully"
    except Exception as e:
        output = str(e)

    return render_template_string("""
    <h2>ML Dev Environment 🚀</h2>

    <form method="POST" action="/run">
        <textarea name="code" rows="10" cols="50">{{code}}</textarea><br><br>
        <button type="submit">Run</button>
    </form>

    <pre>{{output}}</pre>
    """, code=code_store["code"], output=output)

app.run(host='0.0.0.0', port=8888)
