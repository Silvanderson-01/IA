import ollama

print(ollama.list())

resposta = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Diga oi em português."}],
)
print(resposta.message.content)