"""Testes unitários para utils/hash_utils.py."""

from utils.hash_utils import calcular_hash_arquivo


def test_calcular_hash_arquivo_conteudo_identico_gera_mesmo_hash(tmp_path):
    arquivo_a = tmp_path / "a.bin"
    arquivo_b = tmp_path / "b.bin"
    arquivo_a.write_bytes(b"mesmo-conteudo")
    arquivo_b.write_bytes(b"mesmo-conteudo")

    assert calcular_hash_arquivo(arquivo_a) == calcular_hash_arquivo(arquivo_b)


def test_calcular_hash_arquivo_conteudos_diferentes_geram_hashes_diferentes(tmp_path):
    arquivo_a = tmp_path / "a.bin"
    arquivo_b = tmp_path / "b.bin"
    arquivo_a.write_bytes(b"conteudo-a")
    arquivo_b.write_bytes(b"conteudo-b")

    assert calcular_hash_arquivo(arquivo_a) != calcular_hash_arquivo(arquivo_b)


def test_calcular_hash_arquivo_le_em_blocos_para_arquivo_maior_que_o_bloco(tmp_path):
    arquivo = tmp_path / "grande.bin"
    arquivo.write_bytes(b"x" * (10 * 1024 * 1024))

    hash_resultado = calcular_hash_arquivo(arquivo)

    assert len(hash_resultado) == 64
