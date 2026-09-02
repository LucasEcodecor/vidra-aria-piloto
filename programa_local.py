import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, Button, Frame, Label, Text, Tk, messagebox

from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from supabase import Client, create_client

from calculos import moeda


load_dotenv()


def nome_seguro(texto: str) -> str:
    texto = re.sub(r"[^A-Za-z0-9À-ÿ_-]+", "_", texto.strip())
    return texto.strip("_") or "cliente"


def conectar() -> Client:
    url = os.getenv("SUPABASE_URL", "")
    chave = os.getenv("SUPABASE_KEY", "")
    if not url or not chave:
        raise RuntimeError("Configure SUPABASE_URL e SUPABASE_KEY no arquivo .env")
    return create_client(url, chave)


def criar_pdf(pedido: dict, pasta_base: Path) -> Path:
    cliente = pedido.get("clientes") or {}
    itens = pedido.get("itens_orcamento") or []
    pasta = pasta_base / f"OS-{pedido['id']:06d}_{nome_seguro(cliente.get('nome', 'cliente'))}"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"OS-{pedido['id']:06d}.pdf"

    pdf = canvas.Canvas(str(arquivo), pagesize=A4)
    largura, altura = A4
    y = altura - 20 * mm
    pdf.setTitle(f"Ordem de Serviço {pedido['id']}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(18 * mm, y, f"ORDEM DE SERVIÇO #{pedido['id']}")
    y -= 12 * mm

    pdf.setFont("Helvetica", 10)
    dados = [
        f"Cliente: {cliente.get('nome', '')}",
        f"Telefone: {cliente.get('telefone', '')}",
        f"Endereço: {cliente.get('endereco', '')}",
        f"Status: {pedido.get('status', '')}",
        f"Valor: {moeda(float(pedido.get('valor_total', 0)))}",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    ]
    for linha in dados:
        pdf.drawString(18 * mm, y, linha)
        y -= 6 * mm

    y -= 5 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(18 * mm, y, "LISTA DE CORTE")
    y -= 8 * mm

    for indice, item in enumerate(itens, start=1):
        if y < 35 * mm:
            pdf.showPage()
            y = altura - 20 * mm
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(18 * mm, y, f"Peça {indice} — {item.get('ambiente', '')}")
        y -= 5 * mm
        pdf.setFont("Helvetica", 9)
        linhas = [
            f"Vidro: {item.get('tipo_vidro', '')} | Espessura: {item.get('espessura_mm', '')} mm",
            f"Medida: {item.get('largura_mm', '')} x {item.get('altura_mm', '')} mm | Quantidade: {item.get('quantidade', '')}",
            f"Acabamento: {item.get('acabamento', '')} | Área total: {item.get('area_m2', '')} m²",
        ]
        for linha in linhas:
            pdf.drawString(22 * mm, y, linha)
            y -= 5 * mm
        y -= 3 * mm

    pdf.save()
    return arquivo


def abrir_pasta(caminho: Path) -> None:
    pasta = caminho.parent
    if sys.platform.startswith("win"):
        os.startfile(pasta)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(pasta)], check=False)
    else:
        subprocess.run(["xdg-open", str(pasta)], check=False)


class Aplicativo:
    def __init__(self, janela: Tk) -> None:
        self.janela = janela
        self.janela.title("Vidraçaria — Programa local")
        self.janela.geometry("760x500")

        cabecalho = Frame(janela)
        cabecalho.pack(fill="x", padx=16, pady=16)
        Label(cabecalho, text="Vidraçaria — Ordens de Serviço", font=("Arial", 16, "bold")).pack(side=LEFT)
        Button(cabecalho, text="Sincronizar aprovados", command=self.sincronizar).pack(side=RIGHT)

        self.log = Text(janela, wrap="word")
        self.log.pack(fill=BOTH, expand=True, padx=16, pady=(0, 16))
        self.escrever("Pronto. Clique em 'Sincronizar aprovados'.")

    def escrever(self, mensagem: str) -> None:
        self.log.insert(END, mensagem + "\n")
        self.log.see(END)
        self.janela.update_idletasks()

    def sincronizar(self) -> None:
        try:
            cliente = conectar()
            pasta_base = Path(os.getenv("PASTA_ORDENS", "ordens_servico")).expanduser()
            resposta = (
                cliente.table("orcamentos")
                .select("*,clientes(nome,telefone,endereco),itens_orcamento(*)")
                .eq("status", "Aprovado")
                .eq("arquivo_gerado", False)
                .order("id")
                .execute()
            )
            pedidos = resposta.data or []
            if not pedidos:
                self.escrever("Nenhuma ordem aprovada aguardando geração.")
                return

            ultimo_arquivo = None
            for pedido in pedidos:
                arquivo = criar_pdf(pedido, pasta_base)
                cliente.table("orcamentos").update(
                    {
                        "arquivo_gerado": True,
                        "arquivo_gerado_em": datetime.now().astimezone().isoformat(),
                    }
                ).eq("id", pedido["id"]).execute()
                self.escrever(f"OS #{pedido['id']} gerada: {arquivo}")
                ultimo_arquivo = arquivo

            if ultimo_arquivo:
                abrir_pasta(ultimo_arquivo)
            messagebox.showinfo("Concluído", f"{len(pedidos)} ordem(ns) gerada(s).")
        except Exception as erro:
            self.escrever(f"ERRO: {erro}")
            messagebox.showerror("Erro", str(erro))


if __name__ == "__main__":
    raiz = Tk()
    Aplicativo(raiz)
    raiz.mainloop()

