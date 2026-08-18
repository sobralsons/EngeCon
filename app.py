from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

import matplotlib.pyplot as plt
import pandas as pd
import pdfplumber
import streamlit as st

from finance_core import (
    CATEGORY_OPTIONS,
    DEFAULT_SETTINGS,
    calculate_metrics,
    categorize_transaction,
    fetch_settings,
    fetch_transactions,
    format_brl,
    get_engine,
    init_db,
    insert_transaction,
    parse_brl,
    save_settings,
    seed_demo_data,
)

APP_TITLE = "Financial Analytics — Cafeterias"


def parse_csv(uploaded_file: BytesIO) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    normalized = {str(col).strip().lower(): col for col in df.columns}
    required = {"date", "description", "amount"}
    if not required.issubset(normalized):
        raise ValueError("O CSV precisa conter as colunas: date, description e amount.")

    result = pd.DataFrame(
        {
            "date": pd.to_datetime(df[normalized["date"]], errors="coerce").dt.date,
            "description": df[normalized["description"]].astype(str),
            "amount": df[normalized["amount"]].map(parse_brl),
        }
    )
    return result.dropna(subset=["date"])


def parse_generic_pdf(uploaded_file: BytesIO) -> pd.DataFrame:
    rows: list[dict] = []
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                parts = line.split()
                if len(parts) < 3:
                    continue
                try:
                    parsed_date = pd.to_datetime(parts[0], dayfirst=True, errors="raise").date()
                except Exception:
                    continue
                try:
                    amount = parse_brl(parts[-1])
                except Exception:
                    continue
                description = " ".join(parts[1:-1]).strip()
                if description:
                    rows.append({"date": parsed_date, "description": description, "amount": amount})
    return pd.DataFrame(rows, columns=["date", "description", "amount"])


def render_chart(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Ainda não há dados suficientes para o gráfico.")
        return

    chart = df.copy()
    chart["tx_date"] = pd.to_datetime(chart["tx_date"])
    daily = chart.groupby("tx_date", as_index=False)["amount"].sum()

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(daily["tx_date"], daily["amount"], marker="o")
    ax.axhline(0, linewidth=0.8)
    ax.set_title("Resultado líquido diário")
    ax.set_xlabel("Data")
    ax.set_ylabel("R$")
    fig.autofmt_xdate()
    st.pyplot(fig, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="☕", layout="wide")
    st.title("☕ Financial Analytics — Cafeterias")
    st.caption(
        "Aplicação de portfólio com dados fictícios para controle financeiro, "
        "análise de desempenho e apoio à decisão."
    )

    engine = get_engine()
    init_db(engine)

    with st.sidebar:
        st.header("Configuração")
        selection = st.radio("Unidade", ["Consolidado", "Cafeteria A", "Cafeteria B"], index=0)
        unit_ids = {
            "Consolidado": [1, 2],
            "Cafeteria A": [1],
            "Cafeteria B": [2],
        }[selection]

        today = date.today()
        start = st.date_input("Data inicial", today - timedelta(days=90))
        end = st.date_input("Data final", today)

        if st.button("Carregar dados fictícios de demonstração", use_container_width=True):
            inserted = seed_demo_data(engine)
            st.success(f"{inserted} lançamento(s) de demonstração inserido(s).")

    tabs = st.tabs(["Dashboard", "Lançamentos", "Importar dados", "Custos e metas", "Sobre o projeto"])

    with tabs[0]:
        df = fetch_transactions(engine, unit_ids, start, end)
        metrics = calculate_metrics(df)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Receitas", format_brl(metrics.revenue))
        c2.metric("Despesas", format_brl(metrics.expenses))
        c3.metric("Resultado líquido", format_brl(metrics.net_result))
        c4.metric("Ticket médio", format_brl(metrics.average_ticket))

        st.subheader("Evolução no período")
        render_chart(df)

        st.subheader("Distribuição por categoria")
        if df.empty:
            st.info("Nenhum lançamento no período selecionado.")
        else:
            categories = (
                df.assign(expense=lambda x: x["amount"].where(x["amount"] < 0, 0).abs())
                .groupby("category", as_index=False)["expense"]
                .sum()
                .sort_values("expense", ascending=False)
            )
            st.dataframe(categories, use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader("Novo lançamento")
        unit_name = st.selectbox("Unidade", ["Cafeteria A", "Cafeteria B"])
        unit_id = 1 if unit_name == "Cafeteria A" else 2
        tx_date = st.date_input("Data do lançamento", date.today(), key="manual_date")
        description = st.text_input("Descrição")
        amount = st.number_input("Valor (positivo = receita; negativo = despesa)", value=0.0, step=10.0)
        suggested = categorize_transaction(description, amount)
        category = st.selectbox("Categoria", CATEGORY_OPTIONS, index=CATEGORY_OPTIONS.index(suggested))

        if st.button("Salvar lançamento", type="primary"):
            if not description.strip() or amount == 0:
                st.warning("Informe uma descrição e um valor diferente de zero.")
            else:
                inserted = insert_transaction(engine, unit_id, tx_date, description, amount, category)
                if inserted:
                    st.success("Lançamento salvo.")
                else:
                    st.info("Esse lançamento já existe e foi ignorado.")

        st.subheader("Lançamentos no período")
        tx = fetch_transactions(engine, unit_ids, start, end)
        st.dataframe(tx, use_container_width=True, hide_index=True)

    with tabs[2]:
        st.subheader("Importar dados")
        st.caption(
            "Para a versão pública, o importador usa um formato genérico e não contém "
            "regras específicas de bancos, fornecedores ou dados reais."
        )
        import_unit = st.selectbox("Unidade de destino", ["Cafeteria A", "Cafeteria B"], key="import_unit")
        import_unit_id = 1 if import_unit == "Cafeteria A" else 2

        uploaded = st.file_uploader("Arquivo", type=["csv", "pdf"])
        if uploaded is not None:
            try:
                imported = parse_csv(uploaded) if uploaded.name.lower().endswith(".csv") else parse_generic_pdf(uploaded)
                st.write(f"{len(imported)} linha(s) identificada(s).")
                st.dataframe(imported.head(50), use_container_width=True, hide_index=True)

                if st.button("Confirmar importação"):
                    count = 0
                    for row in imported.itertuples(index=False):
                        if insert_transaction(
                            engine,
                            import_unit_id,
                            row.date,
                            row.description,
                            row.amount,
                            source="import",
                        ):
                            count += 1
                    st.success(f"{count} lançamento(s) novo(s) importado(s).")
            except Exception as exc:
                st.error(f"Não foi possível processar o arquivo: {exc}")

        st.markdown(
            """
**Formato CSV esperado**

```csv
date,description,amount
2026-07-01,Vendas balcão,2500.00
2026-07-02,Fornecedor de insumos,-850.00
```
"""
        )

    with tabs[3]:
        st.subheader("Custos e metas")
        settings_unit = st.selectbox("Unidade", ["Cafeteria A", "Cafeteria B"], key="settings_unit")
        settings_unit_id = 1 if settings_unit == "Cafeteria A" else 2
        current = fetch_settings(engine, settings_unit_id)

        labels = {
            "fixed_payroll": "Folha fixa",
            "fixed_rent": "Aluguel",
            "fixed_services": "Serviços",
            "fixed_marketing": "Marketing",
            "fixed_systems": "Sistemas",
            "fixed_taxes": "Impostos",
            "variable_supplies": "Insumos",
            "working_capital_target": "Meta de capital de giro",
            "ticket_goal": "Meta de ticket médio",
        }

        updated: dict[str, float] = {}
        cols = st.columns(3)
        for idx, key in enumerate(DEFAULT_SETTINGS):
            with cols[idx % 3]:
                updated[key] = st.number_input(
                    labels[key],
                    value=float(current[key]),
                    step=50.0 if key != "ticket_goal" else 1.0,
                    key=f"setting_{settings_unit_id}_{key}",
                )

        if st.button("Salvar custos e metas"):
            save_settings(engine, settings_unit_id, updated)
            st.success("Configurações salvas localmente.")

        st.info(
            "Todos os valores iniciais desta versão pública são fictícios e servem apenas "
            "para demonstração técnica."
        )

    with tabs[4]:
        st.subheader("Sobre")
        st.markdown(
            """
Este projeto foi criado para transformar uma necessidade operacional de uma pequena
rede de cafeterias em uma aplicação de análise financeira.

A versão pública foi reconstruída para portfólio com **dados fictícios**, mantendo os
principais conceitos técnicos: persistência em SQLite, deduplicação de lançamentos,
tratamento de dados, categorização, indicadores financeiros, importação de arquivos e
dashboard em Streamlit.

**Tecnologias:** Python, Pandas, SQLAlchemy, SQLite, Streamlit, Matplotlib, PDFPlumber e Pytest.
"""
        )


if __name__ == "__main__":
    main()
