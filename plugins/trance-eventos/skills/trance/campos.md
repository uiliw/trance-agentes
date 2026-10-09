# Campos do evento (`evento.py gravar`)

O script recusa qualquer campo fora desta lista e grava sempre `status='pendente'` e `origem='agente'`. O endereço sai do tipo (`categoria`): Festivais → `/festival/<slug>`, Festas → `/festa/<slug>`, Feiras / Exposições → `/feira-exposicao/<slug>`, Cursos / Retiros → `/curso-retiro/<slug>` (o ensaio mostra a URL final).

| Campo | Formato | Regra |
|---|---|---|
| `nome` | texto (≤ 300) | **Obrigatório.** Nome oficial da edição, como a produtora escreve: `Universo Paralello #20`, `Mundo de Oz 2027`. |
| `slug` | opcional | Gerado do nome + ano; o script resolve colisão. Só informe para corrigir algo estranho. |
| `categoria` | `Festivais` \| `Festas` \| `Feiras / Exposições` \| `Cursos / Retiros` | Festival = vários dias/palcos ou camping; festa = uma noite/dia. |
| `inicio` | `AAAA-MM-DD` ou `AAAA-MM-DDTHH:MM` | **Obrigatório.** Hora local do evento. |
| `fim` | idem | Vazio se não divulgado. Não pode ser antes do início. |
| `resumo` | texto (≤ 160) | 1–2 frases para cards e Google. O que é + quando + onde. |
| `release` | texto puro | 2–5 parágrafos separados por linha em branco (o script converte para HTML). Palavras próprias, pt-BR. |
| `programacao` | lista | Nomes (`["Astrix", "Ajja"]`) ou palcos (`[{"titulo": "Main Stage", "artistas": [...]}]`). Grafia do perfil quando existir. Sem line-up divulgado: lista vazia. |
| `imagem` | `conta:…` | Imagem de capa: ref devolvida por `evento.py imagem` (arte horizontal/banner; sem ela, use o flyer). |
| `flyer` | `conta:…` | Flyer oficial da edição (arte vertical). Aparece no hover da agenda da home e na coluna da direita da página do evento. |
| `logo` | `conta:…` | Opcional. |
| `local` | texto | Nome do lugar e/ou endereço (`Sítio Paraíso, Estrada X km 5`). |
| `cidade` | texto | Cidade do evento. |
| `uf` | sigla | Só Brasil (`MG`, `BA`…). O script preenche o nome do estado. |
| `pais` | texto | Em português (`Brasil`, `Portugal`, `Grécia`). Padrão `Brasil`. |
| `lat`, `lng` | número | Do site/mapa oficial ou `evento.py geocode` conferido. |
| `site`, `instagram`, `facebook`, `youtube`, `video`, `ingresso` | URL http(s) | Oficiais. `video` = aftermovie/teaser no YouTube. `instagram` = perfil do evento (não o post). |
| `fontes` | lista `{url, usado}` | **Obrigatório.** Toda URL usada e o que veio dela (`"datas, local e line-up"`). |
| `notas_agente` | texto | O que ficou incerto ou deduzido, artistas sem perfil, avisos para quem vai aprovar. |

## Exemplo

```json
{
  "nome": "Exemplo Festival 2027",
  "categoria": "Festivais",
  "inicio": "2027-03-12T16:00",
  "fim": "2027-03-15T14:00",
  "resumo": "Festival de psytrance com três dias de música e camping em Itabirito (MG), de 12 a 15 de março de 2027.",
  "release": "Primeiro parágrafo...\n\nSegundo parágrafo...",
  "programacao": [{"titulo": "Main Stage", "artistas": ["Astrix", "Ajja"]}, {"titulo": "Chill Out", "artistas": ["Kaya Project"]}],
  "imagem": "conta:0b6c…/9f1e….webp",
  "local": "Sítio Exemplo",
  "cidade": "Itabirito",
  "uf": "MG",
  "pais": "Brasil",
  "lat": -20.253,
  "lng": -43.801,
  "site": "https://exemplofestival.com.br",
  "instagram": "https://www.instagram.com/exemplofestival/",
  "ingresso": "https://www.sympla.com.br/evento/exemplo-festival-2027/123456",
  "fontes": [
    {"url": "https://exemplofestival.com.br", "usado": "datas, local, line-up"},
    {"url": "https://www.sympla.com.br/evento/exemplo-festival-2027/123456", "usado": "ingresso, horários"}
  ],
  "notas_agente": "Horário de término estimado pelo Sympla. Artistas sem perfil: Fulano, Beltrano."
}
```

## Evento: artistas indicados à mão

`"artistas": ["slug-1", "slug-2"]` soma perfis (publicados ou pendentes) aos que o line-up liga sozinho. Slug que não existe = erro.

## Perfil (artista.py gravar)

| Campo | Valor | Observação |
|---|---|---|
| `nome` | texto | Nome artístico como o artista usa. Obrigatório. |
| `slug` | texto | Opcional (sai do nome). A URL final vem no ensaio (`/dj/<slug>`, `/vj/<slug>`…). |
| `categoria` | `djs` · `vjs` · `foto-video` · `cenografia` · `performances` · `artes-visionarias` · `oficinas` | Padrão `djs`. |
| `produtor` | `true`/`false` | Só para DJ (tag "Produtor"). |
| `pais` | ISO-2 (`BR`, `PT`, `IL`…) | Padrão `BR`. |
| `uf` | sigla (`SP`, `SC`…) | Só Brasil; define a região. |
| `gravadoras` | lista de slugs | Gravadoras do portal (`/gravadora/<slug>`): link no perfil e o artista na página do selo. Slug inexistente = erro. |
| `crew` | texto | Crew, núcleo ou gravadora que ainda não está na base (avise no relatório para a equipe cadastrar). |
| `estilos` | lista de slugs | Só estilos da Wikidelic (`full-on`, `progressive`…); slug inexistente = erro. |
| `resumo` | até 160 caracteres | 1 ou 2 frases. |
| `release` | texto (parágrafos com linha em branco) | Palavras próprias, pt-BR. |
| `foto`, `capa` | `conta:…` | Ref de `evento.py imagem`. Foto quadrada de preferência. |
| `site`, `instagram`, `facebook`, `soundcloud`, `youtube`, `video` | URL | `soundcloud` = página do artista. |
| `sets` | até 3 links (ou `{soundcloud, titulo?, tipo: set|release}`) | Faixas/sets do SoundCloud; título e capa vêm do oEmbed; entram pendentes com o perfil. |
| `fontes` | lista de `{url, usado}` | Obrigatório. |
| `notas_agente` | texto | O que ficou incerto. |

Exemplo:

```json
{
  "nome": "Fulano",
  "categoria": "djs",
  "produtor": true,
  "pais": "BR",
  "uf": "SC",
  "gravadoras": ["zenon-records"],
  "crew": "Coletivo Fulano",
  "estilos": ["full-on"],
  "resumo": "DJ e produtor de full-on de Florianópolis.",
  "release": "Primeiro parágrafo.\n\nSegundo parágrafo.",
  "foto": "conta:0b6c…/9f1e….webp",
  "instagram": "https://instagram.com/fulano",
  "soundcloud": "https://soundcloud.com/fulano",
  "sets": ["https://soundcloud.com/fulano/set-ao-vivo"],
  "fontes": [{"url": "https://soundcloud.com/fulano", "usado": "bio, país, sets"}],
  "notas_agente": "UF deduzida da bio (\"Floripa\")."
}
```
