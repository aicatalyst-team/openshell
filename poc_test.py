"""Original OpenShell PoC validation for run ac05c639abd848998db29ce2352d9a0f.

Uses the pinned source's Python SDK and records every real attempt through
autopoc.capture.AttemptRecorder. No prior-run results are imported.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time

from autopoc.capture import AttemptRecorder
import grpc
from openshell import SandboxClient, TlsConfig
from openshell._proto import datamodel_pb2, openshell_pb2, sandbox_pb2

WORKSPACE = "default"
NODE = os.environ.get("AUTOPOC_WORKLOAD_NODE", "ocp-gb-xz56l-worker-2-nsrd9")
IMAGE = os.environ.get(
    "AUTOPOC_SANDBOX_IMAGE", "registry.access.redhat.com/ubi9/ubi-minimal:9.6"
)
HEALTH_URL = os.environ.get("AUTOPOC_HEALTH_URL", "http://127.0.0.1:8081/healthz")
GATEWAY_ENDPOINT = os.environ.get("AUTOPOC_GATEWAY_ENDPOINT", "127.0.0.1:8080")
TLS_DIR = pathlib.Path(os.environ["AUTOPOC_TLS_DIR"])
TEMPLATE_NAME = "deepseek-node-pinned"

recorder = AttemptRecorder.from_environment()
results: list[dict] = []
created: set[str] = set()


def _session_spec(policy, command: tuple[str, ...] = ("sleep", "infinity")):
    spec = openshell_pb2.SandboxSpec(command=list(command))
    spec.policy.CopyFrom(policy)
    return spec


def _policy(network: bool = False) -> sandbox_pb2.SandboxPolicy:
    policy = sandbox_pb2.SandboxPolicy(version=1)
    policy.filesystem.include_workdir = True
    policy.filesystem.read_only.extend(
        ["/bin", "/usr", "/lib", "/proc", "/dev/urandom", "/etc", "/var/log"]
    )
    policy.filesystem.read_write.extend(["/sandbox", "/tmp", "/dev/null"])
    policy.landlock.compatibility = "best_effort"
    if network:
        rule = policy.network_policies["allow_example"]
        rule.name = "allow-example"
        endpoint = rule.endpoints.add()
        endpoint.host = "example.com"
        endpoint.port = 443
        endpoint.protocol = "rest"
        endpoint.enforcement = sandbox_pb2.NETWORK_ENFORCEMENT_MODE_ENFORCE
        endpoint.access = sandbox_pb2.NETWORK_ACCESS_PRESET_READ_ONLY
        binary = rule.binaries.add()
        binary.path = "/usr/bin/curl"
    return policy


def _record(name: str, mechanism: str, status: str, started: float, error: str | None = None):
    result = recorder.record(
        name,
        mechanism,
        status,
        time.monotonic() - started,
        error=error,
    )
    results.append(result)
    return result


def _safe(name: str, mechanism: str, fn):
    started = time.monotonic()
    try:
        status, error = fn()
    except Exception:  # noqa: BLE001 - unexpected failures must still be terminal
        status, error = "error", "unexpected_exception"
    return _record(name, mechanism, status, started, None if status == "pass" else error)


def _ensure_template(client: SandboxClient):
    templates = client.sandbox_templates()
    try:
        templates.delete(TEMPLATE_NAME, workspace=WORKSPACE, allow_missing=True)
    except Exception:  # noqa: BLE001 - a stale template is recreated below
        pass
    templates.create(
        workspace=WORKSPACE,
        name=TEMPLATE_NAME,
        image=IMAGE,
        cpu="500m",
        memory="512Mi",
        driver_config={
            "kubernetes": {
                "pod": {"node_selector": {"kubernetes.io/hostname": NODE}}
            }
        },
    )


def _create(client: SandboxClient, name: str, network: bool = False):
    session = client.create_session_from_template(
        workspace=WORKSPACE,
        workload_template=TEMPLATE_NAME,
        spec=_session_spec(_policy(network=network)),
        name=name,
    )
    created.add(session.sandbox.name)
    client.wait_ready(session.sandbox.name, workspace=WORKSPACE, timeout_seconds=300)
    return session


def _delete(client: SandboxClient, name: str):
    try:
        client.delete(name, workspace=WORKSPACE, allow_missing=True)
    except Exception:  # noqa: BLE001 - cleanup remains best effort, never hidden
        pass
    created.discard(name)


def _run_process(client: SandboxClient, template_ready: bool):
    def scenario():
        if not template_ready:
            return "error", "workload_template_unavailable"
        session = _create(client, "exec-demo")
        try:
            uname = session.exec(["uname", "-s"], timeout_seconds=60)
            uid = session.exec(["id", "-u"], timeout_seconds=60)
            marker = session.exec(
                ["sh", "-c", "printf 'deepseek-exec-ok'"], timeout_seconds=60
            )
            if uname.exit_code != 0 or uname.stdout.strip() != "Linux":
                return "fail", "uname_assertion_failed"
            if uid.exit_code != 0 or not uid.stdout.strip().isdigit():
                return "fail", "uid_assertion_failed"
            if int(uid.stdout.strip()) == 0:
                return "fail", "sandbox_process_is_root"
            if marker.exit_code != 0 or marker.stdout.strip() != "deepseek-exec-ok":
                return "fail", "marker_assertion_failed"
            return "pass", None
        finally:
            _delete(client, session.sandbox.name)

    return _safe("sandbox_process_execution", "exec", scenario)


def _run_persistence(client: SandboxClient, template_ready: bool):
    def scenario():
        if not template_ready:
            return "error", "workload_template_unavailable"
        session = _create(client, "persist-demo")
        try:
            write = session.exec(
                ["sh", "-c", "printf 'persist-ok' > /sandbox/poc-marker"],
                timeout_seconds=60,
            )
            if write.exit_code != 0:
                return "fail", "workspace_write_failed"
            session.stop()
            client.wait_stopped(
                session.sandbox.name, workspace=WORKSPACE, timeout_seconds=300
            )
            session.start()
            client.wait_ready(
                session.sandbox.name, workspace=WORKSPACE, timeout_seconds=300
            )
            read = session.exec(["cat", "/sandbox/poc-marker"], timeout_seconds=60)
            if read.exit_code != 0 or read.stdout.strip() != "persist-ok":
                return "fail", "workspace_marker_not_preserved"
            return "pass", None
        finally:
            _delete(client, session.sandbox.name)

    return _safe("sandbox_workspace_persistence", "exec", scenario)


def _wait_for_denial(client: SandboxClient, sandbox: str, timeout: float = 60.0):
    request = openshell_pb2.GetSandboxLogsRequest(
        workspace_scope=datamodel_pb2.WorkspaceSelector(workspace=WORKSPACE),
        sandbox=sandbox,
        lines=1000,
        sources=["sandbox"],
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = client._stub.GetSandboxLogs(request, timeout=20)
            for line in response.logs:
                message = line.message
                if "DENIED" in message and "api.github.com" in message:
                    return message
        except grpc.RpcError:
            pass
        time.sleep(5)
    return ""


def _run_network(client: SandboxClient, template_ready: bool):
    if not template_ready:
        _record(
            "network_allow_control",
            "exec",
            "error",
            time.monotonic(),
            "workload_template_unavailable",
        )
        _record(
            "network_deny_enforcement",
            "exec",
            "error",
            time.monotonic(),
            "workload_template_unavailable",
        )
        return

    session = None
    try:
        session = _create(client, "net-demo", network=True)
    except Exception:  # noqa: BLE001
        _record(
            "network_allow_control", "exec", "error", time.monotonic(), "sandbox_create_failed"
        )
        _record(
            "network_deny_enforcement", "exec", "error", time.monotonic(), "sandbox_create_failed"
        )
        return

    try:
        started = time.monotonic()
        try:
            allowed = session.exec(
                [
                    "curl",
                    "-sS",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--max-time",
                    "20",
                    "https://example.com",
                ],
                timeout_seconds=60,
            )
            if allowed.exit_code == 0 and allowed.stdout.strip() == "200":
                _record("network_allow_control", "exec", "pass", started)
            else:
                _record(
                    "network_allow_control",
                    "exec",
                    "fail",
                    started,
                    "control_destination_not_reachable",
                )
        except Exception:  # noqa: BLE001
            _record(
                "network_allow_control", "exec", "error", started, "control_exec_exception"
            )

        started = time.monotonic()
        try:
            denied = session.exec(
                [
                    "curl",
                    "-sS",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--max-time",
                    "20",
                    "https://api.github.com/zen",
                ],
                timeout_seconds=60,
            )
            log_line = _wait_for_denial(client, session.sandbox.name, timeout=60)
            http_denied = (
                denied.exit_code != 0
                or denied.stdout.strip() == "403"
                or "policy_denied" in denied.stderr
                or "403" in denied.stderr
            )
            if http_denied and log_line:
                _record("network_deny_enforcement", "exec", "pass", started)
            elif http_denied:
                _record(
                    "network_deny_enforcement",
                    "exec",
                    "fail",
                    started,
                    "policy_denial_log_missing",
                )
            else:
                _record(
                    "network_deny_enforcement",
                    "exec",
                    "fail",
                    started,
                    "unapproved_destination_not_denied",
                )
        except Exception:  # noqa: BLE001
            _record(
                "network_deny_enforcement", "exec", "error", started, "denial_exec_exception"
            )
    finally:
        _delete(client, session.sandbox.name)


def main() -> int:
    client = None
    template_ready = False
    try:
        tls = TlsConfig(
            ca_path=TLS_DIR / "ca.crt",
            cert_path=TLS_DIR / "tls.crt",
            key_path=TLS_DIR / "tls.key",
        )
        client = SandboxClient(GATEWAY_ENDPOINT, tls=tls, timeout=90)

        try:
            results.append(
                recorder.http(
                    "gateway_health",
                    HEALTH_URL,
                    expected_status=200,
                    timeout=10,
                    retries=6,
                    delay=5,
                )
            )
        except Exception:  # noqa: BLE001
            _record(
                "gateway_health", "http", "error", time.monotonic(), "health_probe_exception"
            )

        try:
            _ensure_template(client)
            template_ready = True
        except Exception:  # noqa: BLE001
            template_ready = False

        _run_process(client, template_ready)
        _run_persistence(client, template_ready)
        _run_network(client, template_ready)
    finally:
        if client is not None:
            for name in list(created):
                _delete(client, name)
            try:
                client.sandbox_templates().delete(
                    TEMPLATE_NAME, workspace=WORKSPACE, allow_missing=True
                )
            except Exception:  # noqa: BLE001
                pass
            client.close()

    # The wrapper requires one terminal result per planned scenario.
    planned = [
        "gateway_health",
        "sandbox_process_execution",
        "sandbox_workspace_persistence",
        "network_allow_control",
        "network_deny_enforcement",
    ]
    by_name = {item["scenario_name"]: item for item in results}
    for name in planned:
        if name not in by_name:
            by_name[name] = recorder.record(
                name, "exec", "error", 0, error="scenario_not_executed"
            )

    print(json.dumps({"results": [by_name[name] for name in planned]}))
    return 0 if all(by_name[name]["status"] == "pass" for name in planned) else 1


if __name__ == "__main__":
    sys.exit(main())
