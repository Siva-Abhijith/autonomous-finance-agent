from ollama import chat

response = chat(
    model="qwen3:8b",
    messages=[
        {
            "role": "user",
            "content": "Explain what an AI agent is in two sentences."
        }
    ]
)

print(response.message.content)