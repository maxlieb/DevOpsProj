# DadJokes API  Final Project (DevOps Course)

**DadJokes API** is the final project for a DevOps course, demonstrating API handling, state management, and integration with DevOps tools like Docker, Kubernetes, and Terraform.  

This Flask application fetches dad jokes from external sources or accepts custom jokes, storing the **entire database** as a single JSON message in an **ntfy** topic — no local disk or database is required. Designed as a learning demo.

## Features
- Fetch external jokes and store them automatically in an **ntfy topic**
- Full CRUD support for custom jokes:
  - **Create** – POST /jokes  
  - **Read** – GET /jokes, GET /jokes/<id>  
  - **Update** – PUT /jokes/<id> (manual or fetch new external joke)  
  - **Delete** – DELETE /jokes/<id>  
- **Reset** the database – POST /reset
- Healthcheck endpoint – GET /health
- Auto-prune to **max 30 jokes** (newest kept)
- Each joke contains: `id`, `title`, `body`, `source`, `pod_name`, `created_at`

## Quick Start (Docker)
```bash
docker build -t youruser/dadjokes-ntfy .
docker run -d -p 5000:5000 --name dj \
  -e NTFY_BASE=https://ntfy.sh \
  -e NTFY_TOPIC=dadjokes-<your-unique-topic> \
  -e MAX_RECORDS=30 \
  youruser/dadjokes-ntfy

curl http://localhost:5000/health
curl http://localhost:5000/         # fetch & store a Reddit joke
curl http://localhost:5000/jokes    # list jokes
```

## Kubernetes (Minikube)
```bash
kubectl apply -f k8s/flask-deployment.yaml
kubectl apply -f k8s/flask-service.yaml
kubectl apply -f k8s/curl-pod.yaml
# Optional external access:
# - set Service type: LoadBalancer
# - run: minikube tunnel
```

### Recommended env in Deployment
```yaml
env:
- name: NTFY_BASE
  value: "https://ntfy.sh"
- name: NTFY_TOPIC
  value: "dadjokes-<your-unique-topic>"
- name: MAX_RECORDS
  value: "30"
# Optional auth if using private ntfy:
# - name: NTFY_AUTH
#   valueFrom:
#     secretKeyRef: { name: ntfy-secret, key: token }
```

## API + Examples

**# curl from pod:**

kubectl exec -it curl -- sh <br>

curl http://dadjokes-service
or

curl http://192.168.49.2

**# curl outside pod:**

minikube service dadjokes-service --url
and curl to the returned URL


### `GET /health`
Check if the app is running.
```bash
curl http://dadjokes-service/health
```

---

### `GET /`
Fetch a random Reddit joke and store it in the DB.
```bash
curl http://dadjokes-service
```

---

### `POST /jokes`
Add a custom joke.
```bash
curl -X POST http://dadjokes-service/jokes \
  -H "Content-Type: application/json" \
  -d '{"title":"Why did the dev go broke?", "body":"Because he used up all his cache."}'
```

---

### `GET /jokes`
List all jokes. Optional query:
```bash
curl http://dadjokes-service/jokes
curl "http://dadjokes-service/jokes?from=2024-01-01T00:00:00Z&to=2025-01-01T00:00:00Z"
```

---

### `GET /jokes/<id>`
Get a specific joke by ID.
```bash
curl http://dadjokes-service/jokes/<id>
```

---

### `PUT /jokes/<id>`
Update a joke manually:
```bash
curl -X PUT http://dadjokes-service/jokes/<id> \
  -H "Content-Type: application/json" \
  -d '{"title":"Updated joke title", "body":"New punchline!"}'
```

Or replace with a new random Reddit joke:
```bash
curl -X PUT http://dadjokes-service/jokes/<id> \
  -H "Content-Type: application/json" \
  -d '{"reddit": true}'
```

---

### `DELETE /jokes/<id>`
Delete a joke by ID.
```bash
curl -X DELETE http://dadjokes-service/jokes/<id>
```

---

### `POST /reset`
Clear all jokes (dangerous).
```bash
curl -X POST http://dadjokes-service/reset
```

---

## Notes
- **Public ntfy (`ntfy.sh`) is open**: anyone knowing the topic can read/write. Use a unique topic; for stability use your private ntfy and `NTFY_AUTH`.
- DB is pruned to **30** on every save to keep messages small.

# DadJokes EKS Terraform 

This project provisions an **AWS EKS cluster** along with a minimal **VPC setup** using **Terraform**. It is designed for learning and demo purposes, providing a ready-to-use Kubernetes environment with essential add-ons and a managed node group.

---

## What Terraform Does

- Configures a **remote backend** in S3 to store the Terraform state securely, with DynamoDB for state locking.
- Creates a **VPC** with public and private subnets, NAT gateway, and appropriate subnet tags for Kubernetes.
- Deploys an **EKS cluster** with:
  - Public endpoint access
  - Essential add-ons (`CoreDNS`, `kube-proxy`, `VPC CNI`)
  - Managed node group with configurable instance type, size, and disk
- Manages **cluster access** explicitly via IAM roles and users (no automatic admin grants).
- Outputs key information after deployment:
  - Cluster name
  - Cluster endpoint
  - CLI command to update kubeconfig for `kubectl`

---

## Prerequisites

- Terraform v1.0 or higher
- AWS CLI configured with credentials that have permissions to create EKS, IAM, VPC, and related resources
- Git (optional, if cloning the repository)

---

## How to Deploy

1. **Initialize Terraform** (installs providers and configures backend):

```bash
terraform init
```
2. **Plan the deployment** 

```bash
terraform plan
```
3. **Apply the configuration**
```bash
terraform apply
```
4. **Configure kubectl to access the cluster**
```bash
aws eks update-kubeconfig --region il-central-1 --name dadjokes-eks
```

## CI/CD with GitHub Actions

This project includes an automated **CI/CD pipeline** built with **GitHub Actions**, covering:

- **CI (Continuous Integration)**:  
  Build the Docker image, run the container locally in the workflow, and perform **end-to-end smoke tests**:
  - `/health` check  
  - `POST /jokes` → validate response  
  - `GET /jokes` → ensure data persists  
  - `PUT /jokes/<id>` → update  
  - `DELETE /jokes/<id>` → verify removal  
  - `POST /reset` → reset DB  

- **CD (Continuous Deployment)**:  
  After tests pass, the pipeline:
  1. Pushes the Docker image to **Docker Hub** with multiple tags (latest, SHA, branch).  
  2. Provisions/updates infrastructure with **Terraform** (EKS cluster on AWS).  
  3. Deploys the latest image to **Kubernetes** (EKS) using `kubectl apply` and `kubectl set image`.  
  4. Waits for rollout completion and prints the external LoadBalancer DNS.  

### Workflow Overview

    A[Push to main] --> B[Build Docker image]
    B --> C[Run tests (smoke/e2e)]
    C --> D[Push image to Docker Hub]
    D --> E[Terraform apply (EKS infra)]
    E --> F[Deploy to EKS via kubectl]
    F --> G[Expose service (LoadBalancer)]

### Example Workflow File

Below is a shortened excerpt of the main workflow (`.github/workflows/ci.yml`):

```yaml
name: CI Pipeline

on:
  push:
    branches:
      - main

jobs:
  build-test-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: Build & Run Tests
        run: |
          docker build -t dadjokes-api .
          docker run -d -p 5000:5000 --name dadjokes dadjokes-api
          curl -f http://localhost:5000/health
      - name: Push to Docker Hub
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: maxlieb/dadjokes-api:latest
```

### Secrets & Configuration

To run the GitHub Actions CI/CD pipeline, you need to configure the following **secrets** in your repository settings (`Settings → Secrets → Actions`):

| Secret Name             | Description |
|-------------------------|-------------|
| `DOCKERHUB_USERNAME`    | Your Docker Hub username. Used to log in and push Docker images. |
| `DOCKERHUB_TOKEN`       | Your Docker Hub access token or password. Keep it secret! |
| `AWS_ROLE_TO_ASSUME`    | The AWS IAM Role ARN used by GitHub Actions to run Terraform and deploy to EKS. Example: `arn:aws:iam::863518423554:role/GHA-Terraform-EKS`. |

> **Note:** These secrets allow the workflow to securely access Docker Hub and AWS without exposing credentials in the repository.
