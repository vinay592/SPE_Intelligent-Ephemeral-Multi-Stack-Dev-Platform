from flask import Flask, request, jsonify
import uuid
import subprocess
import threading
import time
from datetime import datetime, timezone
from flask_cors import CORS
import json
import os
from pymongo import MongoClient


app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
STACK_CONFIG = {
    "flask": {"image": "vinayvb18/flask-env:v5", "port": 5001},
    "mern": {"image": "vinayvb18/mern-env:v5", "port": 3000},
    "java": {"image": "vinayvb18/java-env:v3", "port": 8082},
    "ml": {"image": "vinayvb18/ml-env:v6", "port": 8888}
}

NAMESPACE = "dev-platform"

# ---------------- MONGODB ----------------
MONGO_URI = "mongodb://localhost:27017"
client = MongoClient(MONGO_URI)

db = client["dev_platform"]
users_col = db["users"]
envs_col = db["environments"]

# ---------------- HELPERS ----------------

def load_yaml_template(path, replacements):
    with open(path, "r") as f:
        content = f.read()

    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))

    return content

def delete_k8s_resources(name):
    print(f"Deleting resources for {name}", flush=True)

    subprocess.run(["kubectl", "delete", "deployment", name, "-n", NAMESPACE, "--ignore-not-found"], check=False)
    subprocess.run(["kubectl", "delete", "svc", f"{name}-svc", "-n", NAMESPACE, "--ignore-not-found"], check=False)
    subprocess.run(["kubectl", "delete", "pvc", f"{name}-pvc", "-n", NAMESPACE, "--ignore-not-found"], check=False)

# ---------------- TTL CLEANUP ----------------
TTL = 1800  # 30 min

def cleanup_expired_envs():
    while True:
        time.sleep(60)

        try:
            now = time.time()
            print("[TTL CHECK RUNNING]", flush=True)

            for env in envs_col.find():
                age = now - env.get("created_at", now)

                if age >= TTL:
                    print(f"[AUTO DELETE] {env['env_name']}", flush=True)
                    delete_k8s_resources(env["env_name"])
                    envs_col.delete_one({"env_name": env["env_name"]})

        except Exception as e:
            print("TTL Error:", e)

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return "Dev Platform Backend Running 🚀"

# -------- GET ENVS (FROM DB) --------
@app.route('/envs', methods=['GET'])
def list_envs():
    result = {} 

    for env in envs_col.find():
        user = env["user"]

        if user not in result:
            result[user] = []

        result[user].append({
            "name": env["env_name"],
            "port": env["port"],
            "created_at": env.get("created_at", time.time())
        })

    return jsonify(result)

# -------- DELETE --------
@app.route('/delete-env', methods=['POST'])
def delete_env():
    data = request.get_json()

    if not data or "env_name" not in data:
        return jsonify({"error": "env_name required"}), 400

    env_name = data["env_name"]

    try:
        delete_k8s_resources(env_name)
        envs_col.delete_one({"env_name": env_name})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "status": "deleted",
        "env_name": env_name
    })

# -------- OPEN ENV --------
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
#--------- SIGN-IN and LOG-IN----
import bcrypt

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing fields"}), 400

    if users_col.find_one({"username": username}):
        return jsonify({"error": "User already exists"}), 400

    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    users_col.insert_one({
        "username": username,
        "password": hashed_pw
    })

    return jsonify({"status": "user created"})


@app.route('/login', methods=['POST'])
def login():
    data = request.json

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Missing fields"}), 400

    user = users_col.find_one({"username": username})

    if not user:
        return jsonify({"error": "User not found"}), 404

    if not bcrypt.checkpw(password.encode(), user["password"]):
        return jsonify({"error": "Invalid password"}), 401

    return jsonify({
        "status": "login success",
        "username": username
    })

# -------- CREATE ENV --------
@app.route('/create-env', methods=['POST'])
def create_env():
    try:
        data = request.json
        user = data.get("user", "default").lower()

        if not data or "stack" not in data:
            return jsonify({"error": "Stack is required"}), 400

        stack = data["stack"]

        if stack not in STACK_CONFIG:
            return jsonify({"error": "Invalid stack"}), 400

        # -------- LIMIT CHECK (DB BASED) --------
        current_envs = list(envs_col.find({"user": user}))

        if len(current_envs) >= 3:
            return jsonify({"error": "Max 3 environments allowed"}), 400

        config = STACK_CONFIG[stack]
        image = data.get("image", config["image"])
        port = config["port"]

        cpu = data.get("cpu", "250m")
        memory = data.get("memory", "256Mi")

        # enforce limits strictly
        max_cpu = 500
        max_memory = 512

        cpu_val = int(cpu.replace("m", ""))
        mem_val = int(memory.replace("Mi", ""))

        cpu_val = min(cpu_val, max_cpu)     
        mem_val = min(mem_val, max_memory)

        cpu = f"{cpu_val}m"
        memory = f"{mem_val}Mi"

        env_id = str(uuid.uuid4())[:6]
        env_name = f"{user}-{stack}-{env_id}"

        base_path = os.path.dirname(os.path.abspath(__file__))
        k8s_path = os.path.join(base_path, "..", "k8s")

        # -------- YAML GENERATION --------
        pvc_yaml = load_yaml_template(
            os.path.join(k8s_path, "pvc.yaml"),
            {"ENV_NAME": env_name}
        )

        deployment_yaml = load_yaml_template(
            os.path.join(k8s_path, "deployment.yaml"),
            {
                "ENV_NAME": env_name,
                "IMAGE": image,
                "PORT": port,
                "CPU": cpu,
                "MEMORY": memory
            }
        )

        service_name = f"{env_name}-svc"
        node_port = 30000 + int(env_id[:3], 16) % 2000

        service_yaml = load_yaml_template(
            os.path.join(k8s_path, "service.yaml"),
            {
                "ENV_NAME": env_name,
                "SERVICE_NAME": service_name,
                "PORT": port,
                "NODE_PORT": node_port
            }
        )

        # -------- WRITE TEMP FILES --------
        pvc_file = f"/tmp/pvc-{env_id}.yaml"
        dep_file = f"/tmp/deploy-{env_id}.yaml"
        svc_file = f"/tmp/service-{env_id}.yaml"

        with open(pvc_file, "w") as f:
            f.write(pvc_yaml)

        with open(dep_file, "w") as f:
            f.write(deployment_yaml)

        with open(svc_file, "w") as f:
            f.write(service_yaml)

        # -------- APPLY --------
        subprocess.run(["kubectl", "apply", "-f", pvc_file], check=True)
        subprocess.run(["kubectl", "apply", "-f", dep_file], check=True)
        subprocess.run(["kubectl", "apply", "-f", svc_file], check=True)

        # -------- STORE IN DB --------
        print("SAVING TO DB:", user, env_name, node_port, flush=True)

        envs_col.insert_one({
            "user": user,
            "env_name": env_name,
            "port": node_port,
            "created_at": time.time()
        })

        print("SAVED SUCCESSFULLY", flush=True)

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
