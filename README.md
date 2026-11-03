# Internal Monitoring Automation

This repository contains automation used by Ascender workflows to deploy and manage internal monitoring infrastructure and agents across monitored hosts.

It provisions a monitoring stack based on **VictoriaMetrics**, integrates with Kubernetes cluster components, and configures alerting via Slack.

---

## Overview

The project automates:

* Deployment of the **VictoriaMetrics monitoring stack**
* Configuration of monitoring targets (hosts and Kubernetes components)
* Alerting setup via Slack webhooks
* Integration with Kubernetes cluster services (e.g. controller manager metrics)
* Deployment through **Ascender workflows** into designated namespaces

---

## Architecture

**Core components:**

* **Ascender** – orchestrates workflows and automation
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

### 5. Ascender Access

* An operational Ascender instance
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
Ascender.

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

> ⚠️ Remove the Ascender job template / workflow node that runs the old `install-ipmi-exporter.yaml`,
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

If external access to VictoriaMetrics is required (e.g. for external Grafana dashboards), enable it via an Ascender extra variable.

### Configuration

Set the following variable in the Ascender workflow/job template:

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

The Alertmanager URL can be configured via an Ascender extra variable in the same workflow.

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

* * *

## Log Shipping to VictoriaLogs (Vector)

`install-vector.yaml` installs [Vector](https://vector.dev) from the pinned upstream release package (downloaded through `vector_github_proxy_url` and checked against the sha256 in `vector_checksums`) and ships the systemd journal of every host in the `deploy_vector` group to VictoriaLogs (`https://infralogs.storpool.net`).

### Selecting hosts

- **NetBox:** tag the device with `vector-autodeploy`
- **OpenNebula:** add the `vector` label to a `Production` VM

### Credentials (required)

The playbook fails unless `vector_victorialogs_password` is set. Provide it from an Ascender credential or extra variable — it never lives in git.

```
vector_victorialogs_password: "<victorialogs-writer-password>"
```

### Optional variables

| Variable | Default | Purpose |
|---|---|---|
| `vector_github_proxy_url` | `https://git-release-proxt.storpool.net` | Caching proxy the GitHub release packages are downloaded through |
| `vector_version` | `0.60.0` | Vector release; bumping it upgrades the hosts |
<<<<<<< HEAD
=======
| `vector_checksums` | pinned release | sha256 per package file, update together with `vector_version` |
>>>>>>> f178713 (Adding vector to ship the systemd journal and tetragon logs to VictoriaLogs)
| `vector_victorialogs_url` | `""` | VictoriaLogs endpoint, required (e.g. `https://infralogs.storpool.net`) |
| `vector_victorialogs_compression` | `zstd` | Use `gzip` against older VictoriaLogs |
| `vector_journald_exclude_units` | `[]` | Journal units that are not shipped |
| `vector_tetragon_enabled` | `false` | Install Tetragon and ship its events |
| `vector_tetragon_extended_enabled` | `false` | Ship the full field set instead of the minimal one |
| `vector_tetragon_version` | `1.7.1` | Tetragon release; bumping it upgrades the hosts |
<<<<<<< HEAD
=======
| `vector_tetragon_checksums` | pinned release | sha256 per tarball, update together with `vector_tetragon_version` |
>>>>>>> f178713 (Adding vector to ship the systemd journal and tetragon logs to VictoriaLogs)
| `vector_tetragon_options` | `{}` | Extra Tetragon flags, one `tetragon.conf.d` file each |
| `vector_tetragon_policies_exclude` | `[]` | Policy files to leave out on a host or group |
| `vector_tetragon_policies_prune` | `true` | Remove files from `tetragon.tp.d` that are not in the repository |

### Tetragon

With `vector_tetragon_enabled: true` the role installs [Tetragon](https://tetragon.io) from the pinned upstream release (the same layout as its `install.sh`), writes its JSON export to `/var/log/tetragon/tetragon.log` and ships the events to VictoriaLogs. The kernel must expose BTF (`/sys/kernel/btf/vmlinux`), the playbook fails early otherwise.

Two transformations write the same flat field names, so the UI and LogsQL queries work with either:

- **Minimal** (default, `roles/vector/files/tetragon-minimal.vrl`): event type, a coarse category, hook, policy, enforcement and outcome, the process and parent identity (exec_id, pid, uid, user, binary, args), the first socket or path argument, exit signal/status and the k8s pod
- **Extended** (`vector_tetragon_extended_enabled: true`, `roles/vector/files/tetragon-extended.vrl`): the full set, adding the per-hook category/action table, privilege direction for uid changes, failure reasons, DNS lookups, the rendered argument list, capabilities, namespaces and container ids

Extended events are roughly a third larger.

### Tetragon tracing policies

Without tracing policies Tetragon only reports process exec and exit. Policies live in `roles/vector/files/tetragon-policies/` (`*.yaml` / `*.yml`, one or more `TracingPolicy` documents each, unique `metadata.name`) and are deployed to `/etc/tetragon/tetragon.tp.d/`.

Tetragon loads every regular file in that directory and **refuses to start if any policy fails to load**, so the rollout is guarded:

- the files are checked on the controller first (kind and unique `metadata.name`), a bad file stops the run before any host is touched
- files in `tetragon.tp.d` that are not in the repository are removed (`vector_tetragon_policies_prune`)
- Tetragon is restarted only when a policy changed, then every policy must reach `TP_STATE_ENABLED`
- otherwise the previous policy set is restored, Tetragon restarted on it, and the job fails naming the policies that did not load and the last Tetragon log lines

An empty policy directory in the repository leaves the hosts' policies alone. To skip policies on some hosts, set `vector_tetragon_policies_exclude` for that host or group, e.g. `[ 11-dns-queries.yaml, 12-dns-names.yaml ]`.

> ⚠️ Setting `vector_tetragon_enabled: false` later stops shipping the events but does not uninstall Tetragon.

### Notes

- Journal streams are keyed on `host`, `log_source` and `_SYSTEMD_UNIT`
- The Vector API listens on `127.0.0.1:8686` only (`vector top`), so no firewall port is opened
- The config is checked with `vector validate` before it replaces the running one, a broken template never reaches the service
