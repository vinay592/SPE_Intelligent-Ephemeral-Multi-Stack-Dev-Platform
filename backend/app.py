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
    "flask": {"image": "vinayvb18/flask-env:v2", "port": 5001},
    "mern": {"image": "vinayvb18/mern-env:v2", "port": 3000},
    "java": {"image": "vinayvb18/java-env:v2", "port": 8082},
    "ml": {"image": "vinayvb18/ml-env:v2", "port": 8888}
}

NAMESPACE = "dev-platform"
active_envs = {}
active_color = {}

# ---------------- GET ENVS ----------------
def get_k8s_envs():
    try:
        result = subprocess.check_output(
            ["kubectl", "get", "svc", "-n", NAMESPACE, "-o", "json"],
            text=True
        )

        data = json.loads(result)
        envs = {}

        for item in data["items"]:
            name = item["metadata"]["name"]

            if not name.endswith("-svc"):
                continue

            env_name = name.replace("-svc", "")
            user = env_name.split("-")[0]
            node_port = item["spec"]["ports"][0].get("nodePort")

            if user not in envs:
                envs[user] = []

            envs[user].append({
                "name": env_name,
                "port": node_port
            })

        return envs

    except Exception as e:
        print("Error fetching K8s envs:", e)
        return {}

# ---------------- DELETE ----------------
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

# ---------------- GLOBAL TTL CLEANUP ----------------
TTL = 1800  # 30 mins (change to 60 for testing)

def cleanup_expired_envs():
    while True:
        time.sleep(30)

        now = time.time()
        print("[TTL CHECK RUNNING]", flush=True)

        # 🔥 get real envs from Kubernetes
        envs = get_k8s_envs()

        for user in envs:
            for env in envs[user]:

                env_name = env["name"]

                created_at = None

                # 🔍 find created_at from active_envs
                if user in active_envs:
                    for e in active_envs[user]:
                        if e["name"] == env_name:
                            created_at = e.get("created_at")
                            break

                # ❗ skip if not tracked
                if not created_at:
                    continue

                age = now - created_at

                if age >= TTL:
                    print(f"[AUTO DELETE] {env_name}", flush=True)
                    delete_k8s_resources(env_name)

                    # 🧹 remove from active_envs also
                    active_envs[user] = [
                        e for e in active_envs[user]
                        if e["name"] != env_name
                    ]

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
#-----------------OPEN ENV--------------------
@app.route('/open-env', methods=['POST'])
def open_env():
    data = request.json
    env_name = data.get("env_name")

    try:
        output = subprocess.check_output(
            ["minikube", "service", f"{env_name}-svc", "-n", NAMESPACE, "--url"],
            text=True
        ).strip()

        return jsonify({"url": output})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
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

        key = f"{user}-{stack}"

        if key not in active_color:
            color = "blue"
            active_color[key] = "blue"
        else:
            color = "green" if active_color[key] == "blue" else "blue"
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
        imagePullPolicy: Always
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
            "created_at": time.time()   # 🔥 REQUIRED FOR TTL
        })

        # ---------------- LIMIT ----------------
        if len(active_envs[user]) > 3:
            old_env = active_envs[user].pop(0)
            print("Deleting oldest:", old_env, flush=True)
            delete_k8s_resources(old_env["name"])

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
