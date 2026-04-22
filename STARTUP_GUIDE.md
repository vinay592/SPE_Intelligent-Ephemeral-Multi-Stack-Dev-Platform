# SPE Dev Platform: Complete Startup Guide

Follow these sequential steps to boot everything safely, including Minikube recovery, Namespace setup, and your new professional-grade security and monitoring features.

## Step 1: Infrastructure via Modular Ansible
Your infrastructure setup is now modularized into professional Ansible roles. Run this first to ensure Docker, Kubectl, and Minikube are correctly configured.

```bash
cd dev-platform/ansible
ansible-playbook setup.yml
```

## Step 2: Initialize Core Services (Minikube & ELK)
Start Minikube and your monitoring stack.

```bash
# 1. Start Minikube with sufficient resources (HPA ready)
minikube start --driver=docker --memory=4096 --cpus=4
minikube addons enable metrics-server

# 2. Start Logging & Secrets (ELK + HashiCorp Vault)
docker-compose up -d
```
*(Wait 1 minute for Elasticsearch to initialize).*

## Step 3: CI/CD Pipeline (Build All Stacks)
Your Jenkins pipeline is now "Self-Healing" and "Multi-Stack". 
1. Push your latest code to GitHub.
2. Trigger the Jenkins build.
3. The pipeline will automatically:
   - Clear existing port/container conflicts.
   - Build and Tag **all 4 images** (`flask`, `java`, `mern`, `ml`) as `latest`.
   - Push them to your Docker Hub (`vinayvb18`).

## Step 4: Stand Up the Backend Database
```bash
# Apply Mongo Deployment & Service
kubectl apply -f k8s/mongo.yaml

# Create the Port-Forward (Critical for Backend connection)
kubectl port-forward svc/mongo-svc 27017:27017 -n dev-platform &
```

## Step 5: Boot the Platform Server & UI
```bash
# Start Backend
cd backend && source venv/bin/activate
python app.py &

# Start Frontend
cd ../frontend && python -m http.server 8080 &
```
Open `http://localhost:8080/` in your browser.

---

## Innovation Feature: Live HPA Stress Test
To demonstrate the platform's scalability (Advanced Rubric):
1. Create any environment (e.g., Flask).
2. Once "Running", click the yellow **"Stress Test"** button.
3. Observe how the backend resolves the Pod name and triggers a CPU load.
4. Run `kubectl get hpa -n dev-platform --watch` to see the replicas scale up from 1 to 3!

## Secure Storage - HashiCorp Vault
Your platform now supports **HashiCorp Vault** (integrated into `docker-compose.yml`). This satisfies the "Secure Storage" rubric criteria for high-end project marks.
