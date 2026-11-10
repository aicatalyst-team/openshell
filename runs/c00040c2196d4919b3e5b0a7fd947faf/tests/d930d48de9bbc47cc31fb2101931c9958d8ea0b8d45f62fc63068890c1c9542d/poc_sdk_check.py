"""Fresh generated SDK actions, invoked separately by poc_test.py, never pytest."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from urllib.parse import urlsplit

import poc_test as support


def execute(action, service_url, deadline):
    import grpc
    from openshell import SandboxClient, TlsConfig
    from openshell._proto import openshell_pb2 as api, sandbox_pb2 as policy_api, datamodel_pb2 as dm

    index = {"auth": 0, "process": 1, "lifecycle": 2, "cleanup": 4}[action]
    context = support.Context(support.SCENARIOS[index], deadline)
    parsed = urlsplit(service_url)
    support.require(parsed.scheme == "https" and bool(parsed.hostname)
                    and not parsed.username and not parsed.password
                    and not parsed.query and not parsed.fragment and parsed.path in ("", "/"),
                    "invalid_response_or_configuration")
    endpoint = parsed.netloc  # The SDK expects host:port, never an https:// prefix.
    ca = support.PRIVATE / "ca.crt"
    tls = TlsConfig(ca_path=ca, cert_path=support.PRIVATE / "client.crt",
                    key_path=support.PRIVATE / "client.key")

    class ObservedClient(SandboxClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Include owner lookup and the SDK's internal unrouted-exec retry.
            # Recording only client.exec() would silently lose that first attempt.
            for method in ("Health", "ListSandboxes", "GetSandbox", "CreateSandbox",
                           "StopSandbox", "StartSandbox", "DeleteSandbox", "ExecSandbox"):
                setattr(self._stub, method, RecordedRpc(getattr(self._stub, method), method))

        # wait_deleted calls self.get on every poll, retaining each actual request.
        def get(self, name, *, workspace):
            self._timeout = context.remaining(15)
            value = super().get(name, workspace=workspace)
            context.observe("sandbox_status", {"id": value.id, "name": value.name,
                                               "workspace": value.workspace,
                                               "status_phase": api.SandboxPhase.Name(value.status.phase)})
            return value

    class RecordedRpc:
        def __init__(self, rpc, method):
            self.rpc, self.method = rpc, method

        def __call__(self, *args, **kwargs):
            kwargs["timeout"] = context.remaining(kwargs.get("timeout", 20))
            if self.method == "ExecSandbox":
                # These fixed commands emit only a few bytes. Consume within the
                # attempt boundary so a stream error is recorded before SDK retry.
                events = context.call("rpc_" + self.method, "exec",
                                      lambda: list(self.rpc(*args, **kwargs)))
                return iter(events)
            def unary():
                response = self.rpc(*args, **kwargs)
                if self.method == "CreateSandbox":
                    # Journal the actual wire identity before even recording the RPC.
                    metadata = response.sandbox.metadata
                    data["id"] = metadata.id
                    data["created_by_this_execution"] = True
                    support.write_json(support.IDENTITY, data)
                return response
            return context.call("rpc_" + self.method, "exec", unary)

        def with_call(self, *args, **kwargs):
            kwargs["timeout"] = context.remaining(kwargs.get("timeout", 20))
            return context.call("rpc_" + self.method + "_with_call", "exec",
                                lambda: self.rpc.with_call(*args, **kwargs))

    def request(operation, function):
        client._timeout = context.remaining(20)
        return context.call(operation, "exec", function)

    def same(ref, data):
        support.require(ref.id == data["id"] and ref.name == support.NAME
                        and ref.workspace == support.WORKSPACE, "sandbox_identity_changed")

    def wait_phase(target, data):
        while True:
            ref = client.get(support.NAME, workspace=support.WORKSPACE)
            same(ref, data)
            if ref.status.phase == target:
                return ref
            if ref.status.phase in (api.SANDBOX_PHASE_ERROR, api.SANDBOX_PHASE_COMPLETED):
                raise support.CheckError("sandbox_error_phase", "fail")
            context.remaining()
            time.sleep(min(2, context.remaining()))

    def exec_command(operation, command):
        result = request(operation, lambda: client.exec(
            support.NAME, command, workspace=support.WORKSPACE,
            workdir="/sandbox", timeout_seconds=max(1, int(context.remaining(25))),
            no_login_shell=True))
        # Unexpected output is represented by a digest, never echoed into evidence.
        context.observe(operation + "_result", {
            "command": command, "exit_code": result.exit_code,
            "stdout_bytes": len(result.stdout.encode()),
            "stderr_bytes": len(result.stderr.encode()),
            "stdout_sha256": support.hashlib.sha256(result.stdout.encode()).hexdigest(),
            "stderr_sha256": support.hashlib.sha256(result.stderr.encode()).hexdigest(),
        })
        safe_outputs = {"", "story-c00040c2-stdout\n", "story-c00040c2-stderr\n"}
        if result.stdout in safe_outputs and result.stderr in safe_outputs:
            context.observe(operation + "_known_output", {"stdout": result.stdout, "stderr": result.stderr})
        return result

    with ObservedClient(endpoint, tls=tls, timeout=context.remaining(20)) as client:
        if action == "auth":
            health = request("sdk_Health_with_client_certificate", client.health)
            context.observe("authenticated_health", {"service_status": int(health.status)})
            support.require(health.status == api.SERVICE_STATUS_HEALTHY,
                            "authenticated_health_not_healthy")
            # ListSandboxes is authenticated; Health deliberately is not a negative control.
            request("sdk_ListSandboxes_with_client_certificate", lambda:
                client._stub.ListSandboxes(api.ListSandboxesRequest(
                    workspace_scope=dm.WorkspaceSelector(workspace=support.WORKSPACE), page_size=1)))
            with SandboxClient(endpoint, tls=TlsConfig(ca_path=ca),
                               timeout=context.remaining(12)) as anonymous:
                def negative():
                    try:
                        anonymous._stub.ListSandboxes(api.ListSandboxesRequest(
                            workspace_scope=dm.WorkspaceSelector(workspace=support.WORKSPACE), page_size=1),
                            timeout=context.remaining(12))
                    except grpc.RpcError as exc:
                        code = exc.code()
                        # UNAVAILABLE alone could be DNS or outage, not authentication proof.
                        if code not in (grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.PERMISSION_DENIED):
                            raise support.CheckError("unauthenticated_rpc_transport_ambiguous") from None
                        context.observe("no_client_certificate_authenticated_rpc", {
                            "rpc": "ListSandboxes", "grpc_status": code.name, "rejected": True})
                        return
                    raise support.CheckError("unauthenticated_rpc_not_rejected", "fail")
                context.call("sdk_ListSandboxes_without_client_certificate", "exec", negative)
            return

        data = support.identity(context.execution)
        if action == "process":
            support.require(data is None, "sandbox_already_exists")
            try:
                client.get(support.NAME, workspace=support.WORKSPACE)
            except grpc.RpcError as exc:
                if exc.code() != grpc.StatusCode.NOT_FOUND:
                    raise
            else:
                raise support.CheckError("sandbox_already_exists")
            image = os.environ.get("OPEN_SHELL_WORKLOAD_IMAGE", support.IMAGE)
            support.require(image == support.IMAGE or bool(re.fullmatch(
                r"quay\.io/aicatalyst/openshell-sandbox@sha256:[a-f0-9]{64}", image)),
                "workload_image_not_run_pinned")
            # No baked-in /etc/openshell/policy.yaml exists in this minimal UBI image.
            # Leave user/group unset: the boundary pins these to the SCC workload identity.
            policy = policy_api.SandboxPolicy(
                version=1,
                filesystem=policy_api.FilesystemPolicy(
                    include_workdir=True,
                    read_only=["/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc", "/proc", "/dev/urandom"],
                    read_write=["/sandbox", "/tmp"]),
                landlock=policy_api.LandlockPolicy(compatibility="best_effort"),
                process=policy_api.ProcessPolicy())
            spec = api.SandboxSpec(policy=policy, command=["/usr/bin/sleep", "infinity"])
            spec.template.image = image
            spec.template.driver_config.update({"kubernetes": {"pod": {
                "node_selector": {"kubernetes.io/hostname": support.NODE}}}})
            context.observe("source_and_create_setup", {
                "source_revision": support.REVISION, "sdk": "fresh generated source SDK",
                "workspace": support.WORKSPACE, "name": support.NAME,
                "workload_image": image, "command": list(spec.command),
                "driver_config": {"kubernetes": {"pod": {"node_selector": {
                    "kubernetes.io/hostname": support.NODE}}}},
                "policy": {"version": 1, "read_only": list(policy.filesystem.read_only),
                           "read_write": list(policy.filesystem.read_write),
                           "landlock": "best_effort", "process_identity": "runtime SCC identity",
                           "network_rules": 0},
                "trusted_runtime": "separately configured by Helm; not set by workload template",
            })
            data = {"run_id": support.RUN, "execution_id": context.execution,
                    "name": support.NAME, "workspace": support.WORKSPACE,
                    "create_intent": True}
            support.write_json(support.IDENTITY, data)

            created = request("sdk_CreateSandbox_once_no_retry", lambda: client.create(
                workspace=support.WORKSPACE, name=support.NAME, spec=spec,
                labels={"poc-run": support.RUN, "poc-execution": context.execution}))
            same(created, data)
            ready = wait_phase(api.SANDBOX_PHASE_READY, data)
            support.require(ready.status.phase == api.SANDBOX_PHASE_READY, "sandbox_not_ready")
            result = exec_command("sdk_exec_process_contract", ["/bin/sh", "-c",
                "printf 'story-c00040c2-stdout\\n'; printf 'story-c00040c2-stderr\\n' >&2; exit 7"])
            matches = (result.exit_code == 7 and result.stdout == "story-c00040c2-stdout\n"
                       and result.stderr == "story-c00040c2-stderr\n")
            context.observe("process_contract_assertion", {"matches": matches,
                "expected_exit_code": 7, "expected_stdout": "story-c00040c2-stdout\n",
                "expected_stderr": "story-c00040c2-stderr\n"})
            support.require(matches, "process_contract_mismatch")
            uid = exec_command("sdk_exec_non_root_uid", ["/usr/bin/id", "-u"])
            uid_text = uid.stdout.strip()
            valid = uid.exit_code == 0 and not uid.stderr and uid_text.isascii() and uid_text.isdecimal()
            context.observe("non_root_uid", {"uid": int(uid_text) if valid else None})
            support.require(valid and int(uid_text) > 0, "non_root_uid_not_observed")
            return

        if not data or not data.get("create_intent"):
            raise support.CheckError("sandbox_not_created", "skip")
        if not data.get("id"):
            # A timed-out create is not retried. Reconcile only this execution's labels.
            try:
                ref = client.get(support.NAME, workspace=support.WORKSPACE)
            except grpc.RpcError as exc:
                if exc.code() == grpc.StatusCode.NOT_FOUND:
                    raise support.CheckError("sandbox_not_created", "skip") from None
                raise
            support.require(ref.labels.get("poc-run") == support.RUN
                            and ref.labels.get("poc-execution") == context.execution,
                            "sandbox_ownership_unconfirmed")
            data["id"] = ref.id
            data["created_by_this_execution"] = True
            support.write_json(support.IDENTITY, data)

        if action == "lifecycle":
            same(client.get(support.NAME, workspace=support.WORKSPACE), data)
            marker = f"{support.RUN}:{data['id']}:{context.execution}"
            result = exec_command("sdk_exec_marker_write", ["/bin/sh", "-c",
                "set -e; umask 077; printf '%s' \"$1\" > /sandbox/story-c00040c2.marker; sync",
                "poc-marker", marker])
            support.require(result.exit_code == 0 and not result.stderr, "marker_write_failed")
            same(request("sdk_StopSandbox", lambda: client.stop(
                support.NAME, workspace=support.WORKSPACE)), data)
            stopped = wait_phase(api.SANDBOX_PHASE_STOPPED, data)
            support.require(stopped.status.phase == api.SANDBOX_PHASE_STOPPED, "sandbox_not_stopped")
            same(request("sdk_StartSandbox", lambda: client.start(
                support.NAME, workspace=support.WORKSPACE)), data)
            ready = wait_phase(api.SANDBOX_PHASE_READY, data)
            support.require(ready.status.phase == api.SANDBOX_PHASE_READY, "sandbox_not_ready")
            result = exec_command("sdk_exec_marker_read", ["/usr/bin/cat", "/sandbox/story-c00040c2.marker"])
            matches = result.exit_code == 0 and not result.stderr and result.stdout == marker
            context.observe("marker_identity_assertion", {"same_sandbox_id": ready.id == data["id"],
                "marker_matches": matches, "marker_sha256": support.hashlib.sha256(marker.encode()).hexdigest()})
            support.require(matches, "marker_readback_mismatch")
        elif action == "cleanup":
            try:
                same(client.get(support.NAME, workspace=support.WORKSPACE), data)
            except grpc.RpcError as exc:
                if exc.code() != grpc.StatusCode.NOT_FOUND:
                    raise
                raise support.CheckError("sandbox_not_created", "skip") from None
            support.require(data.get("created_by_this_execution"), "sandbox_ownership_unconfirmed")
            if not data.get("cr_names") or not data.get("pod_names"):
                # A create-response timeout can leave only a recovered SDK identity.
                # Still try deletion if Kubernetes observation itself is unavailable.
                try:
                    support.own_resources(context, data)
                except Exception as exc:
                    context.observe("cleanup_pre_delete_observation", {
                        "error_category": support.category(exc)})
            request("sdk_DeleteSandbox_own_only", lambda: client.delete(
                support.NAME, workspace=support.WORKSPACE, allow_missing=False))
            request("sdk_wait_deleted_own_id", lambda: client.wait_deleted(
                support.NAME, workspace=support.WORKSPACE,
                expected_sandbox_id=data["id"], timeout_seconds=context.remaining(100)))
            context.observe("sdk_deletion", {"sandbox_id": data["id"], "wait_deleted": True})


def main():
    os.umask(0o077)
    logging.disable(logging.CRITICAL)
    action = sys.argv[1] if len(sys.argv) > 1 else "invalid"
    try:
        execute(action, sys.argv[2], float(sys.argv[3]))
        reply = {"action": action, "status": "pass"}
    except Exception as exc:
        reply = {"action": action,
                 "status": exc.status if isinstance(exc, support.CheckError) else "error",
                 "error_category": support.category(exc)}
    print(json.dumps(reply, sort_keys=True))
    return 0 if reply["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
