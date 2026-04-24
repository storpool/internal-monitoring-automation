# Internal Monitoring Automation

This repository contains automation used by AWX workflows to deploy and manage internal monitoring infrastructure and agents across monitored hosts.

It provisions a monitoring stack based on **VictoriaMetrics**, integrates with Kubernetes cluster components, and configures alerting via Slack.

---

## Overview

The project automates:

* Deployment of the **VictoriaMetrics monitoring stack**
* Configuration of monitoring targets (hosts and Kubernetes components)
* Alerting setup via Slack webhooks
* Integration with Kubernetes cluster services (e.g. controller manager metrics)
* Deployment through **AWX workflows** into designated namespaces

---

## Architecture

**Core components:**

* **AWX** – orchestrates workflows and automation
* **VictoriaMetrics** – time-series database and monitoring backend
* **Kubernetes cluster** – monitored infrastructure
* **Traefik** – ingress/controller exposure
* **Slack** – alert notifications

---

## Prerequisites

Before running the automation, ensure the following are in place:

### 1. Kubernetes Cluster

* A running and accessible Kubernetes cluster
* Metrics endpoints exposed for core components

Example: kube-controller-manager service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: kube-controller-manager
  namespace: kube-system
  labels:
    app.kubernetes.io/name: kube-controller-manager
spec:
  ports:
    - name: https-metrics
      port: 10257
      targetPort: 10257
  selector:
    component: kube-controller-manager
  type: ClusterIP
```

---

### 2. Namespaces

Create the required namespace:

```bash
kubectl create namespace internal-monitoring
```

---

### 3. Slack Webhook Secret

Alerting requires a Slack webhook stored as a Kubernetes Secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: alerting-slack-api
  namespace: internal-monitoring
type: Opaque
data:
  url: <base64-encoded-slack-webhook>
```

> ⚠️ Important: The webhook URL must be base64-encoded before applying.

---

### 4. Traefik Configuration

* Traefik must be deployed and configured in the cluster
* Required for exposing monitoring services (if external access is needed)

---

### 5. AWX Access

* An operational AWX instance
* Credentials configured for:

  * Kubernetes cluster access
  * Git repository access
* Permissions to create resources in:

  * `internal-monitoring` namespace

