#!/usr/bin/env python3
"""Revisão da base do Trance.com.br (agente /trance, modo revisar). Plano: cms/PLANO-AGENTE-TRANCE.md, seção 6d.

Os temas só leem (sessão da equipe, como o evento.py). Escrevem: `aplicar vinculos` e `aplicar gravadoras` (vínculos aprovados
no relatório, direto e sem Moderação desde 2026-10-23, acrescentando e tirando) e `inativar` (status arquivado, nunca apaga).
O resto vira proposta/edição (artista.py propor) ou ajuste no CMS.

  revisar.py resumo                         # contagem de cada problema (roda todos os temas)
  revisar.py vinculos [--todos]             # evento ↔ artista: nome no line-up com perfil e sem vínculo; vínculo fora do line-up
  revisar.py gravadoras                     # perfil ↔ gravadora: selo citado no crew sem vínculo; vínculo com selo não publicado
  revisar.py duplicatas                     # perfis, eventos, gravadoras, lojas/serviços repetidos
  revisar.py incompletos                    # campos importantes vazios ou datas invertidas; crews sem artistas/eventos
  revisar.py links [--limite 60]            # sites e SoundCloud fora do ar (amostra; Instagram bloqueia robôs)
  revisar.py estilos                        # estilo inexistente; edições do mesmo evento em séries diferentes
  revisar.py aplicar vinculos <arquivo.json> [--ensaio]     # [{"evento": id, "adicionar": [slugs], "remover": [slugs]}] direto
  revisar.py aplicar gravadoras <arquivo.json> [--ensaio]   # [{"perfil": slug, "adicionar": [gravadoras], "remover": [...]}] direto
  revisar.py inativar <tabela> <chave> [<chave> ...] --motivo "..." [--ensaio]
      # tira do site (status arquivado): perfis <slug>, eventos <id>, gravadoras <slug>, negocios <loja|servico>/<slug>, sets <id>,
      # crews <slug>

Saída em JSON; listas longas vêm cortadas (`total` diz quantos são).
"""
import datetime as dt
import html
import json
import pathlib
import re
import sys
from collections import defaultdict

import requests

from evento import CMS, UA_NAVEGADOR, Erro, eu, mudar_artistas, norm, nota_agente, nucleo, rest, saida, tudo
from artista import ROTAS, _arroba, _sc, gravadoras as ligar_gravadoras

LIMITE = 40


def _corta(lista, n=LIMITE):
    return {"total": len(lista), "itens": lista[:n]}


def _ev_url(e):
    return f"https://www.trance.com.br/{e['rota']}/{e['slug']}"


def _pf_url(p):
    return f"https://www.trance.com.br/{ROTAS.get(p['categoria'], 'artista')}/{p['slug']}"


def _linhas_lineup(prog):
    """Mesma limpeza do evento.py (ligar_lineup): um nome por linha, sem selo/país/"(Live)"."""
    linhas = re.split(r"<br>|</p>", re.sub(r"<strong>.*?</strong>", "", prog or ""))
    nomes = []
    for l in linhas:
        t = html.unescape(re.sub(r"<[^>]+>", "", l)).strip()
        t = re.split(r"\s+[-–|•/@]\s+|\s*\(", t)[0].strip(" -–•*:")
        t = re.sub(r"[^\w\s&.'-]", "", t).strip()
        if 2 <= len(t) <= 60 and t not in nomes:
            nomes.append(t)
    return nomes


def _perfis():
    return tudo("perfis?select=slug,nome,categoria,status,pais,uf,crew,gravadoras,estilos,foto,resumo,instagram,soundcloud,spotify,bandcamp,youtube,site&order=slug")


def _eventos():
    return tudo("eventos?select=id,rota,slug,nome,categoria,inicio,fim,cidade,uf,pais_iso,lat,status,artistas,programacao,serie,serie_chave,imagem,flyer&order=id")


# ---------------------------------------------------------------- temas
def vinculos(todos=False):
    perfis = [p for p in _perfis() if p["status"] == "publicado"]
    por_nome = {}
    for p in perfis:
        por_nome.setdefault(norm(re.sub(r"\s*\(.*\)$", "", p["nome"])), p)
    status = {p["slug"]: p["status"] for p in _perfis()}
    # nome do perfil em qualquer ponto do texto do line-up (vários por linha, "DJ X", "X live set"): provável, conferir no relatório
    padroes = [(p["slug"], p["nome"], re.compile(r"\b" + re.escape(k) + r"\b")) for p in perfis
               for k in [norm(re.sub(r"\s*\(.*\)$", "", p["nome"]))] if len(k) >= 4]
    provaveis = []
    hoje = dt.date.today().isoformat()
    faltam, fora, quebrados = [], [], []
    for e in _eventos():
        if e["status"] != "publicado" or (not todos and (e["fim"] or e["inicio"])[:10] < str(int(hoje[:4]) - 3)):
            continue  # padrão: eventos dos últimos 3 anos e futuros (--todos = todos)
        ligados = e["artistas"] or []
        nomes = _linhas_lineup(e["programacao"])
        achados = {}
        for n in nomes:
            p = por_nome.get(norm(n))
            if p:
                achados[p["slug"]] = p["nome"]
        novos = [s for s in achados if s not in ligados]
        if novos:
            faltam.append({"evento": e["id"], "nome": e["nome"], "inicio": e["inicio"][:10], "site": _ev_url(e),
                           "adicionar": novos, "nomes": [achados[s] for s in novos]})
        texto = norm(html.unescape(re.sub(r"<[^>]+>", " ", e["programacao"] or "")))
        ja = set(ligados) | set(novos)
        prov = [(sl, nm) for sl, nm, rx in padroes if sl not in ja and rx.search(texto)] if texto else []
        if prov:
            provaveis.append({"evento": e["id"], "nome": e["nome"], "inicio": e["inicio"][:10], "site": _ev_url(e),
                              "adicionar": [x[0] for x in prov], "nomes": [x[1] for x in prov]})
        chaves_lineup = {norm(n) for n in nomes}
        sobra = [s for s in ligados if s in status and status[s] == "publicado"
                 and norm(next((p["nome"] for p in perfis if p["slug"] == s), "")) not in chaves_lineup]
        if sobra and nomes:
            fora.append({"evento": e["id"], "nome": e["nome"], "site": _ev_url(e), "vinculados_fora_do_lineup": sobra})
        q = [s for s in ligados if status.get(s) not in ("publicado", "pendente")]
        if q:
            quebrados.append({"evento": e["id"], "nome": e["nome"], "slugs": q, "situacao": {s: status.get(s, "não existe") for s in q}})
    return {"tema": "vinculos", "faltam_vinculos": _corta(faltam, 400), "total_vinculos_novos": sum(len(x["adicionar"]) for x in faltam),
            "provaveis": _corta(provaveis, 400), "total_provaveis": sum(len(x["adicionar"]) for x in provaveis),
            "vinculados_fora_do_lineup": _corta(fora), "vinculos_quebrados": _corta(quebrados),
            "como_corrigir": "Aprovados no relatório: grave a lista [{evento, adicionar, remover}] num JSON e rode `revisar.py aplicar vinculos <arquivo>` (direto, sem Moderação)."}


def gravadoras():
    gs = tudo("gravadoras?select=slug,nome,status&order=slug")
    pub = {g["slug"]: g for g in gs if g["status"] == "publicado"}
    chaves = {g["slug"]: re.sub(r"\b(records?|rec|music|label)\b", "", norm(g["nome"])).strip() for g in pub.values()}
    sem_vinc, vinc_ruim, a_cadastrar = [], [], defaultdict(list)
    for p in _perfis():
        if p["status"] != "publicado":
            continue
        crew = norm(p.get("crew"))
        ligadas = p.get("gravadoras") or []
        for s in ligadas:
            if s not in pub:
                vinc_ruim.append({"perfil": p["slug"], "gravadora": s, "situacao": "não publicada ou inexistente"})
        if not crew:
            continue
        citadas = [s for s, k in chaves.items() if len(k) >= 3 and re.search(r"\b" + re.escape(k) + r"\b", crew)]
        faltam = [s for s in citadas if s not in ligadas]
        if faltam:
            sem_vinc.append({"perfil": p["slug"], "nome": p["nome"], "crew": p["crew"], "sugerir": faltam, "site": _pf_url(p)})
        # selo citado que não existe na base ("X Records", "Y Music"...)
        for m in re.finditer(r"([a-z0-9][a-z0-9 .&'-]{1,40}?\s(?:records?|recordings|music|label))\b", crew):
            nome = m.group(1).strip()
            if not any(k and k in nome for k in chaves.values()):
                a_cadastrar[nome].append(p["slug"])
    cad = sorted(({"selo": k, "perfis": v, "n": len(v)} for k, v in a_cadastrar.items()), key=lambda x: -x["n"])
    return {"tema": "gravadoras", "crew_sem_vinculo": _corta(sem_vinc, 200), "vinculo_com_selo_fora_do_ar": _corta(vinc_ruim),
            "selos_citados_fora_da_base": _corta(cad, 60),
            "como_corrigir": "crew_sem_vinculo = vínculo (lote aprovado no relatório: [{perfil, adicionar}] e `revisar.py aplicar gravadoras <arquivo>`, direto); "
                             "selos fora da base = candidatos a cadastro (fase de gravadoras)."}


def duplicatas():
    def grupos(itens, chaves):
        idx = defaultdict(list)
        for it in itens:
            for nome_k, f in chaves:
                v = f(it)
                if v:
                    idx[(nome_k, v)].append(it)
        vistos, out = set(), []
        for (k, v), lst in idx.items():
            ids = tuple(sorted(x["_id"] for x in lst))
            if len(lst) > 1 and ids not in vistos:
                vistos.add(ids)
                out.append({"por": k, "valor": v, "itens": [{x2: x[x2] for x2 in x if not x2.startswith("_")} for x in lst]})
        return out
    perfis = [{"_id": p["slug"], "slug": p["slug"], "nome": p["nome"], "status": p["status"], "site": _pf_url(p),
               "_ig": _arroba(p.get("instagram")), "_sc": _sc(p.get("soundcloud")).split("/")[0], "_n": norm(p["nome"])} for p in _perfis()]
    pf = grupos(perfis, [("nome", lambda x: x["_n"]), ("instagram", lambda x: x["_ig"]), ("soundcloud", lambda x: x["_sc"])])
    evs = [{"_id": e["id"], "id": e["id"], "nome": e["nome"], "inicio": e["inicio"][:10], "status": e["status"], "site": _ev_url(e),
            "_k": nucleo(e["nome"]) + "|" + e["inicio"][:10]} for e in _eventos()]
    ev = grupos(evs, [("nome e data", lambda x: x["_k"] if x["_k"].split("|")[0] else "")])
    gs = [{"_id": g["slug"], "slug": g["slug"], "nome": g["nome"], "_n": re.sub(r"\b(records?|rec|music|label)\b", "", norm(g["nome"])).strip()}
          for g in tudo("gravadoras?select=slug,nome")]
    gr = grupos(gs, [("nome", lambda x: x["_n"])])
    ns = [{"_id": n["tipo"] + "/" + n["slug"], "chave": n["tipo"] + "/" + n["slug"], "nome": n["nome"], "_n": norm(n["nome"]),
           "_ig": _arroba(n.get("instagram")), "_site": re.sub(r"^https?://(www\.)?|/.*$", "", (n.get("site") or "").lower())}
          for n in tudo("negocios?select=tipo,slug,nome,instagram,site")]
    ng = grupos(ns, [("nome", lambda x: x["_n"]), ("instagram", lambda x: x["_ig"]), ("site", lambda x: x["_site"])])
    return {"tema": "duplicatas", "perfis": _corta(pf, 100), "eventos": _corta(ev, 100), "gravadoras": _corta(gr), "lojas_servicos": _corta(ng),
            "como_corrigir": "Proposta de mesclagem no relatório (qual fica, o que migra); nunca apagar sozinho."}


def incompletos():
    hoje = dt.date.today().isoformat()
    pf = [p for p in _perfis() if p["status"] == "publicado"]
    evs = [e for e in _eventos() if e["status"] == "publicado"]
    fut = [e for e in evs if (e["fim"] or e["inicio"])[:10] >= hoje]
    gv = [g for g in tudo("gravadoras?select=slug,nome,status,logo,release,pais,estilos,seo_description,site,instagram,soundcloud,bandcamp,beatport")
          if g["status"] == "publicado"]
    ng = [n for n in tudo("negocios?select=tipo,slug,nome,cidade,tags,logo,resumo,status") if n["status"] == "publicado"]
    # crews (2026-10-23): página /crew/<slug> com artistas (crews.artistas) e eventos (eventos.crews)
    cr = [c for c in tudo("crews?select=slug,nome,status,artistas,logo,resumo,release,cidade,instagram,site&order=slug") if c["status"] == "publicado"]
    slugs_pf = {p["slug"] for p in pf}
    todos_ev = _eventos_crews()
    com_evento = {c for e in todos_ev if e["status"] == "publicado" for c in (e["crews"] or [])}
    slugs_cr = {c["slug"] for c in tudo("crews?select=slug,status") if c["status"] in ("publicado", "pendente")}

    def lst(itens, f, campos):
        return _corta([{c: x.get(c) for c in campos} for x in itens if f(x)], 60)
    return {"tema": "incompletos",
            "perfis_sem_foto": lst(pf, lambda p: not p["foto"], ["slug", "nome"]),
            "perfis_sem_estilo": lst(pf, lambda p: not p["estilos"], ["slug", "nome"]),
            "perfis_br_sem_uf": lst(pf, lambda p: (p.get("pais") or "BR") == "BR" and not p.get("uf"), ["slug", "nome"]),
            "eventos_futuros_sem_imagem": lst(fut, lambda e: not e["imagem"] and not e["flyer"], ["id", "nome", "inicio"]),
            "eventos_futuros_sem_mapa": lst(fut, lambda e: e["lat"] is None, ["id", "nome", "cidade"]),
            "eventos_br_sem_uf": lst(evs, lambda e: (e.get("pais_iso") or "BR") == "BR" and not e["uf"], ["id", "nome", "cidade"]),
            "eventos_datas_invertidas": lst(evs, lambda e: e["fim"] and e["fim"] < e["inicio"], ["id", "nome", "inicio", "fim"]),
            "perfis_sem_resumo": lst(pf, lambda p: not p.get("resumo"), ["slug", "nome"]),
            # lojas/serviços: a tag define a subpágina (/lojas/vestuario...) e o cartão da lista mostra logo, 1ª tag, cidade e resumo
            **{f"negocios_sem_{c}": _corta([{"chave": n["tipo"] + "/" + n["slug"], "nome": n["nome"]} for n in ng if not n[c]], 60)
               for c in ("cidade", "tags", "logo", "resumo")},
            # gravadoras: logo e release na página; seo_* no Google; sem nenhum link a página fica sem saída
            **{f"gravadoras_sem_{c}": _corta([{"slug": g["slug"], "nome": g["nome"]} for g in gv if not g[c]], 60)
               for c in ("logo", "release", "pais", "estilos", "seo_description")},
            "gravadoras_sem_links": _corta([{"slug": g["slug"], "nome": g["nome"]} for g in gv
                                             if not any(g[k] for k in ("site", "instagram", "soundcloud", "bandcamp", "beatport"))], 60),
            # crews: sem artistas ou sem eventos a página fica vazia; vínculo para perfil fora do ar ou crew inexistente
            "crews_sem_artistas": _corta([{"slug": c["slug"], "nome": c["nome"], "site": f"https://www.trance.com.br/crew/{c['slug']}"}
                                          for c in cr if not [a for a in (c["artistas"] or []) if a in slugs_pf]], 60),
            "crews_sem_eventos": _corta([{"slug": c["slug"], "nome": c["nome"], "site": f"https://www.trance.com.br/crew/{c['slug']}"}
                                         for c in cr if c["slug"] not in com_evento], 60),
            **{f"crews_sem_{c}": _corta([{"slug": x["slug"], "nome": x["nome"]} for x in cr if not x[c]], 60) for c in ("logo", "resumo", "release", "cidade")},
            "crews_artistas_fora_do_ar": _corta([{"crew": c["slug"], "perfis": [a for a in (c["artistas"] or []) if a not in slugs_pf]}
                                                 for c in cr if [a for a in (c["artistas"] or []) if a not in slugs_pf]], 60),
            "eventos_com_crew_inexistente": _corta([{"id": e["id"], "nome": e["nome"], "crews": [c for c in (e["crews"] or []) if c not in slugs_cr]}
                                                    for e in todos_ev if [c for c in (e["crews"] or []) if c not in slugs_cr]], 60)}


def _eventos_crews():
    return tudo("eventos?select=id,nome,status,crews&crews=neq.{}&order=id")


def links(limite=60):
    alvos = []
    for p in _perfis():
        if p["status"] == "publicado":
            for k in ("site", "soundcloud", "spotify", "bandcamp", "youtube"):
                if (p.get(k) or "").startswith("http"):
                    alvos.append(("perfil", p["slug"], k, p[k]))
    for n in tudo("negocios?select=tipo,slug,site,status"):
        if n["status"] == "publicado" and (n.get("site") or "").startswith("http"):
            alvos.append(("negocio", n["tipo"] + "/" + n["slug"], "site", n["site"]))
    ruins = []
    for tipo, chave, campo, url in alvos[:limite]:
        try:
            r = requests.get(url, headers={"User-Agent": UA_NAVEGADOR}, timeout=15, allow_redirects=True, stream=True)
            ok = r.status_code < 400 or r.status_code in (403, 429)  # 403/429 = bloqueio de robô, não link morto
            r.close()
        except requests.RequestException as e:
            ok, r = False, None
        if not ok:
            ruins.append({"tipo": tipo, "chave": chave, "campo": campo, "url": url, "status": getattr(r, "status_code", "sem resposta")})
    return {"tema": "links", "conferidos": min(limite, len(alvos)), "total_de_links": len(alvos), "fora_do_ar": _corta(ruins, 100),
            "obs": "Amostra (use --limite para mais). Instagram não é conferido (bloqueia robôs)."}


def estilos():
    validos = {e["slug"] for e in tudo("estilos?select=slug")}
    pf = [{"perfil": p["slug"], "estilos_invalidos": [s for s in (p["estilos"] or []) if s not in validos]} for p in _perfis()]
    gr = [{"gravadora": g["slug"], "estilos_invalidos": [s for s in (g["estilos"] or []) if s not in validos]} for g in tudo("gravadoras?select=slug,estilos")]
    series = defaultdict(set)
    nomes = defaultdict(list)
    for e in _eventos():
        k = nucleo(e["nome"])
        if k:
            series[k].add(e["serie_chave"] or "")
            nomes[k].append({"id": e["id"], "nome": e["nome"], "serie_chave": e["serie_chave"]})
    racha = [{"nucleo": k, "series": sorted(v), "edicoes": nomes[k][:8]} for k, v in series.items() if len(v) > 1]
    return {"tema": "estilos", "perfis": _corta([x for x in pf if x["estilos_invalidos"]]), "gravadoras": _corta([x for x in gr if x["estilos_invalidos"]]),
            "edicoes_em_series_diferentes": _corta(racha, 60),
            "como_corrigir": "Estilo inválido: proposta com o slug certo. Série: campo \"Série\" no CMS com o mesmo nome nas edições."}


def resumo():
    v, g, d, i, s = vinculos(), gravadoras(), duplicatas(), incompletos(), estilos()
    return {"vinculos": {"eventos_com_vinculo_faltando": v["faltam_vinculos"]["total"], "vinculos_novos": v["total_vinculos_novos"],
                         "provaveis_no_texto": v["total_provaveis"],
                         "vinculados_fora_do_lineup": v["vinculados_fora_do_lineup"]["total"], "quebrados": v["vinculos_quebrados"]["total"]},
            "gravadoras": {"crew_sem_vinculo": g["crew_sem_vinculo"]["total"], "vinculo_com_selo_fora_do_ar": g["vinculo_com_selo_fora_do_ar"]["total"],
                           "selos_citados_fora_da_base": g["selos_citados_fora_da_base"]["total"]},
            "duplicatas": {k: d[k]["total"] for k in ("perfis", "eventos", "gravadoras", "lojas_servicos")},
            "incompletos": {k: x["total"] for k, x in i.items() if isinstance(x, dict)},
            "estilos": {"perfis": s["perfis"]["total"], "gravadoras": s["gravadoras"]["total"], "series": s["edicoes_em_series_diferentes"]["total"]},
            "links": "não incluído no resumo (lento): rode `revisar.py links`"}


def aplicar_vinculos(arquivo, ensaio=False):
    """Vínculos evento ↔ artista aprovados no relatório, direto (sem Moderação, 2026-10-23): soma e tira em eventos.artistas."""
    lote = json.loads(pathlib.Path(arquivo).read_text())
    if not isinstance(lote, list):
        raise Erro("Arquivo: lista de {evento, adicionar, remover}.")
    if not ensaio:
        eu()
    feitos, erros = [], []
    for item in lote:
        try:
            ev = rest("GET", f"eventos?select=id,nome,status,origem,artistas&id=eq.{int(item['evento'])}").json()
            if not ev:
                raise Erro("evento não encontrado")
            atual = ev[0]["artistas"] or []
            novos = [s for s in item.get("adicionar") or [] if s not in atual]
            ignorados = []
            if novos:
                ok = {p["slug"] for p in rest("GET", "perfis?select=slug&slug=in.(" + ",".join(f'"{s}"' for s in novos) + ")").json()}
                ignorados = [s for s in novos if s not in ok]
                novos = [s for s in novos if s in ok]
            fora = [s for s in item.get("remover") or [] if s in atual]  # vínculo errado (nome no meio do texto, outro artista)
            feito = {}
            if (novos or fora) and not ensaio:
                feito = mudar_artistas(ev[0], [s for s in atual + novos if s not in fora])
            feitos.append({"evento": item["evento"], "nome": ev[0]["nome"], "adicionados": novos, "removidos": fora,
                           **({"perfis_inexistentes": ignorados} if ignorados else {}), **feito})
        except (Erro, KeyError, ValueError) as e:
            erros.append({"evento": item.get("evento"), "erro": str(e)})
    return {"ok": not erros, "ensaio": ensaio, "eventos": len(feitos), "vinculos_adicionados": sum(len(f["adicionados"]) for f in feitos),
            "vinculos_removidos": sum(len(f["removidos"]) for f in feitos), "itens": feitos, "erros": erros}


def aplicar_gravadoras(arquivo, ensaio=False):
    """Vínculos artista ↔ gravadora aprovados no relatório, direto (sem Moderação, 2026-10-23): soma e tira em perfis.gravadoras."""
    lote = json.loads(pathlib.Path(arquivo).read_text())
    if not isinstance(lote, list):
        raise Erro("Arquivo: lista de {perfil, adicionar, remover}.")
    feitos, erros = [], []
    for item in lote:
        try:
            slug, r = str(item["perfil"]), {}
            if item.get("remover"):
                r = ligar_gravadoras(slug, item["remover"], ensaio, remover=True)
            if item.get("adicionar"):
                r = {"remover": r.get("remover", [])} | ligar_gravadoras(slug, item["adicionar"], ensaio)
            feitos.append({"perfil": slug, "antes": r.get("antes"), "depois": r.get("depois"), "removidas": r.get("remover", []),
                           "adicionadas": [g["slug"] for g in r.get("adicionar", [])], "avisos": r.get("avisos", [])})
        except (Erro, KeyError, ValueError) as e:
            erros.append({"perfil": item.get("perfil"), "erro": str(e)})
    return {"ok": not erros, "ensaio": ensaio, "perfis": len(feitos), "itens": feitos, "erros": erros}


# ---------------------------------------------------------------- inativar (status arquivado; nunca apaga)
# chave de cada tabela e se ela guarda notas do agente (sets não tem notas_agente: o motivo fica só no relatório)
INATIVAR = {"perfis": ("slug", True), "eventos": ("id", True), "gravadoras": ("slug", True), "negocios": ("tipo/slug", True), "sets": ("id", False),
            "crews": ("slug", True)}


def _filtro(tabela, chave):
    if tabela in ("eventos", "sets"):
        if not str(chave).isdigit():
            raise Erro(f"{tabela}: a chave é o id (número), veio {chave!r}.")
        return f"id=eq.{int(chave)}"
    if tabela == "negocios":
        tipo, _, slug = str(chave).partition("/")
        if tipo not in ("loja", "servico") or not slug:
            raise Erro(f"negocios: use loja/<slug> ou servico/<slug>, veio {chave!r}.")
        return f"tipo=eq.{tipo}&slug=eq.{slug}"
    return f"slug=eq.{chave}"


def inativar(tabela, chaves, motivo, ensaio=False):
    """Tira cadastros do site (status arquivado), nunca apaga. O dono pode editar em conta.trance.com.br e reenviar (volta a
    pendente) e o CMS tem "Publicar de novo". O motivo vai em notas_agente (linha datada), onde a coluna existe."""
    if tabela not in INATIVAR:
        raise Erro("tabela: " + ", ".join(INATIVAR))
    motivo = re.sub(r"\s+", " ", str(motivo or "")).strip()
    if not motivo:
        raise Erro('Informe o motivo: --motivo "..." (vai para as notas do agente e para o relatório).')
    chaves = list(dict.fromkeys(str(c).strip() for c in chaves if str(c).strip()))
    if not chaves:
        raise Erro("Informe ao menos uma chave.")
    _, tem_notas = INATIVAR[tabela]
    campos = {"perfis": "slug,nome,categoria,status", "eventos": "id,rota,slug,nome,inicio,status", "gravadoras": "slug,nome,status",
              "negocios": "tipo,slug,nome,status", "sets": "id,perfil,titulo,status", "crews": "slug,nome,status,artistas"}[tabela] + (",notas_agente" if tem_notas else "")
    itens, ignorados = [], []
    for c in chaves:
        r = rest("GET", f"{tabela}?select={campos}&{_filtro(tabela, c)}").json()
        if not r:
            ignorados.append({"chave": c, "motivo": "não encontrado"})
            continue
        x = r[0]
        if x["status"] not in ("publicado", "pendente"):
            ignorados.append({"chave": c, "motivo": f"já está {x['status']}"})
            continue
        site = {"perfis": lambda: _pf_url(x), "eventos": lambda: _ev_url(x), "gravadoras": lambda: f"https://www.trance.com.br/gravadora/{x['slug']}",
                "negocios": lambda: f"https://www.trance.com.br/{x['tipo']}/{x['slug']}", "sets": lambda: f"(set do perfil {x['perfil']})",
                "crews": lambda: f"https://www.trance.com.br/crew/{x['slug']}"}[tabela]()
        item = {"chave": c, "nome": x.get("nome") or x.get("titulo"), "status": x["status"],
                "sai_do_site": site if x["status"] == "publicado" else "(ainda pendente: sai da fila da Moderação)", "_x": x}
        if tabela == "perfis":
            item["sets_publicados"] = len(rest("GET", f"sets?select=id&perfil=eq.{x['slug']}&status=eq.publicado").json())
            item["eventos_vinculados"] = len(rest("GET", f"eventos?select=id&artistas=cs.{{{x['slug']}}}&status=eq.publicado").json())
        if tabela == "crews":  # os vínculos ficam (voltam se a crew for publicada de novo); só saem do site junto com ela
            item["artistas_vinculados"] = len(x.get("artistas") or [])
            item["eventos_vinculados"] = len(rest("GET", f"eventos?select=id&crews=cs.{{{x['slug']}}}&status=eq.publicado").json())
        itens.append(item)
    res = {"tabela": tabela, "motivo": motivo, "inativar": [{k: v for k, v in i.items() if k != "_x"} for i in itens], "ignorados": ignorados,
           "volta": "O dono pode editar e reenviar em conta.trance.com.br (volta para a Moderação como pendente); no CMS, \"Publicar de novo\" restaura."}
    if ensaio or not itens:
        return res | {"ensaio": ensaio, "alterado": 0}
    eu()
    feitos, erros = [], []
    for i in itens:
        mudar = {"status": "arquivado"}
        if tem_notas:
            mudar["notas_agente"] = nota_agente(i["_x"].get("notas_agente"), "Inativado pelo agente: " + motivo)
        try:
            r = rest("PATCH", f"{tabela}?{_filtro(tabela, i['chave'])}&status=in.(publicado,pendente)&select=status", json=mudar,
                     headers={"Prefer": "return=representation"}).json()
            (feitos if r else erros).append(i["chave"] if r else {"chave": i["chave"], "erro": "mudou de situação: nada alterado"})
        except Erro as e:
            erros.append({"chave": i["chave"], "erro": str(e)})
    return res | {"ok": not erros, "alterado": len(feitos), "arquivados": feitos, "erros": erros}


def main(args):
    if not args or args[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return
    cmd, resto = args[0], args[1:]
    opc = {a for a in resto if a.startswith("--")}
    motivo = next((resto[i + 1] for i, a in enumerate(resto) if a == "--motivo" and i + 1 < len(resto)), "")
    pos = [a for i, a in enumerate(resto) if not a.startswith("--") and not (i and resto[i - 1] in ("--motivo", "--limite"))]
    lim = next((int(resto[i + 1]) for i, a in enumerate(resto) if a == "--limite" and i + 1 < len(resto)), 60)
    temas = {"resumo": resumo, "duplicatas": duplicatas, "incompletos": incompletos, "estilos": estilos, "gravadoras": gravadoras}
    if cmd in temas:
        saida(temas[cmd]())
    elif cmd == "vinculos":
        saida(vinculos("--todos" in opc))
    elif cmd == "links":
        saida(links(lim))
    elif cmd == "aplicar" and pos[:1] == ["vinculos"] and len(pos) > 1:
        saida(aplicar_vinculos(pos[1], "--ensaio" in opc))
    elif cmd == "aplicar" and pos[:1] == ["gravadoras"] and len(pos) > 1:
        saida(aplicar_gravadoras(pos[1], "--ensaio" in opc))
    elif cmd == "inativar" and len(pos) > 1:
        saida(inativar(pos[0], pos[1:], motivo, "--ensaio" in opc))
    else:
        raise Erro("Uso: revisar.py resumo|vinculos|gravadoras|duplicatas|incompletos|links|estilos | aplicar vinculos|gravadoras <arquivo> [--ensaio]"
                   ' | inativar <tabela> <chave> [...] --motivo "..." [--ensaio]')


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Erro as e:
        print(json.dumps({"erro": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(json.dumps({"erro": f"Rede: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
