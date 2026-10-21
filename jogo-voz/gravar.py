# -*- coding: utf-8 -*-
"""Narrador do jogo da tesoura, parte i de n: grava com o edge-tts as frases de faltam.tsv (arquivo, texto) e sobe cada
mp3 direto para o bucket do jogo pela entrada /__voz/ do Worker (chave em CHAVE_VOZ). Mesma voz, taxa e nome de
arquivo do scripts/jogo_voz.py do 30000-cards; a parte é escolhida pelo nome do arquivo, como no jogo_voz_lote.py.

    CHAVE_VOZ=... python gravar.py 3/20 [--paralelas 12]
"""
import asyncio, os, sys, tempfile, urllib.error, urllib.request
from pathlib import Path

import edge_tts

VOZ, TAXA = "en-US-BrianMultilingualNeural", "-8%"
BASE = "https://tesoura.boralula.org/__voz/"
LISTA = Path(__file__).resolve().parent / "faltam.tsv"


def subir(chave, nome, dados):
    erro = None
    for t in range(6):
        req = urllib.request.Request(BASE + nome, data=dados, method="PUT")
        req.add_header("X-Chave-Voz", chave)
        req.add_header("User-Agent", "jogo-voz-actions/1.0")
        req.add_header("Content-Type", "audio/mpeg")
        try:
            with urllib.request.urlopen(req, timeout=60): return None
        except urllib.error.HTTPError as e:
            erro = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            erro = type(e).__name__
        import time; time.sleep(2 ** t)
    return erro


async def uma(chave, nome, texto, pasta, sem):
    async with sem:
        erro = None
        for t in range(6):
            tmp = pasta / nome
            try:
                await edge_tts.Communicate(texto, VOZ, rate=TAXA).save(str(tmp))
                if tmp.stat().st_size > 1000:
                    erro = await asyncio.to_thread(subir, chave, nome, tmp.read_bytes())
                    tmp.unlink()
                    return f"{nome}: subir {erro}" if erro else None
                erro = "áudio vazio"
            except Exception as e:            # rede, 403 de excesso de pedidos, websocket fechado
                erro = f"{type(e).__name__}: {e}"
            await asyncio.sleep(min(60, 2 ** t))
        return f"{nome}: {erro}"


async def main():
    i, n = (int(x) for x in sys.argv[1].split("/"))
    paralelas = int(sys.argv[sys.argv.index("--paralelas") + 1]) if "--paralelas" in sys.argv else 12
    chave = os.environ["CHAVE_VOZ"]
    with open(LISTA, encoding="utf-8") as f:
        minhas = [l.rstrip("\n").split("\t", 1) for l in f if l.strip()]
    minhas = [(a, t) for a, t in minhas if int(a[:8], 16) % n == i - 1]
    print(f"parte {i}/{n}: {len(minhas)} frases", flush=True)
    sem, pasta = asyncio.Semaphore(paralelas), Path(tempfile.mkdtemp())
    pend = [asyncio.ensure_future(uma(chave, a, t, pasta, sem)) for a, t in minhas]
    falhas, feitas = [], 0
    for fut in asyncio.as_completed(pend):
        erro = await fut
        feitas += 1
        if erro: falhas.append(erro)
        if feitas % 500 == 0: print(f"  {feitas}/{len(minhas)} ({len(falhas)} falhas)", flush=True)
    for f in falhas[:20]: print("  falhou:", f)
    print(f"parte {i}/{n}: fim, {feitas - len(falhas)} gravadas, {len(falhas)} falhas", flush=True)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
