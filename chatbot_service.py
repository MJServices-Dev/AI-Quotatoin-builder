"""
chatbot_service.py — Flask-compatible Groq chatbot engine.
No Streamlit dependency. Uses the same CRM_SYSTEM_PROMPT, model config,
and Groq API logic as chatbot/ai_services.py.
"""

from config import Config

import sys
import os
import importlib.util

# Load chatbot/config.py directly by absolute path to avoid shadowing Flask's config.py
_chatbot_config_path = os.path.join(os.path.dirname(__file__), "chatbot", "config.py")
_spec = importlib.util.spec_from_file_location("chatbot_config", _chatbot_config_path)
_chatbot_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_chatbot_config)

from openai import OpenAI

CRM_SYSTEM_PROMPT = _chatbot_config.CRM_SYSTEM_PROMPT
GROQ_BASE_URL     = _chatbot_config.GROQ_BASE_URL
MAX_TOKENS        = _chatbot_config.MAX_TOKENS
TEMPERATURE       = _chatbot_config.TEMPERATURE
DEFAULT_MODEL     = _chatbot_config.DEFAULT_MODEL
MODEL_OPTIONS     = _chatbot_config.MODEL_OPTIONS


# ─── Expand summary prompt ────────────────────────────────────────────────────
EXPAND_PROMPT = """You are a requirements analyst. Below is a Q&A conversation between a CRM consultant and a business client.

Convert this conversation into a well-structured, detailed requirements document that can be used to generate a professional CRM implementation quotation. 

The document should:
- Be written in clear, professional prose
- Cover all the information gathered: business nature, sales process, current tools, dashboard needs, and requested features
- Be structured with numbered sections and sub-points
- Be comprehensive enough to serve as a complete project briefing (aim for 400-600 words)
- Include the client's company/business context where mentioned

CONVERSATION:
{conversation}

Output ONLY the requirements document text, no preamble."""


def _get_client() -> OpenAI:
    return OpenAI(api_key=Config.GROQ_API_KEY, base_url=GROQ_BASE_URL)


def get_greeting(model: str = DEFAULT_MODEL) -> str:
    """Get the initial AI greeting (non-streaming)."""
    if not Config.GROQ_API_KEY:
        return "API key not configured. Please contact the administrator."
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": CRM_SYSTEM_PROMPT}],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Could not connect to AI. ({e})"


def send_message(model: str, history: list, user_msg: str) -> dict:
    """
    Send a user message and get AI response.

    Args:
        model: Model identifier
        history: List of {role, content} dicts (full conversation so far)
        user_msg: New user message

    Returns:
        {
          "reply": str,
          "history": updated list,
          "summary_ready": bool  — True when AI has output the final summary
        }
    """
    if not Config.GROQ_API_KEY:
        return {"reply": "API key not configured.", "history": history, "summary_ready": False}

    updated_history = history + [{"role": "user", "content": user_msg}]

    try:
        client = _get_client()
        payload = [{"role": "system", "content": CRM_SYSTEM_PROMPT}] + updated_history
        resp = client.chat.completions.create(
            model=model,
            messages=payload,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        reply = resp.choices[0].message.content
        updated_history.append({"role": "assistant", "content": reply})
        summary_ready = "Here's everything I've gathered so far:" in reply

        return {
            "reply": reply,
            "history": updated_history,
            "summary_ready": summary_ready,
        }
    except Exception as e:
        err = str(e)
        if "401" in err or "invalid_api_key" in err.lower():
            msg = "Invalid API key — please check and try again."
        elif "rate_limit" in err.lower():
            msg = "Rate limit reached. Please wait a moment."
        else:
            msg = f"AI error: {err}"
        return {"reply": msg, "history": updated_history, "summary_ready": False}


def extract_requirements_text(history: list) -> str:
    """
    Find the final summary message from the conversation history.
    Returns the raw summary text (starting with 'Here's everything I've gathered so far:').
    """
    for msg in reversed(history):
        if msg["role"] == "assistant" and "Here's everything I've gathered so far:" in msg["content"]:
            return msg["content"]
    # Fallback: join all messages as plain text
    lines = []
    for m in history:
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['content']}")
    return "\n\n".join(lines)


def expand_to_requirements(model: str, history: list) -> str:
    """
    Step 1 of chat→quotation handoff:
    Ask the LLM to convert the collected Q&A into a full requirements document.
    The output is then passed to LLMHandler.generate_quotation().
    """
    if not Config.GROQ_API_KEY:
        return extract_requirements_text(history)  # Fallback to raw summary

    # Build a plain-text transcript of the conversation
    lines = []
    for m in history:
        role = "Consultant" if m["role"] == "assistant" else "Client"
        lines.append(f"{role}: {m['content']}")
    conversation_text = "\n\n".join(lines)

    prompt = EXPAND_PROMPT.format(conversation=conversation_text)

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional business analyst."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error expanding to requirements: {e}")
        # Fallback: return raw summary text
        return extract_requirements_text(history)


# Expose model options for the chat UI
AVAILABLE_MODELS = MODEL_OPTIONS
