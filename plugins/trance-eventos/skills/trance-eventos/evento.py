#!/usr/bin/env python3
"""Ferramentas do agente de eventos (skill /trance-eventos). Plano: cms/PLANO-AGENTE-EVENTOS.md (repo trance.local).

Grava no Supabase com a SESSÃO DA PESSOA da equipe do CMS (login + código do app), nunca com a chave secreta:
o RLS (cms_pode_editar) decide o que pode, e o histórico do CMS registra quem gravou.

  evento.py login [--colar]                # num terminal comum: conecta pelo navegador (CMS) + código do app
  evento.py eu                             # quem está logado e se é da equipe
  evento.py sair
  evento.py duplicata "<nome>" <AAAA-MM-DD> [--cidade X]
  evento.py lineup "Artista 1" "Artista 2" ...   (ou --arquivo nomes.txt, um por linha)
  evento.py imagem <url|caminho>           # -> conta:<uid>/<arquivo>.webp (vai para a Duda só na aprovação)
  evento.py geocode "<local, cidade, país>"  # Google pelo CMS (local, cidade, uf, pais_iso, lat/lng); sem ele, Nominatim
  evento.py instagram <link|@usuario> [--perfil @usuario]   # perfil + post (ou 12 recentes) pela Graph API, via CMS
  evento.py candidatos goabase [--pais BR,PT] [--dias 180] [--festivais]
  evento.py candidatos recorrentes [--meses 14]            # festivais da base sem a próxima edição
  evento.py goabase <id|link>                              # detalhes de uma festa do Goabase (line-up, texto, flyer)
  evento.py gravar <evento.json> [--ensaio] [--passado]
  evento.py atualizar <id> <parcial.json>  # completa sugestão do agente ainda pendente (ex.: line-up que chegou depois)

Saída sempre em JSON (stdout); erros em stderr com código 1.
"""
import datetime as dt
import difflib
import html
import io
import json
import os
import pathlib
import re
import sys
import time
import unicodedata
import uuid

import requests
from PIL import Image, ImageOps

AQUI = pathlib.Path(__file__).resolve()
# .env do repositório (quando a skill roda dentro do trance.local); no plugin não existe e vale o config.json
RAIZ = next((d for d in AQUI.parents if (d / ".env").exists()), AQUI.parent)
LOGIN = f"python3 {AQUI} login"
CONFIG = pathlib.Path(os.environ.get("XDG_CONFIG_HOME", pathlib.Path.home() / ".config")) / "trance"
SESSAO = CONFIG / "sessao.json"
CMS = os.environ.get("TRANCE_CMS_URL", "https://app.trance.com.br")
UA = "trance.com.br agente de eventos (+https://www.trance.com.br)"
UA_NAVEGADOR = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

CATEGORIAS = ["Festivais", "Festas", "Feiras / Exposições", "Cursos / Retiros"]
UFS = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
       "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
       "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
       "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
       "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins"}
TEXTO = ["nome", "local", "cidade", "pais"]
URLS = ["site", "instagram", "facebook", "youtube", "video", "ingresso"]
PERMITIDOS = {"nome", "slug", "categoria", "inicio", "fim", "resumo", "release", "programacao", "imagem", "logo", "local", "cidade",
              "uf", "pais", "pais_iso", "lat", "lng", *URLS, "fontes", "notas_agente"}
DATA = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$")
REF = re.compile(r"^conta:[0-9a-f-]{36}/[0-9a-f-]{36}\.(webp|gif|jpg|png)$")


class Erro(Exception):
    pass


def saida(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- configuração e sessão
def config():
    """URL do Supabase e chave pública (anon). Ordem: variáveis TRANCE_*, config.json ao lado do script (plugin),
    ~/.config/trance/config.json, .env do repositório."""
    url, anon = os.environ.get("TRANCE_SUPABASE_URL"), os.environ.get("TRANCE_SUPABASE_ANON_KEY")
    for arq in (AQUI.parent / "config.json", CONFIG / "config.json"):
        if not (url and anon) and arq.exists():
            c = json.loads(arq.read_text())
            url, anon = url or c.get("supabase_url"), anon or c.get("supabase_anon_key")
    if not (url and anon) and (RAIZ / ".env").exists():
        env = dict(re.findall(r"^([A-Z_]+)=(.*)$", (RAIZ / ".env").read_text(), re.M))
        url, anon = url or env.get("SUPABASE_URL", "").strip().strip('"'), anon or env.get("SUPABASE_ANON_KEY", "").strip().strip('"')
    if not (url and anon):
        raise Erro("Sem URL/chave pública do Supabase: crie ~/.config/trance/config.json com supabase_url e supabase_anon_key.")
    return url.rstrip("/"), anon


def gravar_sessao(s):
    CONFIG.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG, 0o700)
    dados = {"access_token": s["access_token"], "refresh_token": s["refresh_token"],
             "expires_at": int(time.time()) + int(s.get("expires_in", 3600)), "email": s.get("user", {}).get("email", "")}
    fd = os.open(SESSAO, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(dados, f)
    return dados


def sessao():
    """Token válido (renova pelo refresh token quando falta menos de 2 min)."""
    if not SESSAO.exists():
        raise Erro(f"Sem sessão. Rode num terminal comum: {LOGIN}")
    s = json.loads(SESSAO.read_text())
    if s["expires_at"] - time.time() > 120:
        return s
    url, anon = config()
    r = requests.post(f"{url}/auth/v1/token?grant_type=refresh_token", json={"refresh_token": s["refresh_token"]},
                      headers={"apikey": anon}, timeout=30)
    if r.status_code != 200:
        raise Erro(f"Sessão expirada. Entre de novo num terminal comum: {LOGIN}")
    return gravar_sessao(r.json() | {"user": {"email": s.get("email", "")}})


def cabecalhos(extra=None):
    _, anon = config()
    return {"apikey": anon, "Authorization": "Bearer " + sessao()["access_token"], **(extra or {})}


def uid():
    import base64
    tok = sessao()["access_token"].split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(tok + "=" * (-len(tok) % 4)))
    if claims.get("aal") != "aal2":
        raise Erro("Sessão sem o 2º fator. Entre de novo com o código do app.")
    return claims["sub"]


def rest(metodo, caminho, **kw):
    url, _ = config()
    r = requests.request(metodo, f"{url}/rest/v1/{caminho}", headers=cabecalhos(kw.pop("headers", None)), timeout=60, **kw)
    if r.status_code >= 400:
        try:
            msg = r.json().get("message", r.text)
        except ValueError:
            msg = r.text
        raise Erro(f"Supabase {r.status_code}: {msg[:300]}")
    return r


def tudo(caminho):
    """Lê uma tabela inteira em páginas de 1000 (limite do PostgREST)."""
    linhas, ini = [], 0
    while True:
        lote = rest("GET", caminho, headers={"Range": f"{ini}-{ini + 999}"}).json()
        linhas += lote
        if len(lote) < 1000:
            return linhas
        ini += 1000


def _receber_link(colar):
    """Abre o CMS no navegador (onde a pessoa já entra com senha, captcha e 2º fator) e espera o link de uso único em 127.0.0.1.
    O Supabase exige captcha no login por senha; o link mágico gerado pelo CMS não."""
    import http.server
    import secrets
    import socket
    import threading
    import urllib.parse
    import webbrowser

    estado = secrets.token_hex(16)
    if colar:
        print(f"Abra no navegador, clique em \"Conectar terminal\" e copie o código:\n  {CMS}/agente/conectar?porta=9999&estado={estado}&colar=1",
              file=sys.stderr)
        return input("Código: ").strip()
    recebido, pronto = {}, threading.Event()

    class Porta(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            ok = q.get("estado", [""])[0] == estado and q.get("h", [""])[0]
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "Terminal conectado. Pode fechar esta aba e, no terminal, digitar o código de 6 dígitos do seu app autenticador (o mesmo do login do CMS)." if ok else "Pedido inválido."
            self.wfile.write(f"<!doctype html><meta charset=utf-8><title>Trance</title><p style='font:16px sans-serif;margin:2rem'>{msg}</p>".encode())
            if ok:
                recebido["h"] = q["h"][0]
                pronto.set()

        def log_message(self, *a):
            pass

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    srv = http.server.HTTPServer(("127.0.0.1", porta), Porta)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    endereco = f"{CMS}/agente/conectar?porta={porta}&estado={estado}"
    print(f"Abra no navegador e clique em \"Conectar terminal\":\n  {endereco}\n(esperando até 10 min; Ctrl+C cancela)", file=sys.stderr)
    try:
        import platform
        if "microsoft" in platform.uname().release.lower():  # WSL: abre no navegador do Windows
            import subprocess
            subprocess.run(["cmd.exe", "/c", "start", "", endereco.replace("&", "^&")], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=False)
        else:
            webbrowser.open(endereco)
    except Exception:  # noqa: BLE001
        pass
    if not pronto.wait(600):
        srv.shutdown()
        raise Erro("Tempo esgotado. Se o navegador não alcança este terminal, use: evento.py login --colar")
    srv.shutdown()
    return recebido["h"]


def login(colar=False):
    url, anon = config()
    h = _receber_link(colar)
    r = requests.post(f"{url}/auth/v1/verify", json={"type": "magiclink", "token_hash": h}, headers={"apikey": anon}, timeout=30)
    if r.status_code != 200:
        raise Erro("Link inválido ou já usado. Rode o login de novo.")
    s = r.json()
    fatores = [f for f in s.get("user", {}).get("factors", []) or [] if f.get("factor_type") == "totp" and f.get("status") == "verified"]
    if not fatores:
        raise Erro("Esta conta não tem app autenticador. Configure no CMS (app.trance.com.br) primeiro.")
    hd = {"apikey": anon, "Authorization": "Bearer " + s["access_token"]}
    fid = fatores[0]["id"]
    for _ in range(3):
        codigo = re.sub(r"\D", "", input("Código de 6 dígitos do app autenticador (o mesmo do login do CMS): "))
        ch = requests.post(f"{url}/auth/v1/factors/{fid}/challenge", headers=hd, timeout=30)
        if ch.status_code != 200:
            raise Erro(f"Falha no desafio do 2º fator ({ch.status_code}).")
        v = requests.post(f"{url}/auth/v1/factors/{fid}/verify", json={"challenge_id": ch.json()["id"], "code": codigo}, headers=hd, timeout=30)
        if v.status_code == 200:
            gravar_sessao(v.json() | {"user": {"email": s.get("user", {}).get("email", "")}})
            return eu()
        print("Código inválido ou expirado.", file=sys.stderr)
    raise Erro("Código do app recusado 3 vezes.")


def eu():
    u = uid()
    m = rest("GET", f"cms_equipe?select=nome,email,papel&user_id=eq.{u}").json()
    if not m:
        raise Erro("Logado, mas fora da equipe do CMS: peça a um admin para incluir você em Equipe.")
    return {"ok": True, "user_id": u, **m[0]}


def sair():
    SESSAO.unlink(missing_ok=True)
    return {"ok": True}


# ---------------------------------------------------------------- base: duplicata e line-up
def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = html.unescape(s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def nucleo(s):
    """Nome sem ano, número de edição e palavras genéricas (para comparar edições do mesmo evento)."""
    s = re.sub(r"\b(19|20)\d{2}\b|#\s*\d+|\b\d+(o|a|th|st|nd|rd)?\b", " ", norm(s))
    s = re.sub(r"\b(festival|festa|edicao|edition|capitulo|chapter|open air|anos|years|reveillon)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parecido(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def mesmo_nome(a, b):
    """Semelhança entre nomes de evento: nome inteiro, só o trecho antes de | / - / :, ou um contido no outro."""
    def cabeca(s):
        return nucleo(re.sub(r"\(.*?\)|\[.*?\]", " ", re.split(r"\s[|/:–-]\s|\|", str(s or ""))[0]))
    na, nb, ca, cb = nucleo(a), nucleo(b), cabeca(a), cabeca(b)
    sim = max(parecido(na, nb), parecido(ca, cb), parecido(ca.replace(" ", ""), cb.replace(" ", "")))
    curto, longo = sorted((ca, cb), key=len)
    if len(curto) >= 6 and re.search(r"\b" + re.escape(curto) + r"\b", longo):
        sim = max(sim, 0.9)
    return sim


def base_eventos():
    return tudo("eventos?select=id,rota,slug,nome,inicio,fim,cidade,status,origem,site,instagram,categoria&order=id")


def duplicata(nome, data, cidade="", eventos=None):
    try:
        alvo = dt.date.fromisoformat(data[:10])
    except ValueError:
        raise Erro("Data inválida: use AAAA-MM-DD.")
    eventos = eventos if eventos is not None else base_eventos()
    c = norm(cidade)
    mesmo, edicoes = [], []
    for e in eventos:
        sim = mesmo_nome(nome, e["nome"])
        if sim < 0.72:
            continue
        try:
            dias = abs((dt.date.fromisoformat(e["inicio"][:10]) - alvo).days)
        except ValueError:
            dias = 9999
        item = {"id": e["id"], "nome": e["nome"], "inicio": e["inicio"], "cidade": e["cidade"], "status": e["status"],
                "semelhanca": round(sim, 2), "dias_de_diferenca": dias,
                "cms": f"{CMS}/eventos/{e['id']}", "site": f"https://www.trance.com.br/{e['rota']}/{e['slug']}"}
        if dias <= 21 and (sim >= 0.85 or not c or norm(e["cidade"]) == c):
            mesmo.append(item)
        elif sim >= 0.85:
            edicoes.append(item)
    mesmo.sort(key=lambda i: (-i["semelhanca"], i["dias_de_diferenca"]))
    edicoes.sort(key=lambda i: i["inicio"], reverse=True)
    return {"duplicata_provavel": mesmo, "outras_edicoes": edicoes[:5]}


def lineup(nomes):
    perfis = tudo("perfis?select=slug,nome,categoria,status")
    por_nome = {}
    for p in perfis:
        por_nome.setdefault(norm(p["nome"]), p)
    chaves = list(por_nome)
    existentes, provaveis, novos = [], [], []
    for nome in dict.fromkeys(n.strip() for n in nomes if n.strip()):
        k = norm(nome)
        if k in por_nome:
            p = por_nome[k]
            existentes.append({"nome": nome, "perfil": p["nome"], "slug": p["slug"], "categoria": p["categoria"], "status": p["status"]})
            continue
        perto = difflib.get_close_matches(k, chaves, n=1, cutoff=0.88)
        if perto:
            p = por_nome[perto[0]]
            provaveis.append({"nome": nome, "perfil": p["nome"], "slug": p["slug"], "categoria": p["categoria"]})
        else:
            novos.append(nome)
    return {"existentes": existentes, "provaveis": provaveis, "novos": novos}


# ---------------------------------------------------------------- imagem e geocode
def imagem(origem):
    if re.match(r"^https?://", origem):
        r = requests.get(origem, headers={"User-Agent": UA_NAVEGADOR}, timeout=40, stream=True)
        r.raise_for_status()
        bruto = b""
        for parte in r.iter_content(65536):
            bruto += parte
            if len(bruto) > 25 * 1024 * 1024:
                raise Erro("Imagem maior que 25 MB.")
    else:
        p = pathlib.Path(origem).expanduser()
        if not p.is_file():
            raise Erro(f"Arquivo não encontrado: {origem}")
        bruto = p.read_bytes()
    try:
        img = Image.open(io.BytesIO(bruto))
        img.load()
    except Exception:  # noqa: BLE001
        raise Erro("Não é uma imagem válida (JPG, PNG, WebP ou GIF).")
    img = ImageOps.exif_transpose(img)
    larg_orig, alt_orig = img.size
    if min(img.size) < 300:
        raise Erro(f"Imagem pequena demais ({larg_orig}x{alt_orig}); procure a versão maior.")
    img.thumbnail((1920, 1920))
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
    for q in (86, 78, 70, 60):
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=q, method=5)
        if buf.tell() <= 3_800_000:
            break
    else:
        raise Erro("Não consegui reduzir a imagem para menos de 3,8 MB.")
    caminho = f"{uid()}/{uuid.uuid4()}.webp"
    url, _ = config()
    r = requests.post(f"{url}/storage/v1/object/conta-imagens/{caminho}", data=buf.getvalue(),
                      headers=cabecalhos({"Content-Type": "image/webp", "x-upsert": "false"}), timeout=60)
    if r.status_code >= 300:
        raise Erro(f"Falha ao guardar a imagem ({r.status_code}): {r.text[:200]}")
    return {"ref": "conta:" + caminho, "largura": img.size[0], "altura": img.size[1], "kb": round(buf.tell() / 1024),
            "original": f"{larg_orig}x{alt_orig}"}


def geocode(consulta):
    """Google (Places, pela rota do CMS; chave só no servidor): local, cidade, UF, país ISO-2 e lat/lng prontos para o evento.
    Sem Google no servidor (503) ou sem sessão: cai no Nominatim (OSM), que não devolve UF/ISO."""
    try:
        r = requests.get(f"{CMS}/api/agente/endereco", params={"q": consulta},
                         headers={"Authorization": "Bearer " + sessao()["access_token"]}, timeout=30)
        if r.status_code == 200:
            j = r.json()
            e = j.get("endereco")
            if not e:
                return []
            outras = [x["nome"] + (", " + x["resto"] if x.get("resto") else "") for x in j.get("sugestoes", [])]
            return [{"fonte": "google", "local": e["local"], "cidade": e["cidade"], "uf": e["uf"], "pais_iso": e["pais"],
                     "lat": e["lat"], "lng": e["lng"], "outras_sugestoes": outras}]
    except (Erro, requests.RequestException, ValueError):
        pass
    r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": consulta, "format": "jsonv2", "limit": 3, "addressdetails": 1},
                     headers={"User-Agent": UA, "Accept-Language": "pt-BR"}, timeout=30)
    r.raise_for_status()
    return [{"lat": round(float(x["lat"]), 6), "lng": round(float(x["lon"]), 6), "nome": x["display_name"],
             "cidade": (x.get("address") or {}).get("city") or (x.get("address") or {}).get("town") or (x.get("address") or {}).get("village", ""),
             "estado": (x.get("address") or {}).get("state", ""), "pais": (x.get("address") or {}).get("country", "")} for x in r.json()]


# ---------------------------------------------------------------- Instagram (rota do CMS; token da Meta só no servidor)
def instagram(entrada, perfil=""):
    r = requests.get(f"{CMS}/api/agente/instagram", params={"u": entrada, "perfil": perfil},
                     headers={"Authorization": "Bearer " + sessao()["access_token"]}, timeout=60)
    try:
        j = r.json()
    except ValueError:
        raise Erro(f"CMS respondeu {r.status_code} sem JSON.")
    if r.status_code != 200:
        raise Erro(j.get("erro", f"CMS {r.status_code}"))
    return j


# ---------------------------------------------------------------- candidatos (modo buscar)
GOABASE = "https://www.goabase.net/api/party/json/"


def _janela(dias):
    hoje = dt.date.today()
    return hoje.isoformat(), (hoje + dt.timedelta(days=dias)).isoformat()


def _hora_local(p, k):
    """Data/hora do Goabase (fuso da Europa) na hora local do evento, AAAA-MM-DDTHH:MM."""
    v = p.get(k) or ""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromisoformat(v).astimezone(ZoneInfo(p.get("timezone") or "UTC")).strftime("%Y-%m-%dT%H:%M")
    except Exception:  # noqa: BLE001
        return v[:16]


def candidatos_goabase(paises=(), dias=180, so_festivais=False):
    """Agenda mundial do Goabase (API pública, psytrance). Marca o que já está na base."""
    r = requests.get(GOABASE, params={"limit": 1000}, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    ini, fim = _janela(dias)
    paises = {p.upper() for p in paises}
    eventos = base_eventos()
    saida_ = []
    for p in r.json().get("partylist", []):
        data = _hora_local(p, "dateStart")[:10]
        if not (ini <= data <= fim) or p.get("nameStatus") in ("Canceled", "Cancelled", "Postponed"):
            continue
        if paises and (p.get("isoCountry") or "").upper() not in paises:
            continue
        if so_festivais and p.get("nameType") != "Festival":
            continue
        dup = duplicata(p["nameParty"], data, p.get("nameTown") or "", eventos)["duplicata_provavel"]
        saida_.append({"nome": p["nameParty"], "inicio": _hora_local(p, "dateStart"), "fim": _hora_local(p, "dateEnd"), "tipo": p.get("nameType"),
                       "cidade": p.get("nameTown"), "pais": p.get("isoCountry"), "url": p.get("urlPartyHtml"),
                       "json": p.get("urlPartyJson"), "organizador": p.get("urlOrganizer"), "flyer": p.get("urlImageFull"),
                       "na_base": [{"id": d["id"], "nome": d["nome"], "status": d["status"]} for d in dup]})
    saida_.sort(key=lambda x: x["inicio"] or "")
    novos = [x for x in saida_ if not x["na_base"]]
    return {"fonte": "goabase", "janela": [ini, fim], "total": len(saida_), "novos": len(novos), "itens": saida_}


def goabase_evento(id_ou_url):
    m = re.search(r"(\d{4,})", str(id_ou_url))
    if not m:
        raise Erro("Informe o id ou o link do Goabase.")
    r = requests.get(GOABASE + m.group(1), headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    p = r.json().get("party") or {}
    campos = ["nameParty", "dateStart", "dateEnd", "nameType", "nameCountry", "nameTown", "geoLat", "geoLon", "textLineUp",
              "textLocation", "textEntryFee", "textMore", "nameOrganizer", "textOrganizer", "urlOrganizer", "urlImageFull", "nameStatus", "urlParty", "timezone"]
    d = {k: p.get(k) for k in campos}
    # o Goabase grava a hora com o fuso da Europa (+01:00/+02:00); devolve também na hora local do evento
    try:
        from zoneinfo import ZoneInfo
        fuso = ZoneInfo(p.get("timezone") or "UTC")
        for k in ("dateStart", "dateEnd"):
            if p.get(k):
                d[k + "Local"] = dt.datetime.fromisoformat(p[k]).astimezone(fuso).strftime("%Y-%m-%dT%H:%M")
    except Exception:  # noqa: BLE001
        pass
    return d


def candidatos_recorrentes(meses=14):
    """Festivais da base com edição nos últimos N meses e nenhuma edição futura cadastrada: procurar a próxima."""
    eventos = base_eventos()
    hoje = dt.date.today()
    desde = (hoje - dt.timedelta(days=int(meses * 30.5))).isoformat()
    futuros = [e["nome"] for e in eventos if (e["inicio"] or "")[:10] >= hoje.isoformat()]
    vistos, itens = set(), []
    for e in sorted(eventos, key=lambda e: e["inicio"] or "", reverse=True):
        if not (desde <= (e["inicio"] or "")[:10] < hoje.isoformat()) or e["status"] != "publicado":
            continue
        n = nucleo(e["nome"])
        if not n or n in vistos or any(mesmo_nome(e["nome"], f) >= 0.85 for f in futuros):
            continue
        vistos.add(n)
        itens.append({"nome": e["nome"], "ultima": e["inicio"][:10], "cidade": e["cidade"], "site": e["site"], "instagram": e["instagram"],
                      "id": e["id"], "categoria": e["categoria"]})
    return {"fonte": "recorrentes", "desde": desde, "total": len(itens), "itens": itens}


# ---------------------------------------------------------------- gravar
def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", norm(s))).strip("-")[:110]


def paragrafos(texto):
    """Texto puro -> HTML do CMS (só p/br), escapado. Parágrafos separados por linha em branco."""
    blocos = [b.strip() for b in re.split(r"\n\s*\n", str(texto or "").strip()) if b.strip()]
    return "".join("<p>" + "<br>".join(html.escape(l.strip(), quote=False) for l in b.splitlines() if l.strip()) + "</p>" for b in blocos)


def programacao(v):
    """Lista de nomes, ou lista de {titulo, artistas}, ou texto -> HTML (um artista por linha)."""
    if isinstance(v, str):
        return paragrafos(v)
    if not isinstance(v, list):
        raise Erro("programacao: use lista de nomes, lista de {titulo, artistas} ou texto.")
    if all(isinstance(x, str) for x in v):
        return paragrafos("\n".join(v))
    partes = []
    for bloco in v:
        if not isinstance(bloco, dict) or not isinstance(bloco.get("artistas"), list):
            raise Erro("programacao: cada bloco precisa de 'artistas' (lista).")
        linhas = [html.escape(str(a).strip(), quote=False) for a in bloco["artistas"] if str(a).strip()]
        titulo = html.escape(str(bloco.get("titulo", "")).strip(), quote=False)
        partes.append("<p>" + (f"<strong>{titulo}</strong><br>" if titulo else "") + "<br>".join(linhas) + "</p>")
    return "".join(partes)


def validar(e, passado=False):
    extras = set(e) - PERMITIDOS
    if extras:
        raise Erro("Campos não aceitos: " + ", ".join(sorted(extras)))
    d, avisos = {}, []
    for k in TEXTO:
        d[k] = str(e.get(k) or "").strip()[:300]
    if not d["nome"]:
        raise Erro("nome é obrigatório.")
    d["pais"] = d["pais"] or "Brasil"
    d["categoria"] = e.get("categoria") or "Festivais"
    if d["categoria"] not in CATEGORIAS:
        raise Erro(f"categoria deve ser uma de: {', '.join(CATEGORIAS)}")
    for k in ("inicio", "fim"):
        v = str(e.get(k) or "").strip()
        if v and not DATA.match(v):
            raise Erro(f"{k} inválido: use AAAA-MM-DD ou AAAA-MM-DDTHH:MM.")
        d[k] = v
    if not d["inicio"]:
        raise Erro("inicio é obrigatório.")
    if d["fim"] and d["fim"] < d["inicio"]:
        raise Erro("fim vem antes do início.")
    if (d["fim"] or d["inicio"])[:10] < dt.date.today().isoformat() and not passado:
        raise Erro("Evento já passou (use --passado só se for de propósito).")
    uf = str(e.get("uf") or "").strip().upper()
    if uf and uf not in UFS:
        raise Erro("uf inválida.")
    if d["pais"].lower() == "brasil" and not uf:
        avisos.append("Evento no Brasil sem UF.")
    d["uf"], d["estado"] = uf, UFS.get(uf, "")
    # país em ISO-2 (o geocode do Google devolve): o banco escreve o nome em `pais` sozinho (gatilho regiao_sincroniza)
    iso = str(e.get("pais_iso") or "").strip().upper()
    if iso:
        if not re.fullmatch(r"[A-Z]{2}", iso):
            raise Erro("pais_iso inválido: use o código de 2 letras (BR, PT, DE...).")
        d["pais_iso"] = iso
        if iso != "BR":
            d["uf"], d["estado"] = "", ""
            avisos = [a for a in avisos if a != "Evento no Brasil sem UF."]
    for k, lim in (("lat", 90), ("lng", 180)):
        v = e.get(k)
        if v in (None, ""):
            d[k] = None
            continue
        v = float(str(v).replace(",", "."))
        if not -lim <= v <= lim:
            raise Erro(f"{k} fora do intervalo.")
        d[k] = round(v, 6)
    for k in URLS:
        v = str(e.get(k) or "").strip()
        if v and not re.match(r"^https?://[^\s]{3,}$", v):
            raise Erro(f"{k}: endereço inválido ({v[:60]}).")
        d[k] = v[:1000]
    for k in ("imagem", "logo"):
        v = str(e.get(k) or "").strip()
        # só imagem guardada pelo próprio script (vai para a Duda na aprovação) ou já na Duda; nada de link externo no site
        if v and not (REF.match(v) or re.match(r"^https://irp\.cdn-website\.com/\S+$", v)):
            raise Erro(f"{k}: use a ref conta:… devolvida por 'evento.py imagem'.")
        d[k] = v
    if not d["imagem"]:
        avisos.append("Sem imagem de capa.")
    d["resumo"] = re.sub(r"\s+", " ", str(e.get("resumo") or "")).strip()
    if len(d["resumo"]) > 160:
        raise Erro(f"resumo com {len(d['resumo'])} caracteres (máx. 160).")
    d["release"] = paragrafos(e.get("release"))
    d["programacao"] = programacao(e.get("programacao") or [])
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
    d["slug"] = slugify(e.get("slug") or f"{d['nome']} {d['inicio'][:4] if d['inicio'][:4] not in d['nome'] else ''}")
    if not d["slug"]:
        raise Erro("Não consegui gerar o endereço (slug).")
    d.update(rota="evento", status="pendente", origem="agente")
    return d, avisos


def _sem_acento(t):
    import unicodedata
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower().strip()


def ligar_lineup(d):
    """Line-up -> perfis (eventos.artistas): cada linha do line-up, sem selo/país/"(Live)", igual ao nome de um perfil publicado.
    Os nomes sem perfil vão para as notas do agente (a moderação confere)."""
    linhas = re.split(r"<br>|</p>", re.sub(r"<strong>.*?</strong>", "", d.get("programacao") or ""))
    nomes = []
    for l in linhas:
        t = html.unescape(re.sub(r"<[^>]+>", "", l)).strip()
        t = re.split(r"\s+[-–|•/@]\s+|\s*\(", t)[0].strip(" -–•*:")
        t = re.sub(r"[^\w\s&.'-]", "", t).strip()
        if 2 <= len(t) <= 60 and t not in nomes:
            nomes.append(t)
    if not nomes:
        return [], []
    perfis = rest("GET", "perfis?select=slug,nome&status=eq.publicado&limit=5000").json()
    por_nome = {}
    for p in perfis:
        por_nome.setdefault(_sem_acento(re.sub(r"\s*\(.*\)$", "", p["nome"])), p["slug"])
    ligados, soltos = [], []
    for n in nomes:
        slug = por_nome.get(_sem_acento(n))
        if slug and slug not in ligados:
            ligados.append(slug)
        elif not slug:
            soltos.append(n)
    return ligados, soltos


def slug_livre(base):
    usados = {r["slug"] for r in rest("GET", f"eventos?select=slug&rota=eq.evento&slug=like.{base}*").json()}
    if base not in usados:
        return base
    n = 2
    while f"{base}-{n}" in usados:
        n += 1
    return f"{base}-{n}"


def gravar(arquivo, ensaio=False, passado=False):
    e = json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())
    d, avisos = validar(e, passado)
    eu()  # falha cedo se a sessão não for da equipe
    d["slug"] = slug_livre(d["slug"])
    d["artistas"], soltos = ligar_lineup(d)
    if soltos:
        nota = "Line-up sem perfil no portal: " + ", ".join(soltos[:40])
        d["notas_agente"] = (d["notas_agente"] + "\n" + nota).strip()[:3000]
        avisos.append(f"{len(d['artistas'])} artistas ligados a perfis; {len(soltos)} sem perfil (nas notas).")
    if ensaio:
        return {"ensaio": True, "avisos": avisos, "registro": d}
    r = rest("POST", "eventos?select=id,slug,status,origem", json=d, headers={"Prefer": "return=representation"}).json()[0]
    return {"ok": True, "id": r["id"], "slug": r["slug"], "status": r["status"], "origem": r["origem"], "avisos": avisos,
            "moderacao": f"{CMS}/moderacao/cadastro/eventos/{r['id']}", "editar": f"{CMS}/eventos/{r['id']}"}


def atualizar(id_, arquivo):
    """Completa uma sugestão do agente que ainda está pendente (só os campos enviados; fontes novas somam às antigas)."""
    e = json.loads(sys.stdin.read() if arquivo == "-" else pathlib.Path(arquivo).read_text())
    if not str(id_).isdigit():
        raise Erro("Uso: atualizar <id> <parcial.json>")
    atual = rest("GET", f"eventos?select=id,nome,inicio,fim,status,origem,fontes&id=eq.{id_}").json()
    if not atual:
        raise Erro(f"Evento {id_} não encontrado.")
    a = atual[0]
    if a["origem"] != "agente" or a["status"] != "pendente":
        raise Erro("Só dá para completar sugestão do agente ainda pendente; o resto se edita no CMS.")
    base = {"nome": a["nome"], "inicio": a["inicio"], "fim": a["fim"], "fontes": a["fontes"] or [{"url": "https://www.trance.com.br"}]}
    novos = {k: v for k, v in e.items() if k != "slug"}
    d, avisos = validar({**base, **novos}, passado=True)
    mudar = {k: d[k] for k in novos if k in d}
    if "uf" in novos:
        mudar["estado"] = d["estado"]
    if "fontes" in novos:
        urls = {f["url"] for f in (a["fontes"] or [])}
        mudar["fontes"] = (a["fontes"] or []) + [f for f in d["fontes"] if f["url"] not in urls]
    r = rest("PATCH", f"eventos?id=eq.{id_}&status=eq.pendente&origem=eq.agente&select=id,status",
             json=mudar, headers={"Prefer": "return=representation"}).json()
    if not r:
        raise Erro("Nada atualizado (o evento mudou de situação?).")
    return {"ok": True, "id": int(id_), "campos": sorted(mudar), "moderacao": f"{CMS}/moderacao/cadastro/eventos/{id_}"}


# ---------------------------------------------------------------- linha de comando
def main(args):
    if not args or args[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return
    cmd, resto = args[0], args[1:]
    opc = {a for a in resto if a.startswith("--") and "=" not in a}
    pos = [a for a in resto if not a.startswith("--")]

    def valor(nome):
        for i, a in enumerate(resto):
            if a == nome and i + 1 < len(resto):
                return resto[i + 1]
        return ""

    if cmd == "login":
        saida(login("--colar" in opc))
    elif cmd == "eu":
        saida(eu())
    elif cmd == "sair":
        saida(sair())
    elif cmd == "duplicata":
        cidade = valor("--cidade")
        pos = [p for p in pos if p != cidade]
        if len(pos) < 2:
            raise Erro('Uso: duplicata "<nome>" <AAAA-MM-DD> [--cidade X]')
        saida(duplicata(pos[0], pos[1], cidade))
    elif cmd == "lineup":
        arq = valor("--arquivo")
        nomes = pathlib.Path(arq).read_text().splitlines() if arq else [p for p in pos if p != arq]
        saida(lineup(nomes))
    elif cmd == "imagem":
        if not pos:
            raise Erro("Uso: imagem <url|caminho>")
        saida(imagem(pos[0]))
    elif cmd == "instagram":
        perfil = valor("--perfil")
        pos = [p for p in pos if p != perfil]
        if not pos:
            raise Erro("Uso: instagram <link|@usuario> [--perfil @usuario]")
        saida(instagram(pos[0], perfil))
    elif cmd == "candidatos":
        fonte = pos[0] if pos else ""
        if fonte == "goabase":
            paises = [x for x in valor("--pais").split(",") if x]
            saida(candidatos_goabase(paises, int(valor("--dias") or 180), "--festivais" in opc))
        elif fonte == "recorrentes":
            saida(candidatos_recorrentes(int(valor("--meses") or 14)))
        else:
            raise Erro("Uso: candidatos goabase [--pais BR,PT] [--dias 180] [--festivais] | candidatos recorrentes [--meses 14]")
    elif cmd == "goabase":
        if not pos:
            raise Erro("Uso: goabase <id|link>")
        saida(goabase_evento(pos[0]))
    elif cmd == "geocode":
        saida(geocode(" ".join(pos)))
    elif cmd == "atualizar":
        if len(pos) < 2:
            raise Erro("Uso: atualizar <id> <parcial.json|->")
        saida(atualizar(pos[0], pos[1]))
    elif cmd == "gravar":
        if not pos:
            raise Erro("Uso: gravar <evento.json|-> [--ensaio] [--passado]")
        saida(gravar(pos[0], "--ensaio" in opc, "--passado" in opc))
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
