# SPE Dev Platform: Complete Startup Guide

Follow these sequential steps to boot everything safely, including Minikube recovery, Namespace setup, and your new Vault (Secrets/Configs).

## Step 1: Recover & Initialize Infrastructure (Minikube)
Since your Minikube crashed, we must start fresh, enable necessary addons like `metrics-server` (critical for HPA scaling), and recreate your namespace.

```bash
# 1. Start Minikube with sufficient resources
minikube start --driver=docker --memory=4096 --cpus=4

# 2. Enable horizontal scaling addons
minikube addons enable metrics-server

# 3. Create the mandatory project namespace
kubectl create namespace dev-platform
```

## Step 2: Apply Vaults (Configuration & Secrets)
You must apply your environmental configurations and sensitive keys to Kubernetes. These satisfy the "Secure Storage/Vault" requirements.

```bash
cd dev-platform/

# 1. Apply ConfigMaps (Plain text configs like ELASTICSEARCH_URI)
kubectl apply -f k8s/config.yml

# 2. Apply Secrets (Base64 encoded sensitive data like DB Passwords)
kubectl apply -f k8s/secrets.yml
```

## Step 3: Start the Logging Stack (ELK)
With our new dedicated Compose file, starting the pipeline components is simplified. Make sure Docker is running on your machine first.

```bash
# Bring up Elasticsearch, Logstash, and Kibana in detached mode
docker-compose up -d
```
*(Wait 1-2 minutes for Elasticsearch to initialize).*

## Step 4: Stand Up Core Kubernetes Services
Now deploy your continuous backend database.

```bash
# Apply Mongo PVC and Deployment
kubectl apply -f k8s/mongo.yaml

# Monitor until Pod is running
kubectl get pods -n dev-platform -w

# OPTIONAL: Map Mongo so backend can connect locally (Open a separate terminal for this!)
kubectl port-forward svc/mongo-svc 27017:27017 -n dev-platform
```

## Step 5: Start the Platform Server
Spin up the Flask Application responsible for dynamically generating your environment architectures.

```bash
cd dev-platform/backend

# Ensure Python dependencies are up-to-date
source venv/bin/activate
pip install -r requirements.txt

# Start Flask Application
python app.py
```

## Step 6: Start Frontend UI
Open a final terminal to host your local static frontend cleanly.

```bash
cd dev-platform/frontend
python -m http.server 8080
```
Open `http://localhost:8080/login.html` in your browser.

---

### Verify Functionality
Log into your platform, create a `mern` or `flask` environment, and run:
```bash
kubectl get hpa -n dev-platform
```
You should proudly see an independent HPA monitor natively bound to your newly generated container!
