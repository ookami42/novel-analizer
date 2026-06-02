"""
consolidator.py — Consolida os JSONs parciais de um capítulo em um único JSON.

Responsabilidades:
- Coletar os analise-fragmento-NNN.md de um capítulo completo
- Montar prompt de merge e chamar o Qwen uma vez
- Sanitizar e validar o JSON retornado
- Salvar capitulo-NNN.json na pasta de saída

O JSON consolidado de cada capítulo é o estado base que será injetado
no primeiro fragmento do capítulo seguinte pelo prompt_builder.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from api_client import chamar_qwen
from config import PASTA_SAIDA, PREFIXO_CAPITULO, PROMPT_CONSOLIDA_PATH
from writer import ErroJSON, ler_analise, _sanitizar


# ---------------------------------------------------------------------------
# Prompt de consolidação
# ---------------------------------------------------------------------------

_INSTRUCCION_USUARIO = """
# IDENTIFICACIÓN DEL CAPÍTULO
El capítulo consolidado es: {cap_id} — {titulo_capitulo}
Este identificador proviene del campo `table_of_contents` del JSON base de la obra.
Úsalo exactamente como aparece arriba en cualquier referencia a este capítulo dentro del JSON consolidado, incluyendo `chapter_history`.
No deduzcas ni reformules el nombre del capítulo.

# ORDEN DE LOS FRAGMENTOS
Los {total} JSONs parciales a continuación están ordenados según su posición narrativa en el libro, del primer fragmento procesado al último.
Esta es la única secuencia válida. No reorganices los eventos según su cronología in-universe.
Si un evento es un flashback o analepsis, consérvalo en su posición narrativa real sin reubicarlo temporalmente.

# CHAPTER_HISTORY
Al consolidar el campo `chapter_history`:
- Usa exclusivamente el `cap_id` proporcionado arriba como identificador de la entrada.
- No uses numeración propia ni inferida.
- Si los JSONs parciales contienen entradas inconsistentes en este campo, normalízalas al `cap_id` correcto.

# FRAGMENTOS A CONSOLIDAR
{bloques}
"""

_BLOQUE_TEMPLATE = "=== Fragmento {indice_relativo} (archivo: {nome}) ===\n\n{json_conteudo}"


# ---------------------------------------------------------------------------
# Exceções próprias
# ---------------------------------------------------------------------------

class ErroConsolidacao(Exception):
    """Falha durante o processo de consolidação de um capítulo."""


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class Consolidator:
    """
    Consolida os JSONs parciais de um capítulo em um único JSON.

    Uso
    ---
        consolidador = Consolidador()
        path = consolidador.consolidar(
            numero_capitulo=1,
            indices_fragmentos=[0, 1, 2, 3],
        )
    """

    def __init__(self, pasta: str | Path = PASTA_SAIDA) -> None:
        self._pasta = Path(pasta)
        self._prompt = self._carregar_prompt()

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    def consolidar(
        self,
        numero_capitulo: int,
        indices_fragmentos: list[int],
    ) -> Path:
        """
        Lê os fragmentos do capítulo, chama o Qwen e salva o JSON consolidado.

        Parâmetros
        ----------
        numero_capitulo : int
            Número do capítulo — usado para nomear o arquivo capitulo-NNN.json.
        indices_fragmentos : list[int]
            Índices (0-based) dos analise-fragmento-NNN.md que compõem o capítulo.

        Retorna
        -------
        Path
            Caminho do arquivo capitulo-NNN.json salvo.

        Levanta
        -------
        ErroConsolidacao
            Se algum fragmento esperado não existir, se a resposta do modelo
            não for JSON válido, ou se houver falha na chamada de API.
        """
        if not indices_fragmentos:
            raise ErroConsolidacao(
                f"Lista de fragmentos vazia para capítulo {numero_capitulo}."
            )

        jsons = self._coletar(indices_fragmentos)
        mensagens = self._montar_mensagens(numero_capitulo, jsons)

        try:
            resposta = chamar_qwen(mensagens)
        except Exception as e:
            raise ErroConsolidacao(
                f"Falha na chamada de API para consolidação do capítulo "
                f"{numero_capitulo}: {e}"
            ) from e

        conteudo_limpo = _sanitizar(resposta)
        json_minify = json.dumps(conteudo_limpo, separators=(',', ':'))
        self._validar(conteudo_limpo, numero_capitulo)

        return self._salvar(numero_capitulo, json_minify)

    def path_capitulo(self, numero_capitulo: int) -> Path:
        """Retorna o path esperado para o capitulo-NNN.json sem verificar se existe."""
        nome = f"{PREFIXO_CAPITULO}-{numero_capitulo:03d}.json"
        return self._pasta / nome

    def capitulo_existe(self, numero_capitulo: int) -> bool:
        """Retorna True se o capitulo-NNN.json já foi salvo."""
        return self.path_capitulo(numero_capitulo).exists()

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _coletar(self, indices: list[int]) -> list[tuple[int, str, str]]:
        """
        Lê os arquivos de análise e retorna lista de (indice, nome, conteudo).

        Levanta ErroConsolidacao se algum arquivo não existir.
        """
        resultado: list[tuple[int, str, str]] = []
        for indice in sorted(indices):
            try:
                conteudo = ler_analise(indice, self._pasta)
            except FileNotFoundError as e:
                raise ErroConsolidacao(
                    f"Fragmento {indice:03d} não encontrado — "
                    f"capítulo incompleto, consolidação abortada."
                ) from e
            nome = f"analise-fragmento-{indice:03d}.md"
            resultado.append((indice, nome, conteudo))
        return resultado

    def _montar_mensagens(
        self,
        numero_capitulo: int,
        jsons: list[tuple[int, str, str]],
    ) -> list[dict]:
        """Monta o payload [system, user] para a chamada de consolidação."""
        bloques = "\n\n".join(
            _BLOQUE_TEMPLATE.format(
                indice_relativo=i + 1,
                nome=nome,
                json_conteudo=conteudo,
            )
            for i, (_, nome, conteudo) in enumerate(jsons)
        )

        user = _INSTRUCCION_USUARIO.format(
            total=len(jsons),
            numero_capitulo=numero_capitulo,
            bloques=bloques,
        )

        return [
            {"role": "system", "content": self._prompt},
            {"role": "user",   "content": user},
        ]

    @staticmethod
    def _validar(conteudo: str, numero_capitulo: int) -> None:
        """Valida que o conteúdo é JSON parseável."""
        try:
            json.loads(conteudo)
        except json.JSONDecodeError as e:
            raise ErroConsolidacao(
                f"JSON consolidado do capítulo {numero_capitulo} é inválido: {e}"
            ) from e

    def _salvar(self, numero_capitulo: int, conteudo: str) -> Path:
        """Salva o JSON consolidado em capitulo-NNN.json."""
        self._pasta.mkdir(parents=True, exist_ok=True)
        path = self.path_capitulo(numero_capitulo)
        path.write_text(conteudo, encoding="utf-8")
        return path


    def _carregar_prompt(self):
        path = Path(PROMPT_CONSOLIDA_PATH)

        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path.resolve()}")

        self._prompt = path.read_text(encoding="utf-8", errors="replace")
