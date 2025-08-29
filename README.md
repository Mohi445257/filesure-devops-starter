# Filesure DevOps Assignment

## 🎯 Overview
This repository contains my implementation of the **Filesure DevOps Assignment**.  
It simulates a simplified document processing pipeline with:

- **API service** (job creation, metrics at `:5001/metrics`)
- **Worker service** (runs as KEDA ScaledJob, processes documents)
- **MongoDB** (job queue + metadata storage)
- **Azure Blob Storage** (simulated uploads)
- **Prometheus** (scrapes metrics from API + Pushgateway)
- **Pushgateway** (ephemeral worker metrics endpoint, `:9091/metrics`)
- **Grafana** (monitoring dashboards)

---

## 🏗️ Architecture

```

┌───────────────┐    ┌───────────────┐    ┌──────────────┐
│    Web UI     │    │   MongoDB     │    │   Azure Blob │
│  (Port 5001)  │◄──►│   - jobs      │◄──►│   Storage    │
└───────▲───────┘    └───────────────┘    └──────────────┘
│                      │
▼                      ▼
┌───────────────┐    ┌──────────────────┐
│   API Service │    │  KEDA ScaledJob  │
│   /create-job │    │  Worker Pods     │
│   /metrics    │    │  /metrics:9100   │
└───────▲───────┘    └──────────┬───────┘
│                       │
▼                       │
┌───────────────┐    ┌──────────▼────────┐
│  Pushgateway  │◄───┤  Prometheus       │
│   (9091)      │    │  (9090, scrapes)  │
└───────────────┘    └──────────▲────────┘
│
▼
┌─────────────┐
│   Grafana   │
│   (3000)    │
└─────────────┘

````

---

## 🚀 Deployment

### 1. Create namespace
```bash
kubectl apply -f k8s/namespace.yaml
````

### 2. Apply secrets (update with your own MongoDB + Azure Blob creds)

```bash
kubectl apply -f k8s/secrets.yaml
```

### 3. Deploy monitoring stack

```bash
kubectl apply -f k8s/prometheus-config.yaml
kubectl apply -f k8s/prometheus-deployment.yaml
kubectl apply -f k8s/prometheus-service.yaml

kubectl apply -f k8s/pushgateway-deployment.yaml
kubectl apply -f k8s/pushgateway-service.yaml

kubectl apply -f k8s/grafana-datasource-config.yaml
kubectl apply -f k8s/grafana-dashboards-provider.yaml
kubectl apply -f k8s/grafana-dashboard-config.yaml
kubectl apply -f k8s/grafana-deployment.yaml
kubectl apply -f k8s/grafana-service.yaml
```

### 4. Deploy services

```bash
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/api-service.yaml

kubectl apply -f k8s/worker-scaledjob.yaml
# (worker-service.yaml only needed if Prometheus scrapes worker pods directly)
```

---

## 🌐 Port Forwarding (Windows PowerShell)

Run these commands in **PowerShell** to access services locally:

```powershell
Start-Process powershell -ArgumentList "kubectl port-forward svc/filesure-api-service -n filesure 5001:5001"
Start-Process powershell -ArgumentList "kubectl port-forward svc/prometheus-service -n filesure 9090:9090"
Start-Process powershell -ArgumentList "kubectl port-forward svc/grafana-service -n filesure 3000:3000"
Start-Process powershell -ArgumentList "kubectl port-forward svc/mongodb -n filesure 27017:27017"
Start-Process powershell -ArgumentList "kubectl port-forward svc/pushgateway -n filesure 9091:9091"
```

Then open in browser:

* API → [http://localhost:5001](http://localhost:5001)
* Prometheus → [http://localhost:9090](http://localhost:9090)
* Grafana → [http://localhost:3000](http://localhost:3000) (default: `admin/admin`)
* Pushgateway → [http://localhost:9091](http://localhost:9091)

---

## 📊 Monitoring

Prometheus scrapes:

* API service (`:5001/metrics`)
* Pushgateway (`:9091/metrics`) for worker jobs

Grafana dashboard (`grafana-dashboard-config.json`) includes panels for:

* Jobs created / processed / pending / completed
* Job progress % (gauge)
* Failed jobs + error rate
* Documents uploaded
* Blob upload failures
* Worker scaling activity
* Prometheus & Pushgateway health

---

## 🎥 Demo Video

👉 [Watch Demo Video](https://youtu.be/zl7Hj5nZ7X0) 

The demo shows:

* Creating jobs via API
* Worker pods scaling up/down with KEDA
* Completed jobs being cleaned up automatically
* Metrics flowing through Prometheus/Pushgateway
* Grafana dashboards updating in real time

---

## ✅ Deliverables Checklist

*  Dockerfiles for API & Worker
*  Kubernetes manifests (API, Worker, Prometheus, Grafana, Pushgateway, KEDA, Secrets)
*  Prometheus metrics integration (API + Worker via Pushgateway)
*  Grafana dashboard JSON export
*  CI/CD workflow (GitHub Actions pipeline provided)
*  Demo video

---

## 📌 Notes

* Worker pods are **short-lived** and auto-clean after 30s (`ttlSecondsAfterFinished`).
* MongoDB tested with **Atlas Free Tier**.
* Azure Blob Storage connection is simulated for testing.
* Alerts in Grafana are optional but can be added.

---

💡 With this setup, you can showcase:

* **Containerization** (API + Worker images)
* **Kubernetes deployment** (manifests)
* **KEDA autoscaling** (workers scale with pending jobs)
* **Monitoring & observability** (Prometheus, Pushgateway, Grafana)



