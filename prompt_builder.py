"""
prompt_builder.py — Monta o payload de mensagens para cada chamada ao Qwen.

Responsabilidades:
- Carregar e parsear o prompt-analise.md uma única vez
- Separar o conteúdo em system prompt, template JSON e marcador de fragmento
- Montar a lista de mensagens [system, user] para cada fragmento
- Injetar o JSON atual (capítulo anterior ou template vazio) e o texto do fragmento

Estrutura esperada do prompt-analise.md:
    <instruções do sistema>
    ---
    === 1. JSON base ===
    ```json
    { ... template ... }
    ```
    === 2. Fragmento de historia ===
"""

from __future__ import annotations

from pathlib import Path

from config import PROMPT_ANALISE_PATH


# ---------------------------------------------------------------------------
# Marcadores do prompt-analise.md
# ---------------------------------------------------------------------------

_MARCADOR_JSON      = "=== 1. JSON base ==="
_MARCADOR_FRAGMENTO = "=== 2. Fragmento de historia ==="
_CERCA_JSON_INICIO  = "```json"
_CERCA_JSON_FIM     = "```"


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class PromptBuilder:
    """
    Carrega o prompt-analise.md e monta payloads para o Qwen.

    O arquivo é lido uma única vez no construtor.
    Instanciar uma vez e reutilizar para todos os fragmentos.

    Uso
    ---
        builder = PromptBuilder()
        mensagens = builder.montar(texto_fragmento, json_atual)
        # mensagens → [{"role": "system", ...}, {"role": "user", ...}]
    """

    def __init__(self, path: str | Path = PROMPT_ANALISE_PATH) -> None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo de prompt não encontrado: {path.resolve()}"
            )

        conteudo = path.read_text(encoding="utf-8")
        self._system, self._template_json = self._parsear(conteudo)

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    def montar(
        self,
        texto_fragmento: str,
        json_atual: str | None = None,
    ) -> list[dict]:
        """
        Monta a lista de mensagens para uma chamada ao Qwen.

        Parâmetros
        ----------
        texto_fragmento : str
            Texto extraído do .xhtml pelo loader.py.
        json_atual : str | None
            JSON do último capítulo consolidado.
            Se None, usa o template vazio do próprio prompt-analise.md.

        Retorna
        -------
        list[dict]
            Lista no formato esperado pela API OpenAI:
            [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        """
        json_injetado = json_atual if json_atual is not None else self._template_json

        user = (
            f"{_MARCADOR_JSON}\n\n"
            f"```json\n{json_injetado}\n```\n\n"
            f"{_MARCADOR_FRAGMENTO}\n\n"
            f"{texto_fragmento}"
        )

        return [
            {"role": "system", "content": self._system},
            {"role": "user",   "content": user},
        ]

    @property
    def template_json(self) -> str:
        """Template JSON vazio extraído do prompt-analise.md."""
        return self._template_json

    @property
    def system_prompt(self) -> str:
        """Bloco de instruções do sistema extraído do prompt-analise.md."""
        return self._system

    # ------------------------------------------------------------------
    # Parsing interno
    # ------------------------------------------------------------------

    @staticmethod
    def _parsear(conteudo: str) -> tuple[str, str]:
        """
        Divide o conteúdo do prompt-analise.md em duas partes:
        - system: tudo antes do marcador === 1. JSON base ===
        - template_json: o conteúdo do bloco ```json ... ```

        Levanta
        -------
        ValueError
            Se qualquer um dos marcadores esperados não for encontrado.
        """
        # --- Localiza os marcadores ---
        idx_json = conteudo.find(_MARCADOR_JSON)
        if idx_json == -1:
            raise ValueError(
                f"Marcador '{_MARCADOR_JSON}' não encontrado no prompt-analise.md"
            )

        idx_fragmento = conteudo.find(_MARCADOR_FRAGMENTO)
        if idx_fragmento == -1:
            raise ValueError(
                f"Marcador '{_MARCADOR_FRAGMENTO}' não encontrado no prompt-analise.md"
            )

        # --- System prompt: tudo antes de === 1. JSON base === ---
        system = conteudo[:idx_json].rstrip()

        # --- Template JSON: entre ```json e ``` no bloco do marcador 1 ---
        bloco = conteudo[idx_json:idx_fragmento]

        inicio_cerca = bloco.find(_CERCA_JSON_INICIO)
        if inicio_cerca == -1:
            raise ValueError("Bloco ```json não encontrado após o marcador JSON base.")

        # Avança além de ```json\n
        inicio_json = inicio_cerca + len(_CERCA_JSON_INICIO)
        fim_cerca = bloco.find(_CERCA_JSON_FIM, inicio_json)
        if fim_cerca == -1:
            raise ValueError("Fechamento ``` não encontrado no bloco JSON base.")

        template_json = bloco[inicio_json:fim_cerca].strip()

        return system, template_json
