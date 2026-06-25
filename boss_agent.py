import json
import os
import subprocess
import sys
from dotenv import load_dotenv
import groq

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")

if not api_key or api_key == "PLACEHOLDER":
    print("GROQ_API_KEY not set or is PLACEHOLDER. Please set it in .env and rerun.")
    sys.exit(1)

client = groq.Groq(api_key=api_key)
from agents.engineering_agent import engineering_agent as run_engineering_agent
from agents.approval_agent import request_approval
from agents.memory_agent import save_memory, get_relevant_memories
from agents.task_agent import create_task

SYSTEM_PROMPT = (
    "You are the Boss Agent — the senior coordinator of an AI multi-agent company. "
    "You behave like a sharp, decisive, real-world boss/employer: confident, practical, "
    "and honest about what is and isn't possible.\n\n"
    "You have persistent memory across conversations. Before responding, you have access to "
    "relevant past context. Use it to provide continuity and refer back to previous discussions. "
    "After each conversation, key points are automatically saved for future reference.\n\n"
    "Always create a task using the create_task tool before delegating significant work to any agent. "
    "This keeps work organized and trackable. For any multi-step work that takes more than one action, "
    "create a task first, then start the work.\n\n"
    "You have an in-browser approval system. Before any significant, irreversible or real-world action "
    "(deploying, publishing, deleting, sending external messages, spending money), call request_approval. "
    "If APPROVED proceed. If REJECTED or TIMEOUT, stop and tell the user. For safe internal tasks like research, "
    "calculations, writing draft code, proceed without approval.\n\n"
    "When given any request or command:\n"
    "1. Quickly evaluate whether it's something you and your team of specialized agents can actually do right now, partially, or not at all.\n"
    "2. Give a clear, direct verdict first — Yes we can do this, We can do part of this and here is what's missing, or No that's not possible right now because of a specific reason.\n"
    "3. Briefly explain your reasoning in plain language, like a boss explaining a decision to someone they respect, not a robot listing steps.\n"
    "4. If it's a follow-up about an ongoing task, refer back to what was discussed earlier in this conversation honestly. If nothing has actually been built yet, say so plainly instead of pretending progress was made.\n\n"
    "Tone: confident, warm, professional. Never robotic, never overly formal, never padded with filler.\n\n"
    "Output rules (critical — this gets read aloud by text-to-speech):\n"
    "- Plain spoken sentences only. No markdown, no lists, no symbols.\n"
    "- Keep answers to 2-4 sentences by default, unless the user explicitly asks for more detail.\n"
    "- Match the language style the user used — Hindi, Hinglish, or English — naturally, the way a real bilingual person would.\n"
    "You also have an Engineering Agent who can write and run Python code for technical tasks. Use it when the user asks to build, calculate, create, process, or automate anything technical. Do not attempt to write code yourself — delegate to Engineering Agent."
)

history = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

MAX_HISTORY = 20

RESEARCH_TOOL = {
    "type": "browser_search",
    "function": {
        "name": "research_agent",
        "description": "Search the web for up-to-date factual information and summarize it clearly.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query text."
                }
            },
            "required": ["query"],
        },
    },
}

REQUEST_APPROVAL_TOOL = {
    "type": "function",
    "function": {
        "name": "request_approval",
        "description": "Request user approval for a significant or irreversible action before proceeding.",
        "parameters": {
            "type": "object",
            "properties": {
                "action_summary": {
                    "type": "string",
                    "description": "A brief summary of the action requiring approval."
                },
                "reason": {
                    "type": "string",
                    "description": "Why approval is needed for this action."
                }
            },
            "required": ["action_summary", "reason"],
        },
    },
}

CREATE_TASK_TOOL = {
    "type": "function",
    "function": {
        "name": "create_task",
        "description": "Use this when delegating any significant work to a specialized agent. Create a task before starting the work so it can be tracked. Required for any multi-step work that takes more than one action.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short task name"
                },
                "assigned_to": {
                    "type": "string",
                    "description": "Which agent does this work (e.g., Research Agent, Engineering Agent)"
                },
                "description": {
                    "type": "string",
                    "description": "Full task details"
                }
            },
            "required": ["title", "assigned_to", "description"],
        },
    },
}

ENGINEERING_TOOL = {
    "type": "function",
    "function": {
        "name": "engineering_agent",
        "description": "Use this when the user asks to build something, write code, create a script, do a calculation, process data, generate a file, or any technical/programming task. This agent will write and run the code and return the result.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The full technical task description."
                }
            },
            "required": ["task"],
        },
    },
}


def trim_history():
    while len(history) > MAX_HISTORY:
        # always keep the system prompt at index 0
        if len(history) > 1:
            history.pop(1)
        else:
            break


def extract_response_text(resp):
    if hasattr(resp, 'choices'):
        for c in resp.choices:
            msg = getattr(c, 'message', None)
            if msg:
                content = getattr(msg, 'content', None)
                if content:
                    return content
                try:
                    return msg['content']
                except Exception:
                    pass
            if getattr(c, 'text', None):
                return c.text
    if getattr(resp, 'message', None):
        content = getattr(resp.message, 'content', None)
        if content:
            return content
    # If the model returned executed tool results without a normal assistant reply,
    # use the first available tool output.
    if getattr(resp, 'choices', None):
        for c in resp.choices:
            msg = getattr(c, 'message', None)
            if not msg:
                continue
            executed = getattr(msg, 'executed_tools', None)
            if executed:
                for tool_run in executed:
                    output = getattr(tool_run, 'output', None)
                    if output:
                        return output
                    search_results = getattr(tool_run, 'search_results', None)
                    if search_results and getattr(search_results, 'results', None):
                        results_text = []
                        for result in search_results.results:
                            title = getattr(result, 'title', None) or ''
                            url = getattr(result, 'url', None) or ''
                            if title or url:
                                results_text.append(f"{title} {url}".strip())
                        if results_text:
                            return ' '.join(results_text)
    return str(resp)


def _get_value(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def handle_tool_call(resp, messages, mid):
    if not getattr(resp, 'choices', None):
        return False, None

    for c in resp.choices:
        msg = getattr(c, 'message', None)
        if not msg:
            continue
        tool_calls = _get_value(msg, 'tool_calls')
        if not tool_calls:
            continue

        for tool_call in tool_calls:
            function = _get_value(tool_call, 'function')
            if not function:
                continue
            func_name = _get_value(function, 'name')

            raw_args = _get_value(function, 'arguments', '{}')
            if isinstance(raw_args, bytes):
                raw_args = raw_args.decode('utf-8', errors='ignore')
            try:
                tool_args = json.loads(raw_args)
            except Exception:
                tool_args = {}

            if func_name == 'engineering_agent':
                task = tool_args.get('task', '')
                tool_output = run_engineering_agent(task)
                return True, tool_output
            if func_name == 'request_approval':
                action_summary = tool_args.get('action_summary', '')
                reason = tool_args.get('reason', '')
                approval_output = request_approval(action_summary, reason)
                return True, approval_output
            if func_name == 'create_task':
                title = tool_args.get('title', '')
                assigned_to = tool_args.get('assigned_to', '')
                description = tool_args.get('description', '')
                task_result = create_task(title, assigned_to, description)
                task_id = task_result.get('id', '')
                tool_output = f"Task created: {title} (ID: {task_id})"
                return True, tool_output

    return False, None


def try_model_get_response(mid, messages, tools):
    try:
        resp = client.chat.completions.create(
            model=mid,
            messages=messages,
            tools=tools,
            tool_choice='auto',
            reasoning_effort='medium',
        )
        return True, resp
    except groq.RateLimitError as e:
        return False, e
    except Exception as e:
        return False, e


def get_chat_model_candidates(exclude: list[str] | None = None):
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


def find_chat_model(exclude: list[str] | None = None):
    candidates = get_chat_model_candidates(exclude=exclude)
    if candidates:
        return candidates[0]
    raise RuntimeError('No suitable model found from the models endpoint.')


def get_response_from_models(messages, tools, preferred: list[str] | None = None, exclude: list[str] | None = None):
    preferred = preferred or []
    tried = set()
    errors = []
    for mid in preferred:
        if not mid:
            continue
        mid_low = mid.lower()
        if mid_low in tried or (exclude and mid_low in [e.lower() for e in exclude]):
            continue
        success, result = try_model_get_response(mid, messages, tools)
        tried.add(mid_low)
        if success:
            return result
        errors.append((mid, str(result)))

    candidates = get_chat_model_candidates(exclude=list(tried) + (exclude or []))
    for mid in candidates:
        mid_low = str(mid).lower()
        if mid_low in tried:
            continue
        success, result = try_model_get_response(mid, messages, tools)
        tried.add(mid_low)
        if success:
            return result
        errors.append((mid, str(result)))
# Fetch relevant memories
    relevant_memories = get_relevant_memories(message, limit=5)
    
    # Create a modified system prompt with memory context
    system_with_memory = history[0]["content"]
    if relevant_memories:
        memory_context = "\n".join(relevant_memories)
        system_with_memory = f"{system_with_memory}\n\nRelevant past context:\n{memory_context}"
    
    # Build messages with memory-injected system prompt
    history.append({"role": "user", "content": message})
    trim_history()
    messages = list(history)
    messages[0] = {"role": "system", "content": system_with_memory}

    preferred = [model_hint] if model_hint else []
    try:
        resp = get_response_from_models(messages, [RESEARCH_TOOL, ENGINEERING_TOOL, REQUEST_APPROVAL_TOOL, CREATE_TASK_TOOL], preferred=preferred, exclude=[model_hint] if model_hint else None)
    except Exception as e:
        raise RuntimeError(f"Failed to get a response from chat models: {e}")

    handled, tool_reply = handle_tool_call(resp, messages, model_hint)
    if handled and tool_reply:
        # Save memory: user message (episodic) and assistant reply (episodic)
        save_memory(f"User: {message}", "episodic")
        save_memory(f"Assistant: {tool_reply}", "episodic")
        history.append({"role": "assistant", "content": tool_reply})
        trim_history()
        return tool_reply

    body = extract_response_text(resp)
    
    # Save memory: user message and assistant reply
    save_memory(f"User: {message}", "episodic")
    save_memory(f"Assistant: {body}", "episodic")
     get a response from chat models: {e}")

    handled, tool_reply = handle_tool_call(resp, messages, model_hint)
    if handled and tool_reply:
        history.append({"role": "assistant", "content": tool_reply})
        trim_history()
        return tool_reply

    body = extract_response_text(resp)
    history.append({"role": "assistant", "content": body})
    trim_history()
    return body


def research_agent(query, model_hint="openai/gpt-oss-120b"):
    """Run the Boss Agent with the research tool enabled.

    This uses Groq's browser_search tool to answer requests that require current
    factual information.
    """
    return chat_with_model(query, model_hint=model_hint)


if __name__ == '__main__':
    try:
        reply1 = chat_with_model("Please explain what you can do in one sentence.")
        print('Reply 1:', reply1)
        reply2 = chat_with_model("Did you remember what you just said?")
        print('Reply 2:', reply2)
    except Exception as e:
        print('Error during test:', e)
