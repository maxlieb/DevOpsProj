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

# DadJokes EKS Terraform Project

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
3. **Apply the configuration
```bash
terraform apply
```
4. **Configure kubectl to access the cluster
```bash
aws eks update-kubeconfig --region <region> --name <cluster_name>
```
