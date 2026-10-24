# Agente /trance

O agente do Trance.com.br cadastra e atualiza **eventos, artistas, gravadoras, lojas, serviços e os textos das regiões**, liga eventos aos artistas e artistas às gravadoras, busca o que ainda falta no portal e revisa a base. Antes de gravar, sempre mostra um relatório com os dados como vão ficar e pergunta o que gravar e como: **publicar direto** no site ou **deixar na Moderação** do CMS. Tudo fica gravado em seu nome.

Versão 2.1.0 · Mac ou Windows · Claude Desktop (aba Code) ou terminal · Python 3 · Conta do CMS com app autenticador

> Saiu a versão **2.1.0** (23/10/2026). Atualize (último passo da instalação) e abra uma sessão nova. O que mudou está na aba Novidades.

## Novidades

O que entrou desde a versão 1.4.0. Para receber, atualize o plugin (passo a passo).

### 2.1.0 — 23/10/2026 · crews

- **Crews:** o agente cadastra coletivos e produtoras de festa (página `/crew/…` com apresentação, cidade, logo, capa, links, artistas e eventos), com o mesmo relatório e a mesma escolha entre publicar direto e deixar na Moderação. Publicando direto, logo e capa novos vão como proposta na Moderação.
- **Buscar crews:** lista os nomes citados no campo "crew" dos perfis que ainda não têm página, sem gravadoras e agências, com quantos artistas citam cada um.
- **Vínculos da crew na hora:** ligar e desligar artistas e eventos de uma crew vale na hora, sem Moderação. A crew aparece no perfil dos artistas e na página dos eventos.
- **Crews e serviços no evento:** o cadastro do evento já pode trazer a crew que organiza e os serviços (som, infraestrutura, alimentação, tenda de cura…); evento que já está no site também ganha esses vínculos na hora.
- **Revisar e inativar:** a revisão aponta crews sem artistas, sem eventos ou incompletas, e o agente também tira crews do site (arquivadas, com confirmação).

### 2.0.0 — 23/10/2026 · publicar direto, vínculos, inativar

- **Publicar direto ou deixar na Moderação:** antes de gravar um lote (eventos, artistas, gravadoras, lojas, serviços, sets ou textos de região), o agente pergunta uma vez se é para publicar direto no site ou deixar na Moderação como antes. Publicando direto, cadastro novo já entra no ar e cadastro publicado é editado na hora, sem proposta.
- **Imagens de quem publica direto:** flyer, capa, logo, foto e galeria vão para uma fila automática que sobe tudo para o site em 1 ou 2 minutos, sem passar pela Moderação. Gravadora é a exceção: o logo novo vai como proposta na Moderação.
- **Vínculos sempre na hora:** ligar e desligar artista de evento, e artista de gravadora, não passa mais pela Moderação, nem para tirar. Os vínculos continuam aparecendo no relatório antes de gravar.
- **Inativar cadastro:** o agente tira do site perfis, eventos, gravadoras, lojas, serviços e sets (fica arquivado, nunca é apagado), sempre com a lista do que vai sair e sua confirmação antes. O motivo fica nas notas do agente. O autor pode editar e reenviar pela conta.trance.com.br (volta para a Moderação) e o CMS tem "Publicar de novo".
- **Criadores de conteúdo / UGC:** nova categoria de serviço; o agente já cadastra criadores de conteúdo como serviço.

### 1.9.3 — 15/10/2026 · regiões

- **País novo pelo CMS:** administradores criam país em **Cena › Novo país** (nome, código de duas letras e continente). Já entraram Chipre, Macedônia do Norte, Panamá, Emirados Árabes Unidos e Irã. Quando o país não existe, o agente avisa que é preciso criá-lo lá.

### 1.9.2 — 15/10/2026 · correção

- **Sempre em português:** o agente às vezes respondia em inglês; agora relatórios, perguntas e avisos saem sempre em português.
- **Região que não existe (ex.: Chipre):** as regiões são uma lista fixa e o CMS só edita o texto, não cria região nova. O agente agora explica isso logo (em vez de pedir para criar no CMS) e mostra quantos cadastros cada região tem: a página /regiao/… só aparece com 3 ou mais cadastros publicados.

### 1.9.1 — 15/10/2026 · correção

- **Texto com &lt;p&gt; aparecendo no site:** quando a apresentação vinha em HTML, as tags saíam escritas no texto (ex.: "&lt;p&gt;Hexaliohm é…"). Agora o agente converte para texto antes de gravar. Os 5 perfis afetados já foram corrigidos.

### 1.9.0 — 15/10/2026 · regiões

- **Textos das regiões:** o agente escreve a apresentação e os textos do Google das páginas de região (/regiao/acre, /regiao/nordeste, /regiao/portugal…) e manda como proposta na Moderação, uma por região.
- Dá para pedir várias de uma vez ("escreva os textos dos estados que estão vazios"): ele mostra o relatório e grava todas juntas; na Moderação, filtre por **Região** + **Agente** e aprove em lote.

### 1.8.0 — 14/10/2026 · vínculos

- **Ligar artista a evento vale na hora:** acrescentar artistas ao line-up de um evento não passa mais pela Moderação (só soma perfis que existem; perfil pendente aparece quando for aprovado).
- Tirar artista de um evento continua como proposta na Moderação.

### 1.7.0 — 14/10/2026 · gravadoras

- **Selo novo junto com o artista:** se o artista cita uma gravadora que ainda não está no portal, o agente pesquisa o selo na mesma rodada e mostra no relatório em "Gravadoras novas". Aprovando, grava a gravadora primeiro e já liga o artista a ela.
- Enquanto a gravadora espera aprovação, o nome dela aparece no perfil como texto; vira link quando ela for aprovada na Moderação.
- **Revisão de gravadoras incompletas:** lista as gravadoras sem logo, apresentação, país, estilos, descrição do Google ou nenhum link, e propõe o que faltar.

### 1.6.0 — 14/10/2026 · propostas, sets, redes

- **Evento já publicado:** data nova, flyer, local, ingresso, textos ou links viram proposta de alteração na Moderação, com antes e depois.
- **Sets em perfil que já existe:** até 3 sets ou lançamentos do SoundCloud, sem repetir os que o perfil já tem.
- **Spotify e Bandcamp** nos perfis de artista (no site, as redes viraram ícones).
- **Imagens sem tamanho mínimo:** imagem pequena não é mais recusada; o relatório só avisa para procurar uma versão maior.
- **Lojas e serviços:** as categorias definem em quais páginas o negócio aparece (/lojas/vestuario, /terapias-holisticas…) e a primeira sai no cartão da lista, então a principal vem primeiro.
- **Revisão:** agora acha lojas e serviços sem categoria, logo, resumo ou cidade, perfis sem resumo, e testa links do Spotify, Bandcamp e YouTube.

### 1.5.0 — 10/10/2026 · cadastro completo

- Todo cadastro sai com todos os campos que existirem na web: resumo para o Google, apresentação, foto, capa e galeria (perfil), flyer, capa e logo (evento).
- O relatório mostra a linha "Faltando:" com o que não foi achado e onde o agente procurou.
- Cadastro que já existe com campos vazios ganha uma proposta para completá-los.

## Instalar no Claude Desktop

### 1. Aceitar o convite do GitHub

O plugin fica num repositório privado. Aceite o convite que chegou por e-mail ou neste link:

[github.com/uiliw/trance-agentes/invitations](https://github.com/uiliw/trance-agentes/invitations)

### 2. Preparar o computador

Uma vez só, no terminal (Mac: app Terminal · Windows: PowerShell).

**Mac:**

Confira o Python. Se o Mac pedir para instalar as ferramentas de linha de comando, aceite (o git vem junto):

```
python3 --version
```

Instale as duas bibliotecas que o agente usa:

```
python3 -m pip install --user requests pillow
```

> Se aparecer `externally-managed-environment`, rode de novo com `--break-system-packages` no fim.

Entre no GitHub pelo terminal, para o Claude conseguir baixar o plugin privado. Sem Homebrew, baixe o instalador em [cli.github.com](https://cli.github.com).

```
brew install gh
gh auth login
gh auth setup-git
```

**Windows:**

Instale o Python, o Git e o GitHub CLI (se algum já estiver instalado, o comando só avisa):

```
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
winget install -e --id GitHub.cli
```

> Sem o `winget`: baixe em [python.org](https://www.python.org/downloads/) (marque **Add python.exe to PATH**), [git-scm.com](https://git-scm.com/download/win) e [cli.github.com](https://cli.github.com).

**Feche e abra o PowerShell** e instale as duas bibliotecas que o agente usa:

```
python -m pip install --user requests pillow
```

> Se `python` não for reconhecido, use `py` no lugar (vale para todos os comandos desta página).

Entre no GitHub pelo terminal, para o Claude conseguir baixar o plugin privado:

```
gh auth login
gh auth setup-git
```

### 3. Abrir uma sessão local no Claude Desktop

Na aba **Code**, comece uma sessão **local** e escolha uma pasta como projeto (por exemplo, uma pasta "trance" em Documentos).

### 4. Instalar o plugin

Uma vez só, na caixa de mensagem da aba Code.

```
/plugin marketplace add uiliw/trance-agentes
```

```
/plugin install trance-eventos@trance-agentes
```

O plugin se chama `trance-eventos` por histórico, mas traz o `/trance` completo. Também dá pelo menu **+ › Plugins › Add plugin**. Depois de instalar, abra uma sessão nova.

### 5. Conectar ao CMS

Uma vez por computador.

- Mande `/trance` com qualquer pedido. Na primeira vez, o agente responde com o comando de login, já com o caminho certo.
- Abra o terminal integrado da aba Code com <kbd>Control</kbd> + <kbd>`</kbd> (ou pelo menu **View**) e rode o comando lá. Ele tem este formato:

**Mac:**

```
python3 …/skills/trance/evento.py login
```

**Windows:**

```
python …\skills\trance\evento.py login
```

- O CMS abre no navegador. Entre normalmente, se pedir, e clique em **Conectar terminal**.
- Volte ao terminal e digite o **código de 6 dígitos do app autenticador** (o mesmo do login do CMS).

Aparecendo seu nome e o seu papel na equipe, está pronto. Quem já fez o login numa versão anterior não precisa repetir.

### 6. Atualizar quando sair versão nova

O Claude não atualiza o plugin sozinho: o app guarda uma cópia do marketplace e só vê a versão nova depois de atualizar essa cópia. Por isso o botão de atualizar pode aparecer desativado, mostrando a versão antiga.

Na caixa de mensagem da aba Code, um comando por vez.

```
/plugin marketplace update trance-agentes
```

```
/plugin update trance-eventos@trance-agentes
```

```
/reload-plugins
```

Ou abra uma sessão nova. Para conferir a versão: `/plugin` › aba **Installed** › `trance-eventos` (a atual é a **2.1.0**).

**Continuou na versão antiga?** Reinstale (o login no CMS continua valendo):

```
/plugin marketplace remove trance-agentes
/plugin marketplace add uiliw/trance-agentes
/plugin install trance-eventos@trance-agentes
```

**Sem os comandos com /**, rode no terminal do mesmo computador (Mac: Terminal · Windows: PowerShell) e depois abra uma sessão nova no app:

```
claude plugin marketplace update trance-agentes
claude plugin update trance-eventos@trance-agentes
```

**Para atualizar sozinho daqui em diante:** `/plugin` › aba **Marketplaces** › `trance-agentes` › **Enable auto-update**. A atualização roda alguns minutos depois da primeira mensagem de cada sessão.

> Se der erro de acesso ao repositório, confira se aceitou o convite do GitHub e se rodou `gh auth login` e `gh auth setup-git` (passo 2).

## Pelo terminal

O mesmo agente roda no Claude Code direto no terminal (Mac: app Terminal · Windows: PowerShell), sem o Claude Desktop. Faça antes os passos 1 e 2 da instalação (convite do GitHub, Python e `gh`).

### 1. Instalar o Claude Code

Uma vez só, no terminal.

**Mac:**

```
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows:**

```
irm https://claude.ai/install.ps1 | iex
```

No Windows o Claude Code precisa do Git instalado (passo 2).

Feche e abra o terminal de novo e confira:

```
claude --version
```

### 2. Abrir o Claude numa pasta

Use sempre a mesma pasta (na primeira vez o Claude pergunta se confia nela: responda que sim, e abre o navegador para entrar na sua conta do Claude).

**Mac:**

```
mkdir -p ~/Documents/trance
cd ~/Documents/trance
claude
```

**Windows:**

```
mkdir -Force $HOME\Documents\trance
cd $HOME\Documents\trance
claude
```

### 3. Instalar o plugin

Uma vez só, dentro do Claude.

```
/plugin marketplace add uiliw/trance-agentes
```

```
/plugin install trance-eventos@trance-agentes
```

Saia com `/exit` e abra de novo com `claude` para o plugin carregar.

### 4. Conectar ao CMS

Uma vez por computador.

- Mande `/trance` com qualquer pedido. Na primeira vez, o agente responde com o comando de login.
- Abra **outra janela do terminal** (Mac: <kbd>⌘</kbd> + <kbd>N</kbd> no Terminal · Windows: abra outro PowerShell) e rode o comando lá: o código do app precisa ser digitado num terminal comum, fora do Claude.
- O CMS abre no navegador: clique em **Conectar terminal** e digite na janela nova o **código de 6 dígitos**.

Aparecendo seu nome, volte para a janela do Claude e avise que terminou.

### 5. Atalhos do terminal

- **Flyer ou print:** digite `/trance ` e arraste o arquivo do Finder (Mac) ou do Explorador de Arquivos (Windows) para a janela (o caminho é colado sozinho), ou cole uma imagem copiada com <kbd>Control</kbd> + <kbd>V</kbd> (no Windows, <kbd>Alt</kbd> + <kbd>V</kbd>).
- **Perguntas do agente:** escolha com as setas, marque com <kbd>Espaço</kbd> quando der para escolher várias, confirme com <kbd>Enter</kbd>.
- **Parar no meio:** <kbd>Esc</kbd>. Sair: `/exit`. Atualizar o Claude Code: `claude update`.
- **Atualizar o plugin:** `/plugin marketplace update trance-agentes`, depois `/plugin update trance-eventos@trance-agentes`, e abra o `claude` de novo (detalhes no passo de atualizar).

## Como usar

Escreva `/trance` e o pedido em português, do jeito que falaria. O agente entende se é evento, artista, gravadora, loja, busca ou revisão; na dúvida, ele pergunta. Todo pedido segue os mesmos passos:

1. **Pesquisa** nas fontes oficiais (site, ingresso, Instagram, SoundCloud, Spotify, Bandcamp, Resident Advisor, Goabase, Discogs) e confere o que já existe no portal, para não duplicar. Nada é gravado nesta etapa.
2. **Relatório** com tudo como vai ficar: endereço final no site, datas, local, imagens (flyer, capa, logo), line-up separado em "com perfil", "a confirmar" e "novos", gravadoras novas, vínculos, fontes, o que ficou incerto e a linha "Faltando:".
3. **Sua escolha**: uma pergunta com o que gravar (o evento, quais artistas e gravadoras novos, quais vínculos) e outra, uma vez por lote, se é para **publicar direto** ou **deixar na Moderação**. Dá para pedir ajustes antes: "troca a capa", "o nome é X".
4. **Gravação**: publicando direto, entra no ar na hora (imagens em 1 ou 2 minutos); deixando na Moderação, vira sugestão pendente (cadastro novo) ou proposta de alteração (cadastro que já está no site). Vínculos valem sempre na hora.
5. **Relatório final** com o link de cada item (no site ou na Moderação) e o que não deu certo.

O que ficou na Moderação: CMS › **Moderação**, filtro **Agente**. Cada item mostra as fontes e as notas do agente; no evento aparece a lista de artistas vinculados e quais perfis ainda esperam aprovação (aprove os perfis, e as gravadoras novas, para o vínculo aparecer no site).

## O que dá para pedir

### Evento

```
/trance https://link-do-site-ou-do-ingresso
```

```
/trance cadastre o Pulsar Festival 2028
```

```
/trance atualize o Pulsar Festival 2028: saiu o flyer e mudou a data
```

- Aceita link (site, Sympla, Shotgun, RA, Facebook, Goabase), nome do evento ou flyer/print arrastado para a mensagem.
- Grava flyer, capa e logo; local no mapa; line-up ligado aos perfis do portal.
- Oferece cadastrar os **artistas do line-up** que ainda não têm perfil (até 15 por vez) e já liga o evento a eles.
- O endereço sai pelo tipo: `/festival/…`, `/festa/…`, `/feira-exposicao/…` ou `/curso-retiro/…`.
- `2.0` Ligar e tirar artistas do line-up vale na hora, sem Moderação.
- Line-up ou horário que saiu depois numa sugestão ainda pendente: mande o print e peça para completar.
- `1.6` **Evento já publicado** que mudou (data, flyer, local, ingresso, textos): mostra antes e depois e, conforme a sua escolha, edita direto ou manda proposta para a Moderação.

### Artista

```
/trance cadastre o DJ Fulano (instagram.com/djfulano)
```

```
/trance atualize o perfil do Ekanta
```

```
/trance adicione os sets novos do Ekanta
```

- Monta o perfil: categoria (DJ, VJ, performance…), se produz, país e estado, estilos, gravadoras, links, foto, capa, galeria e até 3 sets do SoundCloud.
- `1.6` Links do **Spotify e Bandcamp** junto com site, Instagram, Facebook, SoundCloud e YouTube.
- `1.6` **Sets em perfil que já existe:** até 3 por vez, sem repetir os que já estão no portal.
- `1.7` Gravadora citada que ainda não está no portal é pesquisada e cadastrada junto (veja Gravadora).
- Procura os **próximos eventos** em que ele toca: os que já estão no portal (para vincular) e os que faltam (para cadastrar).
- Perfil que já está no site: antes e depois no relatório; edita direto ou vira **proposta de alteração** na Moderação, como você escolher.

### Gravadora

```
/trance cadastre a gravadora Polifonia Records
```

```
/trance revise as gravadoras incompletas
```

- Busca o selo no Discogs: apresentação, links (site, Instagram, SoundCloud, Bandcamp, Beatport), logo e catálogo.
- Cruza o catálogo com o portal: artistas com perfil (para ligar ao selo) e sem perfil (para cadastrar).
- O artista ligado ganha o link para a gravadora no perfil e aparece na página da gravadora. `2.0` Ligar e desligar vale na hora.
- `1.7` **Selo novo junto com o artista:** o relatório traz "Gravadoras novas"; aprovando, a gravadora é gravada primeiro e o artista já sai ligado. Até a aprovação dela, o nome aparece no perfil como texto.
- `1.7` Gravadora publicada sem logo, apresentação, país, estilos, descrição ou links ganha proposta com o que faltar.

### Crew

```
/trance cadastre a crew Origens Gathering
```

```
/trance buscar crews
```

- `2.1` Coletivo ou produtora que organiza festas e reúne artistas. Página `/crew/…` com apresentação, cidade, logo, capa, links, artistas e eventos.
- Mostra os artistas que citam a crew no perfil e as edições dela já cadastradas, para ligar junto. Ligar e desligar artistas e eventos vale na hora.
- Selo, agência ou booking não é crew: gravadora tem modo próprio, e o agente avisa quando o nome é o mesmo de uma gravadora.

### Loja ou serviço

```
/trance cadastre a loja Fulana Psy Wear (instagram.com/fulanapsy)
```

- Monta a ficha com tipo, categorias (as mesmas do CMS), cidade, links, logo e capa. Endereço: `/loja/…` ou `/servico/…`.
- `1.6` As categorias decidem em quais páginas o negócio aparece (/lojas/vestuario, /terapias-holisticas…); a primeira sai no cartão da lista, então a principal vem primeiro.
- Só entra o que tem relação com a cena e a cultura psicodélica.
- `2.0` Nova categoria de serviço: **Criadores de Conteúdo / UGC**.

### Região

```
/trance escreva os textos dos estados que estão vazios
```

```
/trance melhore o texto da região de Goiás
```

- `1.9` Apresentação da página (cena local, festivais marcantes, como chegar) e os textos do Google, para regiões do Brasil, estados, continentes e países.
- Região está sempre no ar: publicando direto, o texto muda o site na hora; deixando na Moderação, vai como proposta, uma por região.
- Mostra antes quais regiões estão sem texto e quais já têm proposta esperando.

### Buscar o que falta

```
/trance buscar eventos brasil 180d
```

```
/trance buscar artistas brasil
```

```
/trance buscar gravadoras brasil ativas desde 2023
```

```
/trance buscar serviços de decoração em SC
```

- **Eventos:** regiões `brasil`, `america-latina`, `europa`, `asia-oceania`, `africa` ou `mundo`; período em dias ou meses.
- **Artistas:** nomes dos line-ups dos próximos eventos que ainda não têm perfil.
- **Gravadoras:** selos de psytrance no Discogs, ativos e do Brasil primeiro, em lotes de cerca de 30.
- `2.1` **Crews:** nomes citados no campo "crew" dos perfis que ainda não têm página (sem gravadoras e agências).
- O agente mostra uma lista numerada; responda com os números, "todos" ou "nenhum".

### Revisar a base

```
/trance revise a base
```

```
/trance revise os vínculos dos artistas com os eventos
```

```
/trance revise as lojas e serviços incompletos
```

- Confere vínculos evento ↔ artista e artista ↔ gravadora, duplicatas, dados incompletos, links fora do ar, estilos e séries.
- `1.6` Incompletos inclui perfis sem resumo e lojas e serviços sem categoria, logo, resumo ou cidade; links testam também Spotify, Bandcamp e YouTube.
- `1.7` Gravadoras sem logo, apresentação, país, estilos, descrição do Google ou nenhum link.
- `2.1` Crews sem artistas, sem eventos ou sem logo, apresentação ou cidade.
- Só lê: mostra a contagem de cada problema com exemplos e corrige apenas o que você escolher.
- Vínculos e grafias são aprovados em lote no próprio relatório e valem na hora; o resto é corrigido item por item, direto ou na Moderação. Duplicata nunca é apagada sozinha.

### Inativar (tirar do site)

```
/trance inative o evento Pulsar Festival 2028: foi cancelado
```

```
/trance tire do site o perfil duplicado do DJ Fulano
```

- `2.0` Perfis, eventos, gravadoras, lojas, serviços, sets `2.1` e crews. O cadastro fica arquivado: nunca é apagado.
- Mostra antes o que vai sair do site (e, no perfil, quantos sets e eventos ligados ele tem) e só inativa depois da sua confirmação.
- O motivo fica nas notas do agente. O autor pode editar e reenviar pela conta.trance.com.br (volta para a Moderação) e o CMS tem "Publicar de novo".

## Regras que o agente segue

- **Não inventa**: Sem fonte, o campo fica vazio e vira nota para a Moderação.
- **Cadastro completo**: Procura todos os campos antes de desistir; o que não achou aparece em "Faltando:" com onde procurou.
- **Fonte oficial primeiro**: Site, ingresso e perfil oficial; agregadores só confirmam. Cada dado guarda o link de onde veio.
- **Texto próprio**: Resumo e apresentação em português, com palavras próprias, sem tom de anúncio.
- **Sem dados pessoais**: Nada de telefone, e-mail pessoal ou endereço de casa.
- **Você decide o que vai ao ar**: Antes de gravar, pergunta uma vez por lote: publicar direto ou deixar na Moderação (cadastro novo pendente, mudança como proposta). Nunca apaga, nunca dá destaque nem dono a cadastro, e só inativa com a sua confirmação.

## Se algo der errado

**"Sem sessão" ou "Sessão expirada"**

Rode o login de novo num terminal (passo "Conectar ao CMS").

**"Fora da equipe do CMS"**

A conta precisa estar em Equipe no CMS. Fale com o Willy.

**"Imagem pequena demais"**

Era a versão antiga recusando imagem pequena. Desde a 1.6.0 ela é aceita, com um aviso no relatório: atualize o plugin.

**"python3" ou "python" não encontrado**

No Mac use `python3`; no Windows, `python` ou `py`. Se nenhum funcionar, refaça o passo 2 e abra o terminal de novo.

**O terminal não reagiu ao clicar em Conectar**

Pare com <kbd>Control</kbd> + <kbd>C</kbd>, rode o mesmo comando com `--colar` no fim e cole o código que a página mostra.

**"Já existe perfil" ou "Já existe"**

O cadastro já está no portal: peça para atualizar, e o agente faz uma proposta de alteração.

**"Já há uma proposta em análise"**

Só cabe uma proposta por cadastro de cada vez: aprove ou recuse a anterior na Moderação, ou peça para publicar direto.

**"gravadoras que não existem na base"**

A gravadora precisa ser cadastrada antes do artista. Peça para o agente cadastrar o selo junto (versão 1.7.0).

**Gravadora aparece como texto no perfil, sem link**

Ela ainda está pendente: aprove a gravadora na Moderação e o nome vira link.

**"&lt;p&gt;" escrito no meio do texto no site**

Era a versão antiga escapando o HTML da apresentação. Corrigido na 1.9.1: atualize o plugin e avise o Willy se achar algum cadastro assim.

**"new row violates row-level security policy for table alteracoes" em região**

Proposta de região só funciona a partir da 1.9.0: atualize o plugin.

**Link do Instagram**

Ainda não funciona: a Meta precisa liberar o acesso. Mande o print do post e cole a legenda.

**"/trance" não aparece**

Atualize o plugin (último passo da instalação) e abra uma sessão nova.

**Botão de atualizar desativado ou versão antiga**

Atualize primeiro o marketplace com `/plugin marketplace update trance-agentes` e depois o plugin (passo a passo). Se continuar na versão antiga, **feche o Claude Desktop** e reinstale do zero pelo terminal (o login no CMS continua valendo):

**Mac:**

```
claude plugin uninstall trance-eventos@trance-agentes
claude plugin marketplace remove trance-agentes
rm -rf ~/.claude/plugins/marketplaces/trance-agentes ~/.claude/plugins/cache/trance-agentes
claude plugin marketplace add uiliw/trance-agentes
claude plugin install trance-eventos@trance-agentes
```

**Windows:**

```
claude plugin uninstall trance-eventos@trance-agentes
claude plugin marketplace remove trance-agentes
Remove-Item -Recurse -Force $HOME\.claude\plugins\marketplaces\trance-agentes, $HOME\.claude\plugins\cache\trance-agentes
claude plugin marketplace add uiliw/trance-agentes
claude plugin install trance-eventos@trance-agentes
```

Depois abra o Claude Desktop de novo. Sem o comando `claude` no terminal, instale antes pela aba Pelo terminal.

**"command not found: claude" ou "claude não é reconhecido"**

Feche e abra o terminal. Se continuar, rode o instalador de novo e siga o que ele mostrar no fim.

**O /plugin não acha o repositório**

Confira se aceitou o convite do GitHub e se rodou `gh auth setup-git`.

Guia com abas e botões de copiar: https://claude.ai/artifact/M9chziN4qoBEbcDVhFkU9a
