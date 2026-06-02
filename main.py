import asyncio
import httpx

# ── Config ─────────────────────────────────────────────────────────────── #
GATEWAY_URL = "http://localhost:8000"
GATEWAY_KEY = "sk-murugan-gateway-2024"

_client = httpx.AsyncClient(
    base_url=GATEWAY_URL,
    headers={"Authorization": f"Bearer {GATEWAY_KEY}"},
    timeout=120,
)

# ── Sample 1: Simple text call (uses your default LLM) ─────────────────── #
async def simple_chat():
    r = await _client.post("/api/proxy/chat", json={
        "messages": [
            {"role": "user", "content": "What is 2 + 2? Answer in one line."}
        ]
    })
    data = r.json()
    print("Response:", data["choices"][0]["message"]["content"])
    print("Model used:", data["model"])

# ── Sample 2: System prompt + user message ─────────────────────────────── #
async def chat_with_system():
    r = await _client.post("/api/proxy/chat", json={
        "messages": [
            {"role": "system", "content": "You are a compliance assistant for IoT standards."},
            {"role": "user",   "content": "Summarize what ETSI EN 18031 covers in 2 sentences."}
        ],
        "temperature": 0.3,
        "max_tokens": 200,
    })
    print("Compliance answer:", r.json()["choices"][0]["message"]["content"])

# ── Sample 3: Call a specific provider by alias ────────────────────────── #
async def call_specific_provider():
    r = await _client.post("/api/proxy/chat/model/vast-llm", json={
        "messages": [
            {"role": "user", "content": "Hello, which model are you?"}
        ]
    })
    print("Vast AI says:", r.json()["choices"][0]["message"]["content"])

# ── Sample 4: Vision/VLM call ──────────────────────────────────────────── #
async def vision_call():
    r = await _client.post("/api/proxy/chat/vlm", json={
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"}}
                ]
            }
        ]
    })
    print("VLM says:", r.json()["choices"][0]["message"]["content"])

# ── Sample 5: Check which providers are active ─────────────────────────── #
async def check_defaults():
    r = await _client.get("/api/providers/defaults/active")
    data = r.json()
    print("Default LLM alias:", data["default_llm"])
    print("Default VLM alias:", data["default_vlm"])

    r2 = await _client.get("/api/providers/")
    providers = r2.json()
    print(f"\nAll configured providers ({len(providers)}):")
    for p in providers:
        status = "✅ active" if p["is_active"] else "⏸ paused"
        default = " ← DEFAULT" if p["is_default_llm"] or p["is_default_vlm"] else ""
        print(f"  {status}  [{p['provider_type'].upper()}]  {p['display_name']}  alias={p['name']}{default}")

# ── Run all samples ─────────────────────────────────────────────────────── #
async def main():
    print("=" * 50)
    print("1. Simple chat")
    print("=" * 50)
    await simple_chat()

    print("\n" + "=" * 50)
    print("2. With system prompt")
    print("=" * 50)
    await chat_with_system()

    print("\n" + "=" * 50)
    print("3. Specific provider alias")
    print("=" * 50)
    await call_specific_provider()

    print("\n" + "=" * 50)
    print("4. Active providers")
    print("=" * 50)
    await check_defaults()

    await _client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
