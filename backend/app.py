from flask import Flask, request, jsonify
import uuid
import subprocess

app = Flask(__name__)

STACK_CONFIG = {
    "flask": {"image": "flask-env:v1", "port": 5001},
    "mern": {"image": "mern-env:v1", "port": 3000},
    "java": {"image": "java-env:v1", "port": 8082},
    "ml": {"image": "ml-env:v1", "port": 8888}
}

NAMESPACE = "dev-platform"
active_envs = {}

@app.route('/')
def home():
    return "Dev Platform Backend Running 🚀"


@app.route('/create-env', methods=['POST'])
def create_env():
    try:
        data = request.json

        user = data.get("user", "default")
        print("User:", user, flush=True)

        if not data or "stack" not in data:
            return jsonify({"error": "Stack is required"}), 400

        stack = data["stack"]

        if stack not in STACK_CONFIG:
            return jsonify({"error": "Invalid stack"}), 400

        cpu = data.get("cpu", "500m")
        memory = data.get("memory", "512Mi")

        # ✅ FIX 1: define env_id first
        env_id = str(uuid.uuid4())[:6]

        # ✅ FIX 2: proper naming
        env_name = f"{user}-{stack}-{env_id}"

        config = STACK_CONFIG[stack]
        image = config["image"]
        port = config["port"]

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

        node_port = 30000 + int(env_id[:3], 16) % 2000

        service_yaml = f"""
apiVersion: v1
kind: Service
metadata:
  name: {env_name}-svc
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

        if user not in active_envs:
        active_envs[user] = []

        active_envs[user].append(env_name)

        print("Active Envs:", active_envs, flush=True)
        return jsonify({
            "env_id": env_id,
            "env_name": env_name,
            "stack": stack,
            "status": "created",
            "access_port": node_port
        })

    except subprocess.CalledProcessError:
        return jsonify({"error": "Kubernetes deployment failed"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete-env/<env_id>', methods=['DELETE'])
def delete_env(env_id):
    try:
        # ⚠️ TEMP (will fix later properly)
        subprocess.run(
            ["kubectl", "delete", "deployment", f"env-{env_id}", "-n", NAMESPACE],
            check=True
        )
        subprocess.run(
            ["kubectl", "delete", "service", f"svc-{env_id}", "-n", NAMESPACE],
            check=True
        )

        return jsonify({
            "env_id": env_id,
            "status": "deleted"
        })

    except subprocess.CalledProcessError:
        return jsonify({"error": "Deletion failed"}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
