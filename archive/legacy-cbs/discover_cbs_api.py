import json
import re
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import Request, Response, sync_playwright


LEAGUE_HOST = "kjfha.football.cbssports.com"
START_URL = f"https://{LEAGUE_HOST}/"
AUTH_STATE = Path(".auth/cbs_state.json")
OUTPUT = Path("discovery_output")
OUTPUT_FILE = OUTPUT / "cbs_lineup_write_candidates.json"
TRACE_FILE = OUTPUT / "cbs_request_trace.jsonl"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MAX_CANDIDATES = 50
MAX_TRACE_REQUESTS = 500

SENSITIVE_NAME = re.compile(
    r"token|auth|cookie|csrf|password|secret|session|api.?key|email|user.?id|^id$",
    re.IGNORECASE,
)
SAFE_HEADERS = {"accept", "content-type", "x-requested-with"}


def _redact_value(name, value):
    if SENSITIVE_NAME.search(name):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {key: _redact_value(str(key), item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(name, item) for item in value]
    return value


def sanitize_url(url):
    """Remove credential-like query values while preserving useful request IDs."""
    parts = urlsplit(url)
    query = [
        (key, "[REDACTED]" if SENSITIVE_NAME.search(key) else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _safe_headers(headers):
    return {
        name.lower(): value
        for name, value in headers.items()
        if name.lower() in SAFE_HEADERS
    }


def sanitize_post_data(post_data, content_type):
    """Keep JSON or form fields needed to understand a request, redacting secrets."""
    if not post_data:
        return None

    if "application/x-www-form-urlencoded" in content_type.lower():
        fields = {}
        for name, value in parse_qsl(post_data, keep_blank_values=True):
            if name in fields:
                current = fields[name]
                fields[name] = (
                    current + [value]
                    if isinstance(current, list)
                    else [current, value]
                )
            else:
                fields[name] = value
        return _redact_value("", fields)

    try:
        payload = json.loads(post_data)
    except json.JSONDecodeError:
        return {"omitted": "unsupported request body", "length": len(post_data)}
    return _redact_value("", payload)


def _save_candidates(candidates):
    temporary_file = OUTPUT_FILE.with_suffix(".tmp")
    temporary_file.write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary_file.replace(OUTPUT_FILE)


def _is_cbs_request(request):
    hostname = urlsplit(request.url).hostname or ""
    return hostname == LEAGUE_HOST or hostname.endswith(".cbssports.com")


def _is_candidate(request):
    parts = urlsplit(request.url)
    if parts.hostname != LEAGUE_HOST:
        return False

    method = request.method.upper()
    if method in WRITE_METHODS:
        return True
    if method != "GET":
        return False

    query = parse_qsl(parts.query, keep_blank_values=True)
    action = any(
        key.lower() in {"action", "type", "operation"}
        and any(term in value.lower() for term in ("lineup", "roster", "add", "drop"))
        for key, value in query
    )
    return action


def main():
    if not AUTH_STATE.is_file():
        raise FileNotFoundError(
            f"CBS login state not found: {AUTH_STATE}. "
            "Run cbs_session.py to create it."
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidates = []
    pending = {}
    trace_request_count = 0
    _save_candidates(candidates)
    TRACE_FILE.write_text("", encoding="utf-8")

    print(
        "This tool only observes requests caused by your manual browser actions. "
        "It never submits or replays a CBS request."
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context(storage_state=str(AUTH_STATE))
            page = context.new_page()

            def capture_request(request: Request):
                nonlocal trace_request_count
                if _is_cbs_request(request) and trace_request_count < MAX_TRACE_REQUESTS:
                    trace_record = {
                        "captured_at": datetime.now().astimezone().isoformat(
                            timespec="seconds"
                        ),
                        "method": request.method.upper(),
                        "url": sanitize_url(request.url),
                        "resource_type": request.resource_type,
                        "candidate": _is_candidate(request),
                    }
                    with TRACE_FILE.open("a", encoding="utf-8") as trace_file:
                        trace_file.write(
                            json.dumps(trace_record, ensure_ascii=False) + "\n"
                        )
                    trace_request_count += 1
                    print(
                        f"Observed CBS {trace_record['method']} "
                        f"{urlsplit(trace_record['url']).path}"
                    )

                if not _is_candidate(request):
                    return
                if len(candidates) >= MAX_CANDIDATES:
                    print(
                        f"Candidate limit reached ({MAX_CANDIDATES}); "
                        "continuing request trace only."
                    )
                    return

                content_type = request.headers.get("content-type", "")
                record = {
                    "captured_at": datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    ),
                    "method": request.method.upper(),
                    "url": sanitize_url(request.url),
                    "headers": _safe_headers(request.headers),
                    "body": sanitize_post_data(request.post_data, content_type),
                    "response": None,
                }
                candidates.append(record)
                pending[id(request)] = record
                _save_candidates(candidates)
                print(f"Captured {record['method']} {urlsplit(record['url']).path}")

            def capture_response(response: Response):
                if _is_cbs_request(response.request):
                    with TRACE_FILE.open("a", encoding="utf-8") as trace_file:
                        trace_file.write(
                            json.dumps(
                                {
                                    "event": "response",
                                    "url": sanitize_url(response.url),
                                    "method": response.request.method.upper(),
                                    "status": response.status,
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )

                record = pending.pop(id(response.request), None)
                if record is None:
                    return
                record["response"] = {
                    "status": response.status,
                    "content_type": response.headers.get("content-type", ""),
                }
                _save_candidates(candidates)
                print(f"  CBS response: HTTP {response.status}")

            context.on("request", capture_request)
            context.on("response", capture_response)
            page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)

            print(
                "\nIn the browser, navigate to your CBS lineup and make the "
                "lineup or player transaction yourself if you want to inspect "
                "its request."
                "\nThe observer must be running before you make/save the change. "
                "It cannot recover requests from earlier changes."
                "\nThe script will not perform or repeat any change."
                f"\nAll CBS-domain requests will be traced to {TRACE_FILE}; "
                "only possible changes go to the candidates file."
                "\nPress Enter here when finished."
            )
            input_finished = threading.Event()

            def wait_for_enter():
                try:
                    input()
                except EOFError:
                    pass
                finally:
                    input_finished.set()

            threading.Thread(target=wait_for_enter, daemon=True).start()
            while not input_finished.is_set():
                page.wait_for_timeout(100)
        finally:
            browser.close()

    print(f"Captured {len(candidates)} request(s).")
    print(f"Sanitized request details saved to: {OUTPUT_FILE}")
    print(f"Observed {trace_request_count} CBS request(s).")
    print(f"Sanitized request trace saved to: {TRACE_FILE}")


if __name__ == "__main__":
    main()
