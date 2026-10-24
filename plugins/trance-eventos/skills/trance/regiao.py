#!/usr/bin/env python3
"""Agente /trance, parte de regiões (/regiao/<slug>: regiões do Brasil, estados, continentes, países).

  regiao.py listar [--nivel uf|regiao|continente|pais] [--vazias]   # regiões com o que já têm (intro, SEO)
  regiao.py propor <slug> <parcial.json|-> [--ensaio] [--publicar]  # texto de uma região: proposta (Moderação) ou direto
  regiao.py lote <regioes.json|-> [--ensaio] [--publicar]           # várias: {"<slug>": {parcial}, ...} ou [{"slug": ..., ...}]

Região não tem status nem dono (está sempre no ar): por padrão o agente propõe em `alteracoes` (tabela 'regioes');
com --publicar ("Publicar direto", escolha do usuário) grava o texto na região e ele vai ao ar na hora. As regiões são fixas (duda/supabase/schema.sql), menos país: admin cria em Cena › Novo país no CMS.
A página /regiao/<slug> só existe com 3 ou mais cadastros publicados (`tem_pagina`); o texto proposto antes fica guardado.
Campos: intro (texto puro, parágrafos por linha em branco; ou HTML p/br/strong/em/a/ul/ol/li),
seo_title (até 60), seo_description (até 158), fontes, notas_agente. Saída em JSON.
"""
import json
import pathlib
import re
import sys

import requests

from evento import CMS, Erro, editar_direto, eu, faltando, paragrafos, rest, saida, tudo, uid

SITE = "https://www.trance.com.br/regiao/"
PROPOR = ["intro", "seo_title", "seo_description"]
PERMITIDOS = {"slug", *PROPOR, "fontes", "notas_agente"}
FIXAS = ("Região {slug} não existe. País novo só um administrador cria, no CMS em Cena › Novo país (nome, código ISO-2 e "
         "continente); a página /regiao/<slug> só aparece com 3 ou mais cadastros publicados.")


def contagem(slug=""):
    q = "regioes_contagem?select=slug,nivel,total" + ("&slug=eq." + slug if slug else "")
    return {c["slug"]: (c["total"] or 0, c["nivel"] == "raiz" or (c["total"] or 0) >= 3) for c in tudo(q)}


def _ler(arquivo):
    return json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())


def validar(e):
    extras = set(e) - PERMITIDOS
    if extras:
        raise Erro("Campos não aceitos: " + ", ".join(sorted(extras)))
    d = {}
    if "intro" in e:
        t = str(e.get("intro") or "").strip()
        d["intro"] = paragrafos(t)  # HTML vira texto antes (evento.paragrafos)
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
    cont = contagem()
    out = []
    for r in tudo(q):
        falta = faltando(r, PROPOR)
        if vazias and not falta:
            continue
        out.append({"slug": r["slug"], "nome": r["nome"], "nivel": r["nivel"], "pai": r["pai"], "faltando": falta,
                    "cadastros": cont.get(r["slug"], (0, False))[0], "tem_pagina": cont.get(r["slug"], (0, False))[1],
                    "proposta_pendente": r["slug"] in pend, "intro_atual": (r.get("intro") or "")[:200]})
    return {"total": len(out), "regioes": out}


def propor(slug, e, ensaio=False, pendentes=None, publicar=False):
    atual = rest("GET", "regioes?select=*&slug=eq." + slug).json()
    if not atual:
        raise Erro(FIXAS.format(slug=slug))
    a = atual[0]
    d, fontes = validar({k: v for k, v in e.items() if k != "slug"})
    mud = {k: {"antes": a.get(k) or "", "depois": d[k]} for k in d if (a.get(k) or "") != d[k]}
    if not mud:
        raise Erro(f"{slug}: nada muda.")
    if pendentes is None:
        pendentes = {x["chave"] for x in rest("GET", f"alteracoes?select=chave&tabela=eq.regioes&status=eq.pendente&chave=eq.{slug}").json()}
    if slug in pendentes:
        raise Erro(f"{slug}: já tem proposta pendente na Moderação (uma por região): decida-a no CMS antes.")
    total, pagina = contagem(slug).get(slug, (0, False))
    res = {"regiao": {"slug": slug, "nome": a["nome"], "nivel": a["nivel"], "site": SITE + slug, "cadastros": total, "tem_pagina": pagina},
           "mudancas": mud, "faltando": faltando(a | {k: d[k] for k in mud}, PROPOR)}
    if not pagina:
        res["aviso"] = (f"{SITE}{slug} ainda não existe ({total} cadastro(s) publicado(s); a página aparece com 3). "
                        "O texto fica guardado e entra no ar quando a página existir.")
    if publicar:  # "Publicar direto": grava na região (sempre no ar)
        return res | editar_direto("regioes", "slug=eq." + slug, slug, {k: d[k] for k in mud}, [], "", ensaio)
    if ensaio:
        return res | {"ensaio": True}
    r = rest("POST", "alteracoes?select=id", headers={"Prefer": "return=representation"},
             json={"tabela": "regioes", "chave": slug, "user_id": uid(), "dados": {k: d[k] for k in mud},
                   "mensagem": str(e.get("notas_agente") or "")[:2000], "origem": "agente", "fontes": fontes}).json()[0]
    return res | {"ok": True, "id": r["id"], "moderacao": f"{CMS}/moderacao/alteracao/{r['id']}"}


def lote(dados, ensaio=False, publicar=False):
    itens = [x | {"slug": s} for s, x in dados.items()] if isinstance(dados, dict) else list(dados)
    eu()
    pend = {a["chave"] for a in tudo("alteracoes?select=chave&tabela=eq.regioes&status=eq.pendente")}
    ok, erros = [], []
    for x in itens:
        slug = str(x.get("slug") or "")
        try:
            r = propor(slug, x, ensaio, pend, publicar)
            ok.append({"slug": slug, **({"id": r["id"]} if "id" in r else {}), "campos": list(r["mudancas"])})
        except Erro as e:
            erros.append({"slug": slug, "erro": str(e)})
        except requests.HTTPError as e:
            erros.append({"slug": slug, "erro": f"{e.response.status_code}: {e.response.text[:200]}"})
    if publicar:
        return {"ensaio": ensaio, "publicar": True, "publicadas": len(ok), "erros": erros, "itens": ok}
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
        saida(propor(pos[0], _ler(pos[1]), ens, publicar="--publicar" in resto))
    elif cmd == "lote" and pos:
        saida(lote(_ler(pos[0]), ens, "--publicar" in resto))
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
