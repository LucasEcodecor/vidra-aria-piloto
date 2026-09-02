import hmac
from datetime import date, timedelta
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
from supabase import Client, create_client

from calculos import calcular_item, moeda


st.set_page_config(
    page_title="Vidraçaria Piloto",
    page_icon="assets/logo.svg",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #d9e7ef;
        border-radius: 14px;
        padding: 14px 18px;
        box-shadow: 0 4px 18px rgba(17, 59, 82, 0.06);
    }
    </style>
    """,
    unsafe_allow_html=True,
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


def cabecalho() -> None:
    logo, titulo = st.columns([1, 10], vertical_alignment="center")
    with logo:
        st.image("assets/logo.svg", width=72)
    with titulo:
        st.title("Vidraçaria Piloto")
        st.caption("Orçamentos, pedidos, produção e instalação")


def data_brasileira(valor: str | None) -> str:
    if not valor:
        return "—"
    try:
        return date.fromisoformat(valor).strftime("%d/%m/%Y")
    except ValueError:
        return valor


def link_maps(endereco: str) -> str | None:
    endereco = endereco.strip()
    if not endereco:
        return None
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(endereco)}"


def link_whatsapp(telefone: str) -> str | None:
    numeros = "".join(caractere for caractere in telefone if caractere.isdigit())
    if len(numeros) in (10, 11):
        numeros = f"55{numeros}"
    return f"https://wa.me/{numeros}" if len(numeros) >= 12 else None


def preparar_itens(itens: pd.DataFrame) -> tuple[list[dict], float]:
    itens_para_salvar = []
    subtotal = 0.0
    for _, linha in itens.fillna("").iterrows():
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
    return itens_para_salvar, round(subtotal, 2)


def autenticar() -> bool:
    senha_configurada = st.secrets.get("APP_PASSWORD", "")
    if not senha_configurada:
        return True
    if st.session_state.get("autenticado"):
        return True

    cabecalho()
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
            "id,status,valor_total,valor_instalacao,instalacao,observacoes,"
            "validade,created_at,arquivo_gerado,"
            "clientes(nome,endereco,telefone,email),"
            "itens_orcamento(ambiente,tipo_vidro,espessura_mm,largura_mm,"
            "altura_mm,quantidade,acabamento,preco_m2,area_m2,valor_item)"
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

cabecalho()

aba_dashboard, aba_novo, aba_pedidos = st.tabs(
    ["📊 Visão geral", "➕ Novo orçamento", "📋 Pedidos"]
)

with aba_dashboard:
    try:
        orcamentos = carregar_orcamentos(supabase)
        total = len(orcamentos)
        em_aberto = sum(
            item["status"] not in ("Concluído", "Cancelado")
            for item in orcamentos
        )
        producao = sum(item["status"] == "Em produção" for item in orcamentos)
        concluidos = sum(item["status"] == "Concluído" for item in orcamentos)
        valor_total = sum(float(item["valor_total"] or 0) for item in orcamentos)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Orçamentos", total)
        c2.metric("Em aberto", em_aberto)
        c3.metric("Em produção", producao)
        c4.metric("Concluídos", concluidos)
        c5.metric("Valor total", moeda(valor_total))

        if orcamentos:
            st.subheader("Pedidos por status")
            por_status = pd.DataFrame(orcamentos)["status"].value_counts()
            st.bar_chart(por_status)

            st.subheader("Últimos pedidos")
            recentes = []
            for item in orcamentos[:5]:
                cliente = item.get("clientes") or {}
                recentes.append(
                    {
                        "OS": item["id"],
                        "Cliente": cliente.get("nome", ""),
                        "Status": item["status"],
                        "Valor": moeda(float(item["valor_total"] or 0)),
                        "Validade": data_brasileira(item.get("validade")),
                    }
                )
            st.dataframe(recentes, use_container_width=True, hide_index=True)
        else:
            st.info("Cadastre o primeiro orçamento para iniciar o teste.")
    except Exception as erro:
        st.error(f"Não foi possível carregar o painel: {erro}")

with aba_novo:
    st.subheader("Dados do cliente")

    if "itens_orcamento" not in st.session_state:
        st.session_state.itens_orcamento = item_inicial()
    if "editor_versao" not in st.session_state:
        st.session_state.editor_versao = 0

    mensagem_salva = st.session_state.pop("mensagem_orcamento", None)
    if mensagem_salva:
        st.success(mensagem_salva)

    c1, c2 = st.columns(2)
    nome = c1.text_input("Nome do cliente *", key="nome_cliente")
    telefone = c2.text_input("Telefone/WhatsApp", key="telefone_cliente")
    email = c1.text_input("E-mail", key="email_cliente")
    endereco = c2.text_input(
        "Endereço completo da instalação",
        placeholder="Rua, número, bairro, cidade e estado",
        key="endereco_cliente",
    )

    st.subheader("Peças de vidro")
    st.caption("Use as medidas em milímetros. Adicione uma linha para cada peça.")
    itens_editados = st.data_editor(
        st.session_state.itens_orcamento,
        key=f"editor_itens_{st.session_state.editor_versao}",
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "ambiente": "Ambiente",
            "tipo_vidro": "Tipo de vidro",
            "espessura_mm": st.column_config.NumberColumn(
                "Espessura (mm)", min_value=1.0
            ),
            "largura_mm": st.column_config.NumberColumn(
                "Largura (mm)", min_value=1.0
            ),
            "altura_mm": st.column_config.NumberColumn(
                "Altura (mm)", min_value=1.0
            ),
            "quantidade": st.column_config.NumberColumn(
                "Quantidade", min_value=1, step=1
            ),
            "acabamento": "Acabamento",
            "preco_m2": st.column_config.NumberColumn(
                "Preço por m²", min_value=0.0, format="R$ %.2f"
            ),
        },
    )

    c1, c2, c3 = st.columns(3)
    instalacao = c1.checkbox("Incluir instalação", key="incluir_instalacao")
    valor_instalacao = c2.number_input(
        "Valor da instalação",
        min_value=0.0,
        value=250.0,
        step=10.0,
        disabled=not instalacao,
        key="valor_instalacao",
    )
    validade = c3.date_input(
        "Validade",
        value=date.today() + timedelta(days=15),
        format="DD/MM/YYYY",
        key="validade_orcamento",
    )
    observacoes = st.text_area("Observações", key="observacoes_orcamento")

    try:
        itens_para_salvar, subtotal = preparar_itens(itens_editados)
        total_estimado = subtotal + (valor_instalacao if instalacao else 0.0)
        r1, r2, r3 = st.columns(3)
        r1.metric("Subtotal das peças", moeda(subtotal))
        r2.metric(
            "Instalação",
            moeda(valor_instalacao if instalacao else 0.0),
        )
        r3.metric("Total do orçamento", moeda(total_estimado))
        erro_calculo = None
    except (TypeError, ValueError, KeyError) as erro:
        itens_para_salvar, subtotal, total_estimado = [], 0.0, 0.0
        erro_calculo = erro
        st.warning("Revise as medidas, quantidades e preços das peças.")

    salvar = st.button("Salvar orçamento", type="primary")

    if salvar:
        if not nome.strip():
            st.warning("Informe o nome do cliente.")
        elif itens_editados.empty:
            st.warning("Adicione pelo menos uma peça.")
        elif erro_calculo:
            st.warning("Corrija os dados das peças antes de salvar.")
        else:
            try:
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
                            "valor_total": round(total_estimado, 2),
                            "observacoes": observacoes.strip(),
                        }
                    )
                    .execute()
                    .data[0]
                )
                for item in itens_para_salvar:
                    item["orcamento_id"] = orcamento["id"]
                supabase.table("itens_orcamento").insert(itens_para_salvar).execute()

                st.session_state.mensagem_orcamento = (
                    f"Orçamento #{orcamento['id']} criado — "
                    f"{moeda(total_estimado)}"
                )
                st.session_state.itens_orcamento = item_inicial()
                st.session_state.editor_versao += 1
                st.rerun()
            except Exception as erro:
                st.error(f"Erro ao salvar o orçamento: {erro}")

with aba_pedidos:
    try:
        orcamentos = carregar_orcamentos(supabase)
        if not orcamentos:
            st.info("Nenhum orçamento cadastrado.")
        else:
            st.subheader("Localizar pedidos")
            f1, f2 = st.columns([2, 3])
            busca = f1.text_input(
                "Buscar",
                placeholder="Nome do cliente ou número da OS",
            ).strip().lower()
            status_escolhidos = f2.multiselect("Filtrar por status", STATUS)

            filtrados = []
            for item in orcamentos:
                cliente = item.get("clientes") or {}
                corresponde_busca = (
                    not busca
                    or busca in str(item["id"]).lower()
                    or busca in cliente.get("nome", "").lower()
                )
                corresponde_status = (
                    not status_escolhidos or item["status"] in status_escolhidos
                )
                if corresponde_busca and corresponde_status:
                    filtrados.append(item)

            if not filtrados:
                st.info("Nenhum pedido encontrado com esses filtros.")
                st.stop()

            linhas = []
            for item in filtrados:
                cliente = item.get("clientes") or {}
                endereco = cliente.get("endereco", "").strip()
                linhas.append(
                    {
                        "OS": item["id"],
                        "Cliente": cliente.get("nome", ""),
                        "Status": item["status"],
                        "Valor": moeda(float(item["valor_total"] or 0)),
                        "Validade": data_brasileira(item.get("validade")),
                        "Arquivo local": "Gerado" if item["arquivo_gerado"] else "Pendente",
                        "Mapa": link_maps(endereco),
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
                for item in filtrados
            }
            escolha = st.selectbox("Selecionar pedido", list(opcoes))
            pedido = opcoes[escolha]
            cliente = pedido.get("clientes") or {}

            st.subheader(f"Detalhes da OS #{pedido['id']}")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Status", pedido["status"])
            d2.metric("Valor total", moeda(float(pedido["valor_total"] or 0)))
            d3.metric("Validade", data_brasileira(pedido.get("validade")))
            d4.metric(
                "Instalação",
                moeda(float(pedido["valor_instalacao"] or 0))
                if pedido["instalacao"]
                else "Não inclusa",
            )

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Cliente:** {cliente.get('nome') or '—'}")
                st.markdown(f"**Telefone:** {cliente.get('telefone') or '—'}")
                st.markdown(f"**E-mail:** {cliente.get('email') or '—'}")
            with c2:
                st.markdown(
                    f"**Endereço da instalação:**  \n{cliente.get('endereco') or '—'}"
                )
                botoes = st.columns(2)
                mapa = link_maps(cliente.get("endereco", ""))
                whatsapp = link_whatsapp(cliente.get("telefone", ""))
                if mapa:
                    botoes[0].link_button(
                        "Abrir no Maps", mapa, use_container_width=True
                    )
                if whatsapp:
                    botoes[1].link_button(
                        "Abrir WhatsApp", whatsapp, use_container_width=True
                    )

            st.markdown("**Peças do pedido**")
            itens_pedido = []
            for item in pedido.get("itens_orcamento") or []:
                itens_pedido.append(
                    {
                        "Ambiente": item["ambiente"],
                        "Vidro": item["tipo_vidro"],
                        "Espessura": f"{float(item['espessura_mm']):g} mm",
                        "Medida": (
                            f"{float(item['largura_mm']):g} × "
                            f"{float(item['altura_mm']):g} mm"
                        ),
                        "Qtd.": item["quantidade"],
                        "Acabamento": item["acabamento"],
                        "Área": f"{float(item['area_m2']):.3f} m²",
                        "Valor": moeda(float(item["valor_item"])),
                    }
                )
            if itens_pedido:
                st.dataframe(
                    itens_pedido,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("Este pedido não possui peças cadastradas.")

            if pedido.get("observacoes"):
                st.info(f"Observações: {pedido['observacoes']}")

            st.markdown("**Andamento do pedido**")
            s1, s2 = st.columns([3, 1], vertical_alignment="bottom")
            novo_status = s1.selectbox(
                "Alterar status",
                STATUS,
                index=STATUS.index(pedido["status"]),
            )
            if s2.button(
                "Salvar status", type="primary", use_container_width=True
            ):
                supabase.table("orcamentos").update(
                    {"status": novo_status}
                ).eq("id", pedido["id"]).execute()
                st.success("Status atualizado.")
                st.rerun()
    except Exception as erro:
        st.error(f"Não foi possível carregar os pedidos: {erro}")

st.divider()
st.caption("Versão piloto — utilize somente dados fictícios durante os testes.")
