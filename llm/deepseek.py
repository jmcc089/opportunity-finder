"""
DeepSeek LLM client with mock support.

Set DEEPSEEK_MOCK=1 to return a fixed fixture response instead of hitting the network.
"""
import json
import os


def call_deepseek(messages: list[dict], max_tokens: int = 512, mock_fixture: str = "mock_stage1_response.json") -> str:
    """Call DeepSeek and return the response content string."""
    if os.environ.get("DEEPSEEK_MOCK") == "1":
        fixture_path = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", mock_fixture
        )
        with open(fixture_path) as f:
            return f.read().strip()

    import openai

    client = openai.OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )
    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=messages,
        max_tokens=max_tokens,
        extra_body={"thinking": {"type": "disabled"}},
    )
    content = response.choices[0].message.content or ""
    # Sanity-check: no reasoning trace leaked through
    if hasattr(response.choices[0].message, "reasoning_content"):
        rc = getattr(response.choices[0].message, "reasoning_content", None)
        if rc:
            raise RuntimeError("DeepSeek returned unexpected reasoning_content; disable thinking mode.")
    return content
