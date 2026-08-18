# ☕ Financial Analytics — Cafeterias

Aplicação em Python criada para organizar e analisar a operação financeira de duas unidades fictícias de cafeteria.

> **Portfólio público:** todos os nomes, valores e dados desta versão são fictícios. Nenhum extrato, saldo, fornecedor, credencial ou informação financeira real é distribuído neste repositório.

## O problema

Pequenas operações costumam acompanhar receitas, despesas, custos e metas em fontes separadas. O projeto transforma esse processo em uma aplicação única, com persistência local, importação de dados e indicadores para apoiar decisões.

## Funcionalidades

- dashboard consolidado ou por unidade;
- receitas, despesas, resultado líquido e ticket médio;
- persistência em SQLite;
- cadastro manual de lançamentos;
- deduplicação por fingerprint;
- categorização automática por regras;
- importação de CSV;
- parser genérico de PDF;
- configuração de custos e metas por unidade;
- dados fictícios de demonstração;
- testes automatizados e CI com GitHub Actions.

## Arquitetura

```text
Streamlit
   ↓
finance_core.py
   ├── regras e tratamento
   ├── indicadores
   ├── deduplicação
   └── persistência
          ↓
       SQLite
```

A interface foi separada da lógica principal para tornar o código mais testável e mais fácil de evoluir.

## Tecnologias

`Python` `Pandas` `SQLAlchemy` `SQLite` `Streamlit` `Matplotlib` `PDFPlumber` `Pytest` `GitHub Actions`

## Como executar

Requer Python 3.12+.

```bash
git clone https://github.com/sobralsons/EngeCon.git
cd EngeCon

python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Depois:

```bash
pip install -r requirements.txt
streamlit run app.py
```

O banco local é criado automaticamente em `data/financial_portfolio.db` e é ignorado pelo Git.

## CSV de exemplo

```csv
date,description,amount
2026-07-01,Vendas balcão,2500.00
2026-07-02,Fornecedor de insumos,-850.00
```

## Testes

```bash
python -m pytest -q
```

O workflow em `.github/workflows/tests.yml` executa os testes automaticamente em pull requests e pushes para `main`.

## Privacidade

A versão original nasceu de uma necessidade real de organização financeira. Para publicação, o projeto foi reconstruído com:

- unidades genéricas;
- valores demonstrativos;
- ausência de dados bancários e extratos;
- ausência de nomes reais de fornecedores;
- banco local ignorado;
- arquivos financeiros protegidos pelo `.gitignore`.

## Próximos passos

- PostgreSQL;
- FastAPI para separar frontend e backend;
- autenticação;
- testes de integração;
- Docker;
- forecasting de fluxo de caixa;
- detecção de anomalias;
- deploy em cloud.

---

Projeto desenvolvido como parte do portfólio de **Lucas Sobral**, com foco em Python, dados e desenvolvimento de software.
