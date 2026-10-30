"""Native in-app AI conversational drafting and formatting studio.

Supports iterative collaboration with Google Gemini:
- Author provides an initial thought, spark, or rough outline.
- Mutual conversational refinement loop: discussion, questions, suggestions, tone/depth tuning.
- Live structured draft maintenance:
    * Micro-post: Body text + tags.
    * Article: Title, tags, and structured text/heading blocks.
      (Articles draft text only; media upload is manually handled by the author).
- One-click finalization: save directly as a draft or publish immediately to the blog.
"""
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
TIMEOUT_S = 90


def _api_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _model() -> str:
    return os.environ.get("REWRITE_MODEL", "").strip() or DEFAULT_MODEL


def is_available() -> bool:
    """True when Gemini API key is configured."""
    return bool(_api_key())


_SYSTEM_INSTRUCTION = (
    "You are an expert AI co-author, editor, and thought partner for a personal technical blog.\n"
    "Your collaborator is a software engineer and architect building modern web systems, distributed tools, and developer workflows.\n\n"
    "Your objective:\n"
    "Engage in an iterative, collaborative conversation to brainstorm, explore, draft, and refine high-quality technical content.\n"
    "Every turn consists of two interconnected parts:\n"
    "1. `reply` (Conversational Message): Discuss the idea with the author. Offer constructive perspectives, suggest structure, ask clarifying questions to uncover details, highlight edge cases, and explain what changes were made in the working draft.\n"
    "2. `draft` (Structured Working Draft): Maintain the active, up-to-date draft reflecting the current state of discussion.\n\n"
    "CRITICAL RULES FOR DRAFT:\n"
    "- If Mode is 'article':\n"
    "  * You MUST ALWAYS provide `title`, `tags`, and `blocks` in `draft`.\n"
    "  * `draft.blocks` MUST contain the complete, structured content of the article split into text blocks: `[{'type': 'text', 'content': '...'}]`.\n"
    "  * Structure blocks using rich Markdown with headings ('# ', '## ', '### '), lists, quotes, and code blocks.\n"
    "  * When the author provides notes or requests additions, integrate them directly into `draft.blocks` so the draft is always ready to publish.\n"
    "  * NEVER omit `blocks` or leave it empty in article mode.\n"
    "  * Generate ONLY text and heading blocks. Do NOT invent fake image URLs, media blocks, or image placeholders. Media is added manually by the author.\n"
    "- If Mode is 'post':\n"
    "  * You MUST provide `body` (punchy, engaging text) and `tags` (2-5 tags) in `draft`.\n\n"
    "Always return valid JSON adhering strictly to the schema."
)


def _clean_json_text(raw_text: str) -> str:
    """Strip markdown code block fences if returned by the model."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _format_draft_context(draft: Optional[Dict[str, Any]], mode: str) -> str:
    """Format existing draft into a clean, compact prompt context string."""
    if not draft:
        return ""
    lines = [f"[Current Working Draft - Mode: {mode.upper()}]"]
    if draft.get("title"):
        lines.append(f"Title: {draft['title']}")
    if draft.get("tags"):
        tags = draft["tags"]
        if isinstance(tags, list):
            lines.append(f"Tags: {', '.join(str(t) for t in tags)}")
        elif isinstance(tags, str):
            lines.append(f"Tags: {tags}")
    if mode == "post" and draft.get("body"):
        lines.append(f"Body:\n{draft['body']}")
    elif mode == "article" and draft.get("blocks"):
        block_lines = []
        for idx, b in enumerate(draft["blocks"]):
            if isinstance(b, dict):
                c = b.get("content", "")
            else:
                c = str(b)
            if c and c.strip():
                block_lines.append(f"--- Block {idx+1} ---\n{c.strip()}")
        if block_lines:
            lines.append("Current Blocks:\n" + "\n\n".join(block_lines))
    return "\n".join(lines) + "\n\n"


def _split_markdown_into_blocks(text: str) -> List[Dict[str, str]]:
    """Split markdown text into structured article blocks by headings."""
    lines = text.strip().split("\n")
    blocks: List[Dict[str, str]] = []
    current_content: List[str] = []

    for line in lines:
        if re.match(r"^#{1,3}\s+", line) and current_content:
            joined = "\n".join(current_content).strip()
            if joined:
                blocks.append({"type": "text", "content": joined})
            current_content = [line]
        else:
            current_content.append(line)

    if current_content:
        joined = "\n".join(current_content).strip()
        if joined:
            blocks.append({"type": "text", "content": joined})

    return blocks


def chat_turn(
    mode: str,
    messages: List[Dict[str, str]],
    current_draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute a conversational turn with Gemini to discuss and update the draft.

    Args:
        mode: 'post' or 'article'
        messages: List of {'role': 'user' | 'assistant', 'content': str}
        current_draft: Optional existing draft object {'title', 'body', 'tags', 'blocks'}

    Returns:
        {'reply': str, 'draft': dict}
    """
    key = _api_key()
    if not key:
        return {
            "reply": "Gemini API key is not configured in the server environment (GEMINI_API_KEY).",
            "draft": current_draft or ({"body": "", "tags": []} if mode == "post" else {"title": "", "tags": [], "blocks": []})
        }

    gemini_contents = []

    # Inject compact draft context into the first message
    context_prefix = _format_draft_context(current_draft, mode)

    for i, msg in enumerate(messages):
        role = "user" if msg.get("role") in ("user", "author") else "model"
        text = msg.get("content", "").strip()
        if i == 0 and role == "user" and context_prefix:
            text = f"{context_prefix}{text}"
        gemini_contents.append({
            "role": role,
            "parts": [{"text": text or "..."}]
        })

    if not gemini_contents:
        gemini_contents.append({"role": "user", "parts": [{"text": f"Let's write a new {mode}."}]})

    if mode == "article":
        schema: Dict[str, Any] = {
            "type": "OBJECT",
            "properties": {
                "reply": {"type": "STRING"},
                "draft": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "tags": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"}
                        },
                        "blocks": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "type": {"type": "STRING"},
                                    "content": {"type": "STRING"}
                                },
                                "required": ["type", "content"]
                            }
                        }
                    },
                    "required": ["title", "tags", "blocks"]
                }
            },
            "required": ["reply", "draft"]
        }
    else:
        schema = {
            "type": "OBJECT",
            "properties": {
                "reply": {"type": "STRING"},
                "draft": {
                    "type": "OBJECT",
                    "properties": {
                        "body": {"type": "STRING"},
                        "tags": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"}
                        }
                    },
                    "required": ["body", "tags"]
                }
            },
            "required": ["reply", "draft"]
        }

    payload: Dict[str, Any] = {
        "contents": gemini_contents,
        "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
            "responseSchema": schema
        }
    }

    url = GEMINI_ENDPOINT % (_model(), key)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        print(f"[ai_studio] Gemini API HTTP error {e.code}: {err_msg}")
        return {
            "reply": f"Gemini API returned an error ({e.code}): {e.reason}",
            "draft": current_draft or {}
        }
    except Exception as e:
        print(f"[ai_studio] Request failed: {e}")
        return {
            "reply": f"Could not reach AI drafting service: {e}",
            "draft": current_draft or {}
        }

    candidates = data.get("candidates") or []
    if not candidates:
        return {
            "reply": "No response generated by the AI model. Please try refining your prompt.",
            "draft": current_draft or {}
        }

    parts = (candidates[0].get("content") or {}).get("parts") or []
    raw_text = "".join(p.get("text", "") for p in parts).strip()
    cleaned = _clean_json_text(raw_text)

    try:
        result = json.loads(cleaned)
    except Exception as e:
        print(f"[ai_studio] JSON parse error: {e}\nRaw: {raw_text[:200]}")
        return {
            "reply": raw_text,
            "draft": current_draft or {}
        }

    reply = result.get("reply", "")
    draft = result.get("draft") or {}

    # Sanitize title
    if draft.get("title"):
        clean_title = re.sub(r"</?[a-zA-Z0-9_ -]+>", "", str(draft["title"])).strip()
        first_line = clean_title.split("\n")[0].strip()
        if len(first_line) > 130 and ":" in first_line:
            p = first_line.split(":")
            if len(p) > 2:
                first_line = f"{p[0].strip()}: {p[1].strip()}"
        draft["title"] = first_line[:140]

    # Enforce article blocks format sanity and fallback extraction
    if mode == "article":
        raw_blocks = draft.get("blocks") or []
        sanitized_blocks = []
        for b in raw_blocks:
            if isinstance(b, dict) and b.get("content"):
                sanitized_blocks.append({
                    "type": "text",
                    "content": str(b.get("content")).strip()
                })
            elif isinstance(b, str) and b.strip():
                sanitized_blocks.append({"type": "text", "content": b.strip()})

        # Fallback: if blocks was omitted or empty, extract from draft body or reply
        if not sanitized_blocks:
            if draft.get("body"):
                sanitized_blocks = _split_markdown_into_blocks(draft["body"])
            elif "# " in reply or "## " in reply:
                sanitized_blocks = _split_markdown_into_blocks(reply)
            elif current_draft and current_draft.get("blocks"):
                sanitized_blocks = current_draft["blocks"]

        draft["blocks"] = sanitized_blocks

    return {
        "reply": reply,
        "draft": draft
    }
