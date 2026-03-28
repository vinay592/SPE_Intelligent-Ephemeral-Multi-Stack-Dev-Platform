from flask import Flask, request, jsonify
import os
import uuid

app = Flask(__name__)


@app.route('/')
def home():
    return "Dev Platform Backend Running"


@app.route('/create-env', methods=['POST'])
def create_env():
    data = request.json

    stack = data.get("stack")
    cpu = data.get("cpu")
    memory = data.get("memory")

    env_id = str(uuid.uuid4())[:6]

    print(f"Creating environment {env_id} with {stack}")

    os.system("kubectl apply -f ../k8s/deployment.yaml")

    return jsonify({
        "env_id": env_id,
        "status": "created",
        "stack": stack
    })


@app.route('/delete-env/<env_id>', methods=['DELETE'])
def delete_env(env_id):
    print(f"Deleting environment {env_id}")

    os.system("kubectl delete deployment flask-env")

    return jsonify({
        "env_id": env_id,
        "status": "deleted"
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
