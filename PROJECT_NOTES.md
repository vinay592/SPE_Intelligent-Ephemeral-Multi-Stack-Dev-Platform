# Developer Platform: Project Overview & Running Notes

Welcome back! Here are the comprehensive notes detailing how your Ephemeral Multi-Stack Development Platform works, what each file does, and how they seamlessly tie together from end-to-end.

## 1. What is happening in each file?

### 🧠 The Control Plane (Backend)
- **`backend/app.py`**: The core brain of the platform.
  - **Responsibilities**: It is a Flask API on port `5001` that handles HTTP requests from the Main Dashboard (frontend). It interfaces directly with MongoDB (for user/environment state), Elasticsearch (for event logging), and Kubernetes (for orchestration via `subprocess` calling `kubectl`).
  - **Key Features**: 
    - Auto-discovers the `minikube ip` in the background.
    - Caches `HPA` (Horizontal Pod Autoscaler) statuses to serve the UI instantly without blocking.
    - Runs a **TTL Cleanup Thread**: Checks the database every 10 seconds to delete generic environments older than 30 minutes (1800s).
    - Exposes endpoints like `/create-env` (generates custom PVC, Deployment, Service, HPA manifests based on the templates in `k8s/` and applies them instantaneously), `/stress-env` (triggers artificial load inside the pod), and Auth (`/signup`, `/login`).

### 🎨 The User Dashboard
- **`frontend/` (index.html, js, css)**: Built with Modern Glassmorphism.
  - **Responsibilities**: Provides the UI for developers to log in and spin up test pods. They click "Deploy Flask", and the Javascript `fetch` calls the `backend/app.py` `/create-env` endpoint. Polls for changes so the status badges go from *Provisioning* to *Running*.

  - **Features**: This is a standalone micro-server running inside the Docker container. It serves an interactive Monaco-based IDE (code editor) directly to the user's browser. It exposes a `/run` endpoint. When a user writes Python code in their browser and clicks Execute, this `app.py` writes the code to a temporary file (`tempfile.NamedTemporaryFile`) and safely runs it via `subprocess.run` with a strict `30-second` timeout and truncated output.
### ⚙️ DevOps & Security configuration
- **`ansible/setup.yml` & `roles/trivy/tasks/main.yml`**: Prepares your machine. Ensures Docker, Minikube, and specifically **Trivy** (for scanning vulnerabilities in your Docker images containerized via `templates/`) are installed.
- **`jenkins/Jenkinsfile`**: Provides your CI/CD Pipeline tracking codebase modifications. Every push builds the templates, scans them with Trivy, and handles container publishing.
- **`k8s/`**: Contains the baseline YAML config (`config.yml`, `secrets.yml`, `mongo.yaml`) defining the `dev-platform` namespace and the stateful backend DB. Includes dynamically populated placeholders (like `{{ENV_NAME}}`) for the dynamic provisioner.

---

## 2. How they are related (The Step-by-Step Flow)

### Scenario: User deploys a "Flask Environment"
1. **User Request**: The user clicks "Deploy Flask Env" on the `frontend` Dashboard (`index.html`).
2. **API Call**: The frontend sends a POST request (`/create-env`) to the `backend/app.py` API including the user's requested stack (`flask`).
3. **Database Logging**: `backend/app.py` instantly logs the new environment into MongoDB (`envs_col`) with status `provisioning`, ensuring the UI reflects it immediately.
4. **K8s Orchestration**: 
   - A background thread in `backend/app.py` takes the YAML templates from `k8s/`, injects unique IDs (`{{ENV_NAME}}`), and saves them to `/tmp/`.
   - It runs `kubectl apply` for PVC, Deployment, Service, and HPA on your minikube cluster.
5. **Deployment Ready**: The backend polls K8s (`kubectl get pods`). Once running, it updates MongoDB to status `running`.
6. **User Access**: The Frontend sees "Running" and provides a link. The link points directly to the K8s NodePort of the newly spawned pod, routing the user to the interactive Monaco string UI hosted by `templates/flask/app.py`.
7. **User Stress Test**: If the user clicks `Stress Test`, `backend/app.py` executes `/dev/urandom` within the pod. The pre-configured K8s HPA notices the spike (>50% CPU) and scales replicas automatically.
8. **Expiration (TTL)**: After 30 minutes, the background loop in `backend/app.py` notices the pod is expired, triggers `delete_k8s_resources`, wipes the K8s objects (saving compute), deletes the MonogoDB record, and issues an Event log to Elasticsearch.

---

## 3. How to Run the Platform Locally

Here is a streamlined checklist to spin everything up:

### Prerequisite Boots
1. **Minikube**: Start your cluster and enable metrics (for HPA tracking).
   ```bash
   minikube start --driver=docker --memory=4096 --cpus=4
   minikube addons enable metrics-server
   ```
2. **Elastic/Monitoring**: Start your ELK logs system via Docker Compose.
   ```bash
   docker-compose up -d
   ```
3. **Kubernetes DB Configuration**: Deploy MongoDB into the cluster and Port-Forward it to make it available to the local backend script.
   ```bash
   kubectl apply -f k8s/config.yml
   kubectl apply -f k8s/secrets.yml
   kubectl apply -f k8s/mongo.yaml
   
   # Leave this running in its own terminal
   kubectl port-forward svc/mongo-svc 27017:27017 -n dev-platform
   ```

### Application Boots
4. **Backend API**: In a new terminal, launch the Python orchestration server.
   ```bash
   cd backend
   source venv/bin/activate
   python app.py
   # Look for outputs: "Elasticsearch connected" and "Minikube IP discovered"
   ```
5. **Frontend UI**: In a new terminal, host the dashboard HTML.
   ```bash
   cd frontend
   python -m http.server 8080
   ```
6. **Visit**: Open `http://localhost:8080` in your browser. From here, login, spin up resources, monitor HPA limits, and interact with the dynamically spawned templates!
