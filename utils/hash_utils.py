"""Cálculo de hash de arquivos em streaming.

Ler o arquivo inteiro em memória antes de hashear violaria o requisito de
processar zips de até 500MB sem estourar memória (RNF1). Por isso o hash é
calculado em blocos, nunca carregando o arquivo inteiro de uma vez.
"""

import hashlib
from pathlib import Path

_TAMANHO_BLOCO = 65_536


def calcular_hash_arquivo(caminho: Path) -> str:
    """Calcula o hash SHA-256 do conteúdo de um arquivo, lendo em blocos.

    Args:
        caminho: caminho do arquivo a ser hasheado.

    Returns:
        Hash SHA-256 em hexadecimal.
    """
    hasher = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(_TAMANHO_BLOCO), b""):
            hasher.update(bloco)
    return hasher.hexdigest()
