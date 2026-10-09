"""Lê arquivos de dentro dos pacotes do DS2 SotFS (Game/<Nome>Ebl.bhd + .bdt).

O índice .bhd vem cifrado com RSA: o jogo traz a chave pública em <Nome>KeyCode.pem e cada bloco de 256 bytes
vira 255 bytes com `m = c^e mod n`. O índice (BHD5) lista os arquivos por hash do nome; alguns trechos de cada
arquivo vêm em AES-128-ECB (chave e trechos no próprio índice) e o conteúdo costuma estar comprimido em DCX.
"""
import os
import struct
import zlib
from pathlib import Path


class ArquivoError(Exception):
    pass


def ds2_hash(path: str) -> int:
    """Hash do nome no índice: minúsculas, barra normal, barra na frente, h = h*37 + c em 32 bits."""
    texto = path.strip().replace("\\", "/").lower()
    if not texto.startswith("/"):
        texto = "/" + texto
    h = 0
    for ch in texto:
        h = (h * 37 + ord(ch)) & 0xFFFFFFFF
    return h


def dcx(data: bytes) -> bytes:
    """Abre um DCX com DFLT (zlib); o que não for DCX volta igual."""
    if data[:4] != b"DCX\x00":
        return data
    if b"DFLT" not in data[:0x80] or b"DCA\x00" not in data[:0x80]:
        raise ArquivoError("DCX em formato inesperado")
    dca = data.index(b"DCA\x00")
    start = dca + struct.unpack_from(">I", data, dca + 4)[0]
    try:
        return zlib.decompressobj().decompress(data[start:])
    except zlib.error as err:
        raise ArquivoError(f"DCX corrompido ({err})") from err


def _decifrar_indice(pem: Path, bhd: Path) -> bytes:
    from Crypto.PublicKey import RSA

    key = RSA.import_key(pem.read_bytes())
    size = key.size_in_bytes()
    data = bhd.read_bytes()
    out = bytearray()
    for i in range(0, len(data) - size + 1, size):
        m = pow(int.from_bytes(data[i:i + size], "big"), key.e, key.n)
        out += m.to_bytes(size, "big")[1:]
    if out[:4] != b"BHD5":
        raise ArquivoError(f"{bhd.name}: índice não abriu com a chave {pem.name}")
    return bytes(out)


def assinatura(game_dir) -> str:
    """Tamanho e data dos índices: muda quando o jogo atualiza, e o cache extraído é refeito."""
    partes = []
    for bhd in sorted(Path(game_dir).glob("*Ebl.bhd")):
        st = bhd.stat()
        partes.append(f"{bhd.name}:{st.st_size}:{int(st.st_mtime)}")
    return "|".join(partes)


class Arquivo:
    def __init__(self, game_dir, nome: str):
        game_dir = Path(game_dir)
        pem, bhd, self.bdt = game_dir / f"{nome}KeyCode.pem", game_dir / f"{nome}Ebl.bhd", game_dir / f"{nome}Ebl.bdt"
        if not (pem.is_file() and bhd.is_file() and self.bdt.is_file()):
            raise ArquivoError(f"pacote {nome} não encontrado em {game_dir}")
        raw = _decifrar_indice(pem, bhd)
        buckets, buckets_off = struct.unpack_from("<ii", raw, 0x10)
        self.arquivos: dict[int, tuple[int, int, tuple | None]] = {}
        for b in range(buckets):
            count, off = struct.unpack_from("<ii", raw, buckets_off + 8 * b)
            for k in range(count):
                h, size, offset, _sha, aes_off = struct.unpack_from("<Iiqqq", raw, off + 0x20 * k)
                aes = None
                if aes_off:
                    chave = raw[aes_off:aes_off + 16]
                    n = struct.unpack_from("<i", raw, aes_off + 16)[0]
                    aes = (chave, [struct.unpack_from("<qq", raw, aes_off + 20 + 16 * r) for r in range(n)])
                self.arquivos[h] = (offset, size, aes)

    def tem(self, caminho: str) -> bool:
        return ds2_hash(caminho) in self.arquivos

    def ler(self, caminho: str) -> bytes:
        entrada = self.arquivos.get(ds2_hash(caminho))
        if entrada is None:
            raise ArquivoError(f"{caminho} não está no pacote")
        offset, size, aes = entrada
        with self.bdt.open("rb") as fh:
            fh.seek(offset)
            data = bytearray(fh.read(size))
        if aes:
            from Crypto.Cipher import AES

            cifra = AES.new(aes[0], AES.MODE_ECB)
            for ini, fim in aes[1]:
                if ini < 0 or fim <= ini:
                    continue
                fim = min(fim, len(data))
                fim -= (fim - ini) % 16
                data[ini:fim] = cifra.decrypt(bytes(data[ini:fim]))
        return dcx(bytes(data))


def game_dir_padrao() -> Path | None:
    env = os.environ.get("BUILDSMITH_DS2_GAME")
    candidatos = [Path(env)] if env else []
    candidatos += [Path(r"C:/Program Files (x86)/Steam/steamapps/common/Dark Souls II Scholar of the First Sin/Game"),
                   Path(r"C:/Program Files/Steam/steamapps/common/Dark Souls II Scholar of the First Sin/Game")]
    return next((p for p in candidatos if (p / "GameDataEbl.bhd").is_file()), None)
