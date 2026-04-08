from flask import Flask, request, jsonify
import uuid
import subprocess
import threading
import time
from flask_cors import CORS
import json

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

# TTL DELETE FUNCTION
def delete_env_after_ttl(env_name, user, ttl):
    time.sleep(ttl)

    print(f"TTL expired. Deleting {env_name}", flush=True)

    subprocess.run(
        ["kubectl", "delete", "deployment", env_name, "-n", NAMESPACE],
        check=False
    )

    subprocess.run(
        ["kubectl", "delete", "svc", f"{env_name}-svc", "-n", NAMESPACE],
        check=False
    )

    if user in active_envs:
        active_envs[user] = [
            env for env in active_envs[user]
            if env["name"] != env_name
        ]

    print("After TTL cleanup:", active_envs, flush=True)


def get_k8s_envs():
    result = subprocess.check_output(
        ["kubectl", "get", "svc", "-n", NAMESPACE, "-o", "json"]
    )

    services = json.loads(result)

    envs = {}

    for svc in services["items"]:
        name = svc["metadata"]["name"]

        if "-svc" not in name:
            continue

        env_name = name.replace("-svc", "")
        user = env_name.split("-")[0]
        port = svc["spec"]["ports"][0]["nodePort"]

        if user not in envs:
            envs[user] = []

        envs[user].append({
            "name": env_name,
            "port": port
        })

    return envs


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

    subprocess.run(
        ["kubectl", "delete", "deployment", env_name, "-n", NAMESPACE],
        check=False
    )
    subprocess.run(
        ["kubectl", "delete", "svc", f"{env_name}-svc", "-n", NAMESPACE],
        check=False
    )
    # remove from active_envs
    for user in active_envs:
        active_envs[user] = [
            env for env in active_envs[user]
            if env["name"] != env_name
        ]

    return jsonify({
        "status": "deleted",
        "env_name": env_name
    })

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

        # 🔵🟢 COLOR LOGIC
        key = f"{user}-{stack}"

        if key not in active_color:
            color = "blue"
            active_color[key] = "blue"
        else:
            current = active_color[key]
            color = "green" if current == "blue" else "blue"
            active_color[key] = color

        print("Color selected:", color, flush=True)

        cpu = data.get("cpu", "100m")
        memory = data.get("memory", "128Mi")

        env_id = str(uuid.uuid4())[:6]
        env_name = f"{user}-{stack}-{color}-{env_id}"

        config = STACK_CONFIG[stack]
        image = config["image"]
        port = config["port"]

        # 🔥 REAL COUNT FROM KUBERNETES
        current_envs = get_k8s_envs().get(user, [])

        if len(current_envs) >= 3:
            return jsonify({"error": "Max 3 environments allowed"}), 400
        # DEPLOYMENT YAML
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

        # 🔥 SINGLE SERVICE PER USER-STACK
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

        # TRACK ENV
        # TRACK ENV
        if user not in active_envs:
            active_envs[user] = []

        active_envs[user].append({
          "name": env_name,
          "port": node_port
        })

        # 🔴 LIMIT = 3 ENV PER USER
        MAX_ENVS = 3

        if len(active_envs[user]) > MAX_ENVS:
            old_env = active_envs[user].pop(0)

            print("Deleting oldest env:", old_env, flush=True)

            subprocess.run(
                ["kubectl", "delete", "deployment", old_env["name"], "-n", NAMESPACE],
                check=False
            )

            subprocess.run(
                ["kubectl", "delete", "svc", f"{old_env['name']}-svc", "-n", NAMESPACE],
                check=False
            )

        print("Active Envs:", active_envs, flush=True)

        # TTL
        ttl_seconds = 1800

        threading.Thread(
            target=delete_env_after_ttl,
            args=(env_name, user, ttl_seconds),
            daemon=True
        ).start()

        return jsonify({
            "env_id": env_id,
            "env_name": env_name,
            "color": color,
            "service": service_name,
            "status": "created",
            "access_port": node_port
        })

    except subprocess.CalledProcessError:
        return jsonify({"error": "Kubernetes deployment failed"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
