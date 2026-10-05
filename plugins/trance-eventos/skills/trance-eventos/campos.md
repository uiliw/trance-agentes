# Campos do evento (`evento.py gravar`)

O script recusa qualquer campo fora desta lista e grava sempre `rota='evento'`, `status='pendente'`, `origem='agente'`.

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
| `imagem` | `conta:…` | Ref devolvida por `evento.py imagem` (flyer oficial). |
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
