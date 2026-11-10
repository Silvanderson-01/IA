import ollama

try:
    print("Tentando conectar ao Ollama...")
    resposta = ollama.chat(model='llama3.2', messages=[
        {'role': 'user', 'content': 'Oi, você está me ouvindo?'}
    ])
    print("✅ SUCESSO! Ollama respondeu:")
    print(resposta['message']['content'])
except Exception as e:
    print("❌ ERRO:")
    print(e)
