# Supported LLM Providers

## Text + Vision Capable

These providers support both `chat()` and `chat_vision()`:

- **anthropic** — Claude models (default: claude-sonnet-4-20250514)
- **openai** — GPT-4o series (default: gpt-4o)
- **glm** — Zhipu GLM-4V (default: glm-4v-flash)
- **qwen** — Alibaba Qwen-VL (default: qwen-vl-plus)
- **doubao** — ByteDance Vision Pro (default: doubao-1.5-vision-pro-32k)
- **openai-compatible** — Any OpenAI API-compatible service

## Text Only

These providers support `chat()` but not `chat_vision()`:

- **deepseek** — DeepSeek-V3/Chat (default: deepseek-chat)
- **minimax** — MiniMax abab series (default: abab6.5s-chat)
- **kimi** — Moonshot Kimi (default: moonshot-v1-8k)

## Vision Usage

The multimodal labeler automatically checks provider capabilities before calling
`chat_vision()`. If the configured provider does not support vision, image
analysis will fall back to heuristic detection without AI-generated alt text.
