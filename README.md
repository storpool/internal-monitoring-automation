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

---

## FortiGate Monitoring (Optional)

To enable monitoring of FortiGate devices, create/update`fortigate-config` ConfigMap in the `internal-monitoring` namespace.

### Steps

1. Retrieve the current ConfigMap:

```bash
kubectl -n internal-monitoring get configmap fortigate-config -o yaml
```

2. Add or update FortiGate endpoints in the following format:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fortigate-config
  namespace: internal-monitoring
data:
  fortigate-key.yaml: |-
    "https://hostname1:8443":
        token: <api-token-1>
    "https://hostname2:8443":
        token: <api-token-2>
```

### Notes

* Each entry represents a FortiGate device API endpoint
* Tokens must be valid API access tokens from the FortiGate device
* Ensure HTTPS connectivity from the cluster to the FortiGate hosts

---
## External Access to VictoriaMetrics (Optional)

If external access to VictoriaMetrics is required (e.g. for external Grafana dashboards), enable it via an AWX extra variable.

### Configuration

Set the following variable in the AWX workflow/job template:

```yaml id="u3k9sd"
victoria_metrics_external_endpoint: "https://<victoria-metrics-external-url>"
```

### Behavior

* When defined, the `deploy-monitoring-stack.yaml` playbook will:

  * Create a Traefik `IngressRoute`
  * Expose the VictoriaMetrics endpoint externally

### Notes

* Ensure DNS resolves to your Traefik entrypoint
* TLS configuration should be handled by Traefik (if enabled)
* Do not expose publicly unless properly secured

---

## Alertmanager Endpoint Configuration (Optional)

The Alertmanager URL can be configured via an AWX extra variable in the same workflow.

### Configuration

```yaml
alertmanager_internal_domain: "<alertmanager-url-domain>"
```

### Behavior

* When defined, the `deploy-monitoring-stack.yaml` configures Alertmanager with the provided endpoint
* Used for alert routing and integrations (e.g. Slack notifications)

### Notes

* Ensure the URL is reachable from within the cluster
* If exposed externally, secure it appropriately (TLS, auth, etc.)
