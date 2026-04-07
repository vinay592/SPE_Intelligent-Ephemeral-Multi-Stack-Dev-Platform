from flask import Flask, request, jsonify
import uuid
import subprocess
import threading
import time

app = Flask(__name__)

STACK_CONFIG = {
    "flask": {"image": "flask-env:v1", "port": 5001},
    "mern": {"image": "mern-env:v1", "port": 3000},
    "java": {"image": "java-env:v1", "port": 8082},
    "ml": {"image": "ml-env:v1", "port": 8888}
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

    if user in active_envs and env_name in active_envs[user]:
        active_envs[user].remove(env_name)

    print("After TTL cleanup:", active_envs, flush=True)


@app.route('/')
def home():
    return "Dev Platform Backend Running 🚀"


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

        cpu = data.get("cpu", "500m")
        memory = data.get("memory", "512Mi")

        env_id = str(uuid.uuid4())[:6]
        env_name = f"{user}-{stack}-{color}-{env_id}"

        config = STACK_CONFIG[stack]
        image = config["image"]
        port = config["port"]

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
        service_name = f"{user}-{stack}-svc"

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
        if user not in active_envs:
            active_envs[user] = []

        # 🔥 DELETE OLD VERSION
        for old_env in active_envs[user]:
            if f"{user}-{stack}" in old_env and old_env != env_name:

                print("Deleting old version:", old_env, flush=True)

                subprocess.run(
                    ["kubectl", "delete", "deployment", old_env, "-n", NAMESPACE],
                    check=False
                )

        # keep only latest
        active_envs[user] = [env_name]

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
