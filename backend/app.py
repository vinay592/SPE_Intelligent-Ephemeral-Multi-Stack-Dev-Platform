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

    deployment_yaml = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: env-{env_id}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: env-{env_id}
  template:
    metadata:
      labels:
        app: env-{env_id}
    spec:
      containers:
      - name: flask-container
        image: flask-env
        imagePullPolicy: Never
        ports:
        - containerPort: 5001
        resources:
          limits:
            memory: "{memory}"
            cpu: "{cpu}"
"""

    file_path = f"/tmp/env-{env_id}.yaml"

    with open(file_path, "w") as f:
        f.write(deployment_yaml)

    os.system(f"kubectl apply -f {file_path}")

    return jsonify({
        "env_id": env_id,
        "status": "created"
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
