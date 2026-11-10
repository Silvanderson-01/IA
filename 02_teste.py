import ollama

def pegar_hora():
    return "10:00"

schema = [{
    "type": "function",
    "function": {
        "name": "pegar_hora",
        "description": "Retorna a hora atual",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}]

r = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Que horas são? Use a ferramenta."}],
    tools=schema,
)
print(r.message.tool_calls)