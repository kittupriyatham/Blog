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
TIMEOUT_S = 45


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
    "Modes & Content Rules:\n"
    "- Mode: 'post' (Short-form / Micro-post for social feed and POSSE syndication):\n"
    "  * `draft.body`: Punchy, engaging, well-formatted text with clear takeaways or questions.\n"
    "  * `draft.tags`: 2-5 relevant tags (e.g. ['WebDev', 'Python', 'Architecture']).\n"
    "- Mode: 'article' (Long-form Technical Blog Article):\n"
    "  * `draft.title`: A compelling, clear, descriptive article title.\n"
    "  * `draft.tags`: 3-6 relevant topic tags.\n"
    "  * `draft.blocks`: An array of structured text blocks: [{'type': 'text', 'content': '...'}]\n"
    "  * CRITICAL ARTICLE RULE: Generate ONLY text and heading blocks. Use rich Markdown format with '# ', '## ', bullet points, blockquotes, and fenced code blocks.\n"
    "  * NEVER invent fake image URLs, media blocks, or image placeholders. The author uploads all screenshots and media files manually.\n\n"
    "Always return valid JSON adhering strictly to the schema."
)


def _clean_json_text(raw_text: str) -> str:
    """Strip markdown code block fences if returned by the model."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


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

    # Inject system instruction context and current draft status into the conversation
    context_prefix = f"[Active Mode: {mode.upper()}]\n"
    if current_draft:
        context_prefix += f"[Current Working Draft: {json.dumps(current_draft, ensure_ascii=False)}]\n\n"

    for i, msg in enumerate(messages):
        role = "user" if msg.get("role") in ("user", "author") else "model"
        text = msg.get("content", "").strip()
        if i == 0 and role == "user":
            text = f"{context_prefix}{text}"
        gemini_contents.append({
            "role": role,
            "parts": [{"text": text or "..."}]
        })

    if not gemini_contents:
        gemini_contents.append({"role": "user", "parts": [{"text": f"Let's write a new {mode}."}]})

    payload: Dict[str, Any] = {
        "contents": gemini_contents,
        "systemInstruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "reply": {"type": "STRING"},
                    "draft": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "body": {"type": "STRING"},
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
                        }
                    }
                },
                "required": ["reply", "draft"]
            }
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
            parts = first_line.split(":")
            if len(parts) > 2:
                first_line = f"{parts[0].strip()}: {parts[1].strip()}"
        draft["title"] = first_line[:140]

    # Enforce article blocks format sanity
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
        draft["blocks"] = sanitized_blocks

    return {
        "reply": reply,
        "draft": draft
    }
