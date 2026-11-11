"""Opt-in live deployment check. Creates and removes only labeled test records.

Run prepare, gracefully restart the application's services, then run complete.
Credentials remain in process memory and are never printed or written to reports.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--stage", choices=("prepare", "complete", "cleanup"), required=True)
    args = parser.parse_args()
    config = json.loads((args.runtime / "config.json").read_text(encoding="utf-8-sig"))
    token = (Path(config["data_dir"]) / "access.token").read_text().strip()
    base = args.base_url.rstrip("/") + "/api/v1"
    if args.base_url != config.get("public_origin") and args.base_url != f"http://127.0.0.1:{config['port']}":
        raise ValueError("Only the configured local or HTTPS origin may receive credentials")
    report_file = args.runtime / "diagnostics" / "deployment-check.json"

    def call(path, body=None, method=None, credential=token, headers=None, expected=200):
        request_headers = {"User-Agent": "SextaFeira-DeploymentVerifier/1.0", "Accept": "application/json"}
        if credential:
            request_headers["Authorization"] = "Bearer " + credential
        data = None
        if body is not None:
            request_headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        request_headers.update(headers or {})
        request = urllib.request.Request(base + path, data=data, headers=request_headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=90)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            status = response.code
            if status != expected:
                raise AssertionError(f"{method or 'GET'} {path}: expected {expected}, got {status}; type={response.headers.get('Content-Type')}; challenge={response.headers.get('cf-mitigated')}")
            payload = json.load(response)
        return payload

    if args.stage == "prepare":
        if report_file.exists():
            raise RuntimeError("Existing check report preserved; finish or review that check first")
        report = {"base_url": args.base_url, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "marker": "Sexta deployment verification " + uuid.uuid4().hex, "checks": {}}
        checks = report["checks"]
        call("/health", credential="", expected=401)
        call("/health", credential="invalid", expected=401)
        checks["unauthenticated_and_invalid_credentials"] = "401"
        call("/health", headers={"Origin": "https://unauthorized.invalid"}, expected=403)
        checks["foreign_origin"] = "403"
        call("/health")
        checks["authenticated_https_health"] = "passed"
        session = call("/sessions", {"role": "user"}, expected=201)
        call("/metrics", credential=session["token"], expected=403)
        call("/sessions/current", method="DELETE", credential=session["token"])
        call("/health", credential=session["token"], expected=401)
        checks["user_role_and_session_revocation"] = "passed"
        marker = report["marker"]
        memory = call("/memories", {"content": marker}, expected=201)
        report["memory_id"] = memory["id"]
        report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        call("/memories/" + str(memory["id"]), {"content": marker + " corrected"}, "PATCH")
        task = call("/tasks", {"content": marker}, expected=201)
        report["task_id"] = task["id"]
        report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        call("/tasks/" + str(task["id"]), {"completed": True}, "PATCH")
        checks["memory_correction_and_task_completion"] = "passed"
        tool = call("/conversations", {"message": "/hora"})
        assert tool["source"] == "tool" and tool["action_executed"] is True
        checks["deterministic_tool"] = "passed"
        timings = []
        for _ in range(2):
            started = time.perf_counter()
            reply = call("/conversations", {"message": "Olá, apresente-se em uma frase."})
            timings.append(round(time.perf_counter() - started, 3))
            assert reply["source"] == "gpt2" and reply["reply"].strip() and not reply["action_executed"]
        report["cold_then_warm_response_seconds"] = timings
        def concurrent_chat(_):
            started = time.perf_counter()
            response = call("/conversations", {"message": "Diga uma frase curta sobre o dia."})
            assert response["source"] == "gpt2" and response["reply"].strip()
            return round(time.perf_counter() - started, 3)
        with ThreadPoolExecutor(max_workers=2) as workers:
            report["two_queued_response_seconds"] = list(workers.map(concurrent_chat, range(2)))
        checks["real_cpu_inference_and_bounded_serial_queue"] = "passed"
        report["metrics"] = call("/metrics")
        checks["database_integrity"] = call("/admin/integrity")["integrity"]
        checks["backup"] = call("/admin/backup", {}, expected=201)["integrity"]
        checks["openapi"] = call("/openapi.json")["openapi"]
        exported = call("/export")
        assert isinstance(exported, dict) and "sessions" not in exported
        checks["export"] = "passed"
        report["stage"] = "awaiting_controlled_restart"
    else:
        report = json.loads(report_file.read_text(encoding="utf-8"))
        if report.get("stage") != "awaiting_controlled_restart":
            raise RuntimeError("No prepared restart check")
        marker = report["marker"]
        memory = next(m for m in call("/memories")["memories"] if m["id"] == report["memory_id"])
        task = next(t for t in call("/tasks")["tasks"] if t["id"] == report["task_id"])
        assert memory["content"] == marker + " corrected" and task["content"] == marker and task["completed"]
        history = call("/history")["history"]
        assert any(m["content"] == "/hora" for m in history)
        read_check = "history_memories_tasks_after_restart" if args.stage == "complete" else "history_memories_tasks_from_new_client"
        report["checks"][read_check] = "passed"
        call("/memories/" + str(report["memory_id"]), method="DELETE")
        call("/tasks/" + str(report["task_id"]), method="DELETE")
        assert not any(m["id"] == report["memory_id"] for m in call("/memories")["memories"])
        assert not any(t["id"] == report["task_id"] for t in call("/tasks")["tasks"])
        report["checks"]["test_records_deleted"] = "passed"
        report["checks"]["database_integrity_after_cleanup"] = call("/admin/integrity")["integrity"]
        report["stage"] = "complete" if args.stage == "complete" else "complete_restart_check_pending"
    report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
