#!/usr/bin/env python3
"""Agente /trance, parte de regiões (/regiao/<slug>: regiões do Brasil, estados, continentes, países).

  regiao.py listar [--nivel uf|regiao|continente|pais] [--vazias]   # regiões com o que já têm (intro, SEO)
  regiao.py propor <slug> <parcial.json|-> [--ensaio]                # proposta de texto de uma região (Moderação do CMS)
  regiao.py lote <regioes.json|-> [--ensaio]                         # várias: {"<slug>": {parcial}, ...} ou [{"slug": ..., ...}]

Região não tem status nem dono (está sempre no ar): o agente nunca grava direto, só propõe em `alteracoes`
(tabela 'regioes'). Campos: intro (texto puro, parágrafos por linha em branco; ou HTML p/br/strong/em/a/ul/ol/li),
seo_title (até 60), seo_description (até 158), fontes, notas_agente. Saída em JSON.
"""
import json
import pathlib
import re
import sys

import requests

from evento import CMS, Erro, eu, faltando, paragrafos, rest, saida, tudo, uid

SITE = "https://www.trance.com.br/regiao/"
PROPOR = ["intro", "seo_title", "seo_description"]
PERMITIDOS = {"slug", *PROPOR, "fontes", "notas_agente"}


def _ler(arquivo):
    return json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())


def validar(e):
    extras = set(e) - PERMITIDOS
    if extras:
        raise Erro("Campos não aceitos: " + ", ".join(sorted(extras)))
    d = {}
    if "intro" in e:
        t = str(e.get("intro") or "").strip()
        d["intro"] = t if t.startswith("<") else paragrafos(t)  # HTML passa pela sanitização do CMS na aprovação
    for k, lim in (("seo_title", 60), ("seo_description", 158)):
        if k in e:
            d[k] = re.sub(r"\s+", " ", str(e.get(k) or "")).strip()
            if len(d[k]) > lim:
                raise Erro(f"{k} com {len(d[k])} caracteres (máx. {lim}).")
    fontes = [str(f).strip() for f in (e.get("fontes") or []) if str(f).strip()]
    return d, fontes


def listar(nivel="", vazias=False):
    q = "regioes?select=slug,nome,nivel,pai,intro,seo_title,seo_description&order=nivel,nome"
    if nivel:
        q += "&nivel=eq." + nivel
    pend = {a["chave"] for a in tudo("alteracoes?select=chave&tabela=eq.regioes&status=eq.pendente")}
    out = []
    for r in tudo(q):
        falta = faltando(r, PROPOR)
        if vazias and not falta:
            continue
        out.append({"slug": r["slug"], "nome": r["nome"], "nivel": r["nivel"], "pai": r["pai"], "faltando": falta,
                    "proposta_pendente": r["slug"] in pend, "intro_atual": (r.get("intro") or "")[:200]})
    return {"total": len(out), "regioes": out}


def propor(slug, e, ensaio=False, pendentes=None):
    atual = rest("GET", "regioes?select=*&slug=eq." + slug).json()
    if not atual:
        raise Erro(f"Região {slug} não existe.")
    a = atual[0]
    d, fontes = validar({k: v for k, v in e.items() if k != "slug"})
    mud = {k: {"antes": a.get(k) or "", "depois": d[k]} for k in d if (a.get(k) or "") != d[k]}
    if not mud:
        raise Erro(f"{slug}: nada muda.")
    if pendentes is None:
        pendentes = {x["chave"] for x in rest("GET", f"alteracoes?select=chave&tabela=eq.regioes&status=eq.pendente&chave=eq.{slug}").json()}
    if slug in pendentes:
        raise Erro(f"{slug}: já tem proposta pendente na Moderação (uma por região).")
    res = {"regiao": {"slug": slug, "nome": a["nome"], "nivel": a["nivel"], "site": SITE + slug}, "mudancas": mud,
           "faltando": faltando(a | {k: d[k] for k in mud}, PROPOR)}
    if ensaio:
        return res | {"ensaio": True}
    r = rest("POST", "alteracoes?select=id", headers={"Prefer": "return=representation"},
             json={"tabela": "regioes", "chave": slug, "user_id": uid(), "dados": {k: d[k] for k in mud},
                   "mensagem": str(e.get("notas_agente") or "")[:2000], "origem": "agente", "fontes": fontes}).json()[0]
    return res | {"ok": True, "id": r["id"], "moderacao": f"{CMS}/moderacao/alteracao/{r['id']}"}


def lote(dados, ensaio=False):
    itens = [x | {"slug": s} for s, x in dados.items()] if isinstance(dados, dict) else list(dados)
    eu()
    pend = {a["chave"] for a in tudo("alteracoes?select=chave&tabela=eq.regioes&status=eq.pendente")}
    ok, erros = [], []
    for x in itens:
        slug = str(x.get("slug") or "")
        try:
            r = propor(slug, x, ensaio, pend)
            ok.append({"slug": slug, **({"id": r["id"]} if "id" in r else {}), "campos": list(r["mudancas"])})
        except Erro as e:
            erros.append({"slug": slug, "erro": str(e)})
        except requests.HTTPError as e:
            erros.append({"slug": slug, "erro": f"{e.response.status_code}: {e.response.text[:200]}"})
    return {"ensaio": ensaio, "propostas": len(ok), "erros": erros, "itens": ok,
            "moderacao": f"{CMS}/moderacao?tabela=regioes&origem=agente"}


def main(args):
    if not args or args[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return
    cmd, resto = args[0], args[1:]
    nivel = next((resto[i + 1] for i, a in enumerate(resto) if a == "--nivel" and i + 1 < len(resto)), "")
    pos = [a for a in resto if not a.startswith("--") and a != nivel]
    ens = "--ensaio" in resto
    if cmd == "listar":
        saida(listar(nivel, "--vazias" in resto))
    elif cmd == "propor" and len(pos) > 1:
        if not ens:
            eu()
        saida(propor(pos[0], _ler(pos[1]), ens))
    elif cmd == "lote" and pos:
        saida(lote(_ler(pos[0]), ens))
    else:
        raise Erro("Uso: regiao.py listar|propor|lote (veja --help)")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Erro as e:
        print(json.dumps({"erro": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(json.dumps({"erro": f"Rede: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
