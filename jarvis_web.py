"""
Fantasma - interface no navegador, pronta para rodar em segundo plano.

Uso normal:  dê duplo clique em iniciar_jarvis.vbs (sem janela de terminal).
Para ver as mensagens no terminal:  python jarvis_web.py

Deixe na mesma pasta: jarvis.py, ferramentas.py, voz.py, jarvis_voz.py e interface.html
"""

import itertools
import json
import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORTA = 8765
PASTA = Path(__file__).parent
ENDERECO = f"http://127.0.0.1:{PORTA}"

# Sem terminal (pythonw): as mensagens e os erros vão para o arquivo jarvis.log
if sys.stdout is None or sys.stderr is None:
    sys.stdout = sys.stderr = open(PASTA / "jarvis.log", "a", encoding="utf-8", buffering=1)

# Se o Fantasma já está rodando, só abre a página dele e sai
with socket.socket() as _teste:
    _teste.settimeout(0.3)
    if _teste.connect_ex(("127.0.0.1", PORTA)) == 0:
        webbrowser.open(ENDERECO)
        sys.exit(0)

from jarvis import conversar                       # cérebro + ferramentas
from voz import falar, parar as parar_fala         # voz do Fantasma

PAGINA = PASTA / "interface.html"

# ---- Acesso pelo celular (mesma rede Wi-Fi), protegido por PIN ----
PERMITIR_CELULAR = True                  # False = só este computador acessa
PIN_ARQUIVO = PASTA / "pin_celular.txt"  # para trocar o PIN, edite este arquivo e reinicie
SESSOES = set()    # celulares já autenticados (zera ao reiniciar o Fantasma)
TENTATIVAS = {}    # ip -> (erros de PIN, bloqueado até)

LOGIN_HTML = '''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Fantasma</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#07131d;color:#d8eef7;font:16px system-ui,sans-serif}
form{display:grid;gap:12px;width:min(320px,86vw);text-align:center}
input{padding:14px;border-radius:12px;border:1px solid #17384f;background:#0d2233;color:inherit;font:inherit;font-size:22px;text-align:center;letter-spacing:6px}
button{padding:12px;border-radius:12px;border:0;background:#5fe0ff;color:#052030;font:inherit;font-weight:600}
p{margin:0;color:#8fb0c0;min-height:24px}</style></head><body>
<form id="f"><h2 style="margin:0">Fantasma</h2><p>Digite o PIN mostrado no computador</p>
<input id="pin" inputmode="numeric" autocomplete="off" maxlength="12" autofocus><button>Entrar</button><p id="msg"></p></form>
<script>
document.getElementById('f').addEventListener('submit', async e => {
  e.preventDefault();
  const r = await fetch('/entrar', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pin: document.getElementById('pin').value.trim()})});
  if (r.ok) location.reload();
  else document.getElementById('msg').textContent = r.status === 429 ? 'Muitas tentativas. Aguarde 1 minuto.' : 'PIN incorreto.';
});
</script></body></html>'''


def _ler_pin() -> str:
    if PIN_ARQUIVO.exists():
        pin = PIN_ARQUIVO.read_text(encoding="utf-8").strip()
        if pin:
            return pin
    pin = f"{secrets.randbelow(10 ** 6):06d}"
    PIN_ARQUIVO.write_text(pin, encoding="utf-8")
    return pin


def _ip_local() -> str:
    """Endereço deste computador na rede (o que o celular precisa digitar)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # não envia nada; só descobre qual interface seria usada
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


PIN = _ler_pin() if PERMITIR_CELULAR else ""
ORIGENS_PERMITIDAS = {f"http://127.0.0.1:{PORTA}", f"http://localhost:{PORTA}"}

jv = None  # módulo jarvis_voz, carregado em segundo plano (é a parte pesada)
estado = {"status": "carregando", "mensagens": [], "ouvi": ""}  # "ouvi" = última frase transcrita
trava = threading.Lock()       # uma conversa por vez (voz ou texto)
cancelado = threading.Event()  # pedido de parada vindo da página


def definir(status: str):
    estado["status"] = status


_contador = itertools.count(1)


def adicionar(papel: str, texto: str, via: str = "pc"):
    estado["mensagens"].append({"id": next(_contador), "papel": papel, "texto": texto, "via": via})
    del estado["mensagens"][:-50]  # guarda só as últimas 50


def encerrar():
    time.sleep(0.3)
    os._exit(0)


def parar_tudo():
    cancelado.set()
    parar_fala()


def processar(texto: str, modelo=None, falar_no_pc=True, via="pc"):
    """Envia o texto ao Llama, mostra e fala a resposta. Retorna o comando dito ao interrompê-lo (ou None)."""
    interrompido = None
    with trava:
        cancelado.clear()
        adicionar("voce", texto, via)
        estado["ouvi"] = texto
        print(f"Você: {texto}")  # também fica registrado no jarvis.log
        definir("pensando")
        try:
            resposta = conversar(texto)
        except Exception:
            resposta = "Não consegui falar com o Ollama. Ele está rodando?"
        adicionar("jarvis", resposta)
        print(f"Fantasma: {resposta}")
        if falar_no_pc and not cancelado.is_set():
            definir("falando")
            interrompido = jv.falar_interrompivel(resposta, modelo)
        definir("aguardando")
    return interrompido


def carregar_e_ouvir():
    """Carrega os modelos e fica escutando 'ei Fantasma' (roda em segundo plano)."""
    global jv
    try:
        import jarvis_voz  # carrega o Whisper: demora alguns segundos
        jv = jarvis_voz
        ativacao = jv.carregar_ativacao() if jv.TEM_ATIVACAO else None
        definir("aguardando")
        if ativacao is None:
            print("[Aviso] Sem palavra de ativação: use a caixa de texto da página.")
            return

        falar("Fantasma online.")
        pendente = None  # comando já dito junto com o nome (ou ao interromper)
        while True:
            try:
                definir("aguardando")
                if pendente is None:
                    pendente = jv.esperar_ativacao(ativacao)
                comando, pendente = pendente, None
                definir("ouvindo")
                if comando:
                    texto = comando
                else:
                    jv.bipe()
                    texto = jv.ouvir()
                if not texto:
                    continue
                if texto.lower().strip(" .!?") in jv.PALAVRAS_SAIR:
                    definir("falando")
                    falar("Até logo!")
                    encerrar()
                pendente = processar(texto, ativacao)
            except Exception as erro:
                print(f"[Erro no ciclo de voz] {erro}")
                definir("aguardando")
    except Exception:
        import traceback
        traceback.print_exc()
        definir("erro")


class Servidor(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # sem poluir o terminal

    def _responder(self, codigo, tipo="text/plain", corpo=b"", extra=None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        for chave, valor in (extra or {}).items():
            self.send_header(chave, valor)
        self.end_headers()
        self.wfile.write(corpo)

    def _local(self) -> bool:
        """A requisição veio deste próprio computador?"""
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _host_valido(self) -> bool:
        # Neste computador só aceita 127.0.0.1/localhost (protege contra ataques de DNS rebinding)
        host = self.headers.get("Host", "")
        return not self._local() or host in (f"127.0.0.1:{PORTA}", f"localhost:{PORTA}")

    def _autenticado(self) -> bool:
        if self._local():
            return True
        if not PERMITIR_CELULAR:
            return False
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        return "fantasma" in cookies and cookies["fantasma"].value in SESSOES

    def _json(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(tamanho) or b"{}")
        except ValueError:
            return None

    def do_GET(self):
        if not self._host_valido():
            return self._responder(400)
        caminho = self.path.split("?")[0]
        if caminho in ("/", "/index.html"):
            if not self._autenticado():  # celular sem PIN: mostra a tela de login
                return self._responder(200, "text/html; charset=utf-8", LOGIN_HTML.encode("utf-8"))
            return self._responder(200, "text/html; charset=utf-8", PAGINA.read_bytes())
        if not self._autenticado():
            return self._responder(401)
        if caminho == "/estado":
            corpo = json.dumps(estado, ensure_ascii=False).encode("utf-8")
            return self._responder(200, "application/json; charset=utf-8", corpo)
        if caminho == "/acesso" and self._local():  # o PIN só aparece no próprio computador
            corpo = json.dumps({"ativo": PERMITIR_CELULAR, "pin": PIN,
                                "url": f"http://{_ip_local()}:{PORTA}"}).encode("utf-8")
            return self._responder(200, "application/json", corpo)
        self._responder(404)

    def _entrar(self):
        ip = self.client_address[0]
        erros, bloqueado_ate = TENTATIVAS.get(ip, (0, 0))
        if time.time() < bloqueado_ate:
            return self._responder(429)
        dados = self._json()
        if dados is None:
            return self._responder(400)
        pin_digitado = str(dados.get("pin", "")).encode("utf-8")
        if PERMITIR_CELULAR and secrets.compare_digest(pin_digitado, PIN.encode("utf-8")):
            TENTATIVAS.pop(ip, None)
            sessao = secrets.token_urlsafe(24)
            SESSOES.add(sessao)
            cookie = f"fantasma={sessao}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000"
            return self._responder(204, extra={"Set-Cookie": cookie})
        erros += 1
        TENTATIVAS[ip] = (0, time.time() + 60) if erros >= 5 else (erros, 0)  # 5 erros: espera 1 minuto
        self._responder(401)

    def do_POST(self):
        if self.path not in ("/entrar", "/enviar", "/parar", "/encerrar"):
            return self._responder(404)
        if not self._host_valido():
            return self._responder(400)
        # Segurança: só aceita comandos vindos desta própria página
        origem = self.headers.get("Origin")
        if origem and origem != f"http://{self.headers.get('Host')}":
            return self._responder(403)

        if self.path == "/entrar":
            return self._entrar()
        if not self._autenticado():
            return self._responder(401)

        if self.path == "/parar":
            parar_tudo()
            return self._responder(204)
        if self.path == "/encerrar":
            if not self._local():  # desligar o Fantasma só pelo próprio computador
                return self._responder(403)
            self._responder(204)
            threading.Thread(target=encerrar, daemon=True).start()
            return

        dados = self._json()
        if dados is None:
            return self._responder(400)
        texto = str(dados.get("texto", "")).strip()[:500]
        if texto and jv is not None:  # antes de carregar, ignora
            remoto = not self._local()  # pedido do celular: a resposta aparece nele, o PC fica quieto
            threading.Thread(target=processar, args=(texto, None, not remoto, "celular" if remoto else "pc"),
                             daemon=True).start()
        self._responder(204)


def main():
    try:
        # Com PERMITIR_CELULAR, aceita a rede local (protegida por PIN); senão, só este computador
        servidor = ThreadingHTTPServer(("0.0.0.0" if PERMITIR_CELULAR else "127.0.0.1", PORTA), Servidor)
    except OSError:
        webbrowser.open(ENDERECO)  # já está rodando
        return

    threading.Thread(target=carregar_e_ouvir, daemon=True).start()
    print(f"Interface do Fantasma em {ENDERECO}  (Ctrl+C para sair)")
    if PERMITIR_CELULAR:
        print(f"No celular (mesmo Wi-Fi): http://{_ip_local()}:{PORTA}  PIN: {PIN}")
    webbrowser.open(ENDERECO)  # abre já, mostrando "Carregando…"
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando o Fantasma.")
        servidor.shutdown()


if __name__ == "__main__":
    main()
