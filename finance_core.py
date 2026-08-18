from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


DEFAULT_SETTINGS = {
    # Valores exclusivamente demonstrativos para a versão pública do portfólio.
    "fixed_payroll": 8500.0,
    "fixed_rent": 9000.0,
    "fixed_services": 1200.0,
    "fixed_marketing": 900.0,
    "fixed_systems": 450.0,
    "fixed_taxes": 2200.0,
    "variable_supplies": 11000.0,
    "working_capital_target": 80000.0,
    "ticket_goal": 42.0,
}

CATEGORY_OPTIONS = [
    "Receita operacional",
    "Fornecedores / Insumos",
    "Pessoal",
    "Aluguel",
    "Serviços",
    "Marketing",
    "Impostos",
    "Taxas / Financeiro",
    "Aporte / Outros",
]

CATEGORY_KEYWORDS = {
    "Fornecedores / Insumos": ["FORNECEDOR", "INSUMO", "CAFÉ", "LEITE", "EMBALAGEM"],
    "Pessoal": ["SALARIO", "FOLHA", "PRO LABORE", "FUNCIONARIO"],
    "Aluguel": ["ALUGUEL", "LOCACAO"],
    "Serviços": ["INTERNET", "TELEFONE", "ENERGIA", "AGUA", "SEGURO", "SERVICO"],
    "Marketing": ["MARKETING", "PUBLICIDADE", "ANUNCIO"],
    "Impostos": ["IMPOSTO", "TRIBUTO", "DARF", "DAS"],
    "Taxas / Financeiro": ["TAXA", "JUROS", "IOF", "TARIFA"],
}


@dataclass(frozen=True)
class Metrics:
    revenue: float
    expenses: float
    net_result: float
    transaction_count: int
    average_ticket: float


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", str(value))
    value = value.replace("\u00ad", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_match_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFD", normalize_text(value))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").upper()


def parse_brl(value: str | float | int | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    raw = normalize_text(value).replace("R$", "").replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    raw = re.sub(r"[^0-9.\-]", "", raw)
    if raw in {"", "-", ".", "-."}:
        return 0.0
    return float(raw)


def format_brl(value: float) -> str:
    sign = "-" if value < 0 else ""
    whole, decimal = f"{abs(float(value)):,.2f}".split(".")
    return f"{sign}R$ {whole.replace(',', '.')},{decimal}"


def categorize_transaction(description: str, amount: float) -> str:
    if amount > 0:
        return "Receita operacional"

    key = normalize_match_text(description)
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in key for keyword in keywords):
            return category
    return "Aporte / Outros"


def transaction_fingerprint(
    unit_id: int,
    tx_date: date | str,
    description: str,
    amount: float,
) -> str:
    date_value = tx_date.isoformat() if isinstance(tx_date, date) else str(tx_date)
    payload = f"{unit_id}|{date_value}|{normalize_match_text(description)}|{float(amount):.2f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def calculate_metrics(df: pd.DataFrame) -> Metrics:
    if df.empty:
        return Metrics(0.0, 0.0, 0.0, 0, 0.0)

    values = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    revenue = float(values[values > 0].sum())
    expenses = float(-values[values < 0].sum())
    net = revenue - expenses
    positive_count = int((values > 0).sum())
    avg_ticket = revenue / positive_count if positive_count else 0.0
    return Metrics(revenue, expenses, net, len(df), avg_ticket)


def get_engine(db_path: str | Path = "data/financial_portfolio.db") -> Engine:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def init_db(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id INTEGER NOT NULL,
                tx_date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                source TEXT NOT NULL,
                fingerprint TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY(unit_id) REFERENCES units(id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS unit_settings (
                unit_id INTEGER PRIMARY KEY,
                fixed_payroll REAL NOT NULL,
                fixed_rent REAL NOT NULL,
                fixed_services REAL NOT NULL,
                fixed_marketing REAL NOT NULL,
                fixed_systems REAL NOT NULL,
                fixed_taxes REAL NOT NULL,
                variable_supplies REAL NOT NULL,
                working_capital_target REAL NOT NULL,
                ticket_goal REAL NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(unit_id) REFERENCES units(id)
            )
            """
        )

        for unit_id, name in {1: "Cafeteria A", 2: "Cafeteria B"}.items():
            conn.execute(
                text("INSERT OR IGNORE INTO units (id, name) VALUES (:id, :name)"),
                {"id": unit_id, "name": name},
            )
            existing = conn.execute(
                text("SELECT 1 FROM unit_settings WHERE unit_id = :unit_id"),
                {"unit_id": unit_id},
            ).scalar()
            if not existing:
                conn.execute(
                    text(
                        """
                        INSERT INTO unit_settings (
                            unit_id, fixed_payroll, fixed_rent, fixed_services,
                            fixed_marketing, fixed_systems, fixed_taxes,
                            variable_supplies, working_capital_target, ticket_goal,
                            updated_at
                        ) VALUES (
                            :unit_id, :fixed_payroll, :fixed_rent, :fixed_services,
                            :fixed_marketing, :fixed_systems, :fixed_taxes,
                            :variable_supplies, :working_capital_target, :ticket_goal,
                            :updated_at
                        )
                        """
                    ),
                    {
                        "unit_id": unit_id,
                        **DEFAULT_SETTINGS,
                        "updated_at": datetime.now().isoformat(timespec="seconds"),
                    },
                )


def insert_transaction(
    engine: Engine,
    unit_id: int,
    tx_date: date,
    description: str,
    amount: float,
    category: str | None = None,
    source: str = "manual",
) -> bool:
    category = category or categorize_transaction(description, amount)
    fingerprint = transaction_fingerprint(unit_id, tx_date, description, amount)

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO transactions (
                        unit_id, tx_date, description, amount, category, source,
                        fingerprint, created_at
                    ) VALUES (
                        :unit_id, :tx_date, :description, :amount, :category, :source,
                        :fingerprint, :created_at
                    )
                    """
                ),
                {
                    "unit_id": unit_id,
                    "tx_date": tx_date.isoformat(),
                    "description": normalize_text(description),
                    "amount": float(amount),
                    "category": category,
                    "source": source,
                    "fingerprint": fingerprint,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
        return True
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            return False
        raise


def fetch_transactions(
    engine: Engine,
    unit_ids: Iterable[int],
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    ids = [int(value) for value in unit_ids]
    if not ids:
        return pd.DataFrame(
            columns=["id", "unit_id", "unit_name", "tx_date", "description", "amount", "category", "source"]
        )

    placeholders = ", ".join(f":u{i}" for i in range(len(ids)))
    params = {f"u{i}": value for i, value in enumerate(ids)}
    filters = [f"t.unit_id IN ({placeholders})"]

    if start_date:
        filters.append("date(t.tx_date) >= date(:start_date)")
        params["start_date"] = start_date.isoformat()
    if end_date:
        filters.append("date(t.tx_date) <= date(:end_date)")
        params["end_date"] = end_date.isoformat()

    query = text(
        f"""
        SELECT t.id, t.unit_id, u.name AS unit_name, t.tx_date,
               t.description, t.amount, t.category, t.source
        FROM transactions t
        JOIN units u ON u.id = t.unit_id
        WHERE {' AND '.join(filters)}
        ORDER BY date(t.tx_date), t.id
        """
    )
    with engine.begin() as conn:
        df = pd.read_sql(query, conn, params=params)
    if not df.empty:
        df["tx_date"] = pd.to_datetime(df["tx_date"]).dt.date
    return df


def save_settings(engine: Engine, unit_id: int, settings: dict[str, float]) -> None:
    payload = {
        "unit_id": unit_id,
        **{key: float(settings[key]) for key in DEFAULT_SETTINGS},
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO unit_settings (
                    unit_id, fixed_payroll, fixed_rent, fixed_services,
                    fixed_marketing, fixed_systems, fixed_taxes,
                    variable_supplies, working_capital_target, ticket_goal, updated_at
                ) VALUES (
                    :unit_id, :fixed_payroll, :fixed_rent, :fixed_services,
                    :fixed_marketing, :fixed_systems, :fixed_taxes,
                    :variable_supplies, :working_capital_target, :ticket_goal, :updated_at
                )
                ON CONFLICT(unit_id) DO UPDATE SET
                    fixed_payroll = excluded.fixed_payroll,
                    fixed_rent = excluded.fixed_rent,
                    fixed_services = excluded.fixed_services,
                    fixed_marketing = excluded.fixed_marketing,
                    fixed_systems = excluded.fixed_systems,
                    fixed_taxes = excluded.fixed_taxes,
                    variable_supplies = excluded.variable_supplies,
                    working_capital_target = excluded.working_capital_target,
                    ticket_goal = excluded.ticket_goal,
                    updated_at = excluded.updated_at
                """
            ),
            payload,
        )


def fetch_settings(engine: Engine, unit_id: int) -> dict[str, float]:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT * FROM unit_settings WHERE unit_id = :unit_id"),
            {"unit_id": unit_id},
        ).mappings().first()
    return dict(row) if row else {"unit_id": unit_id, **DEFAULT_SETTINGS}


def seed_demo_data(engine: Engine) -> int:
    demo = [
        (1, date(2026, 7, 2), "Vendas balcão", 4200.00),
        (1, date(2026, 7, 3), "Fornecedor de café e insumos", -1450.00),
        (1, date(2026, 7, 5), "Aluguel unidade", -9000.00),
        (1, date(2026, 7, 8), "Vendas balcão", 5100.00),
        (1, date(2026, 7, 10), "Energia e internet", -820.00),
        (2, date(2026, 7, 2), "Vendas balcão", 3900.00),
        (2, date(2026, 7, 4), "Fornecedor de embalagens", -1100.00),
        (2, date(2026, 7, 6), "Marketing local", -650.00),
        (2, date(2026, 7, 9), "Vendas balcão", 4750.00),
        (2, date(2026, 7, 11), "Impostos do período", -1250.00),
    ]
    inserted = 0
    for unit_id, tx_date, description, amount in demo:
        if insert_transaction(engine, unit_id, tx_date, description, amount, source="demo"):
            inserted += 1
    return inserted
