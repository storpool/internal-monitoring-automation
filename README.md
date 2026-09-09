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

## IPMI / BMC Monitoring

BMC metrics are collected by a single **`ipmi-exporter` Deployment in the `internal-monitoring`
namespace**, which talks IPMI-over-LAN (RMCP) to each server's BMC. It replaces the previous
per-host `ipmi_exporter` installation.

### 1. Network reachability (required)

The cluster must be able to reach the BMC management networks on **UDP 623**. Verify before
rolling out:

```bash
kubectl -n internal-monitoring run ipmi-probe --rm -it --restart=Never \
  --image=prometheuscommunity/ipmi-exporter:v1.10.0 --command -- \
  ipmi-ping <bmc-address>
```

### 2. BMC credentials Secret (required)

`deploy-monitoring-stack.yaml` fails with a clear message unless an `ipmi-exporter-config` Secret
holding `ipmi.yml` already exists. Create it out of band — the credentials never live in git or in
AWX.

```yaml
modules:
  default:
    user: "<bmc-user>"
    pass: "<bmc-password>"
    driver: "LAN_2_0"
    privilege: "admin"
    timeout: 4000
    collectors: [bmc, ipmi, chassis, dcmi, sel]
  no_dcmi:
    user: "<bmc-user>"
    pass: "<bmc-password>"
    driver: "LAN_2_0"
    privilege: "admin"
    timeout: 4000
    collectors: [bmc, ipmi, chassis, sel]
```

```bash
kubectl -n internal-monitoring create secret generic ipmi-exporter-config \
  --from-file=ipmi.yml=./ipmi.yml
```

> ⚠️ These are **remote-mode** modules. The old host-side config used `collector_cmd: sudo` plus
> `custom_args` to shell out to local `freeipmi` tools — those keys must not be carried over.
> `dcmi` and `sel` generally need more than `user` privilege.

Reloader watches the Deployment, so updating the Secret restarts the exporter automatically.

### 3. Targets

* **BMC addresses** come from the NetBox **`oob_ip`** field. A device without one is excluded from
  BMC monitoring; `create-monitoring-targets.yaml` prints the list of excluded hosts.
* **Per-host module selection** still comes from the NetBox config context key `ipmi_module`
  (`default` when unset). It is passed to the exporter as the `module` query parameter, so every
  value used in NetBox must exist as a module in `ipmi.yml`.

### 4. Removing the old host exporter

Once the in-cluster exporter is confirmed healthy, run the cleanup playbook once against the
baremetal fleet:

```bash
ansible-playbook -i netbox_inventory.yml cleanup-ipmi-exporter.yaml
```

It stops and removes the `ipmi_exporter` systemd unit, binary, config directory, sudoers grant and
`ipmi-exp` user/group, closes the 9290/tcp firewalld port, releases the SELinux port label, and
uninstalls `freeipmi`. Set `ipmi_exporter_cleanup_remove_freeipmi: false` to keep `freeipmi` if
other tooling on the hosts depends on it. The playbook is idempotent and safe to re-run.

> ⚠️ Remove the AWX job template / workflow node that runs the old `install-ipmi-exporter.yaml`,
> otherwise it will reinstall exactly what the cleanup removes.

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
