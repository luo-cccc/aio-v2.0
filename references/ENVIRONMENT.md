# Environment Configuration Reference

## Required for LLM Analysis

At least one of the following API keys must be set:

| Variable | Provider | Notes |
|----------|----------|-------|
| `ANTHROPIC_API_KEY` | Anthropic Claude | Default provider |
| `OPENAI_API_KEY` | OpenAI GPT | |
| `DEEPSEEK_API_KEY` | DeepSeek | |
| `GLM_API_KEY` | Zhipu AI (GLM) | Vision-capable default |
| `MINIMAX_API_KEY` | MiniMax | No vision support |
| `KIMI_API_KEY` | Moonshot Kimi | No vision support |
| `QWEN_API_KEY` | Alibaba Qwen | Vision-capable default |
| `DOUBAO_API_KEY` | ByteDance Doubao | Vision-capable default |

## Optional Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_PROVIDER` | Select provider | `anthropic` |
| `LLM_MODEL` | Override model | Provider default |
| `OPENAI_BASE_URL` | Custom endpoint for openai-compatible | — |

## Optional for Google Search Console Monitoring

| Variable | Purpose |
|----------|---------|
| `GSC_CLIENT_SECRET_PATH` | Path to OAuth 2.0 client_secret.json |

## Installation

```bash
# Core dependencies
pip install aiohttp

# Optional: GSC monitoring
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```
