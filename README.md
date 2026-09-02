# Vidraçaria Piloto

Sistema de treinamento para uma vidraçaria, dividido em duas partes:

- **Nuvem:** cadastro de clientes, peças, orçamentos e acompanhamento do pedido.
- **Computador:** sincronização de pedidos aprovados, criação de pasta e geração de ordem de serviço em PDF.

## Problema do piloto

A vidraçaria recebe medidas e pedidos por WhatsApp, papel e planilhas. O objetivo
é centralizar as informações, calcular o orçamento e reduzir erros entre venda,
produção e instalação.

## Fluxo

`Orçamento → Aguardando aprovação → Aprovado → Em produção → Pronto → Instalação → Concluído`

## 1. Criar um projeto separado no Supabase

Não use o banco da Ecodecor. Crie um projeto novo chamado `vidracaria-piloto`.

1. Abra **SQL Editor**.
2. Cole todo o conteúdo de `supabase.sql`.
3. Clique em **Run**.
4. Use apenas dados fictícios durante o piloto.

## 2. Publicar o sistema na nuvem

No Streamlit Community Cloud, use:

- Repositório: `LucasEcodecor/vidra-aria-piloto`
- Branch: `main`
- Arquivo principal: `app.py`
- Python: `3.12`

Nos **Secrets**, use o conteúdo de `secrets.toml.example`, substituindo os
valores. Nunca envie as chaves para o GitHub.

## 3. Rodar o programa do computador

No Windows:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements-local.txt
copy .env.example .env
python programa_local.py
```

Edite o arquivo `.env` e informe a URL, a Publishable key e a pasta onde as
ordens de serviço serão criadas. O `.env` não deve ser enviado ao GitHub.

## Próximas etapas

- Gerar orçamento em PDF para o cliente.
- Cadastro de tabela de preços por tipo de vidro.
- Login individual por funcionário.
- Controle de estoque e agenda de instalação.
- Empacotar `programa_local.py` como `.exe` com atalho.

