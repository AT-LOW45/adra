import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv()

# Groq's OpenAI-compatible endpoint, so an existing .env with only GROQ_API_KEY set
# keeps working unchanged. Point LLM_BASE_URL elsewhere to use another provider.
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"


def _get_llm() -> ChatOpenAI:
    """The chat model, configured entirely from the environment.

    Deliberately provider-neutral: OpenAI, Groq, OpenRouter, Together, DeepSeek and
    local runtimes (Ollama, LM Studio, vLLM) all expose the same OpenAI-compatible API,
    so switching provider is three environment variables rather than a code change.
    Running a local model matters here — ADRs are a team's internal architecture
    decisions, which not everyone is willing to send to a third party.

    The model MUST support tool calling / structured output: both the ADR review and
    boilerplate generation rely on `with_structured_output`. Small local models often
    don't, and will fail at call time rather than here.
    """
    # GROQ_* are read as fallbacks so existing setups keep working.
    api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("LLM_API_KEY not available.")

    return ChatOpenAI(
        model=os.getenv("LLM_MODEL") or os.getenv("GROQ_MODEL", DEFAULT_MODEL),
        base_url=os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=SecretStr(api_key),
        temperature=0.0,
    )


llm = _get_llm()
