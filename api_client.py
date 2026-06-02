"""
api_client.py — Executa chamadas isoladas ao Qwen para cada fragmento.

Responsabilidades:
- Instanciar um cliente OpenAI novo a cada chamada (garante chat isolado)
- Enviar o payload de mensagens e retornar a resposta bruta
- Aplicar timeout configurável
- Propagar erros com mensagem clara para o main.py tratar por fragmento

Não faz parsing do JSON retornado — isso é responsabilidade do writer.py e
do consolidador.py.
"""

from __future__ import annotations

from openai import OpenAI, APIError, APITimeoutError, APIConnectionError

from config import (
    QWEN_API_KEY,
    QWEN_BASE_URL,
    QWEN_MAX_TOKENS,
    QWEN_MODEL,
    QWEN_TIMEOUT,
)


# ---------------------------------------------------------------------------
# Exceções próprias
# ---------------------------------------------------------------------------

class ErroAPI(Exception):
    """Erro recuperável de API — o pipeline pode continuar no próximo fragmento."""


class ErroConexao(ErroAPI):
    """Servidor inacessível ou timeout."""


class ErroResposta(ErroAPI):
    """Servidor respondeu mas o conteúdo é inválido ou vazio."""


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def chamar_qwen(mensagens: list[dict]) -> str:
    """
    Envia o payload ao Qwen e retorna a resposta como string bruta.

    Cada chamada instancia um cliente novo — sem reuso de sessão,
    sem histórico acumulado entre fragmentos.

    Parâmetros
    ----------
    mensagens : list[dict]
        Payload no formato [{"role": "system", ...}, {"role": "user", ...}]
        produzido pelo PromptBuilder.montar().

    Retorna
    -------
    str
        Conteúdo textual da resposta do modelo, sem pós-processamento.

    Levanta
    -------
    ErroConexao
        Se o servidor estiver inacessível ou a chamada exceder QWEN_TIMEOUT.
    ErroResposta
        Se a resposta vier vazia ou sem conteúdo utilizável.
    ErroAPI
        Para outros erros de API não classificados acima.
    """
    cliente = OpenAI(
        base_url=QWEN_BASE_URL,
        api_key=QWEN_API_KEY,
        timeout=QWEN_TIMEOUT,
    )

    try:
        resposta = cliente.chat.completions.create(
            model=QWEN_MODEL,
            max_tokens=QWEN_MAX_TOKENS,
            messages=mensagens,
        )

    except APITimeoutError as e:
        raise ErroConexao(
            f"Timeout após {QWEN_TIMEOUT}s — servidor não respondeu a tempo."
        ) from e

    except APIConnectionError as e:
        raise ErroConexao(
            f"Falha de conexão com {QWEN_BASE_URL} — verifique se o servidor está ativo."
        ) from e

    except APIError as e:
        raise ErroAPI(
            f"Erro de API ({type(e).__name__}): {e}"
        ) from e

    # --- Valida o conteúdo da resposta ---
    escolhas = resposta.choices
    if not escolhas:
        raise ErroResposta("Resposta do modelo veio sem choices.")

    conteudo = escolhas[0].message.content
    if not conteudo or not conteudo.strip():
        raise ErroResposta("Resposta do modelo veio com conteúdo vazio.")

    return conteudo.strip()
