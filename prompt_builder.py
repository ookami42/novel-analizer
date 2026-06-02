"""
prompt_builder.py — Monta o payload de mensagens para cada chamada ao Qwen.

Responsabilidades:
- Carregar o knowledge-template.json uma única vez
- Carregar e parsear o fragment-analizer.md para obter o system prompt
- Montar a lista de mensagens [system, user] para cada fragmento
- Injetar o JSON atual (capítulo anterior ou template) e o texto do fragmento

Estrutura esperada do fragment-analizer.md:
    <instruções do sistema>
    ---
    === 1. JSON base ===
    ```json
    { ... template ... }
    ```
    === 2. Fragmento de historia ===
"""

from __future__ import annotations

import json
from pathlib import Path

from config import PROMPT_ANALISE_PATH, KNOWLEDGE_TEMPLATE_PATH


# ---------------------------------------------------------------------------
# Marcadores do fragment-analizer.md
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
    Carrega o fragment-analizer.md e o knowledge-template.json, e monta payloads para o Qwen.

    Os arquivos são lidos uma única vez no construtor.
    Instanciar uma vez e reutilizar para todos os fragmentos.

    Uso
    ---
        builder = PromptBuilder()
        mensagens = builder.montar(texto_fragmento, json_atual)
        # mensagens → [{"role": "system", ...}, {"role": "user", ...}]
    """

    def __init__(
        self,
        prompt_path: str | Path = PROMPT_ANALISE_PATH,
        template_path: str | Path = KNOWLEDGE_TEMPLATE_PATH,
    ) -> None:
        prompt_path = Path(prompt_path)
        template_path = Path(template_path)

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Arquivo de prompt não encontrado: {prompt_path.resolve()}"
            )

        if not template_path.exists():
            raise FileNotFoundError(
                f"Arquivo de template JSON não encontrado: {template_path.resolve()}"
            )

        # Carrega o template JSON diretamente do arquivo .json
        with open(template_path, "r", encoding="utf-8") as f:
            self._template_json = json.load(f)

        # Carrega e parseia o prompt para obter o system prompt
        conteudo = prompt_path.read_text(encoding="utf-8")
        self._system = self._parsear_system(conteudo)

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    def montar(
        self,
        texto_fragmento: str,
        json_atual: dict | str | None = None,
    ) -> list[dict]:
        """
        Monta a lista de mensagens para uma chamada ao Qwen.

        Parâmetros
        ----------
        texto_fragmento : str
            Texto extraído do .xhtml pelo loader.py.
        json_atual : dict | str | None
            JSON do último capítulo consolidado (como dict ou string JSON).
            Se None, usa o template vazio do knowledge-template.json.

        Retorna
        -------
        list[dict]
            Lista no formato esperado pela API OpenAI:
            [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        """
        if json_atual is None:
            json_injetado = self._template_json
        elif isinstance(json_atual, str):
            json_injetado = json.loads(json_atual)
        else:
            json_injetado = json_atual

        # Converte o JSON para string formatada
        json_str = json.dumps(json_injetado, ensure_ascii=False, indent=2)

        user = (
            f"{_MARCADOR_JSON}\n\n"
            f"```json\n{json_str}\n```\n\n"
            f"{_MARCADOR_FRAGMENTO}\n\n"
            f"{texto_fragmento}"
        )

        return [
            {"role": "system", "content": self._system},
            {"role": "user",   "content": user},
        ]

    @property
    def template_json(self) -> dict:
        """Template JSON vazio carregado do knowledge-template.json."""
        return self._template_json

    @property
    def system_prompt(self) -> str:
        """Bloco de instruções do sistema extraído do fragment-analizer.md."""
        return self._system

    # ------------------------------------------------------------------
    # Parsing interno
    # ------------------------------------------------------------------

    @staticmethod
    def _parsear_system(conteudo: str) -> str:
        """
        Extrai o system prompt do conteúdo do fragment-analizer.md.
        O system prompt é tudo antes do marcador === 1. JSON base ===

        Levanta
        -------
        ValueError
            Se o marcador não for encontrado.
        """
        idx_json = conteudo.find(_MARCADOR_JSON)
        if idx_json == -1:
            raise ValueError(
                f"Marcador '{_MARCADOR_JSON}' não encontrado no fragment-analizer.md"
            )

        return conteudo[:idx_json].rstrip()
