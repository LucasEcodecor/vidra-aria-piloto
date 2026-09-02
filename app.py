import hmac
from datetime import date, timedelta
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
from supabase import Client, create_client

from calculos import calcular_item, moeda


st.set_page_config(
    page_title="Vidraçaria Piloto",
    page_icon="🪟",
    layout="wide",
)

STATUS = [
    "Orçamento",
    "Aguardando aprovação",
    "Aprovado",
    "Em produção",
    "Pronto",
    "Instalação",
    "Concluído",
    "Cancelado",
]

COLUNAS_ITENS = [
    "ambiente",
    "tipo_vidro",
    "espessura_mm",
    "largura_mm",
    "altura_mm",
    "quantidade",
    "acabamento",
    "preco_m2",
]


def item_inicial() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ambiente": "Banheiro",
                "tipo_vidro": "Temperado incolor",
                "espessura_mm": 8.0,
                "largura_mm": 700.0,
                "altura_mm": 1800.0,
                "quantidade": 1,
                "acabamento": "Lapidado",
                "preco_m2": 350.0,
            }
        ]
    )


def autenticar() -> bool:
    senha_configurada = st.secrets.get("APP_PASSWORD", "")
    if not senha_configurada:
        return True
    if st.session_state.get("autenticado"):
        return True

    st.title("🪟 Vidraçaria Piloto")
    senha = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar", type="primary"):
        if hmac.compare_digest(senha, str(senha_configurada)):
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


@st.cache_resource
def conectar(url: str, chave: str) -> Client:
    return create_client(url, chave)


def carregar_orcamentos(cliente: Client) -> list[dict]:
    resposta = (
        cliente.table("orcamentos")
        .select(
            "id,status,valor_total,validade,created_at,arquivo_gerado,"
            "clientes(nome,endereco)"
        )
        .order("created_at", desc=True)
        .execute()
    )
    return resposta.data or []


if not autenticar():
    st.stop()

if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
    st.error("Configure SUPABASE_URL e SUPABASE_KEY nos Secrets do Streamlit.")
    st.stop()

supabase_url = str(st.secrets["SUPABASE_URL"]).strip()
supabase_key = str(st.secrets["SUPABASE_KEY"]).strip()
supabase = conectar(supabase_url, supabase_key)

st.title("🪟 Vidraçaria Piloto")
st.caption("Orçamentos, pedidos, produção e instalação")

aba_dashboard, aba_novo, aba_pedidos = st.tabs(
    ["📊 Visão geral", "➕ Novo orçamento", "📋 Pedidos"]
)

with aba_dashboard:
    try:
        orcamentos = carregar_orcamentos(supabase)
        total = len(orcamentos)
        aprovados = sum(item["status"] == "Aprovado" for item in orcamentos)
        producao = sum(item["status"] == "Em produção" for item in orcamentos)
        concluidos = sum(item["status"] == "Concluído" for item in orcamentos)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Orçamentos", total)
        c2.metric("Aprovados", aprovados)
        c3.metric("Em produção", producao)
        c4.metric("Concluídos", concluidos)

        if orcamentos:
            por_status = pd.DataFrame(orcamentos)["status"].value_counts()
            st.bar_chart(por_status)
        else:
            st.info("Cadastre o primeiro orçamento para iniciar o teste.")
    except Exception as erro:
        st.error(f"Não foi possível carregar o painel: {erro}")

with aba_novo:
    st.subheader("Dados do cliente")

    if "itens_orcamento" not in st.session_state:
        st.session_state.itens_orcamento = item_inicial()

    with st.form("form_orcamento"):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome do cliente *")
        telefone = c2.text_input("Telefone/WhatsApp")
        email = c1.text_input("E-mail")
        endereco = c2.text_input("Endereço da instalação")

        st.subheader("Peças de vidro")
        itens_editados = st.data_editor(
            st.session_state.itens_orcamento,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "ambiente": "Ambiente",
                "tipo_vidro": "Tipo de vidro",
                "espessura_mm": st.column_config.NumberColumn("Espessura (mm)", min_value=1.0),
                "largura_mm": st.column_config.NumberColumn("Largura (mm)", min_value=1.0),
                "altura_mm": st.column_config.NumberColumn("Altura (mm)", min_value=1.0),
                "quantidade": st.column_config.NumberColumn("Quantidade", min_value=1, step=1),
                "acabamento": "Acabamento",
                "preco_m2": st.column_config.NumberColumn(
                    "Preço por m²",
                    min_value=0.0,
                    format="R$ %.2f",
                ),
            },
        )

        c1, c2, c3 = st.columns(3)
        instalacao = c1.checkbox("Incluir instalação")
        valor_instalacao = c2.number_input(
            "Valor da instalação",
            min_value=0.0,
            value=250.0,
            step=10.0,
        )
        validade = c3.date_input("Validade", value=date.today() + timedelta(days=15))
        observacoes = st.text_area("Observações")
        salvar = st.form_submit_button("Salvar orçamento", type="primary")

    if salvar:
        if not nome.strip():
            st.warning("Informe o nome do cliente.")
        elif itens_editados.empty:
            st.warning("Adicione pelo menos uma peça.")
        else:
            try:
                itens_para_salvar = []
                subtotal = 0.0
                for _, linha in itens_editados.fillna("").iterrows():
                    calculo = calcular_item(
                        largura_mm=float(linha["largura_mm"]),
                        altura_mm=float(linha["altura_mm"]),
                        quantidade=int(linha["quantidade"]),
                        preco_m2=float(linha["preco_m2"]),
                    )
                    subtotal += calculo["valor_item"]
                    itens_para_salvar.append(
                        {
                            **{coluna: linha[coluna] for coluna in COLUNAS_ITENS},
                            "quantidade": int(linha["quantidade"]),
                            **calculo,
                        }
                    )

                total = subtotal + (valor_instalacao if instalacao else 0.0)
                cliente_criado = (
                    supabase.table("clientes")
                    .insert(
                        {
                            "nome": nome.strip(),
                            "telefone": telefone.strip(),
                            "email": email.strip(),
                            "endereco": endereco.strip(),
                        }
                    )
                    .execute()
                    .data[0]
                )
                orcamento = (
                    supabase.table("orcamentos")
                    .insert(
                        {
                            "cliente_id": cliente_criado["id"],
                            "status": "Aguardando aprovação",
                            "validade": validade.isoformat(),
                            "instalacao": instalacao,
                            "valor_instalacao": valor_instalacao if instalacao else 0.0,
                            "valor_total": round(total, 2),
                            "observacoes": observacoes.strip(),
                        }
                    )
                    .execute()
                    .data[0]
                )
                for item in itens_para_salvar:
                    item["orcamento_id"] = orcamento["id"]
                supabase.table("itens_orcamento").insert(itens_para_salvar).execute()

                st.success(
                    f"Orçamento #{orcamento['id']} criado — {moeda(total)}"
                )
                st.session_state.itens_orcamento = item_inicial()
            except Exception as erro:
                st.error(f"Erro ao salvar o orçamento: {erro}")

with aba_pedidos:
    try:
        orcamentos = carregar_orcamentos(supabase)
        if not orcamentos:
            st.info("Nenhum orçamento cadastrado.")
        else:
            linhas = []
            for item in orcamentos:
                cliente = item.get("clientes") or {}
                endereco = cliente.get("endereco", "").strip()
                linhas.append(
                    {
                        "OS": item["id"],
                        "Cliente": cliente.get("nome", ""),
                        "Status": item["status"],
                        "Valor": item["valor_total"],
                        "Validade": item["validade"],
                        "Arquivo local": "Gerado" if item["arquivo_gerado"] else "Pendente",
                        "Mapa": (
                            "https://www.google.com/maps/search/?api=1&query="
                            f"{quote_plus(endereco)}"
                            if endereco
                            else None
                        ),
                    }
                )
            st.dataframe(
                linhas,
                use_container_width=True,
                hide_index=True,
                column_config={"Mapa": st.column_config.LinkColumn(
                    "Mapa", display_text="Abrir no Maps"
                )},
            )

            opcoes = {
                f"OS #{item['id']} — {(item.get('clientes') or {}).get('nome', '')}": item
                for item in orcamentos
            }
            escolha = st.selectbox("Selecionar pedido", list(opcoes))
            pedido = opcoes[escolha]
            novo_status = st.selectbox(
                "Alterar status",
                STATUS,
                index=STATUS.index(pedido["status"]),
            )
            if st.button("Salvar novo status", type="primary"):
                supabase.table("orcamentos").update(
                    {"status": novo_status}
                ).eq("id", pedido["id"]).execute()
                st.success("Status atualizado.")
                st.rerun()
    except Exception as erro:
        st.error(f"Não foi possível carregar os pedidos: {erro}")
