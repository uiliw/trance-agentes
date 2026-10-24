#!/usr/bin/env python3
"""Agente /trance, parte de crews (coletivos e produtoras que organizam festas/festivais e reúnem artistas).
Página no site: /crew/<slug>; a crew aparece também no perfil de cada artista (crews.artistas) e na página dos eventos
(eventos.crews). Mesma sessão e regras do evento.py (sessão da pessoa da equipe, nunca chave secreta).

  crew.py candidatos [--min 2] [--limite 60]          # crews citadas no texto livre "crew" dos perfis publicados, fora da base
                                                       # (sem gravadoras nem agências/bookings), com contagem e perfis
  crew.py buscar "<nome>" [--instagram @x|url] [--site url]   # existentes / prováveis + perfis e eventos que citam o nome
  crew.py gravar <crew.json|-> [--ensaio] [--publicar]         # crew nova (pendente; --publicar: no ar direto)
  crew.py propor <slug> <parcial.json|-> [--ensaio] [--publicar]   # crew publicada: proposta na Moderação ou edita direto
  crew.py vincular <slug> artistas <perfil> [<perfil> ...] [--ensaio]   # crews.artistas, direto (sem Moderação)
  crew.py vincular <slug> eventos <id> [<id> ...] [--ensaio]            # eventos.crews, direto (sem Moderação)
  crew.py remover <slug> artistas|eventos <...> [--ensaio]              # tira o vínculo, direto

Crews não têm destaque nem fila automática de imagem: com --publicar, logo/capa novos (conta:…) vão como proposta só das
imagens na Moderação (a aprovação sobe para a Duda); o resto vai ao ar na hora. Sem sessão (expirada), os comandos de leitura
e os ensaios leem só o que é público (publicados) e avisam em `sem_sessao`.

Saída em JSON; erros em stderr com código 1.
"""
import difflib
import json
import pathlib
import re
import sys
from collections import defaultdict

import requests

from evento import (CMS, REF, UFS, Erro, config, editar_direto, eu, faltando, norm, paragrafos, rest, saida,
                    slugify, tudo, uid)
from artista import _arroba, url_perfil

URLS = ["site", "instagram", "facebook", "soundcloud", "youtube"]
PERMITIDOS = {"nome", "slug", "pais", "uf", "cidade", "resumo", "release", "logo", "capa", "artistas", "estilos", *URLS,
              "seo_title", "seo_description", "fontes", "notas_agente", "eventos"}
# o que o CMS aplica de uma proposta do agente (cms/src/lib/secoes.ts CAMPOS_AGENTE.crews), menos artistas = vincular
PROPOR = ["nome", "pais", "uf", "cidade", "estilos", "resumo", "release", "logo", "capa", *URLS, "seo_title", "seo_description"]
IMAGENS = ["logo", "capa"]
# tudo o que a página da crew mostra: o ensaio lista o que ficou vazio ("faltando")
COMPLETO = ["cidade", "resumo", "release", "logo", "capa", "artistas", "estilos", "instagram", "site", "facebook", "soundcloud",
            "youtube", "seo_title", "seo_description"]
# texto do campo crew dos perfis que não é crew: gravadoras (têm tabela própria) e agências/bookings
NAO_CREW = re.compile(r"\b(records?|recordings|rec|music|musik|label|labels|bookings?|agency|agencia|agencies|management|mgmt|"
                      r"artist ?management|independente|independent|indie)\b")
# palavras genéricas tiradas só para juntar variações do mesmo nome ("HOMmega" e "HOMmega Productions")
GENERICO = re.compile(r"\b(crew|coletivo|collective|productions?|producoes|producao|prod|produtora|family|familia|tribe|team|sound ?system)\b")

SEM_SESSAO = []  # vira [True] quando a leitura caiu para a chave pública (só publicados)


def ler(caminho):
    """Lê com a sessão da equipe; sem sessão (expirada ou ausente), lê só o público com a chave anon e marca SEM_SESSAO."""
    try:
        return tudo(caminho)
    except Erro as e:
        if "sess" not in str(e).lower() or "Supabase" in str(e):
            raise
    SEM_SESSAO[:] = [True]
    url, anon = config()
    linhas, ini = [], 0
    while True:
        r = requests.get(f"{url}/rest/v1/{caminho}", headers={"apikey": anon, "Authorization": "Bearer " + anon, "Range": f"{ini}-{ini + 999}"},
                         timeout=60)
        if r.status_code >= 400:
            raise Erro(f"Supabase {r.status_code}: {r.text[:300]}")
        lote = r.json()
        linhas += lote
        if len(lote) < 1000:
            return linhas
        ini += 1000


def _aviso_sessao(res):
    if SEM_SESSAO:
        res["sem_sessao"] = "Sessão expirada ou ausente: li só o que é público (publicados). Para gravar, rode num terminal comum: evento.py login"
    return res


def _url(c):
    return f"https://www.trance.com.br/crew/{c['slug']}"


def _k(nome):
    """Chave para juntar variações: sem acento, sem palavras genéricas (crew, coletivo, productions...)."""
    n = norm(nome)
    return " ".join(GENERICO.sub(" ", n).split()) or n


def _kg(nome):
    """Chave de gravadora (mesma regra do site, _pf_crew): sem records/music/label."""
    return " ".join(re.sub(r"\b(records?|recordings|rec|music|label)\b", " ", norm(nome)).split())


def _dominio(u):
    return re.sub(r"^https?://(www\.)?|/.*$", "", str(u or "").lower())


def _em(lista):
    return "(" + ",".join(f'"{x}"' for x in lista) + ")"


def base():
    return ler("crews?select=slug,nome,status,origem,pais,uf,cidade,artistas,instagram,site,logo&order=slug")


def _partes(crew):
    """Texto livre do campo crew -> nomes (separados por vírgula, ponto e vírgula, barra, barra vertical, + ou quebra de linha)."""
    for p in re.split(r"\s*[,;/|+\n]\s*|\s+-\s+", str(crew or "")):
        p = re.sub(r"\s+", " ", p).strip(" .-–()[]\"'")
        if 2 <= len(p) <= 60 and "http" not in p.lower() and "@" not in p:
            yield p


# ---------------------------------------------------------------- candidatos e busca
def candidatos(minimo=2, limite=60):
    perfis = ler("perfis?select=slug,nome,categoria,crew,status&status=eq.publicado&crew=neq.&order=slug")
    gravs = ler("gravadoras?select=slug,nome&order=slug")
    chaves_g = {_kg(g["nome"]): g["slug"] for g in gravs if len(_kg(g["nome"])) >= 3}
    crews = base()
    na_base = {_k(c["nome"]): c for c in crews}
    grupos, gravadoras, agencias = defaultdict(lambda: {"variantes": defaultdict(int), "perfis": {}}), defaultdict(int), defaultdict(int)
    for p in perfis:
        for parte in _partes(p["crew"]):
            n = norm(parte)
            if not n:
                continue
            kg = _kg(parte)
            if kg in chaves_g or any(re.search(r"\b" + re.escape(k) + r"\b", n) for k in chaves_g if len(k) >= 5):
                gravadoras[parte] += 1
                continue
            if NAO_CREW.search(n):
                agencias[parte] += 1
                continue
            g = grupos[_k(parte)]
            g["variantes"][parte] += 1
            g["perfis"][p["slug"]] = {"slug": p["slug"], "nome": p["nome"], "site": url_perfil(p)}
    lista = []
    for k, g in grupos.items():
        n = len(g["perfis"])
        if n < minimo:
            continue
        variantes = sorted(g["variantes"], key=lambda v: (-g["variantes"][v], v))
        c = na_base.get(k)
        item = {"nome": variantes[0], "variantes": variantes, "perfis": n, "lista_perfis": list(g["perfis"].values())[:30]}
        if c:
            ligados = [s for s in g["perfis"] if s in (c.get("artistas") or [])]
            item["na_base"] = {"slug": c["slug"], "status": c["status"], "site": _url(c), "artistas_ja_vinculados": len(ligados),
                               "falta_vincular": [s for s in g["perfis"] if s not in ligados][:30]}
        # mesmo nome de gravadora da base ou de um selo citado ("Phantom Unit" e "Phantom Unit Records"): pode ser só o selo
        selos = sorted({x for x in list(gravadoras) + list(agencias) if _k(_kg(x)) == k} | {g["nome"] for g in gravs if _k(_kg(g["nome"])) == k})
        if selos:
            item["conferir"] = "Mesmo nome de selo/agência (" + ", ".join(selos[:3]) + "): confirme na web que é crew e não só o selo"
        elif re.search(r"\bproductions?\b", norm(" ".join(variantes))):
            item["conferir"] = "\"Productions\" no nome: pode ser gravadora (confira no Discogs com gravadora.py selo)"
        lista.append(item)
    lista.sort(key=lambda x: (-x["perfis"], norm(x["nome"])))
    top = lambda d: [{"nome": k, "perfis": v} for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:20]]
    return _aviso_sessao({
        "total": len(lista), "candidatos": lista[:limite],
        "descartados": {"gravadoras": top(gravadoras), "agencias_e_outros": top(agencias)},
        "obs": "Nome citado no campo crew de perfis publicados (texto livre). Confirme na web que é crew/coletivo/produtora de festas "
               "(não selo nem agência) antes de cadastrar; na_base = já existe (ofereça vincular os perfis que faltam)."})


def buscar(nome, instagram="", site=""):
    k, ig, dom = _k(nome), _arroba(instagram), _dominio(site)
    ex, prov = [], []
    for c in base():
        item = {"slug": c["slug"], "nome": c["nome"], "status": c["status"], "cidade": c["cidade"], "uf": c["uf"], "pais": c["pais"],
                "artistas": len(c.get("artistas") or []), "site": _url(c), "cms": f"{CMS}/crews/{c['slug']}"}
        if (k and _k(c["nome"]) == k) or (ig and _arroba(c.get("instagram")) == ig) or (dom and _dominio(c.get("site")) == dom):
            ex.append(item)
        elif k and difflib.SequenceMatcher(None, k, _k(c["nome"])).ratio() >= 0.82:
            prov.append(item)
    # quem cita o nome: perfis (campo crew) e eventos (nome); ajudam a montar os vínculos
    n = norm(nome)
    padrao = re.compile(r"\b" + re.escape(k if len(k) >= 4 else n) + r"\b") if (k or n) else None
    perfis = [{"slug": p["slug"], "nome": p["nome"], "status": p["status"], "crew": p["crew"], "site": url_perfil(p)}
              for p in ler("perfis?select=slug,nome,categoria,status,crew&crew=neq.&status=in.(publicado,pendente)&order=slug")
              if padrao and any(padrao.search(_k(x)) or padrao.search(norm(x)) for x in _partes(p["crew"]))]
    eventos = [{"id": e["id"], "nome": e["nome"], "inicio": e["inicio"], "status": e["status"], "crews": e.get("crews") or [],
                "site": f"https://www.trance.com.br/{e['rota']}/{e['slug']}"}
               for e in ler("eventos?select=id,rota,slug,nome,inicio,status,crews&status=in.(publicado,pendente)&order=inicio.desc")
               if padrao and padrao.search(norm(e["nome"]))]
    gv = [g for g in ler("gravadoras?select=slug,nome,status") if _kg(g["nome"]) and _k(_kg(g["nome"])) == _k(_kg(nome))]
    res = {"existentes": ex, "provaveis": prov[:10], "perfis_que_citam": perfis[:60], "eventos_com_o_nome": eventos[:40]}
    if gv:
        res["aviso"] = "Há gravadora com esse nome: " + ", ".join(f"{g['nome']} (/gravadora/{g['slug']})" for g in gv) + \
                       ". Selo não é crew: só cadastre se for também coletivo que faz festas."
    return _aviso_sessao(res)


# ---------------------------------------------------------------- validar e gravar
def _perfis_existentes(slugs):
    if not slugs:
        return {}
    return {p["slug"]: p for p in ler("perfis?select=slug,nome,categoria,status&slug=in." + _em(slugs))}


def _eventos_existentes(ids):
    if not ids:
        return {}
    return {e["id"]: e for e in ler("eventos?select=id,rota,slug,nome,inicio,status,crews&id=in.(" + ",".join(str(i) for i in ids) + ")")}


def validar(e):
    extras = set(e) - PERMITIDOS
    if extras:
        raise Erro("Campos não aceitos: " + ", ".join(sorted(extras)))
    d, avisos = {}, []
    d["nome"] = re.sub(r"\s+", " ", str(e.get("nome") or "")).strip()[:120]
    if not d["nome"]:
        raise Erro("nome é obrigatório.")
    pais = str(e.get("pais") or "BR").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", pais):
        raise Erro("pais: use o código de 2 letras (BR, PT, IL...).")
    d["pais"] = pais
    uf = str(e.get("uf") or "").strip().upper()
    if uf and (pais != "BR" or uf not in UFS):
        raise Erro("uf inválida (só para o Brasil).")
    d["uf"] = uf
    if pais == "BR" and not uf:
        avisos.append("Crew do Brasil sem UF.")
    d["cidade"] = re.sub(r"\s+", " ", str(e.get("cidade") or "")).strip()[:120]
    art = list(dict.fromkeys(str(x).strip() for x in (e.get("artistas") or []) if str(x).strip()))
    if art:
        achados = _perfis_existentes(art)
        faltam = [x for x in art if x not in achados]
        if faltam:
            raise Erro("artistas sem perfil na base (use o slug do perfil): " + ", ".join(faltam))
        pend = [achados[x]["nome"] for x in art if achados[x]["status"] != "publicado"]
        if pend:
            avisos.append("Artistas ainda não publicados (aparecem na crew quando aprovados): " + ", ".join(pend))
    d["artistas"] = art
    est = list(dict.fromkeys(str(x).strip() for x in (e.get("estilos") or []) if str(x).strip()))
    if est:
        validos = {x["slug"] for x in ler("estilos?select=slug")}
        ruins = [x for x in est if x not in validos]
        if ruins:
            raise Erro("estilos que não existem na Wikidelic (use o slug): " + ", ".join(ruins))
    d["estilos"] = est
    d["resumo"] = re.sub(r"\s+", " ", str(e.get("resumo") or "")).strip()
    if len(d["resumo"]) > 160:
        raise Erro(f"resumo com {len(d['resumo'])} caracteres (máx. 160).")
    d["release"] = paragrafos(e.get("release"))
    for k in IMAGENS:
        v = str(e.get(k) or "").strip()
        if v and not (REF.match(v) or re.match(r"^https://irp\.cdn-website\.com/\S+$", v)):
            raise Erro(f"{k}: use a ref conta:… devolvida por 'evento.py imagem'.")
        d[k] = v
    if not d["logo"]:
        avisos.append("Sem logo.")
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
    d.update(status="pendente", origem="agente")
    return d, avisos


def proposta_imagens(slug, imagens, fontes):
    """Logo/capa novos de crew publicada direto: a fila automática (revalidar.mjs) não atende crews, então vão como proposta só
    das imagens (a aprovação na Moderação sobe para a Duda). Proposta pendente de outra pessoa: avisa em vez de travar."""
    pend = rest("GET", f"alteracoes?select=id,origem&tabela=eq.crews&chave=eq.{slug}&status=eq.pendente&tipo=neq.imagem").json()
    if pend:
        return {"aviso_imagens": f"Imagens não enviadas: já há proposta em análise (#{pend[0]['id']}). Proponha depois que ela for decidida."}
    r = rest("POST", "alteracoes?select=id", headers={"Prefer": "return=representation"},
             json={"tabela": "crews", "chave": slug, "user_id": uid(), "tipo": "edicao", "dados": imagens,
                   "mensagem": "Imagens (crew publicada direto pelo agente)", "origem": "agente", "fontes": fontes}).json()[0]
    return {"imagens_na_moderacao": f"{CMS}/moderacao/alteracao/{r['id']}",
            "aviso_imagens": "Logo/capa vão como proposta na Moderação (crew não tem fila automática de imagem)."}


def _ligar_eventos(slug, ids, remover=False):
    """eventos.crews de cada evento (PATCH da lista inteira; editor pleno edita evento em qualquer situação)."""
    feitos, erros = [], []
    for e in _eventos_existentes(ids).values():
        atual = e.get("crews") or []
        nova = [c for c in atual if c != slug] if remover else list(dict.fromkeys(atual + [slug]))
        if nova == atual:
            continue
        try:
            r = rest("PATCH", f"eventos?id=eq.{e['id']}&select=id", json={"crews": nova}, headers={"Prefer": "return=representation"}).json()
            (feitos if r else erros).append(e["id"] if r else {"evento": e["id"], "erro": "nada alterado"})
        except Erro as x:
            erros.append({"evento": e["id"], "erro": str(x)})
    return feitos, erros


def gravar(arquivo, ensaio=False, publicar=False):
    e = json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())
    d, avisos = validar(e)
    if not ensaio:
        eu()  # falha cedo se a sessão não for da equipe
    ja = buscar(d["nome"], d["instagram"], d["site"])
    if ja["existentes"]:
        raise Erro("Já existe: " + "; ".join(f"{c['nome']} ({c['status']}) {c['site']}" for c in ja["existentes"]))
    if ja["provaveis"]:
        avisos.append("Nomes parecidos na base: " + ", ".join(f"{c['nome']} ({c['slug']})" for c in ja["provaveis"][:5]))
    if ja.get("aviso"):
        avisos.append(ja["aviso"])
    # eventos da crew (ids): ligados direto depois de criar (vínculo não passa pela Moderação)
    ids = list(dict.fromkeys(int(x) for x in (e.get("eventos") or []) if str(x).strip().isdigit()))
    if len(ids) != len(e.get("eventos") or []):
        raise Erro("eventos: lista de ids (números) de eventos da base.")
    evs = _eventos_existentes(ids)
    faltam = [i for i in ids if i not in evs]
    if faltam:
        raise Erro("eventos não encontrados: " + ", ".join(map(str, faltam)))
    usados = {r["slug"] for r in ler(f"crews?select=slug&slug=like.{d['slug']}*")}
    base_slug, n = d["slug"], 2
    while d["slug"] in usados:
        d["slug"], n = f"{base_slug}-{n}", n + 1
    url = _url(d)
    falta = faltando(d, COMPLETO + (["uf"] if d["pais"] == "BR" else []))
    if not ids:
        falta.append("eventos")
    imagens = {}
    if publicar:  # "Publicar direto" (crew não tem destaque); logo/capa conta:… vão como proposta à parte
        d["status"] = "publicado"
        imagens = {k: d[k] for k in IMAGENS if REF.match(d[k])}
        for k in imagens:
            d[k] = ""
        if imagens:
            avisos.append("Logo/capa vão como proposta na Moderação (crew não tem fila automática de imagem).")
    lista_ev = [{"id": x["id"], "nome": x["nome"], "inicio": x["inicio"], "status": x["status"]} for x in evs.values()]
    if ensaio:
        return _aviso_sessao({"ensaio": True, "publicar": publicar, "url": url, "faltando": falta, "avisos": avisos,
                              "imagens_na_moderacao": sorted(imagens), "eventos_a_ligar": lista_ev, "registro": d | imagens})
    r = rest("POST", "crews?select=slug,status,origem", json=d, headers={"Prefer": "return=representation"}).json()[0]
    res = {"ok": True, "slug": r["slug"], "url": url, "status": r["status"], "origem": r["origem"], "artistas": d["artistas"],
           "faltando": falta, "avisos": avisos, "editar": f"{CMS}/crews/{r['slug']}"}
    if ids:
        feitos, erros = _ligar_eventos(r["slug"], ids)
        res |= {"eventos_ligados": feitos, "erros_eventos": erros}
    if publicar:
        return res | (proposta_imagens(r["slug"], imagens, d["fontes"]) if imagens else {})
    return res | {"moderacao": f"{CMS}/moderacao/cadastro/crews/{r['slug']}"}


def propor(slug, arquivo, ensaio=False, publicar=False):
    e = json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())
    if "artistas" in e or "eventos" in e:
        raise Erro("Vínculos não vão em proposta: use crew.py vincular/remover (direto, sem Moderação).")
    atual = ler("crews?select=*&slug=eq." + slug)
    if not atual or atual[0]["status"] != "publicado":
        raise Erro("Crew não encontrada ou não publicada (pendente: edite a sugestão no CMS).")
    a = atual[0]
    novos = {k: v for k, v in e.items() if k in PROPOR}
    if not novos:
        raise Erro("Nada para propor: use só os campos " + ", ".join(PROPOR))
    base_ = {"nome": a["nome"], "pais": a.get("pais") or "BR", "uf": a.get("uf") or "", "fontes": e.get("fontes") or [{"url": _url(a)}]}
    d, avisos = validar(base_ | novos)
    avisos = [x for x in avisos if not (x == "Sem logo." and "logo" not in novos) and not (x == "Crew do Brasil sem UF." and "uf" not in novos)]
    dados = {k: d[k] for k in novos}
    mud = {k: {"antes": a.get(k), "depois": dados[k]} for k in dados if a.get(k) != dados[k]}
    if not mud:
        raise Erro("Os valores propostos são iguais aos atuais.")
    res = {"crew": {"slug": slug, "nome": a["nome"], "site": _url(a)}, "mudancas": mud,
           "faltando": faltando(a | {k: dados[k] for k in mud}, COMPLETO), "avisos": avisos}
    if publicar:  # "Publicar direto": PATCH; logo/capa conta:… vão como proposta só das imagens
        dados = {k: dados[k] for k in mud}
        imagens = {k: dados.pop(k) for k in IMAGENS if k in dados and REF.match(str(dados[k] or ""))}
        if ensaio:
            return _aviso_sessao(res | {"ensaio": True, "publicar": True, "editar_direto": sorted(dados), "imagens_na_moderacao": sorted(imagens)})
        feito = editar_direto("crews", "slug=eq." + slug, slug, dados, [], e.get("notas_agente")) if dados or e.get("notas_agente") else {"ok": True}
        return res | feito | (proposta_imagens(slug, imagens, d["fontes"]) if imagens else {})
    if ensaio:
        return _aviso_sessao(res | {"ensaio": True})
    eu()
    pend = rest("GET", f"alteracoes?select=id,origem&tabela=eq.crews&chave=eq.{slug}&status=eq.pendente&tipo=neq.imagem").json()
    if pend:
        raise Erro(f"Já há uma proposta em análise para esta crew (#{pend[0]['id']}, {pend[0]['origem']}): aguarde a Moderação ou publique direto.")
    r = rest("POST", "alteracoes?select=id", headers={"Prefer": "return=representation"},
             json={"tabela": "crews", "chave": slug, "user_id": uid(), "tipo": "edicao", "dados": {k: dados[k] for k in mud},
                   "mensagem": str(e.get("notas_agente") or "")[:2000], "origem": "agente", "fontes": d["fontes"] if e.get("fontes") else []}).json()[0]
    return res | {"ok": True, "id": r["id"], "moderacao": f"{CMS}/moderacao/alteracao/{r['id']}"}


# ---------------------------------------------------------------- vínculos (direto, sem Moderação)
def vincular(slug, alvo, chaves, ensaio=False, remover=False):
    """artistas: crews.artistas (slugs de perfis); eventos: eventos.crews de cada evento. Acrescenta ou, com remover=True, tira."""
    if alvo not in ("artistas", "eventos"):
        raise Erro("Uso: crew.py vincular|remover <slug> artistas|eventos <...>")
    chaves = list(dict.fromkeys(str(c).strip() for c in chaves if str(c).strip()))
    if not chaves:
        raise Erro(f"Informe ao menos um {'slug de perfil' if alvo == 'artistas' else 'id de evento'}.")
    c = ler("crews?select=slug,nome,status,artistas,notas_agente&slug=eq." + slug)
    if not c:
        raise Erro(f"Crew {slug} não encontrada" + (" (sem sessão só aparecem as publicadas)." if SEM_SESSAO else "."))
    c = c[0]
    info = {"slug": slug, "nome": c["nome"], "status": c["status"], "site": _url(c)}
    avisos = [] if c["status"] == "publicado" else [f"Crew ainda {c['status']}: os vínculos aparecem no site quando ela for aprovada."]
    if alvo == "artistas":
        antes = c.get("artistas") or []
        if remover:
            mexe = [s for s in chaves if s in antes]
            depois = [s for s in antes if s not in mexe]
            res = {"remover": mexe, "nao_vinculados": [s for s in chaves if s not in antes]}
        else:
            achados = _perfis_existentes(chaves)
            faltam = [s for s in chaves if s not in achados]
            if faltam:
                raise Erro("Perfis não encontrados: " + ", ".join(faltam))
            mexe = [s for s in chaves if s not in antes]
            depois = antes + mexe
            pend = [achados[s]["nome"] for s in mexe if achados[s]["status"] != "publicado"]
            if pend:
                avisos.append("Perfis ainda não publicados (aparecem quando aprovados): " + ", ".join(pend))
            res = {"adicionar": [{"slug": s, "nome": achados[s]["nome"], "status": achados[s]["status"], "site": url_perfil(achados[s])} for s in mexe],
                   "ja_vinculados": [s for s in chaves if s in antes]}
        res = {"crew": info, "antes": antes, "depois": depois, **res, "avisos": avisos}
        if ensaio or not mexe:
            return _aviso_sessao(res | {"ensaio": ensaio, "alterado": False})
        eu()
        r = rest("PATCH", f"crews?slug=eq.{slug}&select=slug", json={"artistas": depois}, headers={"Prefer": "return=representation"}).json()
        if not r:
            raise Erro(f"Crew {slug}: nada alterado.")
        return res | {"ok": True, "alterado": True, "site_aviso": "sem Moderação: vale na hora"}
    ids = []
    for x in chaves:
        if not x.isdigit():
            raise Erro(f"eventos: use o id (número), veio {x!r}.")
        ids.append(int(x))
    evs = _eventos_existentes(ids)
    faltam = [i for i in ids if i not in evs]
    if faltam:
        raise Erro("Eventos não encontrados: " + ", ".join(map(str, faltam)))
    def item(ev):
        return {"id": ev["id"], "nome": ev["nome"], "inicio": ev["inicio"], "status": ev["status"],
                "site": f"https://www.trance.com.br/{ev['rota']}/{ev['slug']}"}
    if remover:
        mexe = [i for i in ids if slug in (evs[i].get("crews") or [])]
        res = {"remover": [item(evs[i]) for i in mexe], "nao_vinculados": [i for i in ids if i not in mexe]}
    else:
        mexe = [i for i in ids if slug not in (evs[i].get("crews") or [])]
        res = {"adicionar": [item(evs[i]) for i in mexe], "ja_vinculados": [i for i in ids if i not in mexe]}
    res = {"crew": info, **res, "avisos": avisos}
    if ensaio or not mexe:
        return _aviso_sessao(res | {"ensaio": ensaio, "alterado": False})
    eu()
    feitos, erros = _ligar_eventos(slug, mexe, remover)
    return res | {"ok": not erros, "alterado": len(feitos), "eventos": feitos, "erros": erros, "site_aviso": "sem Moderação: vale na hora"}


def main(args):
    if not args or args[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return
    cmd, resto = args[0], args[1:]

    def valor(nome, padrao=""):
        return next((resto[i + 1] for i, a in enumerate(resto) if a == nome and i + 1 < len(resto)), padrao)
    com_valor = ("--instagram", "--site", "--min", "--limite")
    pos = [a for i, a in enumerate(resto) if not a.startswith("--") and not (i and resto[i - 1] in com_valor)]
    ens, pub = "--ensaio" in resto, "--publicar" in resto
    if cmd == "candidatos":
        saida(candidatos(int(valor("--min", "2") or 2), int(valor("--limite", "60") or 60)))
    elif cmd == "buscar" and pos:
        saida(buscar(" ".join(pos), valor("--instagram"), valor("--site")))
    elif cmd == "gravar" and pos:
        saida(gravar(pos[0], ens, pub))
    elif cmd == "propor" and len(pos) > 1:
        saida(propor(pos[0], pos[1], ens, pub))
    elif cmd in ("vincular", "remover") and len(pos) > 2:
        saida(vincular(pos[0], pos[1], pos[2:], ens, cmd == "remover"))
    else:
        raise Erro("Uso: crew.py candidatos|buscar|gravar|propor|vincular|remover (veja --help)")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Erro as e:
        print(json.dumps({"erro": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(json.dumps({"erro": f"Rede: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
