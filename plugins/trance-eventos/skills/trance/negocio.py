#!/usr/bin/env python3
"""Agente /trance, parte de lojas e serviços (tabela negocios). Plano: cms/PLANO-AGENTE-TRANCE.md, seção 6b.

  negocio.py buscar "<nome>" [--instagram @x] [--site url]   # existentes / prováveis
  negocio.py gravar <negocio.json|-> [--ensaio]              # loja ou serviço novo pendente (/loja/<slug>, /servico/<slug>)
  negocio.py propor <loja|servico>/<slug> <parcial.json|-> [--ensaio]
  negocio.py tags                                            # tags aceitas (as mesmas do CMS)

Saída em JSON.
"""
import difflib
import json
import pathlib
import re
import sys

import requests

from evento import CMS, REF, UFS, Erro, eu, norm, paragrafos, rest, saida, slugify, tudo, uid
from artista import _arroba

# mesmas opções do CMS (cms/src/lib/secoes.ts: TAGS_LOJA, TAGS_SERVICO): tag fora da lista trava a aprovação
TAGS = {"loja": ["Acessórios", "Artesanato", "Cartucheiras", "Comidas / Bebidas", "Cuidados Pessoais", "Decoração", "Ingressos", "Jóias e Bijus",
                 "Livros", "Malabares", "Tabacaria", "Tattoo / Piercing", "Vestuário", "Óleos e Essencias"],
        "servico": ["Agências / Booking", "Alimentação / Bar", "Excursões", "Infraestrutura", "Oficinas / Rodas", "Promoter / Comissário de Vendas",
                    "Saúde / Segurança", "Sonorização / Imagem", "Sustentabilidade", "Tendas de Cura / Redução de Danos", "Terapias Holísticas"]}
URLS = ["site", "instagram", "facebook", "youtube", "video"]
PERMITIDOS = {"tipo", "nome", "slug", "tags", "cidade", "uf", "pais", "resumo", "release", "logo", "capa", *URLS, "fontes", "notas_agente"}
PROPOR = ["nome", "tags", "cidade", "uf", "pais", "resumo", "release", "logo", "capa", *URLS]


def _dom(u):
    return re.sub(r"^https?://(www\.)?|/.*$", "", str(u or "").lower())


def _url(n):
    return f"https://www.trance.com.br/{n['tipo']}/{n['slug']}"


def buscar(nome, instagram="", site=""):
    k, ig, dom = norm(nome), _arroba(instagram), _dom(site)
    ex, prov = [], []
    for n in tudo("negocios?select=tipo,slug,nome,status,instagram,site,cidade&order=slug"):
        item = {"chave": f"{n['tipo']}/{n['slug']}", "nome": n["nome"], "cidade": n["cidade"], "status": n["status"], "site": _url(n)}
        if (k and norm(n["nome"]) == k) or (ig and _arroba(n.get("instagram")) == ig) or (dom and _dom(n.get("site")) == dom):
            ex.append(item)
        elif k and difflib.SequenceMatcher(None, k, norm(n["nome"])).ratio() >= 0.85:
            prov.append(item)
    return {"existentes": ex, "provaveis": prov[:10]}


def validar(e):
    extras = set(e) - PERMITIDOS
    if extras:
        raise Erro("Campos não aceitos: " + ", ".join(sorted(extras)))
    d, avisos = {}, []
    d["tipo"] = str(e.get("tipo") or "").strip()
    if d["tipo"] not in TAGS:
        raise Erro("tipo: loja ou servico.")
    d["nome"] = re.sub(r"\s+", " ", str(e.get("nome") or "")).strip()[:120]
    if not d["nome"]:
        raise Erro("nome é obrigatório.")
    tags = [str(t).strip() for t in (e.get("tags") or []) if str(t).strip()]
    ruins = [t for t in tags if t not in TAGS[d["tipo"]]]
    if ruins:
        raise Erro(f"tags fora da lista de {d['tipo']}: {', '.join(ruins)} (veja `negocio.py tags`).")
    if not tags:
        avisos.append("Sem tag (a página de listagem por tipo não mostra).")
    d["tags"] = tags
    pais = str(e.get("pais") or "BR").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", pais):
        raise Erro("pais: código de 2 letras.")
    uf = str(e.get("uf") or "").strip().upper()
    if uf and (pais != "BR" or uf not in UFS):
        raise Erro("uf inválida (só Brasil).")
    d["pais"], d["uf"], d["cidade"] = pais, uf, re.sub(r"\s+", " ", str(e.get("cidade") or "")).strip()[:120]
    if not d["cidade"]:
        avisos.append("Sem cidade.")
    d["resumo"] = re.sub(r"\s+", " ", str(e.get("resumo") or "")).strip()
    if len(d["resumo"]) > 160:
        raise Erro(f"resumo com {len(d['resumo'])} caracteres (máx. 160).")
    d["release"] = paragrafos(e.get("release"))
    for k in ("logo", "capa"):
        v = str(e.get(k) or "").strip()
        if v and not (REF.match(v) or re.match(r"^https://irp\.cdn-website\.com/\S+$", v)):
            raise Erro(f"{k}: use a ref conta:… devolvida por 'evento.py imagem'.")
        d[k] = v
    for k in URLS:
        v = str(e.get(k) or "").strip()
        if v and not re.match(r"^https?://[^\s]{3,}$", v):
            raise Erro(f"{k}: endereço inválido.")
        d[k] = v[:1000]
    fontes = e.get("fontes") or []
    if not isinstance(fontes, list) or not fontes:
        raise Erro("fontes é obrigatório: lista de {url, usado}.")
    d["fontes"] = [{"url": str(f.get("url") if isinstance(f, dict) else f)[:1000], "usado": str(f.get("usado", "") if isinstance(f, dict) else "")[:300]} for f in fontes]
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
    ja = buscar(d["nome"], d["instagram"], d["site"])
    if ja["existentes"]:
        raise Erro("Já existe: " + "; ".join(f"{n['nome']} {n['site']}" for n in ja["existentes"]))
    usados = {r["slug"] for r in rest("GET", f"negocios?select=slug&tipo=eq.{d['tipo']}&slug=like.{d['slug']}*").json()}
    base, n = d["slug"], 2
    while d["slug"] in usados:
        d["slug"], n = f"{base}-{n}", n + 1
    url = _url(d)
    if ensaio:
        return {"ensaio": True, "url": url, "avisos": avisos, "registro": d}
    r = rest("POST", "negocios?select=tipo,slug,status", json=d, headers={"Prefer": "return=representation"}).json()[0]
    return {"ok": True, "chave": f"{r['tipo']}/{r['slug']}", "url": url, "avisos": avisos,
            "moderacao": f"{CMS}/moderacao/cadastro/negocios/{r['tipo']}/{r['slug']}"}


def propor(chave, arquivo, ensaio=False):
    e = json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())
    tipo, _, slug = chave.partition("/")
    atual = rest("GET", f"negocios?select=*&tipo=eq.{tipo}&slug=eq.{slug}").json()
    if not atual or atual[0]["status"] != "publicado":
        raise Erro("Loja/serviço não encontrado ou não publicado.")
    a = atual[0]
    novos = {k: v for k, v in e.items() if k in PROPOR}
    d, avisos = validar({"tipo": tipo, "nome": a["nome"], "pais": a.get("pais") or "BR", "fontes": e.get("fontes") or []} | novos)
    mud = {k: {"antes": a.get(k), "depois": d[k]} for k in novos if a.get(k) != d[k]}
    if not mud:
        raise Erro("Nada muda.")
    res = {"negocio": {"chave": chave, "nome": a["nome"], "site": _url(a)}, "mudancas": mud, "avisos": avisos}
    if ensaio:
        return res | {"ensaio": True}
    eu()
    r = rest("POST", "alteracoes?select=id", headers={"Prefer": "return=representation"},
             json={"tabela": "negocios", "chave": chave, "user_id": uid(), "dados": {k: d[k] for k in mud},
                   "mensagem": str(e.get("notas_agente") or "")[:2000], "origem": "agente", "fontes": d["fontes"]}).json()[0]
    return res | {"ok": True, "id": r["id"], "moderacao": f"{CMS}/moderacao/alteracao/{r['id']}"}


def main(args):
    if not args or args[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return
    cmd, resto = args[0], args[1:]

    def valor(nome):
        return next((resto[i + 1] for i, a in enumerate(resto) if a == nome and i + 1 < len(resto)), "")
    usados = {valor("--instagram"), valor("--site")} - {""}
    pos = [a for a in resto if not a.startswith("--") and a not in usados]
    if cmd == "tags":
        saida(TAGS)
    elif cmd == "buscar" and pos:
        saida(buscar(" ".join(pos), valor("--instagram"), valor("--site")))
    elif cmd == "gravar" and pos:
        saida(gravar(pos[0], "--ensaio" in resto))
    elif cmd == "propor" and len(pos) > 1:
        saida(propor(pos[0], pos[1], "--ensaio" in resto))
    else:
        raise Erro("Uso: negocio.py buscar|gravar|propor|tags (veja --help)")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Erro as e:
        print(json.dumps({"erro": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(json.dumps({"erro": f"Rede: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
