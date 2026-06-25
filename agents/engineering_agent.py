import json
import os
import re
import subprocess
from dotenv import load_dotenv
import groq
from agents.approval_agent import send_notification

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")
if not api_key or api_key == "PLACEHOLDER":
    raise RuntimeError("GROQ_API_KEY not set or is PLACEHOLDER. Please set it in .env.")

client = groq.Groq(api_key=api_key)

SYSTEM_PROMPT = (
    "You are an expert software engineer. When given a task, write clean, correct, complete Python code that solves it. "
    "The code must print the final answer or result to standard output. "
    "Output ONLY the raw Python code, nothing else — no explanation, no markdown, no code fences, no comments unless they are actual Python comments needed for the code to work."
)

MAX_ATTEMPTS = 3


def extract_raw_code(response):
    if hasattr(response, 'choices'):
        for c in response.choices:
            msg = getattr(c, 'message', None)
            if msg:
                content = getattr(msg, 'content', None)
                if content:
                    return content.strip()
                try:
                    return msg['content'].strip()
                except Exception:
                    pass
    if getattr(response, 'message', None):
        content = getattr(response.message, 'content', None)
        if content:
            return content.strip()
    return ''


def get_engineering_model_candidates(exclude: list[str] | None = None):
    exclude = {e.lower() for e in exclude or []}
    try:
        ml = client.models.list()
        models = getattr(ml, 'data', None) or getattr(ml, 'models', None) or ml
    except Exception as e:
        raise RuntimeError(f"Failed to list models: {e}")

    candidates = []
    for m in models:
        if isinstance(m, dict):
            mid = m.get('id')
            caps = m.get('capabilities', []) or []
        else:
            mid = getattr(m, 'id', None)
            caps = getattr(m, 'capabilities', []) or []
        if not mid:
            continue
        mid_low = str(mid).lower()
        if mid_low in exclude:
            continue
        if any('chat' in str(c).lower() for c in caps):
            candidates.append(mid)
        elif 'gpt' in mid_low or 'chat' in mid_low:
            candidates.append(mid)

    seen = []
    unique = []
    for mid in candidates:
        if mid not in seen:
            seen.append(mid)
            unique.append(mid)
    return unique


def call_groq_for_code(task, error_message=None, model_hint="openai/gpt-oss-120b"):
    prompt = SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": task},
    ]
    if error_message:
        messages.append({
            "role": "assistant",
            "content": f"The previous code execution failed with this error: {error_message}. Please fix the code and return only the corrected raw Python code.",
        })

    tried = set()
    last_error = None
    candidate_models = [model_hint] if model_hint else []
    candidate_models.extend(get_engineering_model_candidates(exclude=[model_hint] if model_hint else None))

    for model in candidate_models:
        if not model:
            continue
        model_low = model.lower()
        if model_low in tried:
            continue
        tried.add(model_low)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
            )
            code = extract_raw_code(resp)
            if code:
                return code
            last_error = f"Model {model} returned no code."
        except groq.RateLimitError as e:
            last_error = f"RateLimitError from {model}: {e}"
        except Exception as e:
            last_error = f"Error from {model}: {e}"

    if last_error:
        raise RuntimeError(last_error)
    return ""


def run_python_code(code):
    try:
        completed = subprocess.run([
            "python3",
            "-c",
            code,
        ], capture_output=True, text=True, timeout=15)
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except subprocess.TimeoutExpired as exc:
        return -1, exc.stdout or "", f"TimeoutExpired: {exc}"
    except Exception as exc:
        return -1, "", str(exc)


def engineering_agent(task: str) -> str:
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        code = call_groq_for_code(task, last_error)
        if not code:
            last_error = "No code was returned by the model."
            continue

        returncode, stdout, stderr = run_python_code(code)
        if returncode == 0:
            output_text = stdout if stdout else "<no output>"
            message = f"Engineering Agent built and ran Python code for the task. Final output: {output_text}."
            try:
                send_notification(message)
            except Exception:
                pass
            return message

        last_error = stderr or f"Non-zero return code: {returncode}"

    failure_message = f"Engineering Agent tried 3 times but couldn't complete this task. Here is the last error: {last_error}"
    try:
        send_notification(failure_message)
    except Exception:
        pass
    return failure_message
