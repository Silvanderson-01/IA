"""
Fantasma - Etapa 3: chat com Llama local (Ollama) + ferramentas.

Requisitos:
  1. Ollama rodando e o modelo baixado:  ollama pull llama3.2
  2. pip install -U ollama
  3. Arquivo ferramentas.py na mesma pasta
"""

import ollama

from ferramentas import FUNCOES, SCHEMAS, CIDADE_PADRAO

# Modelo local. Troque por "llama3.1:8b" se o seu PC aguentar
# (modelos maiores acertam mais ao escolher ferramentas).
MODELO = "llama3.2"

PERSONALIDADE = (
    "Você é o Fantasma, assistente pessoal do usuário. "
    "Responda sempre em português do Brasil, de forma educada, direta "
    "e com um toque sutil de humor. Mantenha as respostas curtas, "
    "pois elas serão faladas em voz alta. "
    "Use as ferramentas disponíveis para hora, data, clima, abrir sites e tocar música. "
    "Nunca invente dados de clima ou hora: sempre chame a ferramenta. "
    "Use as ferramentas do computador (volume, desligar, reiniciar, bloquear a tela) "
    "somente quando o usuário pedir. Nunca desligue ou reinicie sem um pedido explícito. "
    "Para bolsa de valores, use as ferramentas de cotação e de carteira simulada. "
    "A carteira é uma simulação com dinheiro fictício e as cotações têm atraso de cerca de 30 minutos. "
    "Nunca recomende comprar ou vender e nunca prometa resultados: apenas informe dados "
    "e execute o que o usuário pedir na simulação. "
    f"Se o usuário não disser a cidade, use {CIDADE_PADRAO}."
)

historico = [{"role": "system", "content": PERSONALIDADE}]


def conversar(texto_usuario: str) -> str:
    """Envia a mensagem ao modelo, executa ferramentas se ele pedir, e devolve a resposta."""
    historico.append({"role": "user", "content": texto_usuario})

    for _ in range(4):  # limite de rodadas de ferramentas, evita loop infinito
        resposta = ollama.chat(model=MODELO, messages=historico, tools=SCHEMAS)
        mensagem = resposta.message
        historico.append(mensagem)

        if not mensagem.tool_calls:
            return mensagem.content

        for chamada in mensagem.tool_calls:
            nome = chamada.function.name
            argumentos = chamada.function.arguments or {}
            funcao = FUNCOES.get(nome)
            
            if not funcao:
                resultado = f"Ferramenta '{nome}' não existe."
            else:
                try:
                    # Proteção contra argumentos inválidos não mapeados na função
                    import inspect
                    sig = inspect.signature(funcao)
                    # Filtra apenas os argumentos aceitos pela função, descartando "alucinações" do LLM
                    argumentos_validos = {
                        k: v for k, v in argumentos.items() 
                        if k in sig.parameters
                    }
                    
                    resultado = funcao(**argumentos_validos)
                except Exception as erro:
                    resultado = f"Erro ao executar {nome}: {erro}. Verifique os parâmetros corretos."
            
            print(f"   [ferramenta] {nome}({argumentos}) -> {resultado}")
            historico.append({"role": "tool", "tool_name": nome, "content": str(resultado)})


def main():
    print("Fantasma online. Digite 'sair' para encerrar.\n")
    while True:
        texto = input("Você: ").strip()
        if not texto:
            continue
        if texto.lower() in ("sair", "exit", "quit"):
            print("Fantasma: Até logo!")
            break
        try:
            print(f"Fantasma: {conversar(texto)}\n")
        except Exception as erro:
            print(f"[Erro] Verifique se o Ollama está rodando e o modelo baixado.\n{erro}\n")


if __name__ == "__main__":
    main()
