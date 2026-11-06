# MCP Skills Extractor Agents Helm Chart

Deploys the MCP Skills Extractor Agents server (resume/job-posting skill-extraction tools over
streamable HTTP) to a Kubernetes cluster. The chart installs a `Deployment`, a `Service`, a
`ConfigMap`, a `Secret`, and (if `serviceAccount.create` is true) a `ServiceAccount`.

All commands below assume the repository root as the working directory.

## Prerequisites

1. [Docker](https://docs.docker.com/get-docker/), to build the image.
2. A Kubernetes cluster reachable via `kubectl`. Pick one:
   *   **Production / shared environments:** any managed or self-hosted Kubernetes cluster.
   *   **Local development:** [minikube](https://minikube.sigs.k8s.io/docs/start/), or
       [Rancher Desktop](https://rancherdesktop.io/) with its bundled Kubernetes enabled.
3. [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl)
4. [Helm](https://helm.sh/docs/intro/install/)

## 1. Build the Docker image

```sh
# Build and run locally
docker build -t mcp-skills-extractor-agents:local .
docker run --rm -p 8000:8000 mcp-skills-extractor-agents:local

# Build and publish to a registry
docker build -t mcp-skills-extractor-agents:0.1.0 .
docker tag mcp-skills-extractor-agents:0.1.0 luigisamurai/mcp-skills-extractor-agents:0.1.0
docker push luigisamurai/mcp-skills-extractor-agents:0.1.0
```

The image's default command runs the `mcp-skills-extractor-agents` entrypoint over streamable HTTP
(`--protocol http --host 0.0.0.0 --port 8000`); the Helm chart overrides these via
`config.protocol`/`config.host`/`service.targetPort` instead of baking them into the image.

To use a published image instead of building locally, point `image.repository`/`image.tag` in
`values.yaml` (or via `--set`) at it; `imagePullPolicy` defaults to `IfNotPresent`.

## 2. Deploy to Kubernetes

If you're deploying to a production/shared cluster, make sure `kubectl config current-context`
already points at it, then skip to the `helm install` step below. For local development, start
(or switch to) one of the following instead — only run one at a time, since minikube and Rancher
Desktop's Kubernetes conflict over ports and the active `kubectl` context:

**Option A — minikube:**
```sh
minikube start
```

**Option B — Rancher Desktop:** enable Kubernetes in its preferences
(*Kubernetes Settings → Enable Kubernetes*), then point `kubectl` at it:
```sh
kubectl config use-context rancher-desktop
```

Every extraction tool runs a real Claude Agent SDK agent (see e.g.
`src/mcp_skills_extractor_agents/server/tools/technical_skill_extraction.py`) through
`labs_agent_lib` — they are **not** mocked, despite what the root `CLAUDE.md` says. Without a
real Portkey or Anthropic API key, every tool call fails. Pass a real credential at install
time — never commit one to `values.yaml`:

```sh
# Install the chart - a single release running every tool
helm install mcp-skills-extractor-agents ./helm/mcp-skills-extractor-agents \
  --set secrets.portkeyApiKey=***

# ...or upgrade an existing install
helm upgrade mcp-skills-extractor-agents ./helm/mcp-skills-extractor-agents \
  --set secrets.portkeyApiKey=***

# Check the pods came up
kubectl get pods -l app.kubernetes.io/instance=mcp-skills-extractor-agents
```

or with a separate, untracked values file (`helm install ... -f secrets.values.yaml`). See
"Credentials" below for the full set of `secrets.*` / `config.*` keys this maps to.

### Deploying one tool (or a subset) per release

`config.activeTools` is rendered into `MCP_SKILLS_EXTRACTOR_AGENTS_ACTIVE_TOOLS`, which restricts a
pod to registering only the listed tools. Leaving it empty (the default above) registers every
tool. To run each tool as its own independent deployment instead, install one release per tool
with a distinct release name. Each release name gets prefixed onto the chart name for every
resource it creates (`<release>-mcp-skills-extractor-agents`) unless you also set
`fullnameOverride` to something shorter, as done below:

Each release needs its own credential too (every pod runs its own Claude Agent SDK agent):

```sh
helm install skill-agent-technical ./helm/mcp-skills-extractor-agents \
  --set config.activeTools="{extract_technical_skills}" \
  --set fullnameOverride=skill-agent-technical \
  --set secrets.portkeyApiKey=**

helm install skill-agent-soft ./helm/mcp-skills-extractor-agents \
  --set config.activeTools="{extract_soft_skills}" \
  --set fullnameOverride=skill-agent-soft \
  --set secrets.portkeyApiKey=**

helm install skill-agent-certifications ./helm/mcp-skills-extractor-agents \
  --set config.activeTools="{extract_certifications}" \
  --set fullnameOverride=skill-agent-certifications \
  --set secrets.portkeyApiKey=**

helm install skill-agent-languages ./helm/mcp-skills-extractor-agents \
  --set config.activeTools="{extract_languages}" \
  --set fullnameOverride=skill-agent-languages \
  --set secrets.portkeyApiKey=**
```

Each release gets its own `Service` (named after the release, via the chart's fullname
template), so consumers can address a specific tool's deployment directly, or address the
single do-everything release instead — whichever topology the environment needs. A release can
also be pinned to more than one tool, e.g. `--set config.activeTools="{extract_technical_skills,extract_soft_skills,extract_certifications,extract_languages}"`.

## 3. Access the service

The `Service` is `ClusterIP` by default (this server is meant to be reached by other in-cluster
MCP clients, e.g. another agent's `*_SKILL_AGENT_MCP_URL` setting, not from outside the
cluster). Switch `service.type` to `NodePort` or `LoadBalancer` if you need outside access (for
example, to point the MCP Inspector at a local minikube cluster).

**Every command below targets one `Service` by name.** If you installed the single
do-everything release, that name is `mcp-skills-extractor-agents`. If you installed one
release per tool (see above), each one has its *own* `Service` named after its
`fullnameOverride` instead — substitute accordingly. Run `kubectl get svc` to list what's
actually deployed:

```sh
kubectl get svc
# NAME                          TYPE        ...
# skill-agent-technical         ClusterIP   ...
# skill-agent-soft              ClusterIP   ...
# skill-agent-certifications    ClusterIP   ...
# skill-agent-languages         ClusterIP   ...
```

### For local testing from your own machine (MCP Inspector, manual curl, etc.)

** port-forward to localhost (any cluster):**
```sh
# forwarding more than one Service at once needs a distinct local port each, in separate
# terminals, e.g.:

kubectl port-forward svc/skill-agent-technical 8000:80
# then point an MCP client at http://localhost:8000/mcp

kubectl port-forward svc/skill-agent-soft 8001:80
# then point an MCP client at http://localhost:8001/mcp

kubectl port-forward svc/skill-agent-certifications 8002:80
# then point an MCP client at http://localhost:8002/mcp

kubectl port-forward svc/skill-agent-languages 8003:80
# then point an MCP client at http://localhost:8003/mcp

```

`kubectl port-forward` only tunnels to the machine running `kubectl` — it does not make the
`Service` reachable from other pods. Use these addresses only for a client running on that
same machine.

### For another in-cluster consumer (e.g. the coordinator)

Address this chart's `Service` by its cluster-DNS name on its `Service` port (`80`, i.e.
`service.port` — not a port-forward port), not the `localhost` addresses above:

```sh
# same namespace as the consumer
http://skill-agent-technical/mcp
http://skill-agent-soft/mcp
http://skill-agent-certifications/mcp
http://skill-agent-languages/mcp

# different namespace
http://skill-agent-technical.<namespace>.svc.cluster.local/mcp

# single do-everything release (use your fullnameOverride if you set one)
http://mcp-skills-extractor-agents/mcp
```

Set these as the consumer's own `*_MCP_URL` env vars (e.g. `talent-distiller-agent`'s
`TALENT_DISTILLER_AGENT_SKILL_AGENT_TECHNICAL_MCP_URL` and its three siblings), via that
chart's own values/`--set`, then redeploy it.
