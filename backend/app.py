from flask import Flask, request, jsonify
import uuid
import subprocess
import threading
import time
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

STACK_CONFIG = {
    "flask": {"image": "vinayvb18/flask-env:v1", "port": 5001},
    "mern": {"image": "vinayvb18/mern-env:v1", "port": 3000},
    "java": {"image": "vinayvb18/java-env:v1", "port": 8082},
    "ml": {"image": "vinayvb18/ml-env:v1", "port": 8888}
}

NAMESPACE = "dev-platform"
active_envs = {}
active_color = {}

# ---------------- DELETE FUNCTION ----------------
def delete_k8s_resources(name):
    print(f"Deleting resources for {name}", flush=True)

    subprocess.run(
        ["kubectl", "delete", "deployment", name, "-n", NAMESPACE, "--ignore-not-found"],
        check=False
    )

    subprocess.run(
        ["kubectl", "delete", "svc", f"{name}-svc", "-n", NAMESPACE, "--ignore-not-found"],
        check=False
    )

# ---------------- TTL THREAD (PER ENV) ----------------
def delete_env_after_ttl(env_name, user, ttl):
    time.sleep(ttl)

    print(f"[TTL THREAD] Deleting {env_name}", flush=True)

    delete_k8s_resources(env_name)

    if user in active_envs:
        active_envs[user] = [
            env for env in active_envs[user]
            if env["name"] != env_name
        ]

# ---------------- GLOBAL CLEANUP ----------------
TTL = 1800  # 30 mins

def cleanup_expired_envs():
    while True:
        time.sleep(60)

        now = time.time()

        for user in list(active_envs.keys()):
            updated_envs = []

            for env in active_envs[user]:
                created_at = env.get("created_at", now)
                age = now - created_at

                if age < TTL:
                    updated_envs.append(env)
                else:
                    print(f"[AUTO CLEANUP] Removing {env['name']}", flush=True)
                    delete_k8s_resources(env["name"])

            active_envs[user] = updated_envs

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return "Dev Platform Backend Running 🚀"

@app.route('/envs', methods=['GET'])
def list_envs():
    return jsonify(get_k8s_envs())

@app.route('/delete-env', methods=['POST'])
def delete_env():
    data = request.json
    env_name = data.get("env_name")

    if not env_name:
        return jsonify({"error": "env_name required"}), 400

    delete_k8s_resources(env_name)

    for user in active_envs:
        active_envs[user] = [
            env for env in active_envs[user]
            if env["name"] != env_name
        ]

    return jsonify({
        "status": "deleted",
        "env_name": env_name
    })

# ---------------- CREATE ENV ----------------
@app.route('/create-env', methods=['POST'])
def create_env():
    try:
        data = request.json
        user = data.get("user", "default")

        if not data or "stack" not in data:
            return jsonify({"error": "Stack is required"}), 400

        stack = data["stack"]

        if stack not in STACK_CONFIG:
            return jsonify({"error": "Invalid stack"}), 400

        print("User:", user, flush=True)

        # COLOR LOGIC
        key = f"{user}-{stack}"

        if key not in active_color:
            color = "blue"
            active_color[key] = "blue"
        else:
            current = active_color[key]
            color = "green" if current == "blue" else "blue"
            active_color[key] = color

        cpu = data.get("cpu", "100m")
        memory = data.get("memory", "128Mi")

        env_id = str(uuid.uuid4())[:6]
        env_name = f"{user}-{stack}-{color}-{env_id}"

        config = STACK_CONFIG[stack]
        image = config["image"]
        port = config["port"]

        current_envs = get_k8s_envs().get(user, [])

        if len(current_envs) >= 3:
            return jsonify({"error": "Max 3 environments allowed"}), 400

        # ---------------- DEPLOYMENT ----------------
        deployment_yaml = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {env_name}
  namespace: {NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {env_name}
  template:
    metadata:
      labels:
        app: {env_name}
    spec:
      containers:
      - name: app-container
        image: {image}
        ports:
        - containerPort: {port}
        resources:
          limits:
            memory: "{memory}"
            cpu: "{cpu}"
"""

        # ---------------- SERVICE ----------------
        service_name = f"{env_name}-svc"
        node_port = 30000 + int(env_id[:3], 16) % 2000

        service_yaml = f"""
apiVersion: v1
kind: Service
metadata:
  name: {service_name}
  namespace: {NAMESPACE}
spec:
  type: NodePort
  selector:
    app: {env_name}
  ports:
    - port: 80
      targetPort: {port}
      nodePort: {node_port}
"""

        dep_file = f"/tmp/deploy-{env_id}.yaml"
        svc_file = f"/tmp/service-{env_id}.yaml"

        with open(dep_file, "w") as f:
            f.write(deployment_yaml)

        with open(svc_file, "w") as f:
            f.write(service_yaml)

        subprocess.run(["kubectl", "apply", "-f", dep_file], check=True)
        subprocess.run(["kubectl", "apply", "-f", svc_file], check=True)

        # ---------------- TRACK ----------------
        if user not in active_envs:
            active_envs[user] = []

        active_envs[user].append({
            "name": env_name,
            "port": node_port,
            "created_at": time.time()
        })

        # ---------------- LIMIT ----------------
        if len(active_envs[user]) > 3:
            old_env = active_envs[user].pop(0)
            print("Deleting oldest:", old_env, flush=True)
            delete_k8s_resources(old_env["name"])

        # ---------------- TTL THREAD ----------------
        threading.Thread(
            target=delete_env_after_ttl,
            args=(env_name, user, TTL),
            daemon=True
        ).start()

        return jsonify({
            "env_name": env_name,
            "access_port": node_port,
            "status": "created"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- START ----------------
if __name__ == '__main__':
    threading.Thread(target=cleanup_expired_envs, daemon=True).start()
    app.run(debug=True, host='0.0.0.0', port=5001)
