"""Run c00040c2 validation. Execute only through capture-execution (1800s)."""

from __future__ import annotations

import hashlib
import http.client
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

RUN = "c00040c2196d4919b3e5b0a7fd947faf"
REVISION = "f4a6137513b777c9b362be54baf388f7d45398aa"
NAMESPACE = "poc-openshell-story-c00040c2"
NAME = "story-c00040c2"
WORKSPACE = "default"
NODE = "ocp-gb-xz56l-worker-3-cpu-f88sc"
IMAGE = "quay.io/aicatalyst/openshell-sandbox:story-c00040c2"
DEFAULT_URL = f"https://openshell.{NAMESPACE}.svc.cluster.local:8080"
PRIVATE = Path("/workspace/private")
IDENTITY = PRIVATE / "sandbox-identity.json"
OBSERVATIONS = Path(f"/workspace/evidence/{RUN}/staging/test-observations.json")
SCENARIOS = (
    "Gateway readiness and mTLS access",
    "Sandbox readiness and process contract",
    "Persistent workspace lifecycle",
    "Scoped reachable-control network contrast",
    "Run-owned sandbox deletion",
)
MECHANISMS = ("cli", "exec", "exec", "cli", "cli")


class CheckError(Exception):
    """Only fixed, locally authored categories may cross the output boundary."""

    def __init__(self, category, status="error"):
        self.category = category
        self.status = status


def require(condition, category):
    if not condition:
        raise CheckError(category, "fail")


def write_json(path, value):
    # Atomic replacement also prevents following an existing destination symlink.
    fd, temporary = tempfile.mkstemp(prefix=".poc-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def category(exc):
    if isinstance(exc, CheckError):
        return exc.category
    if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired)):
        return "operation_timeout"
    if isinstance(exc, FileNotFoundError):
        return "required_file_or_executable_missing"
    if isinstance(exc, (ValueError, KeyError, TypeError, AttributeError)):
        return "invalid_response_or_configuration"
    if isinstance(exc, OSError):
        return "local_io_or_transport_error"
    code = getattr(exc, "code", None)
    if callable(code):
        name = getattr(code(), "name", "")
        if name in GRPC_CODES:
            return "grpc_" + name.lower()
    return "sdk_or_validation_error"


GRPC_CODES = {"UNAVAILABLE", "DEADLINE_EXCEEDED", "UNAUTHENTICATED", "PERMISSION_DENIED",
              "NOT_FOUND", "ALREADY_EXISTS", "INVALID_ARGUMENT", "FAILED_PRECONDITION",
              "INTERNAL", "UNKNOWN", "CANCELLED", "RESOURCE_EXHAUSTED", "UNIMPLEMENTED"}


def recorder():
    # The SDK venv need not install autopoc or its dependencies.
    try:
        from autopoc.capture import AttemptRecorder
    except ModuleNotFoundError:
        spec = importlib.util.spec_from_file_location(
            "poc_capture", "/opt/autopoc/src/autopoc/capture.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        AttemptRecorder = module.AttemptRecorder
    return AttemptRecorder.from_environment()


class Context:
    def __init__(self, scenario, deadline):
        self.name = scenario
        self.deadline = deadline
        self.recorder = recorder()
        self.execution = os.environ["AUTOPOC_EXECUTION_ID"]

    def remaining(self, maximum=30):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise CheckError("scenario_deadline")
        return min(maximum, remaining)

    def observe(self, operation, facts):
        document = json.loads(OBSERVATIONS.read_text())
        require(document["execution_id"] == self.execution, "observation_identity_mismatch")
        document["actions"].append({
            "scenario_name": self.name,
            "operation": operation,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            **facts,
        })
        write_json(OBSERVATIONS, document)

    def call(self, operation, mechanism, function):
        start = time.monotonic()
        started = datetime.now(timezone.utc).isoformat()
        try:
            self.remaining()
            value = function()
        except Exception as exc:
            error = category(exc)
            status = exc.status if isinstance(exc, CheckError) else "error"
            self.recorder.record(self.name, mechanism, status, time.monotonic() - start,
                                 started_at=started, error=error)
            self.observe(operation, {"status": status, "error_category": error})
            raise
        # Successful operations are not a claim that the whole scenario passed.
        self.recorder.record(self.name, mechanism, None, time.monotonic() - start,
                             started_at=started)
        self.observe(operation, {"status": "observed"})
        return value

    def terminal(self, status, error, start):
        return self.recorder.record(self.name, MECHANISMS[SCENARIOS.index(self.name)],
                                    status, time.monotonic() - start, error=error)


def identity(execution):
    if not IDENTITY.exists():
        return None
    require(not IDENTITY.is_symlink(), "unsafe_identity_file")
    data = json.loads(IDENTITY.read_text())
    require(data.get("run_id") == RUN and data.get("execution_id") == execution
            and data.get("name") == NAME and data.get("workspace") == WORKSPACE,
            "sandbox_ownership_unconfirmed")
    return data


def oc(context, operation, resource, *, selector=None, name=None):
    argv = ["oc", "--request-timeout=15s", "-n", NAMESPACE, "get", resource]
    if name:
        argv += [name, "--ignore-not-found"]
    if selector:
        argv += ["-l", selector]
    argv += ["-o", "json"]

    def invoke():
        context.observe(operation + "_selection", {"namespace": NAMESPACE,
            "resource": resource, "selector": selector, "name": name})
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=context.remaining(20), check=False)
        # Never retain full Kubernetes specs (which can contain credential env).
        write_json(PRIVATE / f"oc-{os.getpid()}-{time.monotonic_ns()}.json", {
            "operation": operation, "returncode": result.returncode,
            "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr),
        })
        if result.returncode:
            raise CheckError("kubernetes_observation_failed")
        return json.loads(result.stdout) if result.stdout.strip() else None

    return context.call(operation, "cli", invoke)


def helper(context, action, service_url):
    argv = ["/workspace/openshell-venv/bin/python", "-B",
            str(Path(__file__).with_name("poc_sdk_check.py")), action, service_url,
            str(context.deadline)]

    def invoke():
        # No shell, credential arguments, active-gateway discovery or token refresh.
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=context.remaining(650), check=False,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                                     "GRPC_VERBOSITY": "NONE"})
        write_json(PRIVATE / f"helper-{action}-{time.monotonic_ns()}.json", {
            "action": action, "returncode": result.returncode,
            "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr),
        })
        try:
            reply = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise CheckError("sdk_helper_protocol_error") from None
        require(reply.get("action") == action, "sdk_helper_action_mismatch")
        if reply.get("status") != "pass" or result.returncode:
            # Categories are an allowlist, not arbitrary child exception text.
            error = reply.get("error_category")
            if error not in HELPER_ERRORS:
                error = "sdk_helper_failed"
            status = reply.get("status")
            raise CheckError(error, status if status in ("fail", "error", "skip") else "error")
        return reply

    return context.call("sdk_helper_" + action, "exec", invoke)


HELPER_ERRORS = {
    "sdk_helper_failed", "operation_timeout", "scenario_deadline",
    "required_file_or_executable_missing", "invalid_response_or_configuration",
    "local_io_or_transport_error", "sdk_or_validation_error", "sandbox_already_exists",
    "sandbox_ownership_unconfirmed", "sandbox_identity_changed", "sandbox_not_ready",
    "sandbox_error_phase", "process_contract_mismatch", "non_root_uid_not_observed",
    "marker_write_failed", "marker_readback_mismatch", "sandbox_not_stopped",
    "workload_image_not_run_pinned", "authenticated_health_not_healthy",
    "unauthenticated_rpc_not_rejected", "unauthenticated_rpc_transport_ambiguous",
    "sandbox_not_created", "unsafe_identity_file", "observation_identity_mismatch",
} | {"grpc_" + code.lower() for code in GRPC_CODES}


def gateway(context, service_url):
    for resource, selector in (
        ("statefulsets,deployments", "app.kubernetes.io/name=openshell,app.kubernetes.io/instance=openshell"),
        ("deployments", "app.kubernetes.io/name=openshell,app.kubernetes.io/instance=openshell,app.kubernetes.io/component=supervisor"),
    ):
        result = oc(context, "selected_gateway_or_supervisor_workloads", resource, selector=selector)
        workloads = result.get("items", [])
        facts = [{"kind": item["kind"], "name": item["metadata"]["name"],
                  "desired": item.get("spec", {}).get("replicas", 1),
                  "ready": item.get("status", {}).get("readyReplicas", 0),
                  "generation": item["metadata"].get("generation"),
                  "observed_generation": item.get("status", {}).get("observedGeneration")}
                 for item in workloads]
        context.observe("workload_readiness", {"workloads": facts})
        require(bool(facts) and all(w["desired"] > 0 and w["ready"] >= w["desired"]
                and w["observed_generation"] is not None
                and w["observed_generation"] >= w["generation"] for w in facts),
                "gateway_or_supervisor_not_ready")
    helper(context, "auth", service_url)


def own_resources(context, data):
    sandbox_id = data.get("id", "")
    require(bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,63}", sandbox_id)), "sandbox_ownership_unconfirmed")
    result = oc(context, "own_sandbox_cr", "sandboxes.agents.x-k8s.io",
                selector=f"openshell.ai/sandbox-id={sandbox_id}")
    crs = result.get("items", [])
    require(len(crs) <= 1, "ambiguous_sandbox_cr")
    all_pods = oc(context, "namespace_pods_for_own_cr", "pods").get("items", [])
    uids = {cr["metadata"]["uid"] for cr in crs}
    uids.update(data.get("cr_uids", []))
    reported_pods = {cr["metadata"].get("annotations", {}).get("agents.x-k8s.io/pod-name")
                     for cr in crs}
    pods = []
    for pod in all_pods:
        metadata = pod["metadata"]
        annotated = metadata.get("annotations", {}).get("openshell.ai/sandbox-id") == sandbox_id
        owned = any(owner.get("uid") in uids for owner in metadata.get("ownerReferences", []))
        workload_owned = any(owner.get("uid") in uids and owner.get("controller") is True
                             for owner in metadata.get("ownerReferences", []))
        labeled = metadata.get("labels", {}).get("openshell.ai/sandbox-id") == sandbox_id
        if annotated or owned or labeled:
            pods.append({"name": metadata["name"], "uid": metadata["uid"],
                         "ip": pod.get("status", {}).get("podIP"),
                         "node": pod.get("spec", {}).get("nodeName"),
                         # Paired supervisors also carry the ID annotation but
                         # have a non-controller Sandbox owner reference.
                         "workload": workload_owned or metadata["name"] in reported_pods,
                         "phase": pod.get("status", {}).get("phase")})
    cr_facts = [{"name": cr["metadata"]["name"], "uid": cr["metadata"]["uid"]} for cr in crs]
    context.observe("physical_sandbox_resources", {"sandbox_id": sandbox_id,
                                                 "crs": cr_facts, "pods": pods})
    data["cr_uids"] = sorted(uids)
    data["cr_names"] = sorted(set(data.get("cr_names", [])) | {cr["name"] for cr in cr_facts})
    data["pod_names"] = sorted(set(data.get("pod_names", [])) | {pod["name"] for pod in pods})
    write_json(IDENTITY, data)
    return cr_facts, pods


def process(context, service_url):
    helper(context, "process", service_url)
    data = identity(context.execution)
    require(bool(data and data.get("id")), "sandbox_ownership_unconfirmed")
    crs, pods = own_resources(context, data)
    workload = [pod for pod in pods if pod["workload"]]
    require(len(crs) == 1 and len(workload) == 1, "physical_creation_not_observed")
    require(workload[0]["node"] == NODE, "sandbox_node_placement_mismatch")


def network(context):
    data = identity(context.execution)
    if not data or not data.get("id"):
        raise CheckError("sandbox_not_created", "skip")
    crs, pods = own_resources(context, data)
    workload = [pod for pod in pods if pod["workload"] and pod["ip"] and pod["phase"] == "Running"]
    require(len(crs) == 1 and len(workload) == 1, "sandbox_pod_ip_not_observed")
    ipaddress.ip_address(workload[0]["ip"])
    host = f"openshell.{NAMESPACE}.svc.cluster.local"

    def metrics():
        connection = http.client.HTTPConnection(host, 9090, timeout=context.remaining(8))
        try:
            connection.request("GET", "/metrics")
            response = connection.getresponse()
            sample = response.read(1024)
            context.observe("gateway_metrics_control", {"http_status": response.status,
                                                       "sample_bytes": len(sample)})
            require(response.status == 200 and bool(sample), "reachable_control_missing")
        finally:
            connection.close()

    context.call("worker_gateway_metrics_request", "http", metrics)

    def connect():
        start = time.monotonic()
        try:
            with socket.create_connection((workload[0]["ip"], 2222), timeout=context.remaining(5)):
                reachability = "reachable"
        except socket.timeout:
            reachability = "timeout"
        except ConnectionRefusedError:
            reachability = "refused"
        except OSError:
            reachability = "transport_error"
        context.observe("worker_sandbox_tcp_2222", {
            "pod_name": workload[0]["name"], "pod_ip": workload[0]["ip"],
            "port": 2222, "reachability": reachability,
            "elapsed_seconds": time.monotonic() - start,
            "interpretation": "Reachability contrast only; not policy-enforcement proof",
        })
        if reachability == "transport_error":
            raise CheckError("sandbox_tcp_transport_error")

    context.call("worker_sandbox_tcp_connect", "exec", connect)


def cleanup(context, service_url):
    data = identity(context.execution)
    if not data:
        raise CheckError("sandbox_not_created", "skip")
    # Attempt SDK deletion even if earlier physical-resource observation fails.
    observation_error = None
    if data.get("id"):
        try:
            own_resources(context, data)
        except Exception as exc:
            observation_error = category(exc)
    helper(context, "cleanup", service_url)
    data = identity(context.execution)
    require(bool(data and data.get("id")), "sandbox_ownership_unconfirmed")
    while True:
        crs, pods = own_resources(context, data)
        # Check exact previously observed names, not only label disappearance.
        remaining = bool(crs or pods)
        for resource, names in (("sandboxes.agents.x-k8s.io", data.get("cr_names", [])),
                                ("pods", data.get("pod_names", []))):
            for name in names:
                obj = oc(context, "exact_own_resource_deletion", resource, name=name)
                context.observe("exact_resource_presence", {"resource": resource, "name": name,
                                                           "present": bool(obj)})
                remaining = remaining or bool(obj)
        if not remaining:
            break
        context.remaining()
        time.sleep(min(2, context.remaining()))
    require(bool(data.get("cr_names")) and bool(data.get("pod_names")),
            "physical_creation_not_observed")
    if observation_error:
        raise CheckError("cleanup_initial_observation_failed")
    context.observe("cleanup_scope", {"sandbox_id": data["id"],
                                      "pvc_reclamation": "not_asserted"})


def main():
    os.umask(0o077)
    service_url = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else DEFAULT_URL
    overall = time.monotonic() + 1730
    # Initialization is intentionally capture-only; never create a new harness execution.
    execution = os.environ["AUTOPOC_EXECUTION_ID"]
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    if OBSERVATIONS.exists():
        # Preserve earlier execution observations, rather than silently overwriting them.
        old = json.loads(OBSERVATIONS.read_text())
        old_id = old.get("execution_id", "")
        require(bool(re.fullmatch(r"[a-f0-9]{32}", old_id)), "observation_identity_mismatch")
        write_json(OBSERVATIONS.with_name(f"test-observations-{old_id}.json"), old)
    write_json(OBSERVATIONS, {"run_id": RUN, "execution_id": execution,
                              "source_revision": REVISION, "actions": [],
                              "kind_note": "Original action observations; register later as JSON or text analysis"})
    results = []

    def run(index, seconds, function):
        start = time.monotonic()
        deadline = min(start + seconds, overall if index == 4 else overall - 190)
        context = Context(SCENARIOS[index], deadline)
        try:
            function(context)
            status, error = "pass", None
        except Exception as exc:
            status = exc.status if isinstance(exc, CheckError) else "error"
            error = category(exc)
        result = context.terminal(status, error, start)
        results.append(result)

    def blocked(reason):
        raise CheckError(reason, "skip")

    try:
        run(0, 90, lambda ctx: gateway(ctx, service_url))
        if results[0]["status"] == "pass":
            run(1, 600, lambda ctx: process(ctx, service_url))
        else:
            run(1, 1, lambda ctx: blocked("gateway_dependency_failed"))
        if results[1]["status"] == "pass":
            run(2, 600, lambda ctx: helper(ctx, "lifecycle", service_url))
        else:
            run(2, 1, lambda ctx: blocked("process_dependency_failed"))
        run(3, 45, network)
    finally:
        run(4, 180, lambda ctx: cleanup(ctx, service_url))
    print(json.dumps({"results": results}, sort_keys=True))
    return 0 if all(result["status"] == "pass" for result in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Capture will mark missing terminal records incomplete; never print raw exceptions.
        print(json.dumps({"error": "validation_initialization_or_recording_failed"}))
        sys.exit(2)
