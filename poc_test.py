#!/usr/bin/env python3
"""OpenShell PoC validation tests (run a189bdf54ac849778a8ed7b228db599f).

Validates the source-built OpenShell deployment in poc-openshell:
  1. gateway-health              - gateway HTTP health endpoint (pod-level 8081)
  2. gateway-metrics             - Prometheus metrics endpoint (9090)
  3. gateway-api                 - gRPC control plane over mTLS (Python SDK)
  4. sandbox-lifecycle           - Agent Sandbox CR materialization, exec, teardown
  5. network-policy-enforcement  - allowed egress passes, denied egress blocked,
                                   outer-fence NetworkPolicy present

Every real HTTP/exec attempt is recorded through the AutoPoC AttemptRecorder
before any retry. The script prints {"results": [...]} to stdout and exits 0
only if no scenario failed or errored (skips are recorded explicitly).
"""

import base64
import json
import os
import subprocess
import sys
import time

from autopoc.capture import AttemptRecorder

REPO = "/workspace/repos/openshell"
STAGING = "/workspace/evidence/a189bdf54ac849778a8ed7b228db599f/staging"
NS = "poc-openshell"
GW_HOST = "openshell.poc-openshell.svc.cluster.local"
GRPC_ENDPOINT = GW_HOST + ":8080"
WORKSPACE = "default"
SANDBOX_NAME = "autopoc-a189bdf5"
TLS_DIR = os.path.join(STAGING, "client-tls")

recorder = AttemptRecorder.from_environment()
results = []

# Sandbox created in scenario 4, reused by scenario 5, deleted at the end.
sandbox_state = {"session": None, "client": None, "tool": None}


def kubectl(*args, timeout=60):
    proc = subprocess.run(
        ["kubectl", *args, "-n", NS], capture_output=True, text=True, timeout=timeout
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def sanitize_error(err):
    text = str(err).replace("\n", " ")
    for secret in ("QUAY_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "OPENSHIFT_TOKEN"):
        value = os.environ.get(secret, "")
        if value:
            text = text.replace(value, "<redacted>")
    return text[:400]


def load_client_tls():
    code, out, err = kubectl("get", "secret", "openshell-client-tls", "-o", "json")
    if code != 0:
        raise RuntimeError(f"cannot read openshell-client-tls secret: {err or out}")
    data = json.loads(out)["data"]
    os.makedirs(TLS_DIR, mode=0o700, exist_ok=True)
    for key in ("tls.crt", "tls.key", "ca.crt"):
        with open(os.path.join(TLS_DIR, key), "wb") as fh:
            fh.write(base64.b64decode(data[key]))
    os.chmod(os.path.join(TLS_DIR, "tls.key"), 0o600)
    return TLS_DIR


def make_client():
    sys.path.insert(0, os.path.join(REPO, "python"))
    from openshell import SandboxClient, TlsConfig

    tls_dir = load_client_tls()
    return SandboxClient(
        GRPC_ENDPOINT,
        tls=TlsConfig(
            ca_path=os.path.join(tls_dir, "ca.crt"),
            cert_path=os.path.join(tls_dir, "tls.crt"),
            key_path=os.path.join(tls_dir, "tls.key"),
        ),
        timeout=30.0,
    )


def build_spec():
    from openshell._proto import openshell_pb2

    spec = openshell_pb2.SandboxSpec()
    spec.policy.version = 1
    spec.policy.filesystem.include_workdir = True
    spec.policy.landlock.compatibility = "best_effort"
    rule = spec.policy.network_policies["example"]
    rule.name = "example"
    for port in (80, 443):
        endpoint = rule.endpoints.add()
        endpoint.host = "example.com"
        endpoint.port = port
        endpoint.protocol = "tcp"
    rule.binaries.add().path = "/**"
    return spec


def gateway_pod_ip():
    code, out, _ = kubectl(
        "get",
        "pods",
        "-l",
        "app.kubernetes.io/name=openshell",
        "-o",
        "jsonpath={.items[0].status.podIP}",
    )
    if code != 0 or not out:
        raise RuntimeError("gateway pod IP not found")
    return out


def scenario_gateway_health():
    url = "http://" + gateway_pod_ip() + ":8081/health"
    return recorder.http(
        "gateway-health",
        url,
        expected_status=200,
        expected_content="healthy",
        timeout=30,
        retries=9,
        delay=10,
    )


def scenario_gateway_metrics():
    url = "http://" + GW_HOST + ":9090/metrics"
    return recorder.http(
        "gateway-metrics",
        url,
        expected_status=200,
        expected_content="# HELP",
        timeout=30,
        retries=3,
        delay=10,
    )


def scenario_gateway_api():
    start = time.monotonic()
    try:
        client = make_client()
        health = client.health()
        if health.status != 1:  # SERVICE_STATUS_HEALTHY
            raise RuntimeError(f"gRPC health status is not healthy: {health.status}")
        listed = list(client.list(workspace=WORKSPACE))
        recorder.record(
            "gateway-api",
            "exec",
            "pass",
            time.monotonic() - start,
            error=None,
        )
        return {
            "scenario_name": "gateway-api",
            "status": "pass",
            "output": f"gRPC healthy; {len(listed)} sandbox(es) listed",
        }
    except Exception as err:
        recorder.record(
            "gateway-api",
            "exec",
            "error",
            time.monotonic() - start,
            error=sanitize_error(err),
        )
        return {
            "scenario_name": "gateway-api",
            "status": "error",
            "output": sanitize_error(err),
        }


def scenario_sandbox_lifecycle():
    from openshell._proto import openshell_pb2

    start = time.monotonic()
    try:
        client = make_client()
        spec = build_spec()
        session = client.create_session(
            workspace=WORKSPACE, spec=spec, name=SANDBOX_NAME
        )
        ref = client.wait_ready(
            session.sandbox.name, workspace=WORKSPACE, timeout_seconds=240
        )
        exec_result = session.exec(
            ["sh", "-c", "echo openshell-poc-marker"], timeout_seconds=60
        )
        if exec_result.exit_code != 0 or "openshell-poc-marker" not in exec_result.stdout:
            raise RuntimeError(
                f"marker exec failed rc={exec_result.exit_code} "
                f"out={exec_result.stdout!r} err={exec_result.stderr!r}"
            )
        # Verify the Agent Sandbox CR and its pod in the namespace.
        code, cr_out, cr_err = kubectl("get", "sandbox", SANDBOX_NAME, "-o", "json")
        if code != 0:
            raise RuntimeError(f"Sandbox CR not found: {cr_err}")
        cr = json.loads(cr_out)
        code, pod_out, pod_err = kubectl(
            "get",
            "pods",
            "-l",
            f"openshell.ai/sandbox={SANDBOX_NAME}",
            "-o",
            "json",
        )
        if code != 0 or not pod_out:
            # Fall back to listing managed pods and matching by name prefix.
            code, pod_out, pod_err = kubectl(
                "get", "pods", "-l", "openshell.ai/managed-by=openshell", "-o", "json"
            )
        pods = json.loads(pod_out or "{}").get("items", [])
        match = [
            p
            for p in pods
            if SANDBOX_NAME in p["metadata"].get("name", "")
        ]
        if not match:
            raise RuntimeError(
                f"no pod found for sandbox {SANDBOX_NAME} "
                f"(managed pods: {len(pods)})"
            )
        containers = [c["name"] for c in match[0]["spec"]["containers"]]
        if not any("sandbox" in c.lower() or "runtime" in c.lower() for c in containers):
            raise RuntimeError(f"no sandbox-runtime container in pod: {containers}")
        sandbox_state["session"] = session
        sandbox_state["client"] = client
        recorder.record(
            "sandbox-lifecycle",
            "exec",
            "pass",
            time.monotonic() - start,
            error=None,
        )
        return {
            "scenario_name": "sandbox-lifecycle",
            "status": "pass",
            "output": (
                f"sandbox {ref.name} ready; marker exec ok; "
                f"CR present; pod containers: {containers}"
            ),
        }
    except Exception as err:
        recorder.record(
            "sandbox-lifecycle",
            "exec",
            "error",
            time.monotonic() - start,
            error=sanitize_error(err),
        )
        return {
            "scenario_name": "sandbox-lifecycle",
            "status": "error",
            "output": sanitize_error(err),
        }


def sandbox_exec(session, command, timeout_seconds=60):
    return session.exec(command, timeout_seconds=timeout_seconds)


def detect_tool(session):
    result = sandbox_exec(
        session,
        [
            "sh",
            "-c",
            "t=''; command -v curl >/dev/null && t=\"$t curl\"; "
            "command -v python3 >/dev/null && t=\"$t python3\"; "
            "command -v bash >/dev/null && t=\"$t bash\"; echo TOOL:$t",
        ],
    )
    text = (result.stdout or "") + (result.stderr or "")
    tool = "curl" if " curl" in text else "python3" if " python3" in text else "bash"
    return tool, result


def scenario_network_policy_enforcement():
    start = time.monotonic()
    session = sandbox_state["session"]
    if session is None:
        recorder.record(
            "network-policy-enforcement",
            "exec",
            "skip",
            time.monotonic() - start,
            error="sandbox from scenario 4 unavailable; enforcement not exercised",
        )
        return {
            "scenario_name": "network-policy-enforcement",
            "status": "skip",
            "output": "skipped: sandbox unavailable from scenario 4",
        }
    try:
        # Record every actual invocation; the terminal record carries the
        # scenario's overall outcome.
        det = detect_tool(session)
        tool = det[0]
        sandbox_state["tool"] = tool
        recorder.record(
            "network-policy-enforcement",
            "exec",
            "pass",
            0.0,
            error=f"tool detection: {det[1].stdout.strip()[:120]}",
        )

        # (a) allowed destination: example.com is in the sandbox policy.
        if tool == "curl":
            allowed_cmd = [
                "sh",
                "-c",
                'code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 20 '
                "http://example.com/ 2>&1) || true; echo ALLOWED:$code",
            ]
        elif tool == "python3":
            allowed_cmd = [
                "python3",
                "-c",
                "import urllib.request;"
                "r=urllib.request.urlopen('http://example.com/', timeout=20);"
                "print('ALLOWED:'+str(r.status))",
            ]
        else:
            allowed_cmd = [
                "bash",
                "-c",
                "exec 3<>/dev/tcp/example.com/80 && echo ALLOWED:connected || "
                "echo ALLOWED:failed",
            ]
        a_start = time.monotonic()
        allowed = sandbox_exec(session, allowed_cmd, timeout_seconds=45)
        allowed_text = (allowed.stdout or "") + (allowed.stderr or "")
        allowed_ok = (
            "ALLOWED:200" in allowed_text
            or "ALLOWED:connected" in allowed_text
        )
        recorder.record(
            "network-policy-enforcement",
            "exec",
            "pass" if allowed_ok else "fail",
            time.monotonic() - a_start,
            error=None if allowed_ok else "allowed egress assertion failed",
        )

        # (b) denied destination: 198.51.100.1 (TEST-NET-1) is not in policy.
        if tool == "curl":
            denied_cmd = [
                "sh",
                "-c",
                "curl -sS -o /dev/null --max-time 15 http://198.51.100.1/ "
                "2>/dev/null; echo DENIED_RC:$?",
            ]
        elif tool == "python3":
            denied_cmd = [
                "python3",
                "-c",
                "import socket,sys;"
                "s=socket.socket(); s.settimeout(15);"
                "try: s.connect(('198.51.100.1', 80)); print('DENIED_RC:0')"
                "except Exception as e: print('DENIED_RC:1')",
            ]
        else:
            denied_cmd = [
                "bash",
                "-c",
                "timeout 15 bash -c 'exec 3<>/dev/tcp/198.51.100.1/80' && "
                "echo DENIED_RC:0 || echo DENIED_RC:1",
            ]
        d_start = time.monotonic()
        denied = sandbox_exec(session, denied_cmd, timeout_seconds=45)
        denied_text = (denied.stdout or "") + (denied.stderr or "")
        denied_ok = "DENIED_RC:1" in denied_text
        if tool == "curl" and "DENIED_RC:0" in denied_text:
            denied_ok = False
        recorder.record(
            "network-policy-enforcement",
            "exec",
            "pass" if denied_ok else "fail",
            time.monotonic() - d_start,
            error=None if denied_ok else "denied egress was not blocked",
        )

        # (b2) real-reachable negative control: 1.1.1.1:443 is reachable from
        # the cluster (verified outside the sandbox) but is NOT in the sandbox
        # policy, so the kernel-mediated boundary should block it. This
        # disambiguates the doc-address (198.51.100.1) denial: a failure to
        # reach a documentation IP alone does not prove policy caused it, but a
        # real reachable host being blocked does.
        if tool == "curl":
            ctrl_cmd = [
                "sh",
                "-c",
                "curl -sS -o /dev/null --connect-timeout 12 --max-time 15 -k "
                "https://1.1.1.1/ 2>/dev/null; echo CTRL_RC:$?",
            ]
        elif tool == "python3":
            ctrl_cmd = [
                "python3",
                "-c",
                "import socket;"
                "s=socket.socket(); s.settimeout(15);"
                "try: s.connect(('1.1.1.1', 443)); print('CTRL_RC:0')"
                "except Exception as e: print('CTRL_RC:1')",
            ]
        else:
            ctrl_cmd = [
                "bash",
                "-c",
                "timeout 15 bash -c 'exec 3<>/dev/tcp/1.1.1.1/443' && "
                "echo CTRL_RC:0 || echo CTRL_RC:1",
            ]
        c_start = time.monotonic()
        ctrl = sandbox_exec(session, ctrl_cmd, timeout_seconds=45)
        ctrl_text = (ctrl.stdout or "") + (ctrl.stderr or "")
        negctrl_blocked = any(
            tag in ctrl_text for tag in ("CTRL_RC:1", "CTRL_RC:7", "CTRL_RC:28")
        )
        if any(tag in ctrl_text for tag in ("CTRL_RC:0", "CTRL_RC:52")):
            negctrl_blocked = False
        recorder.record(
            "network-policy-enforcement",
            "exec",
            "pass" if negctrl_blocked else "fail",
            time.monotonic() - c_start,
            error=None if negctrl_blocked else "real reachable host was not blocked",
        )

        # (c) outer fence: a NetworkPolicy governing the sandbox pod exists.
        code, np_out, np_err = kubectl("get", "networkpolicies", "-o", "json")
        fence_names = []
        if code == 0 and np_out:
            for np in json.loads(np_out).get("items", []):
                sel = (
                    np.get("spec", {})
                    .get("podSelector", {})
                    .get("matchLabels", {})
                )
                if "openshell.ai/boundary-pair" in sel or "openshell.ai/managed-by" in sel:
                    fence_names.append(np["metadata"]["name"])

        # Enforcement is demonstrated when the in-policy real host is allowed
        # AND a real reachable out-of-policy host is blocked, with the outer
        # fence present. The doc-address denial (b) is corroborating only: a
        # documentation IP is unreachable regardless of policy, so it cannot by
        # itself prove the boundary blocked the egress.
        outcome = "pass" if (allowed_ok and negctrl_blocked and fence_names) else "fail"
        detail = (
            f"tool={tool}; allowed example.com[in-policy] -> {allowed_text.strip()[:120]}; "
            f"negctrl 1.1.1.1:443[real,out-of-policy] -> {ctrl_text.strip()[:120]}; "
            f"denied 198.51.100.1[doc] -> {denied_text.strip()[:120]}; "
            f"outer-fence NetworkPolicies: {fence_names}"
        )
        err = None if outcome == "pass" else ("enforcement assertion failed: " + detail)
        recorder.record(
            "network-policy-enforcement",
            "exec",
            outcome,
            0.0,
            error=err,
        )
        return {
            "scenario_name": "network-policy-enforcement",
            "status": outcome,
            "output": detail,
        }
    except Exception as err:
        recorder.record(
            "network-policy-enforcement",
            "exec",
            "error",
            time.monotonic() - start,
            error=sanitize_error(err),
        )
        return {
            "scenario_name": "network-policy-enforcement",
            "status": "error",
            "output": sanitize_error(err),
        }
    finally:
        # Tear down the sandbox regardless of outcome.
        try:
            client = sandbox_state["client"]
            if client is not None:
                client.delete(
                    SANDBOX_NAME, workspace=WORKSPACE, allow_missing=True
                )
                client.wait_deleted(
                    SANDBOX_NAME, workspace=WORKSPACE, timeout_seconds=120
                )
        except Exception:
            pass


def main():
    results.append(scenario_gateway_health())
    results.append(scenario_gateway_metrics())
    results.append(scenario_gateway_api())
    results.append(scenario_sandbox_lifecycle())
    results.append(scenario_network_policy_enforcement())

    for r in results:
        r.setdefault("error_message", None)
        r.setdefault("duration_seconds", 0)

    print(json.dumps({"results": results}))
    bad = [r for r in results if r["status"] in ("fail", "error")]
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
