#!/usr/bin/env python3
"""Ferramentas do agente /trance, parte de artistas (perfis da cena). Plano: cms/PLANO-AGENTE-TRANCE.md (repo trance.local).

Mesma sessão e regras do evento.py (sessão da pessoa da equipe, nunca chave secreta): perfis entram como pendente/agente
e só vão ao ar aprovados na Moderação do CMS.

  artista.py buscar "<nome>" [--instagram @x|url] [--soundcloud url]   # existentes / prováveis na base
  artista.py gravar <perfil.json|-> [--ensaio]                           # perfil novo pendente (+ até 3 sets do SoundCloud)
  artista.py vincular <evento_id> <slug> [<slug> ...] [--ensaio]         # vínculo: proposta na Moderação (publicado) ou completa a própria sugestão pendente
  artista.py propor <slug> <parcial.json|-> [--ensaio]                   # proposta de alteração de perfil publicado (Moderação)
  artista.py eventos "<nome>" [--slug x] [--sem-goabase]                 # eventos do artista: base (vinculados/no line-up) + Goabase
  artista.py candidatos [--pais BR] [--goabase 20]                        # artistas sem perfil nos line-ups dos próximos eventos
  artista.py soundcloud <url>                                            # título e capa de um set/faixa (oEmbed)
  artista.py sets <slug> <url> [<url> ...] [--release] [--ensaio]        # sets/releases para perfil que já existe (pendentes)

Saída sempre em JSON (stdout); erros em stderr com código 1.
"""
import difflib
import json
import pathlib
import re
import sys

import requests

import datetime as dt
import html

from evento import (CMS, faltando, GOABASE, REF, UA, UFS, Erro, _hora_local, duplicata, eu, goabase_evento, mudar_artistas, norm, paragrafos, rest, saida, slugify,
                    tudo, uid)

# categoria do banco -> caminho do perfil no site (mesmo mapa de _rota_perfil no nativo.sql)
ROTAS = {"djs": "dj", "vjs": "vj", "foto-video": "foto-e-video", "cenografia": "cenografia", "performances": "performance",
         "artes-visionarias": "arte-visionaria", "oficinas": "oficina"}
URLS = ["site", "instagram", "facebook", "soundcloud", "spotify", "bandcamp", "youtube", "video"]
PERMITIDOS = {"nome", "slug", "categoria", "produtor", "pais", "uf", "gravadoras", "crew", "estilos", "resumo", "release", "foto", "capa",
              "galeria", *URLS, "fontes", "notas_agente", "sets"}
MAX_SETS = 3
MAX_GALERIA = 12
# tudo o que o site mostra do perfil: o ensaio lista o que ficou vazio ("faltando")
COMPLETO = ["estilos", "resumo", "release", "foto", "capa", "galeria", "instagram", "soundcloud", "spotify", "bandcamp", "facebook", "site", "youtube", "video"]


def url_perfil(p):
    return f"https://www.trance.com.br/{ROTAS.get(p.get('categoria'), 'artista')}/{p['slug']}"


def _arroba(v):
    """@usuario de um link ou texto do Instagram (minúsculo, sem @)."""
    v = str(v or "").strip().lower()
    m = re.search(r"instagram\.com/([a-z0-9_.]+)", v)
    return (m.group(1) if m else v.lstrip("@")).strip("/ ") if v else ""


def _sc(v):
    """Caminho do SoundCloud (usuario[/faixa]) sem barra final, minúsculo."""
    m = re.search(r"soundcloud\.com/([^?#\s]+)", str(v or "").lower())
    return m.group(1).strip("/") if m else ""


def _resumo(p, motivo=None):
    r = {"slug": p["slug"], "nome": p["nome"], "categoria": p["categoria"], "status": p["status"], "origem": p.get("origem"),
         "produtor": bool(p.get("produtor")), "pais": p.get("pais"), "uf": p.get("uf"), "gravadoras": p.get("gravadoras") or [], "crew": p.get("crew"),
         "instagram": p.get("instagram"), "soundcloud": p.get("soundcloud"), "tem_foto": bool(p.get("foto")),
         "estilos": p.get("estilos") or [], "site": url_perfil(p), "cms": f"{CMS}/artistas/{p['slug']}"}
    if motivo:
        r["motivo"] = motivo
    return r


def base_perfis():
    return tudo("perfis?select=slug,nome,categoria,status,origem,produtor,pais,uf,gravadoras,crew,estilos,foto,instagram,soundcloud&order=slug")


def buscar(nome, instagram="", soundcloud="", perfis=None):
    """Perfil com o mesmo nome (sem acento), o mesmo @ do Instagram ou o mesmo SoundCloud = existente; nome parecido = provável."""
    perfis = perfis if perfis is not None else base_perfis()
    k, ig, sc = norm(nome), _arroba(instagram), _sc(soundcloud).split("/")[0]
    existentes, provaveis = {}, {}
    for p in perfis:
        motivo = None
        if k and norm(p["nome"]) == k:
            motivo = "mesmo nome"
        elif ig and _arroba(p.get("instagram")) == ig:
            motivo = "mesmo Instagram"
        elif sc and _sc(p.get("soundcloud")).split("/")[0] == sc:
            motivo = "mesmo SoundCloud"
        if motivo:
            existentes[p["slug"]] = _resumo(p, motivo)
            continue
        n = norm(p["nome"])
        curto, longo = sorted((k, n), key=len)
        if k and n and (difflib.SequenceMatcher(None, k, n).ratio() >= 0.85
                        or (len(curto) >= 4 and curto != longo and re.search(r"\b" + re.escape(curto) + r"\b", longo))):
            provaveis[p["slug"]] = _resumo(p, "nome parecido")
    return {"existentes": list(existentes.values()), "provaveis": list(provaveis.values())[:10]}


def soundcloud(link):
    """Título e capa (maior versão) de um set/faixa pelo oEmbed público do SoundCloud."""
    if not re.match(r"^https?://(www\.|m\.)?soundcloud\.com/[^/\s]+/[^\s]+$", str(link or "")):
        raise Erro(f"Link de set/faixa do SoundCloud inválido: {str(link)[:80]}")
    r = requests.get("https://soundcloud.com/oembed", params={"format": "json", "url": link}, timeout=30)
    if r.status_code != 200:
        raise Erro(f"SoundCloud não achou {link[:80]} ({r.status_code}).")
    j = r.json()
    capa = re.sub(r"-(large|t\d+x\d+|crop)\.", "-t500x500.", j.get("thumbnail_url") or "")
    titulo = re.sub(r"\s+by\s+[^\n]+$", "", j.get("title") or "").strip()
    return {"titulo": titulo, "autor": j.get("author_name"), "capa": capa, "soundcloud": link.split("?")[0]}


def estilos_validos():
    return {e["slug"] for e in tudo("estilos?select=slug")}


def validar(e):
    extras = set(e) - PERMITIDOS
    if extras:
        raise Erro("Campos não aceitos: " + ", ".join(sorted(extras)))
    d, avisos = {}, []
    d["nome"] = re.sub(r"\s+", " ", str(e.get("nome") or "")).strip()[:120]
    if not d["nome"]:
        raise Erro("nome é obrigatório.")
    d["categoria"] = str(e.get("categoria") or "djs").strip()
    if d["categoria"] not in ROTAS:
        raise Erro("categoria deve ser uma de: " + ", ".join(ROTAS))
    d["produtor"] = 1 if e.get("produtor") and d["categoria"] == "djs" else 0
    pais = str(e.get("pais") or "BR").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", pais):
        raise Erro("pais: use o código de 2 letras (BR, PT, IL...).")
    d["pais"] = pais
    uf = str(e.get("uf") or "").strip().upper()
    if uf and (pais != "BR" or uf not in UFS):
        raise Erro("uf inválida (só para o Brasil).")
    d["uf"], d["estado"] = uf, UFS.get(uf, "")
    if pais == "BR" and not uf:
        avisos.append("Artista do Brasil sem UF.")
    d["crew"] = re.sub(r"\s+", " ", str(e.get("crew") or "")).strip()[:200]
    # gravadoras do portal (slugs): link no perfil e o artista na página da gravadora; selo que não existe vai no crew
    grav = list(dict.fromkeys(str(x).strip() for x in (e.get("gravadoras") or []) if str(x).strip()))
    if grav:
        achadas = {g["slug"]: g for g in rest("GET", "gravadoras?select=slug,nome,status&slug=in.(" + ",".join(f'"{x}"' for x in grav) + ")").json()}
        faltam = [x for x in grav if x not in achadas]
        if faltam:
            raise Erro("gravadoras que não existem na base (cadastre com gravadora.py gravar antes, ou escreva no crew): " + ", ".join(faltam))
        # gravadora ainda pendente (ex.: cadastrada agora pelo agente): o site só liga a publicada, então o nome vai também no
        # crew e aparece como texto até a aprovação (depois vira link e o crew repetido some, _pf_crew)
        for g in achadas.values():
            if g["status"] != "publicado":
                if norm(g["nome"]) not in norm(d["crew"]):
                    d["crew"] = ", ".join(x for x in (d["crew"], g["nome"]) if x)[:200]
                avisos.append(f"Gravadora {g['nome']} ainda {g['status']}: no site sai como texto até ser aprovada na Moderação.")
    d["gravadoras"] = grav
    est = [str(x).strip() for x in (e.get("estilos") or []) if str(x).strip()]
    if est:
        validos = estilos_validos()
        ruins = [x for x in est if x not in validos]
        if ruins:
            raise Erro("estilos que não existem na Wikidelic (use o slug): " + ", ".join(ruins))
    d["estilos"] = list(dict.fromkeys(est))
    d["resumo"] = re.sub(r"\s+", " ", str(e.get("resumo") or "")).strip()
    if len(d["resumo"]) > 160:
        raise Erro(f"resumo com {len(d['resumo'])} caracteres (máx. 160).")
    d["release"] = paragrafos(e.get("release"))
    for k in ("foto", "capa"):
        v = str(e.get(k) or "").strip()
        if v and not (REF.match(v) or re.match(r"^https://irp\.cdn-website\.com/\S+$", v)):
            raise Erro(f"{k}: use a ref conta:… devolvida por 'evento.py imagem'.")
        d[k] = v
    if not d["foto"]:
        avisos.append("Sem foto.")
    gal = e.get("galeria") or []
    if not isinstance(gal, list) or len(gal) > MAX_GALERIA:
        raise Erro(f"galeria: lista com até {MAX_GALERIA} refs conta:… (fotos do artista tocando, em festa, divulgação).")
    gal = list(dict.fromkeys(str(x).strip() for x in gal if str(x).strip()))
    for v in gal:
        if not (REF.match(v) or re.match(r"^https://irp\.cdn-website\.com/\S+$", v)):
            raise Erro("galeria: use refs conta:… devolvidas por 'evento.py imagem'.")
    d["galeria"] = gal
    for k in URLS:
        v = str(e.get(k) or "").strip()
        if v and not re.match(r"^https?://[^\s]{3,}$", v):
            raise Erro(f"{k}: endereço inválido ({v[:60]}).")
        d[k] = v[:1000]
    fontes = e.get("fontes") or []
    if not isinstance(fontes, list) or not fontes:
        raise Erro("fontes é obrigatório: lista de {url, usado}.")
    d["fontes"] = []
    for f in fontes:
        u = str((f or {}).get("url", "")).strip() if isinstance(f, dict) else str(f).strip()
        if not re.match(r"^https?://\S+$", u):
            raise Erro(f"fonte inválida: {u[:80]}")
        d["fontes"].append({"url": u[:1000], "usado": str((f or {}).get("usado", "") if isinstance(f, dict) else "")[:300]})
    d["notas_agente"] = str(e.get("notas_agente") or "").strip()[:3000]
    d["slug"] = slugify(e.get("slug") or d["nome"])
    if not d["slug"]:
        raise Erro("Não consegui gerar o endereço (slug).")
    sets = e.get("sets") or []
    if not isinstance(sets, list) or len(sets) > MAX_SETS:
        raise Erro(f"sets: lista com até {MAX_SETS} links do SoundCloud.")
    d["_sets"] = [s if isinstance(s, dict) else {"soundcloud": s} for s in sets]
    d.update(status="pendente", origem="agente")
    return d, avisos


def slug_livre(base):
    usados = {r["slug"] for r in rest("GET", f"perfis?select=slug&slug=like.{base}*").json()}
    if base not in usados:
        return base
    n = 2
    while f"{base}-{n}" in usados:
        n += 1
    return f"{base}-{n}"


def gravar(arquivo, ensaio=False, forcar=False):
    e = json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())
    d, avisos = validar(e)
    eu()  # falha cedo se a sessão não for da equipe
    ja = buscar(d["nome"], d["instagram"], d["soundcloud"])
    if ja["existentes"] and not forcar:
        raise Erro("Já existe perfil para este artista (proponha alteração em vez de criar): "
                   + "; ".join(f"{p['nome']} ({p['motivo']}) {p['site']}" for p in ja["existentes"]))
    if ja["provaveis"]:
        avisos.append("Nomes parecidos na base: " + ", ".join(f"{p['nome']} ({p['slug']})" for p in ja["provaveis"][:5]))
    d["slug"] = slug_livre(d["slug"])
    sets = []
    for s in d.pop("_sets"):
        info = soundcloud(s.get("soundcloud"))
        tipo = s.get("tipo") or "set"
        if tipo not in ("set", "release"):
            raise Erro("tipo de set: set ou release.")
        sets.append({"perfil": d["slug"], "titulo": (s.get("titulo") or info["titulo"] or "Set")[:200], "tipo": tipo,
                     "soundcloud": info["soundcloud"], "capa": info["capa"], "status": "pendente", "origem": "agente"})
    url = url_perfil(d)
    falta = faltando(d, COMPLETO + (["uf"] if d["pais"] == "BR" else []) + ([] if d["gravadoras"] or d["crew"] else ["gravadoras"]))
    if not sets:
        falta.append("sets")
    if ensaio:
        return {"ensaio": True, "url": url, "faltando": falta, "avisos": avisos, "registro": d, "sets": sets}
    r = rest("POST", "perfis?select=slug,status,origem", json=d, headers={"Prefer": "return=representation"}).json()[0]
    gravados = []
    for s in sets:
        gravados.append(rest("POST", "sets?select=id,titulo", json=s, headers={"Prefer": "return=representation"}).json()[0])
    return {"ok": True, "slug": r["slug"], "url": url, "status": r["status"], "origem": r["origem"], "sets": gravados, "faltando": falta, "avisos": avisos,
            "moderacao": f"{CMS}/moderacao/cadastro/perfis/{r['slug']}", "editar": f"{CMS}/artistas/{r['slug']}"}


def vincular(evento_id, slugs, ensaio=False):
    """Soma perfis (publicados ou pendentes) em eventos.artistas. Vínculo vale em lote: aprovado no relatório do agente."""
    if not str(evento_id).isdigit():
        raise Erro("Uso: vincular <evento_id> <slug> [<slug> ...]")
    slugs = list(dict.fromkeys(s.strip() for s in slugs if s.strip()))
    if not slugs:
        raise Erro("Informe ao menos um slug de perfil.")
    ev = rest("GET", f"eventos?select=id,rota,slug,nome,status,origem,artistas&id=eq.{evento_id}").json()
    if not ev:
        raise Erro(f"Evento {evento_id} não encontrado.")
    ev = ev[0]
    achados = {p["slug"]: p for p in rest("GET", "perfis?select=slug,nome,categoria,status&slug=in.(" + ",".join(f'"{s}"' for s in slugs) + ")").json()}
    faltam = [s for s in slugs if s not in achados]
    if faltam:
        raise Erro("Perfis não encontrados: " + ", ".join(faltam))
    antes = ev["artistas"] or []
    novos = [s for s in slugs if s not in antes]
    depois = antes + novos
    res = {"evento": {"id": ev["id"], "nome": ev["nome"], "status": ev["status"], "site": f"https://www.trance.com.br/{ev['rota']}/{ev['slug']}"},
           "novos": [{"slug": s, "nome": achados[s]["nome"], "status": achados[s]["status"]} for s in novos],
           "ja_vinculados": [s for s in slugs if s in antes]}
    if ensaio or not novos:
        return res | {"ensaio": ensaio, "alterado": False}
    eu()
    feito = mudar_artistas(ev, depois, "Vínculo de artistas do line-up: " + ", ".join(novos))  # só acrescenta: direto, sem Moderação
    pendentes = [n["nome"] for n in res["novos"] if n["status"] != "publicado"]
    return res | feito | {"ok": True, "alterado": True,
                  "aviso": ("Aparecem no site quando os perfis forem aprovados: " + ", ".join(pendentes)) if pendentes else ""}


# ---------------------------------------------------------------- proposta de alteração (perfil publicado)
# o que o CMS aplica de uma proposta do agente (CAMPOS_PUBLICO de perfis + uf, pais e produtor; ver cms/src/lib/secoes.ts)
PROPOR = ["nome", "categoria", "produtor", "pais", "uf", "gravadoras", "crew", "estilos", "resumo", "release", "foto", "capa", "galeria",
          "site", "instagram", "facebook", "soundcloud", "spotify", "bandcamp", "youtube", "video"]


def propor(slug, arquivo, ensaio=False):
    e = json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())
    atual = rest("GET", "perfis?select=*&slug=eq." + slug).json()
    if not atual:
        raise Erro(f"Perfil {slug} não encontrado.")
    a = atual[0]
    if a["status"] != "publicado":
        raise Erro("Perfil ainda não publicado: edite a sugestão pendente no CMS em vez de propor.")
    novos = {k: v for k, v in e.items() if k in PROPOR}
    if not novos:
        raise Erro("Nada para propor: use só os campos " + ", ".join(PROPOR))
    # valida só o que foi proposto (o resto do cadastro atual pode estar fora das regras novas, ex.: resumo antigo longo)
    base = {"nome": a["nome"], "categoria": a["categoria"], "pais": a.get("pais") or "BR", "uf": a.get("uf") or "",
            "produtor": bool(a.get("produtor")), "crew": a.get("crew") or "", "fontes": e.get("fontes") or []}
    d, avisos = validar(base | novos)
    avisos = [x for x in avisos if not (x in ("Sem foto.", "Artista do Brasil sem UF.") and x.split()[1].lower().rstrip(".") not in novos)]
    dados = {k: d[k] for k in novos}
    if "gravadoras" in novos and d["crew"] != (a.get("crew") or ""):  # gravadora pendente: nome no crew até a aprovação
        dados["crew"] = d["crew"]
    if "uf" in novos:
        dados["estado"] = d["estado"]
    mudancas = {k: {"antes": a.get(k), "depois": dados[k]} for k in dados if a.get(k) != dados[k]}
    if not mudancas:
        raise Erro("Os valores propostos são iguais aos atuais.")
    res = {"perfil": {"slug": slug, "nome": a["nome"], "site": url_perfil(a)}, "mudancas": mudancas,
           "faltando": faltando(a | dados, COMPLETO), "avisos": avisos}
    if ensaio:
        return res | {"ensaio": True}
    eu()
    pend = rest("GET", f"alteracoes?select=id,origem&tabela=eq.perfis&chave=eq.{slug}&status=eq.pendente").json()
    if pend:
        raise Erro(f"Já há uma proposta em análise para este perfil (#{pend[0]['id']}, {pend[0]['origem']}): aguarde a Moderação.")
    r = rest("POST", "alteracoes?select=id", headers={"Prefer": "return=representation"},
             json={"tabela": "perfis", "chave": slug, "user_id": uid(), "tipo": "edicao", "dados": {k: dados[k] for k in mudancas},
                   "mensagem": str(e.get("notas_agente") or "")[:2000], "origem": "agente", "fontes": d["fontes"]}).json()[0]
    return res | {"ok": True, "id": r["id"], "moderacao": f"{CMS}/moderacao/alteracao/{r['id']}"}


def sets(slug, links, tipo="set", ensaio=False):
    """Sets/releases do SoundCloud para um perfil que já existe: entram pendentes (origem agente) e vão ao ar aprovados na Moderação."""
    if not links or len(links) > MAX_SETS:
        raise Erro(f"Mande de 1 a {MAX_SETS} links do SoundCloud.")
    p = rest("GET", "perfis?select=slug,nome,categoria,status&slug=eq." + slug).json()
    if not p or p[0]["status"] not in ("publicado", "pendente"):
        raise Erro(f"Perfil {slug} não encontrado (ou recusado/despublicado).")
    ja = {x["soundcloud"] for x in rest("GET", "sets?select=soundcloud&perfil=eq." + slug).json()}
    novos, repetidos = [], []
    for link in links:
        info = soundcloud(link)
        if info["soundcloud"] in ja:
            repetidos.append(info["soundcloud"])
            continue
        novos.append({"perfil": slug, "titulo": (info["titulo"] or "Set")[:200], "tipo": tipo, "soundcloud": info["soundcloud"],
                      "capa": info["capa"], "status": "pendente", "origem": "agente"})
    res = {"perfil": {"slug": slug, "nome": p[0]["nome"], "site": url_perfil(p[0])}, "sets": novos, "ja_cadastrados": repetidos}
    if ensaio or not novos:
        return res | {"ensaio": ensaio}
    eu()
    gravados = [rest("POST", "sets?select=id,titulo", json=x, headers={"Prefer": "return=representation"}).json()[0] for x in novos]
    return res | {"ok": True, "gravados": gravados, "moderacao": f"{CMS}/moderacao?origem=agente&tabela=sets&q={slug}"}


# ---------------------------------------------------------------- eventos do artista
def _texto(h):
    return norm(html.unescape(re.sub(r"<[^>]+>", " ", h or "")))


def eventos(nome, slug="", goabase=True):
    """Eventos da base em que o artista está (vinculado em eventos.artistas ou citado no line-up) e próximas festas do Goabase
    com o nome no line-up (marcando as que já estão na base)."""
    k = norm(nome)
    if not k:
        raise Erro("Informe o nome do artista.")
    hoje = dt.date.today().isoformat()
    base = tudo("eventos?select=id,rota,slug,nome,inicio,fim,cidade,uf,status,artistas,programacao&status=in.(publicado,pendente)&order=inicio.desc")
    na_base = []
    for e in base:
        ligado = bool(slug) and slug in (e.get("artistas") or [])
        citado = re.search(r"\b" + re.escape(k) + r"\b", _texto(e.get("programacao"))) is not None
        if ligado or citado:
            na_base.append({"id": e["id"], "nome": e["nome"], "inicio": e["inicio"], "cidade": e["cidade"], "uf": e["uf"], "status": e["status"],
                            "futuro": (e["fim"] or e["inicio"])[:10] >= hoje, "vinculado": ligado, "no_lineup": citado,
                            "site": f"https://www.trance.com.br/{e['rota']}/{e['slug']}", "cms": f"{CMS}/eventos/{e['id']}"})
    fora = []
    if goabase:
        r = requests.get(GOABASE, params={"search": nome}, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        for p in r.json().get("partylist", [])[:25]:
            if _hora_local(p, "dateEnd")[:10] < hoje or p.get("nameStatus") in ("Canceled", "Cancelled"):
                continue
            det = goabase_evento(p["id"])
            if not re.search(r"\b" + re.escape(k) + r"\b", _texto(det.get("textLineUp"))):
                continue  # a busca do Goabase também acha o nome em outros campos
            dup = duplicata(p["nameParty"], _hora_local(p, "dateStart")[:10], p.get("nameTown") or "", base)["duplicata_provavel"]
            fora.append({"nome": p["nameParty"], "inicio": _hora_local(p, "dateStart"), "cidade": p.get("nameTown"), "pais": p.get("isoCountry"),
                         "tipo": p.get("nameType"), "goabase": p.get("urlPartyHtml"), "flyer": p.get("urlImageFull"),
                         "na_base": [{"id": d["id"], "nome": d["nome"], "site": d["site"]} for d in dup]})
    return {"artista": nome, "slug": slug or None,
            "na_base": {"futuros": [x for x in na_base if x["futuro"]], "passados": [x for x in na_base if not x["futuro"]][:20],
                        "sem_vinculo": [x["id"] for x in na_base if x["no_lineup"] and not x["vinculado"]] if slug else []},
            "goabase": {"novos": [x for x in fora if not x["na_base"]], "ja_na_base": [x for x in fora if x["na_base"]]}}


# ---------------------------------------------------------------- buscar artistas (sem perfil, nos line-ups futuros)
def candidatos(pais="BR", n_goabase=20):
    """Nomes dos line-ups de eventos futuros (base + Goabase do país) que não têm perfil, por número de eventos."""
    from revisar import _linhas_lineup
    perfis = base_perfis()
    tem = {norm(p["nome"]) for p in perfis}
    hoje = dt.date.today().isoformat()
    vistos = {}

    def soma(nome, onde):
        k = norm(nome)
        if len(k) < 3 or k in tem:
            return
        v = vistos.setdefault(k, {"nome": nome, "eventos": []})
        if onde not in v["eventos"]:
            v["eventos"].append(onde)
    for e in tudo("eventos?select=nome,inicio,fim,programacao,status&status=eq.publicado"):
        if (e["fim"] or e["inicio"])[:10] >= hoje:
            for n in _linhas_lineup(e["programacao"]):
                soma(n, e["nome"])
    if n_goabase:
        r = requests.get(GOABASE, params={"limit": 1000}, headers={"User-Agent": UA}, timeout=60)
        festas = [p for p in r.json().get("partylist", []) if (not pais or (p.get("isoCountry") or "").upper() == pais.upper())
                  and _hora_local(p, "dateStart")[:10] >= hoje][:n_goabase]
        for p in festas:
            linhas = re.split(r"[\n\r]+|,|\s/\s", goabase_evento(p["id"]).get("textLineUp") or "")
            for l in linhas:
                t = re.split(r"\s+[-–|•@]\s+|\s*\(", re.sub(r"<[^>]+>", "", l))[0].strip(" -–•*:")
                # nome artístico: até 4 palavras, sem pontuação de frase, emoji ou horário
                if (2 <= len(t) <= 40 and len(t.split()) <= 4 and not re.search(r"[.!?%:;❄\u2600-\u27bf\U0001F300-\U0001FAFF]|\d+\s*(min|h\b)", t)
                        and not re.search(r"(?i)\b(lineup|line up|stage|palco|tba|more|soon|day|dia|ride|ticket|ingresso)\b", t)):
                    soma(t, p["nameParty"])
    lista = sorted(vistos.values(), key=lambda x: (-len(x["eventos"]), x["nome"]))
    return {"pais": pais, "total": len(lista), "artistas": [x | {"n": len(x["eventos"])} for x in lista[:80]],
            "obs": "Nomes de line-up sem perfil (podem ser grafia diferente: confira com `buscar`). Pesquise até 15 por lote."}


def main(args):
    if not args or args[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return
    cmd, resto = args[0], args[1:]
    opc = {a for a in resto if a.startswith("--") and "=" not in a}

    def valor(nome):
        for i, a in enumerate(resto):
            if a == nome and i + 1 < len(resto):
                return resto[i + 1]
        return ""

    usados = {valor("--instagram"), valor("--soundcloud")} - {""}
    pos = [a for a in resto if not a.startswith("--") and a not in usados]
    if cmd == "buscar":
        if not pos:
            raise Erro('Uso: buscar "<nome>" [--instagram @x] [--soundcloud url]')
        saida(buscar(" ".join(pos), valor("--instagram"), valor("--soundcloud")))
    elif cmd == "gravar":
        if not pos:
            raise Erro("Uso: gravar <perfil.json|-> [--ensaio] [--forcar]")
        saida(gravar(pos[0], "--ensaio" in opc, "--forcar" in opc))
    elif cmd == "vincular":
        if len(pos) < 2:
            raise Erro("Uso: vincular <evento_id> <slug> [<slug> ...] [--ensaio]")
        saida(vincular(pos[0], pos[1:], "--ensaio" in opc))
    elif cmd == "propor":
        if len(pos) < 2:
            raise Erro("Uso: propor <slug> <parcial.json|-> [--ensaio]")
        saida(propor(pos[0], pos[1], "--ensaio" in opc))
    elif cmd == "eventos":
        sl = valor("--slug")
        pos = [p for p in pos if p != sl]
        if not pos:
            raise Erro('Uso: eventos "<nome>" [--slug x] [--sem-goabase]')
        saida(eventos(" ".join(pos), sl, "--sem-goabase" not in opc))
    elif cmd == "candidatos":
        saida(candidatos(valor("--pais") or "BR", int(valor("--goabase") or 20)))
    elif cmd == "sets":
        if len(pos) < 2:
            raise Erro("Uso: sets <slug> <url> [<url> ...] [--release] [--ensaio]")
        saida(sets(pos[0], pos[1:], "release" if "--release" in opc else "set", "--ensaio" in opc))
    elif cmd == "soundcloud":
        if not pos:
            raise Erro("Uso: soundcloud <url>")
        saida(soundcloud(pos[0]))
    else:
        raise Erro(f"Comando desconhecido: {cmd}")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Erro as e:
        print(json.dumps({"erro": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(json.dumps({"erro": f"Rede: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
