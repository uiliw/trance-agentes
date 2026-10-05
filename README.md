# Agentes do Trance.com.br (plugin do Claude Code)

Para quem é da **equipe do CMS** (app.trance.com.br). Versão 1.1.0.

## Instalar (uma vez)

No Claude Code:

```
/plugin marketplace add uiliw/trance-agentes
/plugin install trance-eventos@trance-agentes
```

Precisa de acesso ao repositório privado no GitHub (o Claude Code usa o seu login do git/gh) e de Python 3 com
`requests` e `Pillow` (`pip install requests pillow`).

## Entrar (uma vez por computador)

Num terminal comum (fora do Claude Code), rode o comando que a skill mostrar, algo como:

```
python3 ~/.claude/plugins/.../skills/trance-eventos/evento.py login
```

Abre o CMS no navegador: clique em "Conectar terminal" e digite no terminal o código do seu app autenticador.

## Usar

```
/trance-eventos https://site-do-festival.com
/trance-eventos @perfil_do_evento
/trance-eventos /caminho/do/flyer.jpg
/trance-eventos buscar brasil 180d
```

Tudo vai como sugestão para a Moderação do CMS; nada é publicado sem aprovação.

## Atualizar

```
/plugin marketplace update trance-agentes
```
