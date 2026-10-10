#!/usr/bin/env python3
"""Agente /trance, parte de gravadoras (selos). Plano: cms/PLANO-AGENTE-TRANCE.md, seção 6c e busca de gravadoras.

  gravadora.py buscar "<nome>" [--site url]                  # existentes / prováveis na base
  gravadora.py candidatos [--pais Brazil] [--desde 2023] [--estilo Psy-Trance] [--paginas 3]
                                                             # selos do Discogs fora da base (busca em lotes)
  gravadora.py selo "<nome>"                                 # Discogs: perfil, links, logo e catálogo cruzado com os perfis
  gravadora.py gravar <gravadora.json|-> [--ensaio]          # gravadora nova pendente
  gravadora.py propor <slug> <parcial.json|-> [--ensaio]     # proposta de alteração de gravadora publicada

Discogs pela rota do CMS (/api/agente/discogs; a chave fica só no servidor). Saída em JSON.
"""
import difflib
import json
import pathlib
import re
import sys

import requests

from evento import CMS, faltando, REF, Erro, eu, norm, paragrafos, rest, saida, sessao, slugify, tudo, uid
from artista import base_perfis, url_perfil

URLS = ["site", "instagram", "soundcloud", "bandcamp", "beatport"]
PERMITIDOS = {"nome", "slug", "pais", "estilos", "logo", "release", "seo_title", "seo_description", *URLS, "fontes", "notas_agente"}
PROPOR = ["nome", "pais", "estilos", "logo", "release", "seo_title", "seo_description", *URLS]
# tudo o que o site mostra da gravadora: o ensaio lista o que ficou vazio ("faltando")
COMPLETO = ["pais", "estilos", "logo", "release", "seo_title", "seo_description", *URLS]


def _k(nome):
    """Nome sem "records/music/label" (mesma regra do site para casar selos)."""
    return " ".join(re.sub(r"\b(records?|recordings|rec|music|label)\b", " ", norm(nome)).split())


def _dominio(u):
    return re.sub(r"^https?://(www\.)?|/.*$", "", str(u or "").lower())


def _url(g):
    return f"https://www.trance.com.br/gravadora/{g['slug']}"


def base():
    return tudo("gravadoras?select=slug,nome,pais,status,origem,site,bandcamp,estilos,logo&order=slug")


def buscar(nome, site="", gs=None):
    gs = gs if gs is not None else base()
    k, dom = _k(nome), _dominio(site)
    ex, prov = [], []
    for g in gs:
        item = {"slug": g["slug"], "nome": g["nome"], "pais": g["pais"], "status": g["status"], "site": _url(g), "cms": f"{CMS}/gravadoras/{g['slug']}"}
        if (k and _k(g["nome"]) == k) or (dom and dom in (_dominio(g.get("site")), _dominio(g.get("bandcamp")))):
            ex.append(item)
        elif k and difflib.SequenceMatcher(None, k, _k(g["nome"])).ratio() >= 0.82:
            prov.append(item)
    return {"existentes": ex, "provaveis": prov[:10]}


def _cms(params):
    r = requests.get(f"{CMS}/api/agente/discogs", params=params, headers={"Authorization": "Bearer " + sessao()["access_token"]}, timeout=120)
    try:
        j = r.json()
    except ValueError:
        raise Erro(f"CMS respondeu {r.status_code} sem JSON.")
    if r.status_code != 200:
        raise Erro(j.get("erro", f"CMS {r.status_code}"))
    return j


def candidatos(pais="", desde=0, estilo="Psy-Trance", paginas=3):
    j = _cms({"modo": "selos", "estilo": estilo, "pais": pais, "desde": desde or "", "paginas": paginas})
    gs = base()
    novos, na_base = [], []
    for s in j["selos"]:
        b = buscar(s["nome"], "", gs)
        (na_base if b["existentes"] else novos).append(s | ({"na_base": b["existentes"][0]["slug"]} if b["existentes"] else {}))
    return {"estilo": estilo, "pais": pais, "desde": desde, "lancamentos_no_estilo": j["lancamentos_no_estilo"],
            "novos": novos, "ja_na_base": [x["nome"] for x in na_base],
            "obs": "Ordem: último lançamento, depois nº de lançamentos (da amostra lida). Mostre em lotes de ~30."}


def selo(nome):
    j = _cms({"modo": "selo", "nome": nome})
    if not j.get("achado"):
        return {"achado": False, "nome": nome}
    perfis = base_perfis()
    por_nome = {norm(p["nome"]): p for p in perfis}
    g = buscar(j["nome"])["existentes"]
    slug_g = g[0]["slug"] if g else None
    com, sem = [], []
    for a in j["artistas"]:
        p = por_nome.get(norm(a["nome"]))
        if p:
            com.append({"nome": p["nome"], "slug": p["slug"], "site": url_perfil(p), "lancamentos": a["lancamentos"],
                        "ja_vinculado": bool(slug_g) and slug_g in (p.get("gravadoras") or [])})
        else:
            sem.append(a)
    return j | {"na_base": g, "catalogo": {"com_perfil": com, "sem_perfil": sem}}


def validar(e):
    extras = set(e) - PERMITIDOS
    if extras:
        raise Erro("Campos não aceitos: " + ", ".join(sorted(extras)))
    d, avisos = {}, []
    d["nome"] = re.sub(r"\s+", " ", str(e.get("nome") or "")).strip()[:120]
    if not d["nome"]:
        raise Erro("nome é obrigatório.")
    d["pais"] = str(e.get("pais") or "").strip()[:60]  # nome do país por extenso, como no CMS (Brasil, Israel...)
    est = [str(x).strip() for x in (e.get("estilos") or []) if str(x).strip()]
    if est:
        validos = {x["slug"] for x in tudo("estilos?select=slug")}
        ruins = [x for x in est if x not in validos]
        if ruins:
            raise Erro("estilos que não existem na Wikidelic: " + ", ".join(ruins))
    d["estilos"] = est
    d["logo"] = str(e.get("logo") or "").strip()
    if d["logo"] and not (REF.match(d["logo"]) or re.match(r"^https://irp\.cdn-website\.com/\S+$", d["logo"])):
        raise Erro("logo: use a ref conta:… devolvida por 'evento.py imagem'.")
    if not d["logo"]:
        avisos.append("Sem logo.")
    d["release"] = paragrafos(e.get("release"))
    # textos do Google (bloco "Google" do CMS): título até 60, descrição até 158
    for k, lim in (("seo_title", 60), ("seo_description", 158)):
        d[k] = re.sub(r"\s+", " ", str(e.get(k) or "")).strip()
        if len(d[k]) > lim:
            raise Erro(f"{k} com {len(d[k])} caracteres (máx. {lim}).")
    for k in URLS:
        v = str(e.get(k) or "").strip()
        if v and not re.match(r"^https?://[^\s]{3,}$", v):
            raise Erro(f"{k}: endereço inválido ({v[:60]}).")
        d[k] = v[:1000]
    fontes = e.get("fontes") or []
    if not isinstance(fontes, list) or not fontes:
        raise Erro("fontes é obrigatório: lista de {url, usado}.")
    d["fontes"] = [{"url": str((f or {}).get("url", f) if isinstance(f, dict) else f)[:1000],
                    "usado": str((f or {}).get("usado", "") if isinstance(f, dict) else "")[:300]} for f in fontes]
    if not all(re.match(r"^https?://\S+$", f["url"]) for f in d["fontes"]):
        raise Erro("fonte inválida.")
    d["notas_agente"] = str(e.get("notas_agente") or "").strip()[:3000]
    d["slug"] = slugify(e.get("slug") or d["nome"])
    d.update(status="pendente", origem="agente")
    return d, avisos


def gravar(arquivo, ensaio=False):
    e = json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())
    d, avisos = validar(e)
    eu()
    ja = buscar(d["nome"], d["site"])
    if ja["existentes"]:
        raise Erro("Já existe: " + "; ".join(f"{g['nome']} {g['site']}" for g in ja["existentes"]))
    usados = {r["slug"] for r in rest("GET", f"gravadoras?select=slug&slug=like.{d['slug']}*").json()}
    base_slug, n = d["slug"], 2
    while d["slug"] in usados:
        d["slug"], n = f"{base_slug}-{n}", n + 1
    url = _url(d)
    falta = faltando(d, COMPLETO)
    if ensaio:
        return {"ensaio": True, "url": url, "faltando": falta, "avisos": avisos, "registro": d}
    r = rest("POST", "gravadoras?select=slug,status", json=d, headers={"Prefer": "return=representation"}).json()[0]
    return {"ok": True, "slug": r["slug"], "url": url, "status": r["status"], "faltando": falta, "avisos": avisos,
            "moderacao": f"{CMS}/moderacao/cadastro/gravadoras/{r['slug']}"}


def propor(slug, arquivo, ensaio=False):
    e = json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())
    atual = rest("GET", "gravadoras?select=*&slug=eq." + slug).json()
    if not atual or atual[0]["status"] != "publicado":
        raise Erro("Gravadora não encontrada ou não publicada.")
    a = atual[0]
    novos = {k: v for k, v in e.items() if k in PROPOR}
    d, avisos = validar({"nome": a["nome"], "fontes": e.get("fontes") or []} | novos)
    mud = {k: {"antes": a.get(k), "depois": d[k]} for k in novos if a.get(k) != d[k]}
    if not mud:
        raise Erro("Nada muda.")
    res = {"gravadora": {"slug": slug, "nome": a["nome"], "site": _url(a)}, "mudancas": mud,
           "faltando": faltando(a | {k: d[k] for k in mud}, COMPLETO), "avisos": avisos}
    if ensaio:
        return res | {"ensaio": True}
    eu()
    r = rest("POST", "alteracoes?select=id", headers={"Prefer": "return=representation"},
             json={"tabela": "gravadoras", "chave": slug, "user_id": uid(), "dados": {k: d[k] for k in mud},
                   "mensagem": str(e.get("notas_agente") or "")[:2000], "origem": "agente", "fontes": d["fontes"]}).json()[0]
    return res | {"ok": True, "id": r["id"], "moderacao": f"{CMS}/moderacao/alteracao/{r['id']}"}


def main(args):
    if not args or args[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return
    cmd, resto = args[0], args[1:]

    def valor(nome, padrao=""):
        return next((resto[i + 1] for i, a in enumerate(resto) if a == nome and i + 1 < len(resto)), padrao)
    usados = {valor(x) for x in ("--site", "--pais", "--desde", "--estilo", "--paginas")} - {""}
    pos = [a for a in resto if not a.startswith("--") and a not in usados]
    ens = "--ensaio" in resto
    if cmd == "buscar" and pos:
        saida(buscar(" ".join(pos), valor("--site")))
    elif cmd == "candidatos":
        saida(candidatos(valor("--pais"), int(valor("--desde", "0") or 0), valor("--estilo", "Psy-Trance"), int(valor("--paginas", "3"))))
    elif cmd == "selo" and pos:
        saida(selo(" ".join(pos)))
    elif cmd == "gravar" and pos:
        saida(gravar(pos[0], ens))
    elif cmd == "propor" and len(pos) > 1:
        saida(propor(pos[0], pos[1], ens))
    else:
        raise Erro("Uso: gravadora.py buscar|candidatos|selo|gravar|propor (veja --help)")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Erro as e:
        print(json.dumps({"erro": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(json.dumps({"erro": f"Rede: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
