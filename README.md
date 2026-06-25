# Boss-agent-system-

This project runs a simple Boss Agent voice assistant backed by Groq and Flask.

Endpoints:
- `GET /` serves the voice UI
- `POST /chat` sends a normal boss-agent chat request
- `POST /research` sends the same message through the Boss Agent research path, allowing Groq browser-search tool integration for up-to-date factual answers

Example request body:

```json
{ "message": "What is the latest news on Groq?" }
```
