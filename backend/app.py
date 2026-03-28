from flask import Flask, request, jsonify
import os
import uuid

app = Flask(__name__)


@app.route('/')
def home():
    return "Dev Platform Backend Running 🚀"


@app.route('/create-env', methods=['POST'])
def create_env():
    data = request.json

    stack = data.get("stack")
    cpu = data.get("cpu", "500m")
    memory = data.get("memory", "512Mi")

    env_id = str(uuid.uuid4())[:6]

    #  Stack Mapping
    if stack == "flask":
        image = "flask-env"
        port = 5001

    elif stack == "mern":
        image = "mern-env"
        port = 3000

    elif stack == "java":
        image = "java-env"
        port = 8082

    elif stack == "ml":
        image = "ml-env"
        port = 8888

    else:
        return jsonify({"error": "Invalid stack"}), 400

    #  Dynamic Deployment YAML
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
      - name: app-container
        image: {image}
        imagePullPolicy: Never
        ports:
        - containerPort: {port}
        resources:
          limits:
            memory: "{memory}"
            cpu: "{cpu}"
"""

    # 🔥 Dynamic Service YAML
    node_port = 30000 + int(env_id[:3], 16) % 2000

    service_yaml = f"""
apiVersion: v1
kind: Service
metadata:
  name: svc-{env_id}
spec:
  type: NodePort
  selector:
    app: env-{env_id}
  ports:
    - port: 80
      targetPort: {port}
      nodePort: {node_port}
"""

    # Save files
    dep_file = f"/tmp/deploy-{env_id}.yaml"
    svc_file = f"/tmp/service-{env_id}.yaml"

    with open(dep_file, "w") as f:
        f.write(deployment_yaml)

    with open(svc_file, "w") as f:
        f.write(service_yaml)

    # Apply to Kubernetes
    os.system(f"kubectl apply -f {dep_file}")
    os.system(f"kubectl apply -f {svc_file}")

    return jsonify({
        "env_id": env_id,
        "stack": stack,
        "status": "created",
        "access_port": node_port
    })


@app.route('/delete-env/<env_id>', methods=['DELETE'])
def delete_env(env_id):
    os.system(f"kubectl delete deployment env-{env_id}")
    os.system(f"kubectl delete service svc-{env_id}")

    return jsonify({
        "env_id": env_id,
        "status": "deleted"
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
