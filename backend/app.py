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
import logging
from elasticsearch import Elasticsearch
import bcrypt

app = Flask(__name__)
CORS(app)

# Ensure kubectl can find the config even when run via sudo/Jenkins
os.environ["HOME"] = "/home/vinay-v-bhandare"
if "/snap/bin" not in os.environ.get("PATH", ""):
    os.environ["PATH"] += ":/snap/bin"

# ---------------- CONFIG ----------------
STACK_CONFIG = {
    "flask": {"image": "vinayvb18/flask-env:latest", "port": 5001},
    "mern": {"image": "vinayvb18/mern-env:latest", "port": 3000},
    "java": {"image": "vinayvb18/java-env:latest", "port": 8082},
    "ml": {"image": "vinayvb18/ml-env:latest", "port": 8888}
}

logging.basicConfig(
    filename="/tmp/app.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# ---------------- ELASTICSEARCH ----------------
es = None
ELASTICSEARCH_URI = os.getenv("ELASTICSEARCH_URI", "http://127.0.0.1:9200")

for i in range(5):
    try:
        es = Elasticsearch(ELASTICSEARCH_URI)
        es.info()
        print("Elasticsearch connected ✅")
        break
    except:
        print("Retrying Elasticsearch...", i + 1)
        time.sleep(5)

if not es:
    print("Elasticsearch not available ⚠️")

def log_to_es_async(index_name, doc):
    if es:
        def task():
            try:
                es.index(index=index_name, document=doc)
            except Exception as e:
                logging.error(f"Elasticsearch indexing failed: {e}")
        threading.Thread(target=task, daemon=True).start()


NAMESPACE = "dev-platform"

# ---------------- MONGODB ----------------
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
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
    subprocess.run(
        ["kubectl", "delete", "deployment", name, "-n", NAMESPACE, "--ignore-not-found"],
        check=False
    )
    subprocess.run(
        ["kubectl", "delete", "svc", f"{name}-svc", "-n", NAMESPACE, "--ignore-not-found"],
        check=False
    )
    subprocess.run(
        ["kubectl", "delete", "pvc", f"{name}-pvc", "-n", NAMESPACE, "--ignore-not-found"],
        check=False
    )
    subprocess.run(
        ["kubectl", "delete", "hpa", f"{name}-hpa", "-n", NAMESPACE, "--ignore-not-found"],
        check=False
    )


# ---------------- TTL CLEANUP ----------------
TTL = 1800


def cleanup_expired_envs():
    while True:
        time.sleep(60)
        # Ensure path access for cleanup too
        if "/snap/bin" not in os.environ.get("PATH", ""):
            os.environ["PATH"] += ":/snap/bin"
        os.environ["HOME"] = "/home/vinay-v-bhandare"
        try:
            now = time.time()
            cutoff_time = now - TTL

            expired_envs = envs_col.find({"created_at": {"$lte": cutoff_time}})

            for env in expired_envs:
                delete_k8s_resources(env["env_name"])
                envs_col.delete_one({"env_name": env["env_name"]})

                logging.info(f"TTL DELETE: {env['env_name']}")

                log_to_es_async(index_name="app-logs", doc={
                    "event": "ttl_delete",
                    "env": env["env_name"]
                })

        except Exception as e:
            print("TTL Error:", e)


# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return "Dev Platform Backend Running 🚀"


@app.route('/envs', methods=['GET'])
def list_envs():
    result = {}

    for env in envs_col.find():
        user = env["user"]

        if user not in result:
            result[user] = []

        result[user].append({
            "name": env["env_name"],
            "stack": env.get("stack", "unknown"),
            "port": env["port"],
            "created_at": env.get("created_at", time.time())
        })

    return jsonify(result)


@app.route('/delete-env', methods=['POST'])
def delete_env():
    data = request.get_json()
    env_name = data["env_name"]

    delete_k8s_resources(env_name)
    envs_col.delete_one({"env_name": env_name})

    logging.info(f"ENV DELETED: {env_name}")

    log_to_es_async(index_name="app-logs", doc={
        "event": "delete_env",
        "env": env_name
    })

    return jsonify({"status": "deleted"})


@app.route('/open-env', methods=['POST'])
def open_env():
    try:
        data = request.json
        env_name = data.get("env_name")

        # WAIT FOR POD
        for i in range(15):
            try:
                pod_status = subprocess.check_output(
                    [
                        "kubectl", "get", "pods", "-n", NAMESPACE,
                        "-l", f"app={env_name}",
                        "-o", "jsonpath={.items[0].status.phase}"
                    ],
                    text=True, stderr=subprocess.STDOUT
                ).strip()

                print(f"Pod status: {pod_status}")

                if pod_status == "Running":
                    break
            except subprocess.CalledProcessError:
                print("Pod status check failed, retrying...")

            time.sleep(2)
        else:
            return jsonify({"error": "Pod not ready"}), 500

        # WAIT FOR CONTAINER READY
        for i in range(10):
            try:
                ready = subprocess.check_output(
                    [
                        "kubectl", "get", "pods", "-n", NAMESPACE,
                        "-l", f"app={env_name}",
                        "-o", "jsonpath={.items[0].status.containerStatuses[0].ready}"
                    ],
                    text=True, stderr=subprocess.STDOUT
                ).strip()

                if ready == "true":
                    break
            except subprocess.CalledProcessError:
                print("Container ready check failed, retrying...")

            time.sleep(2)

        # GET SERVICE URL
        output = subprocess.check_output(
            ["minikube", "service", f"{env_name}-svc", "-n", NAMESPACE, "--url"],
            text=True
        ).strip()

        return jsonify({"url": output})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------- AUTH --------
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if users_col.find_one({"username": username}):
        return jsonify({"error": "User exists"}), 400

    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    users_col.insert_one({
        "username": username,
        "password": hashed_pw
    })

    logging.info(f"SIGNUP SUCCESS: {username}")

    log_to_es_async(index_name="app-logs", doc={
        "event": "signup",
        "user": username
    })

    return jsonify({"status": True, "message": "Signup successful"})


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    user = users_col.find_one({"username": username})

    if not user:
        return jsonify({"status": False}), 404

    if not bcrypt.checkpw(password.encode(), user["password"]):
        return jsonify({"status": False}), 401

    logging.info(f"LOGIN SUCCESS: {username}")

    log_to_es_async(index_name="app-logs", doc={
        "event": "login",
        "user": username
    })

    return jsonify({"status": True, "message": "Login successful"})


# -------- CREATE ENV --------
@app.route('/create-env', methods=['POST'])
def create_env():
    try:
        data = request.json
        user = data.get("user", "default").lower()
        stack = data["stack"]

        current_envs = list(envs_col.find({"user": user}))
        if len(current_envs) >= 3:
            return jsonify({"error": "Max 3 environments"}), 400

        config = STACK_CONFIG[stack]
        image = data.get("image", config["image"])
        port = config["port"]

        cpu = data.get("cpu", "250m")
        memory = data.get("memory", "256Mi")

        cpu_val = min(int(cpu.replace("m", "")), 500)
        mem_val = min(int(memory.replace("Mi", "")), 512)

        cpu = f"{cpu_val}m"
        memory = f"{mem_val}Mi"

        env_id = str(uuid.uuid4())[:6]
        env_name = f"{user}-{stack}-{env_id}"

        base_path = os.path.dirname(os.path.abspath(__file__))
        k8s_path = os.path.join(base_path, "..", "k8s")

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

        hpa_yaml = load_yaml_template(
            os.path.join(k8s_path, "hpa.yaml"),
            {"ENV_NAME": env_name}
        )

        pvc_file = f"/tmp/pvc-{env_id}.yaml"
        dep_file = f"/tmp/deploy-{env_id}.yaml"
        svc_file = f"/tmp/service-{env_id}.yaml"
        hpa_file = f"/tmp/hpa-{env_id}.yaml"

        open(pvc_file, "w").write(pvc_yaml)
        open(dep_file, "w").write(deployment_yaml)
        open(svc_file, "w").write(service_yaml)
        open(hpa_file, "w").write(hpa_yaml)

        def run_kubectl(args):
            res = subprocess.run(args, capture_output=True, text=True)
            if res.returncode != 0:
                raise Exception(f"Kubernetes error: {res.stderr or res.stdout}")
            return res.stdout

        run_kubectl(["kubectl", "apply", "-f", pvc_file])
        run_kubectl(["kubectl", "apply", "-f", dep_file])
        run_kubectl(["kubectl", "apply", "-f", svc_file])
        run_kubectl(["kubectl", "apply", "-f", hpa_file])

        envs_col.insert_one({
            "user": user,
            "stack": stack,
            "env_name": env_name,
            "port": node_port,
            "created_at": time.time()
        })

        logging.info(f"ENV CREATED: {env_name} by {user}")

        log_to_es_async(index_name="app-logs", doc={
            "event": "create_env",
            "user": user,
            "env": env_name,
            "port": node_port
        })

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
