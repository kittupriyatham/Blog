"""GitHub integration module for automatic issue tracking.

Creates issues in GitHub repository when blog/syndication errors or
feedback reports are logged.
"""
import json
import os
import threading
import urllib.request
import urllib.error

from core.config import SITE_URL

GITHUB_REPO = os.environ.get("GITHUB_REPO", "kittupriyatham/Blog").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()


def is_configured() -> bool:
    """Return True if GitHub issue reporting is enabled with a token."""
    return bool(GITHUB_TOKEN and GITHUB_REPO)


def create_github_issue(title: str, body: str, labels: list = None) -> dict:
    """Synchronously create an issue in the configured GitHub repo.

    Returns dict with {"ok": True, "issue_url": str, "issue_number": int}
    or {"ok": False, "error": str}.
    """
    token = os.environ.get("GITHUB_TOKEN", "").strip() or GITHUB_TOKEN
    repo = os.environ.get("GITHUB_REPO", "").strip() or GITHUB_REPO

    if not token or not repo:
        return {"ok": False, "error": "GITHUB_TOKEN or GITHUB_REPO not configured"}

    api_url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "KittuBlog-IssueTracker",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title[:250],
        "body": body,
    }
    if labels:
        payload["labels"] = labels

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(api_url, data=data_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_body = resp.read().decode("utf-8")
            result = json.loads(resp_body)
            issue_url = result.get("html_url")
            issue_num = result.get("number")
            print(f"[github] Created issue #{issue_num}: {issue_url}")
            return {"ok": True, "issue_url": issue_url, "issue_number": issue_num}
    except urllib.error.HTTPError as he:
        err_msg = f"HTTP {he.code}: {he.read().decode('utf-8', errors='replace')[:300]}"
        print(f"[github] HTTPError creating issue: {err_msg}")
        return {"ok": False, "error": err_msg}
    except Exception as e:
        print(f"[github] Error creating issue: {e}")
        return {"ok": False, "error": str(e)}


def create_issue_for_report(issue_doc: dict):
    """Format and open a GitHub issue from an IssueReport document."""
    report_id = issue_doc.get("report_id") or "unknown"
    reporter = issue_doc.get("reporter") or "Author"
    user_text = issue_doc.get("text") or "No description"
    post_id = issue_doc.get("post_id") or "N/A"
    created_at = issue_doc.get("created_at") or ""

    title = f"[Report] {user_text[:80]}"
    body = (
        f"### 🚨 Issue Reported via Telegram\n\n"
        f"- **Report ID:** `{report_id}`\n"
        f"- **Reporter:** {reporter}\n"
        f"- **Target Post ID:** `{post_id}`\n"
        f"- **Reported At:** `{created_at}`\n\n"
        f"#### Description:\n"
        f"> {user_text}\n\n"
        f"---\n"
        f"*Logged automatically by Blog System*"
    )
    res = create_github_issue(title, body, labels=["bug", "telegram-report"])
    if res.get("ok"):
        try:
            from core.db import IssueReport
            IssueReport._get_collection().update_one(
                {"report_id": report_id},
                {"$set": {
                    "github_issue_url": res.get("issue_url"),
                    "github_issue_number": res.get("issue_number")
                }}
            )
        except Exception as e:
            print(f"[github] Could not update IssueReport with github info: {e}")
    return res


def create_issue_async(title: str, body: str, labels: list = None):
    """Spawns background thread so it doesn't block web requests or Telegram webhook response."""
    threading.Thread(target=create_github_issue, args=(title, body, labels), daemon=True).start()


def create_report_issue_async(issue_doc: dict):
    """Spawns background thread to open issue from IssueReport doc."""
    threading.Thread(target=create_issue_for_report, args=(issue_doc,), daemon=True).start()
