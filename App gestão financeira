"""
Gestão Financeira para Duas Franquias de Cafeteria
---------------------------------------------------
App Streamlit com:
- Filtro por Franquia 1, Franquia 2 ou Consolidado
- Persistência total em SQLite
- Upload de extrato PDF com deduplicação
- Lançamento manual
- Edição e exclusão de lançamentos
- Exclusão de uploads importados
- Exclusão em lote por mês (selecionados ou todos)
- Configurações de custos por unidade
- Dashboard com período personalizado, termômetros e gráficos

Como executar:
    streamlit run gestao_cafeteria_app.py
"""

from __future__ import annotations

import calendar
import hashlib
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from xml.sax.saxutils import escape

import matplotlib.pyplot as plt
import pandas as pd
import pdfplumber
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# -----------------------------------------------------------------------------
# Configurações gerais
# -----------------------------------------------------------------------------

APP_TITLE = "Gestão Financeira - Cafeterias"
APP_ICON = "☕"
APP_DATA_DIR = Path.home() / "GestaoCafeFinanceiro"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DATA_DIR / "cafeteria_financeira.db"

UNITS = {1: "Franquia 1", 2: "Franquia 2"}

DEFAULT_SETTINGS = {
    "fixed_payroll": 6000.0,
    "fixed_royalties": 2500.0,
    "fixed_brand_marketing": 690.0,
    "fixed_equipment_suppliers": 1200.0,
    "fixed_taxes": 1500.0,
    "fixed_services": 400.0,
    "fixed_rent": 14500.0,
    "fixed_card_machine": 80.0,
    "fixed_accounting": 600.0,
    "fixed_system": 260.0,
    "fixed_own_marketing": 1000.0,
    "fixed_pro_labore": 3000.0,
    "variable_supplies": 8500.0,
    "variable_other": 0.0,
    "capital_giro_target": 126724.50,
    "reserve_months": 36,
    "days_in_month": 30,
    "ticket_goal": 45.0,
    "owner_current_balance": 0.0,
    "owner_balance_goal": 126724.50,
}

CATEGORY_OPTIONS = [
    "Receita operacional",
    "Despesa operacional",
    "Tarifa",
    "Aporte / Outros",
    "Fornecedores / Insumos",
    "Pessoal / Pró-labore",
    "Aluguel",
    "Serviços",
    "Franquia / Marca",
    "Impostos",
    "Taxas / Financeiro",
]

# -----------------------------------------------------------------------------
# Texto / moeda / datas
# -----------------------------------------------------------------------------


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", str(value))
    value = value.replace("", ":").replace("", "-").replace("•", " ")
    value = value.replace("\u00ad", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()



def normalize_match_text(value: str) -> str:
    cleaned = unicodedata.normalize("NFD", normalize_text(value))
    return "".join(ch for ch in cleaned if unicodedata.category(ch) != "Mn").upper()



def parse_brl(value: str) -> float:
    if value is None:
        return 0.0
    s = normalize_text(value)
    s = s.replace("R$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in {"", "-", ".", "-."}:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0



def format_brl(value: float) -> str:
    sign = "-" if float(value) < 0 else ""
    value = abs(float(value))
    whole, frac = f"{value:,.2f}".split(".")
    whole = whole.replace(",", ".")
    return f"{sign}R$ {whole},{frac}"



def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()



def month_bounds(any_day: date) -> Tuple[date, date]:
    first = any_day.replace(day=1)
    last_day = calendar.monthrange(any_day.year, any_day.month)[1]
    return first, any_day.replace(day=last_day)



def normalize_date_range(value, default_start: date, default_end: date) -> Tuple[date, date]:
    if isinstance(value, tuple) and len(value) == 2:
        start, end = value
        return start or default_start, end or default_end
    return default_start, default_end


# -----------------------------------------------------------------------------
# Banco de dados
# -----------------------------------------------------------------------------


def get_engine() -> Engine:
    return create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})



def table_columns(engine: Engine, table: str) -> List[str]:
    with engine.begin() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return [r[1] for r in rows]



def ensure_column(engine: Engine, table: str, column: str, ddl: str) -> None:
    cols = table_columns(engine, table)
    if column not in cols:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")



def init_db(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS unit_settings (
                unit_id INTEGER PRIMARY KEY,
                fixed_payroll REAL NOT NULL,
                fixed_royalties REAL NOT NULL,
                fixed_brand_marketing REAL NOT NULL,
                fixed_equipment_suppliers REAL NOT NULL,
                fixed_taxes REAL NOT NULL,
                fixed_services REAL NOT NULL,
                fixed_rent REAL NOT NULL,
                fixed_card_machine REAL NOT NULL,
                fixed_accounting REAL NOT NULL,
                fixed_system REAL NOT NULL,
                fixed_own_marketing REAL NOT NULL,
                fixed_pro_labore REAL NOT NULL,
                variable_supplies REAL NOT NULL,
                variable_other REAL NOT NULL,
                capital_giro_target REAL NOT NULL,
                reserve_months INTEGER NOT NULL,
                days_in_month INTEGER NOT NULL,
                ticket_goal REAL NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(unit_id) REFERENCES units(id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id INTEGER NOT NULL,
                tx_date TEXT NOT NULL,
                direction TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                balance REAL,
                category TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_file TEXT,
                source_hash TEXT,
                tx_hash TEXT NOT NULL UNIQUE,
                raw_text TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(unit_id) REFERENCES units(id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                rows_inserted INTEGER NOT NULL,
                rows_skipped INTEGER NOT NULL,
                FOREIGN KEY(unit_id) REFERENCES units(id)
            )
            """
        )

    # Migração simples para instalações antigas.
    ensure_column(engine, "transactions", "source_hash", "TEXT")
    ensure_column(engine, "unit_settings", "owner_current_balance", "REAL NOT NULL DEFAULT 0")
    ensure_column(engine, "unit_settings", "owner_balance_goal", "REAL NOT NULL DEFAULT 126724.50")

    with engine.begin() as conn:
        existing_units = conn.execute(text("SELECT id, name FROM units ORDER BY id")).fetchall()
        if not existing_units:
            for unit_id, unit_name in UNITS.items():
                conn.execute(
                    text("INSERT INTO units (id, name) VALUES (:id, :name)"),
                    {"id": unit_id, "name": unit_name},
                )
            existing_units = conn.execute(text("SELECT id, name FROM units ORDER BY id")).fetchall()

        for unit_id, _ in existing_units:
            has_settings = conn.execute(
                text("SELECT 1 FROM unit_settings WHERE unit_id = :unit_id"),
                {"unit_id": unit_id},
            ).fetchone()
            if not has_settings:
                params = {
                    "unit_id": unit_id,
                    **DEFAULT_SETTINGS,
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                }
                conn.execute(
                    text(
                        """
                        INSERT INTO unit_settings (
                            unit_id, fixed_payroll, fixed_royalties, fixed_brand_marketing,
                            fixed_equipment_suppliers, fixed_taxes, fixed_services, fixed_rent,
                            fixed_card_machine, fixed_accounting, fixed_system, fixed_own_marketing,
                            fixed_pro_labore, variable_supplies, variable_other, capital_giro_target,
                            reserve_months, days_in_month, ticket_goal, updated_at
                        )
                        VALUES (
                            :unit_id, :fixed_payroll, :fixed_royalties, :fixed_brand_marketing,
                            :fixed_equipment_suppliers, :fixed_taxes, :fixed_services, :fixed_rent,
                            :fixed_card_machine, :fixed_accounting, :fixed_system, :fixed_own_marketing,
                            :fixed_pro_labore, :variable_supplies, :variable_other, :capital_giro_target,
                            :reserve_months, :days_in_month, :ticket_goal, :updated_at
                        )
                        """
                    ),
                    params,
                )



def fetch_units(engine: Engine) -> pd.DataFrame:
    with engine.begin() as conn:
        return pd.read_sql(text("SELECT id, name FROM units ORDER BY id"), conn)



def fetch_settings(engine: Engine, unit_id: int) -> Dict[str, float]:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT * FROM unit_settings WHERE unit_id = :unit_id"),
            {"unit_id": unit_id},
        ).mappings().first()
    return dict(row) if row else {"unit_id": unit_id, **DEFAULT_SETTINGS}



def save_settings(engine: Engine, unit_id: int, settings: Dict[str, float]) -> None:
    keys = [
        "fixed_payroll", "fixed_royalties", "fixed_brand_marketing", "fixed_equipment_suppliers",
        "fixed_taxes", "fixed_services", "fixed_rent", "fixed_card_machine", "fixed_accounting",
        "fixed_system", "fixed_own_marketing", "fixed_pro_labore", "variable_supplies",
        "variable_other", "capital_giro_target", "reserve_months", "days_in_month", "ticket_goal",
        "owner_current_balance", "owner_balance_goal",
    ]
    payload = {k: settings[k] for k in keys}
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    payload["unit_id"] = unit_id

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO unit_settings (
                    unit_id, fixed_payroll, fixed_royalties, fixed_brand_marketing,
                    fixed_equipment_suppliers, fixed_taxes, fixed_services, fixed_rent,
                    fixed_card_machine, fixed_accounting, fixed_system, fixed_own_marketing,
                    fixed_pro_labore, variable_supplies, variable_other, capital_giro_target,
                    reserve_months, days_in_month, ticket_goal, owner_current_balance,
                    owner_balance_goal, updated_at
                ) VALUES (
                    :unit_id, :fixed_payroll, :fixed_royalties, :fixed_brand_marketing,
                    :fixed_equipment_suppliers, :fixed_taxes, :fixed_services, :fixed_rent,
                    :fixed_card_machine, :fixed_accounting, :fixed_system, :fixed_own_marketing,
                    :fixed_pro_labore, :variable_supplies, :variable_other, :capital_giro_target,
                    :reserve_months, :days_in_month, :ticket_goal, :owner_current_balance,
                    :owner_balance_goal, :updated_at
                )
                ON CONFLICT(unit_id) DO UPDATE SET
                    fixed_payroll = excluded.fixed_payroll,
                    fixed_royalties = excluded.fixed_royalties,
                    fixed_brand_marketing = excluded.fixed_brand_marketing,
                    fixed_equipment_suppliers = excluded.fixed_equipment_suppliers,
                    fixed_taxes = excluded.fixed_taxes,
                    fixed_services = excluded.fixed_services,
                    fixed_rent = excluded.fixed_rent,
                    fixed_card_machine = excluded.fixed_card_machine,
                    fixed_accounting = excluded.fixed_accounting,
                    fixed_system = excluded.fixed_system,
                    fixed_own_marketing = excluded.fixed_own_marketing,
                    fixed_pro_labore = excluded.fixed_pro_labore,
                    variable_supplies = excluded.variable_supplies,
                    variable_other = excluded.variable_other,
                    capital_giro_target = excluded.capital_giro_target,
                    reserve_months = excluded.reserve_months,
                    days_in_month = excluded.days_in_month,
                    ticket_goal = excluded.ticket_goal,
                    owner_current_balance = excluded.owner_current_balance,
                    owner_balance_goal = excluded.owner_balance_goal,
                    updated_at = excluded.updated_at
                """
            ),
            payload,
        )



def fetch_transactions(
    engine: Engine,
    unit_ids: Iterable[int],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    unit_ids = [int(x) for x in unit_ids]
    columns = [
        "id", "unit_id", "unit_name", "tx_date", "direction", "description", "amount",
        "balance", "category", "source_type", "source_file", "source_hash", "tx_hash",
        "raw_text", "created_at",
    ]
    if not unit_ids:
        return pd.DataFrame(columns=columns)

    placeholders = ", ".join(f":u{i}" for i in range(len(unit_ids)))
    params = {f"u{i}": unit_id for i, unit_id in enumerate(unit_ids)}
    filters = [f"t.unit_id IN ({placeholders})"]

    if start_date is not None:
        filters.append("date(t.tx_date) >= date(:start_date)")
        params["start_date"] = start_date.isoformat()
    if end_date is not None:
        filters.append("date(t.tx_date) <= date(:end_date)")
        params["end_date"] = end_date.isoformat()

    query = text(
        f"""
        SELECT t.*, u.name AS unit_name
        FROM transactions t
        JOIN units u ON u.id = t.unit_id
        WHERE {' AND '.join(filters)}
        ORDER BY date(t.tx_date) ASC, t.id ASC
        """
    )
    with engine.begin() as conn:
        df = pd.read_sql(query, conn, params=params)
    if not df.empty:
        df["tx_date"] = pd.to_datetime(df["tx_date"]).dt.date
    return df



def sum_transaction_amounts(
    engine: Engine,
    unit_ids: Iterable[int],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> float:
    unit_ids = [int(x) for x in unit_ids]
    if not unit_ids:
        return 0.0

    placeholders = ", ".join(f":u{i}" for i in range(len(unit_ids)))
    params = {f"u{i}": unit_id for i, unit_id in enumerate(unit_ids)}
    filters = [f"unit_id IN ({placeholders})"]

    if start_date is not None:
        filters.append("date(tx_date) >= date(:start_date)")
        params["start_date"] = start_date.isoformat()
    if end_date is not None:
        filters.append("date(tx_date) <= date(:end_date)")
        params["end_date"] = end_date.isoformat()

    with engine.begin() as conn:
        value = conn.execute(
            text(
                f"""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE {' AND '.join(filters)}
                """
            ),
            params,
        ).scalar()
    return float(value or 0.0)



def fetch_latest_recorded_balance(engine: Engine, unit_ids: Iterable[int]) -> float:
    unit_ids = [int(x) for x in unit_ids]
    if not unit_ids:
        return 0.0

    placeholders = ", ".join(f":u{i}" for i in range(len(unit_ids)))
    params = {f"u{i}": unit_id for i, unit_id in enumerate(unit_ids)}
    query = text(
        f"""
        SELECT balance
        FROM transactions
        WHERE unit_id IN ({placeholders})
          AND balance IS NOT NULL
        ORDER BY date(tx_date) DESC, id DESC
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        value = conn.execute(query, params).scalar()
    return float(value or 0.0)


def fetch_recent_transactions(engine: Engine, unit_id: int, limit: int = 100) -> pd.DataFrame:
    with engine.begin() as conn:
        df = pd.read_sql(
            text(
                """
                SELECT t.*, u.name AS unit_name
                FROM transactions t
                JOIN units u ON u.id = t.unit_id
                WHERE t.unit_id = :unit_id
                ORDER BY date(t.tx_date) DESC, t.id DESC
                LIMIT :limit
                """
            ),
            conn,
            params={"unit_id": unit_id, "limit": limit},
        )
    if not df.empty:
        df["tx_date"] = pd.to_datetime(df["tx_date"]).dt.date
    return df



def fetch_transactions_by_month(engine: Engine, unit_id: int, ref_date: date) -> pd.DataFrame:
    ym = ref_date.strftime("%Y-%m")
    with engine.begin() as conn:
        df = pd.read_sql(
            text(
                """
                SELECT id, unit_id, tx_date, direction, description, amount, balance, category, source_type
                FROM transactions
                WHERE unit_id = :unit_id
                  AND strftime('%Y-%m', tx_date) = :ym
                ORDER BY date(tx_date) ASC, id ASC
                """
            ),
            conn,
            params={"unit_id": unit_id, "ym": ym},
        )
    if not df.empty:
        df["tx_date"] = pd.to_datetime(df["tx_date"]).dt.date
    return df



def fetch_uploaded_files(engine: Engine, unit_id: int) -> pd.DataFrame:
    with engine.begin() as conn:
        return pd.read_sql(
            text(
                """
                SELECT id, file_name, file_hash, uploaded_at, rows_inserted, rows_skipped
                FROM uploaded_files
                WHERE unit_id = :unit_id
                ORDER BY id DESC
                """
            ),
            conn,
            params={"unit_id": unit_id},
        )



def delete_transaction(engine: Engine, tx_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM transactions WHERE id = :tx_id"), {"tx_id": tx_id})



def delete_transactions(engine: Engine, tx_ids: Iterable[int]) -> int:
    tx_ids = [int(x) for x in tx_ids]
    if not tx_ids:
        return 0
    placeholders = ", ".join(f":id{i}" for i in range(len(tx_ids)))
    params = {f"id{i}": tx_id for i, tx_id in enumerate(tx_ids)}
    with engine.begin() as conn:
        result = conn.execute(text(f"DELETE FROM transactions WHERE id IN ({placeholders})"), params)
    return int(result.rowcount or 0)



def update_transaction(
    engine: Engine,
    tx_id: int,
    unit_id: int,
    tx_date: date,
    direction: str,
    description: str,
    amount: float,
    category: str,
) -> None:
    signed_amount = abs(float(amount))
    if direction == "Saída":
        signed_amount *= -1
    desc = normalize_text(description)
    tx_hash = sha1_text(
        f"{unit_id}|{tx_date.isoformat()}|{direction}|{desc.upper()}|{abs(float(amount)):.2f}|manual-edit"
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE transactions
                SET unit_id = :unit_id,
                    tx_date = :tx_date,
                    direction = :direction,
                    description = :description,
                    amount = :amount,
                    category = :category,
                    tx_hash = :tx_hash
                WHERE id = :tx_id
                """
            ),
            {
                "tx_id": tx_id,
                "unit_id": unit_id,
                "tx_date": tx_date.isoformat(),
                "direction": direction,
                "description": desc,
                "amount": signed_amount,
                "category": category,
                "tx_hash": tx_hash,
            },
        )



def delete_uploaded_file(engine: Engine, upload_id: int) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT unit_id, file_hash FROM uploaded_files WHERE id = :upload_id"),
            {"upload_id": upload_id},
        ).mappings().first()
        if not row:
            return 0
        unit_id = int(row["unit_id"])
        file_hash = str(row["file_hash"])
        deleted_tx = conn.execute(
            text(
                """
                DELETE FROM transactions
                WHERE unit_id = :unit_id
                  AND source_type = 'pdf'
                  AND source_hash = :file_hash
                """
            ),
            {"unit_id": unit_id, "file_hash": file_hash},
        ).rowcount or 0
        conn.execute(text("DELETE FROM uploaded_files WHERE id = :upload_id"), {"upload_id": upload_id})
        return int(deleted_tx)


# -----------------------------------------------------------------------------
# Classificação / parser
# -----------------------------------------------------------------------------

REVENUE_KEYWORDS = [
    "RECEBIMENTO VENDAS", "PIX QRS", "PIX RECEBIDO", "TOPAZI", "REDE",
    "VISA ELECTRON", "VISA", "MAST", "AMEX", "ELO",
    "DEBITO", "CREDITO", "ANTECIPACAO", "ALELO",
    "TICKET SERVICOS", "PLUXEE", "VR BENEF", "IFOOD", "FOOD TO SAVE",
    "TED RECEBIDA", "RESGATE CDB", "RENDIMENTOS", "MAQUININHA",
]

EXPENSE_KEYWORDS = {
    "Tarifa": ["TARIFA", "TAR PIXQR", "MAQUININHA"],
    "Fornecedores / Insumos": [
        "ASSAI", "SPAL", "CODISPEL", "LABELLA", "UF DISTRIBUIDORA", "GRAN COFFEE",
        "SISPAG FORNECEDORES", "PAG TIT", "PIX QR-CODE", "PIX QR- CODE",
    ],
    "Pessoal / Pró-labore": ["PRO-LABORE", "SALARIO", "FUNCION", "FOLHA"],
    "Aluguel": ["ALUGUEL"],
    "Serviços": ["VIVO", "INTERNET", "TELEFONE", "SEGUROS", "ITAU SEG", "BUSINESS 4004-9091"],
    "Franquia / Marca": ["ROYALT", "MARKETING", "SINDICATO DO COMERCIO", "UF GESTAO DE MARCAS", "PATENTES"],
    "Impostos": ["MINISTERIO DA FAZENDA", "IMPOSTO", "TRIBUTO", "DARF", "DAS", "SISPAG TRIBUTOS"],
    "Taxas / Financeiro": ["MAQUININHA", "TAXA", "IOF", "JUROS", "TAR PIXQR", "BUSINESS 4004-9091"],
}



def classify_revenue_or_cost(direction: str, description: str) -> str:
    direction_key = normalize_match_text(direction)
    desc_key = normalize_match_text(description)
    if direction_key.startswith("ENTRADA"):
        if any(key in desc_key for key in REVENUE_KEYWORDS):
            return "Receita operacional"
        return "Aporte / Outros"
    if any(key in desc_key for key in EXPENSE_KEYWORDS["Tarifa"]):
        return "Tarifa"
    for label, keys in EXPENSE_KEYWORDS.items():
        if label == "Tarifa":
            continue
        if any(key in desc_key for key in keys):
            return label
    return "Despesa operacional"



def expense_bucket(description: str) -> str:
    desc_key = normalize_match_text(description)
    if any(key in desc_key for key in EXPENSE_KEYWORDS["Tarifa"]):
        return "Tarifas"
    if any(key in desc_key for key in EXPENSE_KEYWORDS["Fornecedores / Insumos"]):
        return "Insumos / Fornecedores"
    if any(key in desc_key for key in EXPENSE_KEYWORDS["Serviços"]):
        return "Serviços"
    if any(key in desc_key for key in EXPENSE_KEYWORDS["Aluguel"]):
        return "Aluguel"
    if any(key in desc_key for key in EXPENSE_KEYWORDS["Impostos"]):
        return "Impostos"
    if any(key in desc_key for key in EXPENSE_KEYWORDS["Franquia / Marca"]):
        return "Franquia / Marca"
    if any(key in desc_key for key in EXPENSE_KEYWORDS["Taxas / Financeiro"]):
        return "Taxas / Financeiro"
    if any(key in desc_key for key in EXPENSE_KEYWORDS["Pessoal / Pró-labore"]):
        return "Pessoal"
    if any(key in desc_key for key in ["TRANSFERENCIA", "PIX", "TED"]):
        return "Transferencias / Retiradas"
    return "Outros"


STONE_DATE_LINE_RE = re.compile(r"^(?P<date>\d{2}/\d{2}/\d{2})\s+(?P<direction>\S+)\s+(?P<rest>.*)$")
STONE_CUR_RE = re.compile(r"(?<!\w)(-?\s*R\$\s?[\d\.]+,[\d]{2})")
STONE_SKIP_PREFIXES = (
    "EXTRATO DE CONTA CORRENTE",
    "EMITIDO EM",
    "PAGINA",
    "PERIODO:",
    "DATA TIPO DESCRICAO",
    "DADOS DA CONTA",
    "NOME",
    "DOCUMENTO",
    "INSTITUICAO",
    "AGENCIA",
    "CONTA",
)
ITAU_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
ITAU_AMOUNT_RE = re.compile(r"^-?\d[\d\.]*,\d{2}$")
ITAU_DOC_RE = re.compile(r"^\d{2,3}\.\d{3}\.\d{3}(?:/\d{4})?-\d{2}$")
ITAU_SKIP_LABELS = (
    "SALDO TOTAL DISPONIVEL DIA",
    "SALDO ANTERIOR",
)



def extract_stone_blocks_from_pdf(pdf_path: str) -> List[str]:
    lines: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            for raw_line in txt.splitlines():
                line = normalize_text(raw_line)
                if not line:
                    continue
                line_key = normalize_match_text(line)
                if any(line_key.startswith(prefix) for prefix in STONE_SKIP_PREFIXES):
                    continue
                lines.append(line)

    blocks: List[str] = []
    current: List[str] = []
    for line in lines:
        if STONE_DATE_LINE_RE.match(line):
            if current:
                blocks.append(" ".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(" ".join(current))
    return blocks



def parse_stone_transaction_block(block: str) -> Optional[Dict[str, object]]:
    block = normalize_text(block)
    match = STONE_DATE_LINE_RE.match(block)
    if not match:
        return None

    tx_date = datetime.strptime(match.group("date"), "%d/%m/%y").date()
    direction = match.group("direction")
    direction_key = normalize_match_text(direction)
    if direction_key not in {"ENTRADA", "SAIDA"}:
        return None
    rest = normalize_text(match.group("rest"))

    currencies = list(STONE_CUR_RE.finditer(rest))
    if not currencies:
        return None

    amount_match = currencies[0]
    balance_match = currencies[1] if len(currencies) > 1 else None

    prefix = rest[:amount_match.start()].strip()
    between = rest[amount_match.end():balance_match.start()] if balance_match else ""
    after = rest[balance_match.end():] if balance_match else ""
    description = normalize_text(" ".join(part for part in [prefix, between, after] if part))

    amount = parse_brl(amount_match.group(1))
    amount = -abs(amount) if direction_key == "SAIDA" else abs(amount)
    balance = parse_brl(balance_match.group(1)) if balance_match else None

    return {
        "tx_date": tx_date.isoformat(),
        "direction": direction,
        "description": description,
        "amount": amount,
        "balance": balance,
        "category": classify_revenue_or_cost(direction, description),
        "raw_text": block,
    }



def parse_stone_statement_pdf(pdf_path: str, unit_id: int, source_file: str, source_hash: str) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for block in extract_stone_blocks_from_pdf(pdf_path):
        parsed = parse_stone_transaction_block(block)
        if parsed:
            parsed["unit_id"] = unit_id
            parsed["source_type"] = "pdf"
            parsed["source_file"] = source_file
            parsed["source_hash"] = source_hash
            parsed["created_at"] = datetime.now().isoformat(timespec="seconds")
            rows.append(parsed)
    return finalize_statement_rows(rows)



def detect_statement_layout(pdf_path: str) -> str:
    snippets: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:2]:
            snippets.append(page.extract_text() or "")
    sample = normalize_match_text(" ".join(snippets))
    if any(token in sample for token in ["LANCAMENTOS DO PERIODO", "SALDO TOTAL DISPONIVEL DIA", "SALDO ANTERIOR"]):
        return "itau"
    if " ENTRADA " in f" {sample} " or " SAIDA " in f" {sample} ":
        return "stone"
    return "unknown"



def extract_itau_rows_from_pdf(pdf_path: str) -> List[List[Dict[str, float]]]:
    grouped_rows: List[List[Dict[str, float]]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words: List[Dict[str, float]] = []
            for raw_word in page.extract_words(use_text_flow=True, keep_blank_chars=False) or []:
                text_value = normalize_text(raw_word.get("text"))
                if not text_value:
                    continue
                words.append(
                    {
                        "text": text_value,
                        "top": float(raw_word["top"]),
                        "x0": float(raw_word["x0"]),
                    }
                )

            anchors = [word for word in words if word["x0"] < 85 and ITAU_DATE_RE.match(str(word["text"]))]
            anchors.sort(key=lambda item: item["top"])
            if not anchors:
                continue

            for idx, anchor in enumerate(anchors):
                prev_top = anchors[idx - 1]["top"] if idx > 0 else anchor["top"] - 12
                next_top = anchors[idx + 1]["top"] if idx + 1 < len(anchors) else anchor["top"] + 12
                lower_bound = (prev_top + anchor["top"]) / 2 if idx > 0 else anchor["top"] - 12
                upper_bound = (anchor["top"] + next_top) / 2 if idx + 1 < len(anchors) else anchor["top"] + 12
                row_words = [word for word in words if lower_bound <= word["top"] < upper_bound]
                if row_words:
                    grouped_rows.append(row_words)
    return grouped_rows



def parse_itau_row_words(row_words: List[Dict[str, float]]) -> Optional[Dict[str, object]]:
    sorted_words = sorted(row_words, key=lambda item: (item["top"], item["x0"]))
    date_word = next((word for word in sorted_words if word["x0"] < 85 and ITAU_DATE_RE.match(str(word["text"]))), None)
    if not date_word:
        return None

    amount_candidates = [word for word in sorted_words if word["x0"] >= 470 and ITAU_AMOUNT_RE.match(str(word["text"]))]
    if not amount_candidates:
        return None
    amount_word = sorted(amount_candidates, key=lambda item: (item["x0"], item["top"]))[-1]

    description_tokens: List[str] = []
    for word in sorted_words:
        token = normalize_text(word["text"])
        if word is date_word or word is amount_word:
            continue
        if ITAU_DOC_RE.match(token):
            continue
        if ITAU_AMOUNT_RE.match(token):
            continue
        description_tokens.append(token)

    description = normalize_text(" ".join(description_tokens))
    if not description:
        return None
    if any(normalize_match_text(description).startswith(label) for label in ITAU_SKIP_LABELS):
        return None

    amount = parse_brl(str(amount_word["text"]))
    direction = "Saída" if str(amount_word["text"]).startswith("-") else "Entrada"
    signed_amount = -abs(amount) if direction.startswith("Sa") else abs(amount)
    raw_text = normalize_text(" ".join(str(word["text"]) for word in sorted_words))

    return {
        "tx_date": datetime.strptime(str(date_word["text"]), "%d/%m/%Y").date().isoformat(),
        "direction": direction,
        "description": description,
        "amount": signed_amount,
        "balance": None,
        "category": classify_revenue_or_cost(direction, description),
        "raw_text": raw_text,
    }



def parse_itau_statement_pdf(pdf_path: str, unit_id: int, source_file: str, source_hash: str) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for row_words in extract_itau_rows_from_pdf(pdf_path):
        parsed = parse_itau_row_words(row_words)
        if parsed:
            parsed["unit_id"] = unit_id
            parsed["source_type"] = "pdf"
            parsed["source_file"] = source_file
            parsed["source_hash"] = source_hash
            parsed["created_at"] = datetime.now().isoformat(timespec="seconds")
            rows.append(parsed)
    return finalize_statement_rows(rows)



def finalize_statement_rows(rows: List[Dict[str, object]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    def make_hash(row: pd.Series) -> str:
        payload = "|".join([
            str(int(row["unit_id"])),
            str(row["tx_date"]),
            str(row["direction"]),
            normalize_text(str(row["description"])).upper(),
            f"{abs(float(row['amount'])):.2f}",
            str(row["source_type"]),
            str(row.get("source_hash", "")),
        ])
        return sha1_text(payload)

    df["tx_hash"] = df.apply(make_hash, axis=1)
    df["description"] = df["description"].astype(str).map(normalize_text)
    return df



def parse_statement_pdf(pdf_path: str, unit_id: int, source_file: str, source_hash: str) -> pd.DataFrame:
    layout = detect_statement_layout(pdf_path)
    if layout == "itau":
        parsed = parse_itau_statement_pdf(pdf_path, unit_id, source_file, source_hash)
        return parsed if not parsed.empty else parse_stone_statement_pdf(pdf_path, unit_id, source_file, source_hash)
    if layout == "stone":
        parsed = parse_stone_statement_pdf(pdf_path, unit_id, source_file, source_hash)
        return parsed if not parsed.empty else parse_itau_statement_pdf(pdf_path, unit_id, source_file, source_hash)

    stone_df = parse_stone_statement_pdf(pdf_path, unit_id, source_file, source_hash)
    itau_df = parse_itau_statement_pdf(pdf_path, unit_id, source_file, source_hash)
    return stone_df if len(stone_df) >= len(itau_df) else itau_df


def insert_transactions(engine: Engine, df: pd.DataFrame) -> Tuple[int, int]:
    if df.empty:
        return 0, 0
    inserted = 0
    skipped = 0

    with engine.begin() as conn:
        for _, row in df.iterrows():
            exists = conn.execute(
                text("SELECT 1 FROM transactions WHERE tx_hash = :tx_hash"),
                {"tx_hash": row["tx_hash"]},
            ).fetchone()
            if exists:
                skipped += 1
                continue
            try:
                conn.execute(
                    text(
                        """
                        INSERT INTO transactions (
                            unit_id, tx_date, direction, description, amount, balance,
                            category, source_type, source_file, source_hash, tx_hash, raw_text, created_at
                        ) VALUES (
                            :unit_id, :tx_date, :direction, :description, :amount, :balance,
                            :category, :source_type, :source_file, :source_hash, :tx_hash, :raw_text, :created_at
                        )
                        """
                    ),
                    {
                        "unit_id": int(row["unit_id"]),
                        "tx_date": row["tx_date"],
                        "direction": row["direction"],
                        "description": row["description"],
                        "amount": float(row["amount"]),
                        "balance": None if pd.isna(row.get("balance")) else float(row.get("balance")),
                        "category": row["category"],
                        "source_type": row["source_type"],
                        "source_file": row.get("source_file"),
                        "source_hash": row.get("source_hash"),
                        "tx_hash": row["tx_hash"],
                        "raw_text": row.get("raw_text"),
                        "created_at": row["created_at"],
                    },
                )
                inserted += 1
            except Exception:
                skipped += 1
    return inserted, skipped



def record_uploaded_file(engine: Engine, unit_id: int, file_name: str, file_hash: str, rows_inserted: int, rows_skipped: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO uploaded_files (
                    unit_id, file_name, file_hash, uploaded_at, rows_inserted, rows_skipped
                ) VALUES (
                    :unit_id, :file_name, :file_hash, :uploaded_at, :rows_inserted, :rows_skipped
                )
                """
            ),
            {
                "unit_id": unit_id,
                "file_name": file_name,
                "file_hash": file_hash,
                "uploaded_at": datetime.now().isoformat(timespec="seconds"),
                "rows_inserted": rows_inserted,
                "rows_skipped": rows_skipped,
            },
        )


# -----------------------------------------------------------------------------
# Cálculos
# -----------------------------------------------------------------------------

@dataclass
class ComputedTargets:
    fixed_total: float
    variable_total: float
    break_even: float
    monthly_reserve: float
    healthy_target: float
    daily_target: float
    daily_clients_goal: float



def compute_targets(settings: Dict[str, float]) -> ComputedTargets:
    fixed_total = sum(float(settings[k]) for k in [
        "fixed_payroll", "fixed_royalties", "fixed_brand_marketing", "fixed_equipment_suppliers",
        "fixed_taxes", "fixed_services", "fixed_rent", "fixed_card_machine", "fixed_accounting",
        "fixed_system", "fixed_own_marketing", "fixed_pro_labore",
    ])
    variable_total = float(settings["variable_supplies"]) + float(settings["variable_other"])
    break_even = fixed_total + variable_total
    monthly_reserve = float(settings["capital_giro_target"]) / max(int(settings["reserve_months"]), 1)
    healthy_target = break_even + monthly_reserve
    daily_target = healthy_target / max(int(settings["days_in_month"]), 1)
    daily_clients_goal = daily_target / max(float(settings["ticket_goal"]), 1.0)
    return ComputedTargets(fixed_total, variable_total, break_even, monthly_reserve, healthy_target, daily_target, daily_clients_goal)



def period_days(start_date: date, end_date: date) -> int:
    return max((end_date - start_date).days + 1, 1)


def direction_key(value: str) -> str:
    key = normalize_match_text(value)
    if key.startswith("ENTRADA"):
        return "ENTRADA"
    if key.startswith("SAIDA"):
        return "SAIDA"
    return key


def category_key(value: str) -> str:
    return normalize_match_text(value)



def period_metrics(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {
            "revenue": 0.0,
            "expense": 0.0,
            "net": 0.0,
            "inflows_total": 0.0,
            "outflows_total": 0.0,
            "balance_last": 0.0,
        }
    direction_keys = df["direction"].map(direction_key)
    category_keys = df["category"].map(category_key)
    inflow_mask = direction_keys.eq("ENTRADA")
    outflow_mask = direction_keys.eq("SAIDA")
    revenue_mask = inflow_mask & category_keys.eq("RECEITA OPERACIONAL")
    revenue = df.loc[revenue_mask, "amount"].sum()
    expense = df.loc[outflow_mask, "amount"].abs().sum()
    inflows_total = df.loc[inflow_mask, "amount"].sum()
    outflows_total = df.loc[outflow_mask, "amount"].abs().sum()
    balance_last = df["balance"].dropna().iloc[-1] if "balance" in df.columns and df["balance"].notna().any() else 0.0
    return {
        "revenue": float(revenue),
        "expense": float(expense),
        "net": float(revenue - expense),
        "inflows_total": float(inflows_total),
        "outflows_total": float(outflows_total),
        "balance_last": float(balance_last),
    }


def daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["tx_date", "revenue", "expense", "net"])
    temp = df.copy()
    temp["day"] = pd.to_datetime(temp["tx_date"])
    direction_keys = temp["direction"].map(direction_key)
    category_keys = temp["category"].map(category_key)
    rev = temp[direction_keys.eq("ENTRADA") & category_keys.eq("RECEITA OPERACIONAL")].groupby(temp["day"].dt.date)["amount"].sum()
    exp = temp[direction_keys.eq("SAIDA")].groupby(temp["day"].dt.date)["amount"].sum().abs()
    out = pd.DataFrame({"revenue": rev, "expense": exp}).fillna(0.0)
    out["net"] = out["revenue"] - out["expense"]
    out = out.reset_index().rename(columns={"index": "tx_date"})
    out = out.rename(columns={"day": "tx_date"})
    if "tx_date" not in out.columns:
        out.columns = ["tx_date", "revenue", "expense", "net"]
    return out



def build_daily_revenue_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["day", "revenue"])
    temp = df.copy()
    temp["day"] = pd.to_datetime(temp["tx_date"]).dt.date
    direction_keys = temp["direction"].map(direction_key)
    category_keys = temp["category"].map(category_key)
    temp = temp[direction_keys.eq("ENTRADA") & category_keys.eq("RECEITA OPERACIONAL")]
    return temp.groupby("day")["amount"].sum().reset_index().rename(columns={"amount": "revenue"})



def build_expense_donut_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["bucket", "value"])
    temp = df[df["direction"].map(direction_key).eq("SAIDA")].copy()
    if temp.empty:
        return pd.DataFrame(columns=["bucket", "value"])
    temp["bucket"] = temp["description"].map(expense_bucket)
    out = temp.groupby("bucket")["amount"].sum().abs().reset_index().rename(columns={"amount": "value"})
    return out.sort_values("value", ascending=False)


def build_balance_projection(
    engine: Engine,
    unit_ids: Iterable[int],
    period_df: pd.DataFrame,
    end_date: date,
    settings: Dict[str, float],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
    unit_ids = [int(x) for x in unit_ids]
    current_balance = float(settings.get("owner_current_balance") or 0.0)
    goal_balance = float(settings.get("owner_balance_goal") or settings.get("capital_giro_target") or 0.0)
    balance_source = "saldo informado"
    fallback_balance = fetch_latest_recorded_balance(engine, unit_ids)

    if abs(current_balance) < 0.005 and fallback_balance:
        current_balance = fallback_balance
        balance_source = "ultimo saldo do extrato"

    future_total = sum_transaction_amounts(engine, unit_ids, start_date=end_date + timedelta(days=1))
    period_total = float(period_df["amount"].sum()) if not period_df.empty else 0.0
    opening_balance = current_balance - future_total - period_total

    working = period_df.copy()
    if not working.empty:
        working = working.sort_values(["tx_date", "id"]).reset_index(drop=True)
        working["running_balance"] = opening_balance + working["amount"].cumsum()
        working["tx_day"] = pd.to_datetime(working["tx_date"]).dt.date
        daily_balance = (
            working.groupby("tx_day")
            .agg(
                revenue=("amount", lambda s: float(s[s > 0].sum())),
                expense=("amount", lambda s: float(s[s < 0].abs().sum())),
                net=("amount", "sum"),
                closing_balance=("running_balance", "last"),
            )
            .reset_index()
            .rename(columns={"tx_day": "tx_date"})
        )
        closing_balance = float(working["running_balance"].iloc[-1])
    else:
        daily_balance = pd.DataFrame(columns=["tx_date", "revenue", "expense", "net", "closing_balance"])
        closing_balance = float(opening_balance)

    return working, daily_balance, {
        "current_balance": float(current_balance),
        "goal_balance": float(goal_balance),
        "opening_balance": float(opening_balance),
        "closing_balance": float(closing_balance),
        "period_change": float(period_total),
        "future_total": float(future_total),
        "balance_source": balance_source,
    }



def build_export_frame(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Data", "Unidade", "Tipo", "Descricao", "Categoria", "Valor", "Saldo projetado", "Origem",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)

    export_df = pd.DataFrame(
        {
            "Data": pd.to_datetime(df["tx_date"]).dt.date,
            "Unidade": df.get("unit_name", "").fillna(""),
            "Tipo": df["direction"].fillna(""),
            "Descricao": df["description"].fillna(""),
            "Categoria": df["category"].fillna(""),
            "Valor": df["amount"].astype(float),
            "Saldo projetado": df.get("running_balance", pd.Series([0.0] * len(df))).astype(float),
            "Origem": df["source_type"].fillna(""),
        }
    )
    return export_df[columns]



def excel_column_name(index: int) -> str:
    result = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result



def dataframe_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Movimentacoes") -> bytes:
    frame = df.copy()
    if frame.empty:
        frame = pd.DataFrame(columns=["Data", "Unidade", "Tipo", "Descricao", "Categoria", "Valor", "Saldo projetado", "Origem"])

    headers = list(frame.columns)
    rows = frame.to_dict(orient="records")
    widths = []
    for column in headers:
        column_width = max(len(str(column)), *(len(str(value)) for value in frame[column].tolist()), 10)
        widths.append(min(max(column_width + 2, 12), 34))

    def cell_xml(value, style_index: int) -> str:
        if pd.isna(value):
            return f'<c s="{style_index}"/>'
        if isinstance(value, (pd.Timestamp, datetime, date)):
            date_value = pd.Timestamp(value).date()
            serial = (date_value - date(1899, 12, 30)).days
            return f'<c s="{style_index}" t="n"><v>{serial}</v></c>'
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<c s="{style_index}" t="n"><v>{float(value):.2f}</v></c>'
        return f'<c s="{style_index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'

    row_xml = []
    header_cells = "".join(cell_xml(header, 1) for header in headers)
    row_xml.append(f'<row r="1">{header_cells}</row>')
    for row_index, row in enumerate(rows, start=2):
        cells = []
        for column in headers:
            value = row.get(column)
            if column == "Data":
                style_index = 2
            elif column in {"Valor", "Saldo projetado"}:
                style_index = 3
            else:
                style_index = 0
            cells.append(cell_xml(value, style_index))
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    cols_xml = "".join(
        f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>'
        for idx, width in enumerate(widths, start=1)
    )
    last_cell = f'{excel_column_name(len(headers) - 1)}{len(rows) + 1}'
    safe_sheet_name = escape(sheet_name[:31] or "Movimentacoes")

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
    <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
    <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
    <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
    <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
    <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''
    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
    <sheets>
        <sheet name="{safe_sheet_name}" sheetId="1" r:id="rId1"/>
    </sheets>
</workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <numFmts count="2">
        <numFmt numFmtId="164" formatCode="dd/mm/yyyy"/>
        <numFmt numFmtId="165" formatCode="[$R$-416] #,##0.00;[Red]-[$R$-416] #,##0.00"/>
    </numFmts>
    <fonts count="2">
        <font><sz val="11"/><name val="Aptos"/></font>
        <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Aptos"/></font>
    </fonts>
    <fills count="3">
        <fill><patternFill patternType="none"/></fill>
        <fill><patternFill patternType="gray125"/></fill>
        <fill><patternFill patternType="solid"><fgColor rgb="FF18171D"/><bgColor indexed="64"/></patternFill></fill>
    </fills>
    <borders count="1">
        <border><left/><right/><top/><bottom/><diagonal/></border>
    </borders>
    <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
    <cellXfs count="4">
        <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
        <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
        <xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
        <xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    </cellXfs>
    <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''
    worksheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <sheetViews>
        <sheetView workbookViewId="0">
            <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
        </sheetView>
    </sheetViews>
    <sheetFormatPr defaultRowHeight="15"/>
    <cols>{cols_xml}</cols>
    <sheetData>{''.join(row_xml)}</sheetData>
    <autoFilter ref="A1:{last_cell}"/>
</worksheet>'''
    core_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <dc:creator>Codex</dc:creator>
    <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
    <dcterms:created xsi:type="dcterms:W3CDTF">2026-04-19T00:00:00Z</dcterms:created>
    <dcterms:modified xsi:type="dcterms:W3CDTF">2026-04-19T00:00:00Z</dcterms:modified>
</cp:coreProperties>'''
    app_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
    <Application>Codex</Application>
    <HeadingPairs>
        <vt:vector size="2" baseType="variant">
            <vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant>
            <vt:variant><vt:i4>1</vt:i4></vt:variant>
        </vt:vector>
    </HeadingPairs>
    <TitlesOfParts>
        <vt:vector size="1" baseType="lpstr">
            <vt:lpstr>{safe_sheet_name}</vt:lpstr>
        </vt:vector>
    </TitlesOfParts>
</Properties>'''

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("docProps/core.xml", core_xml)
        archive.writestr("docProps/app.xml", app_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
    buffer.seek(0)
    return buffer.getvalue()


# -----------------------------------------------------------------------------
# Interface
# -----------------------------------------------------------------------------


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0) 28%),
                linear-gradient(135deg, #f7f1e8 0%, #efe7da 45%, #f8f4ee 100%);
            color: #16161a;
            font-family: "Aptos", "Trebuchet MS", sans-serif;
        }
        .block-container {
            padding-top: 1.1rem;
            padding-bottom: 2.2rem;
            max-width: 1480px;
        }
        h1, h2, h3, h4 {
            color: #16161a !important;
            letter-spacing: -0.02em;
            font-weight: 800;
        }
        [data-testid="stTabs"] [role="tablist"] {
            gap: 0.6rem;
        }
        [data-testid="stTabs"] [role="tab"] {
            background: rgba(255, 255, 255, 0.78);
            border-radius: 999px;
            border: 1px solid rgba(24, 23, 29, 0.08);
            padding: 0.55rem 1rem;
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            background: #18171d;
            color: #ffffff;
        }
        .stButton > button, .stDownloadButton > button {
            background: #18171d;
            color: #ffffff;
            border-radius: 999px;
            border: none;
            padding: 0.55rem 1rem;
            font-weight: 700;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            background: #0f1014;
            color: #ffffff;
        }
        .stNumberInput input, .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stDateInput input {
            border-radius: 14px !important;
            border: 1px solid rgba(24, 23, 29, 0.12) !important;
            background: rgba(255, 255, 255, 0.82) !important;
        }
        .stDataFrame {
            border-radius: 22px;
            overflow: hidden;
            border: 1px solid rgba(24, 23, 29, 0.06);
            box-shadow: 0 18px 45px rgba(44, 33, 17, 0.08);
        }
        .shell-card, .side-card, .section-card {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(24, 23, 29, 0.08);
            box-shadow: 0 18px 45px rgba(44, 33, 17, 0.08);
            border-radius: 28px;
            padding: 1.2rem 1.25rem;
            margin-bottom: 1rem;
            backdrop-filter: blur(10px);
        }
        .hero-card {
            background: linear-gradient(135deg, #16161a 0%, #23222b 55%, #0c482f 100%);
            color: #ffffff;
            border-radius: 30px;
            padding: 1.4rem 1.45rem;
            box-shadow: 0 22px 55px rgba(15, 16, 20, 0.25);
            margin-bottom: 1rem;
        }
        .eyebrow {
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            opacity: 0.72;
            margin-bottom: 0.4rem;
        }
        .hero-title {
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .hero-amount {
            font-size: 2.35rem;
            line-height: 1.02;
            font-weight: 900;
            letter-spacing: -0.05em;
        }
        .hero-subtitle {
            color: rgba(255,255,255,0.72);
            margin-top: 0.35rem;
            font-size: 0.92rem;
        }
        .hero-grid, .tile-grid {
            display: grid;
            gap: 0.8rem;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            margin-top: 1rem;
        }
        .tile, .mini-tile {
            background: rgba(255, 255, 255, 0.82);
            color: #18171d;
            border-radius: 22px;
            padding: 0.95rem 1rem;
            border: 1px solid rgba(24, 23, 29, 0.06);
        }
        .tile.dark {
            background: rgba(255,255,255,0.12);
            color: #ffffff;
            border-color: rgba(255,255,255,0.09);
        }
        .tile-label {
            font-size: 0.82rem;
            color: #6b6a70;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        .tile.dark .tile-label {
            color: rgba(255,255,255,0.64);
        }
        .tile-value {
            font-size: 1.4rem;
            font-weight: 800;
            letter-spacing: -0.03em;
        }
        .tile-note {
            font-size: 0.85rem;
            color: #7a7882;
            margin-top: 0.25rem;
        }
        .tile.dark .tile-note {
            color: rgba(255,255,255,0.72);
        }
        .pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.38rem 0.7rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
        }
        .tone-positive {
            background: rgba(28, 175, 98, 0.13);
            color: #11834b;
        }
        .tone-negative {
            background: rgba(214, 75, 70, 0.14);
            color: #b53a35;
        }
        .tone-neutral {
            background: rgba(255, 255, 255, 0.14);
            color: #ffffff;
        }
        .progress-rail {
            background: rgba(24, 23, 29, 0.08);
            border-radius: 999px;
            height: 10px;
            overflow: hidden;
            margin-top: 0.7rem;
        }
        .progress-fill {
            display: block;
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #14a35d 0%, #46d38f 100%);
        }
        .feed-card {
            background: rgba(255, 255, 255, 0.82);
            border-radius: 28px;
            border: 1px solid rgba(24, 23, 29, 0.08);
            box-shadow: 0 18px 45px rgba(44, 33, 17, 0.08);
            padding: 1.15rem;
        }
        .feed-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.8rem;
        }
        .feed-title {
            font-size: 1.1rem;
            font-weight: 800;
        }
        .feed-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.9rem;
            padding: 0.8rem 0;
            border-bottom: 1px solid rgba(24, 23, 29, 0.07);
        }
        .feed-row:last-child {
            border-bottom: none;
            padding-bottom: 0.2rem;
        }
        .feed-name {
            font-weight: 700;
            color: #18171d;
        }
        .feed-date {
            font-size: 0.82rem;
            color: #76737e;
            margin-top: 0.18rem;
        }
        .feed-amount {
            font-weight: 800;
            white-space: nowrap;
        }
        .section-title {
            font-size: 1.1rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
        }
        .section-note {
            font-size: 0.9rem;
            color: #6f6b74;
            margin-bottom: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def hero_card_html(unit_filter: str, balance_info: Dict[str, float], status_label: str, tone_class: str) -> str:
    goal_balance = float(balance_info.get("goal_balance", 0.0))
    goal_progress = 0.0 if goal_balance <= 0 else max(min(balance_info["current_balance"] / goal_balance, 1.0), 0.0)
    return f"""
    <div class="hero-card">
        <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;flex-wrap:wrap;">
            <div>
                <div class="eyebrow">Conta da proprietaria</div>
                <div class="hero-title">{escape(unit_filter)}</div>
                <div class="hero-amount">{format_brl(balance_info['current_balance'])}</div>
                <div class="hero-subtitle">Fonte do saldo: {escape(balance_info['balance_source'])} | Fechamento projetado do periodo: {format_brl(balance_info['closing_balance'])}</div>
            </div>
            <div class="pill {tone_class}">{escape(status_label)}</div>
        </div>
        <div class="hero-grid">
            <div class="tile dark">
                <div class="tile-label">Meta de caixa</div>
                <div class="tile-value">{format_brl(goal_balance)}</div>
                <div class="tile-note">Faltam {format_brl(max(goal_balance - balance_info['current_balance'], 0.0))} para atingir a meta.</div>
            </div>
            <div class="tile dark">
                <div class="tile-label">Saldo no inicio do periodo</div>
                <div class="tile-value">{format_brl(balance_info['opening_balance'])}</div>
                <div class="tile-note">Estimativa do saldo no primeiro dia, antes das movimentacoes do intervalo.</div>
            </div>
            <div class="tile dark">
                <div class="tile-label">Variacao do periodo</div>
                <div class="tile-value">{format_brl(balance_info['period_change'])}</div>
                <div class="tile-note">Resultado liquido do intervalo: entradas menos saidas.</div>
            </div>
        </div>
        <div class="progress-rail">
            <span class="progress-fill" style="width:{goal_progress * 100:.1f}%"></span>
        </div>
    </div>
    """



def metric_tile_html(title: str, value: str, note: str, tone_class: str = "") -> str:
    tone_label = f" pill {tone_class}" if tone_class else ""
    pill = f'<div class="{tone_label.strip()}">{escape(note)}</div>' if tone_class else f'<div class="tile-note">{escape(note)}</div>'
    return f"""
    <div class="tile">
        <div class="tile-label">{escape(title)}</div>
        <div class="tile-value">{escape(value)}</div>
        {pill}
    </div>
    """



def transaction_feed_html(df: pd.DataFrame) -> str:
    if df.empty:
        return (
            '<div class="feed-card">'
            '<div class="feed-header"><div class="feed-title">Movimentacoes</div></div>'
            '<div class="section-note">Ainda nao ha lancamentos para o periodo selecionado.</div>'
            "</div>"
        )

    rows_html = []
    preview = df.sort_values(["tx_date", "id"], ascending=[False, False]).head(8)
    for _, row in preview.iterrows():
        amount_class = "tone-negative" if float(row["amount"]) < 0 else "tone-positive"
        amount_value = format_brl(float(row["amount"]))
        date_value = pd.to_datetime(row["tx_date"]).strftime("%d/%m/%Y")
        description = escape(str(row["description"])[:42])
        category = escape(str(row["category"]))
        rows_html.append(
            f'<div class="feed-row"><div><div class="feed-name">{description}</div>'
            f'<div class="feed-date">{date_value} | {category}</div></div>'
            f'<div class="feed-amount {amount_class}">{amount_value}</div></div>'
        )

    return (
        '<div class="feed-card">'
        '<div class="feed-header">'
        '<div class="feed-title">Movimentacoes</div>'
        '<div class="pill tone-neutral" style="background:#18171d;color:#fff;">Ultimas 8</div>'
        "</div>"
        f"{''.join(rows_html)}"
        "</div>"
    )



def plot_money_flow(df_daily: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 4.2))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    if df_daily.empty:
        ax.text(0.5, 0.5, "Sem dados para o periodo selecionado.", ha="center", va="center")
        ax.axis("off")
    else:
        temp = df_daily.copy().sort_values("tx_date")
        x = pd.to_datetime(temp["tx_date"])
        ax.plot(x, temp["revenue"], color="#15a869", linewidth=2.6, marker="o", label="Entradas")
        ax.plot(x, temp["expense"], color="#d75b4f", linewidth=2.2, marker="o", linestyle="--", label="Saidas")
        ax.fill_between(x, temp["revenue"], color="#15a869", alpha=0.08)
        ax.fill_between(x, temp["expense"], color="#d75b4f", alpha=0.04)
        ax.set_title("Fluxo diario de caixa", loc="left", fontsize=13, fontweight="bold")
        ax.grid(True, alpha=0.18)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", rotation=30)
        ax.legend(frameon=False)
    st.pyplot(fig, clear_figure=True)



def plot_balance_flow(df_balance: pd.DataFrame, goal_balance: float) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 4.2))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    if df_balance.empty:
        ax.text(0.5, 0.5, "Defina um saldo atual ou importe movimentacoes para ver a curva de saldo.", ha="center", va="center")
        ax.axis("off")
    else:
        temp = df_balance.copy().sort_values("tx_date")
        x = pd.to_datetime(temp["tx_date"])
        y = temp["closing_balance"].astype(float)
        line_color = "#15a869" if float(y.iloc[-1]) >= 0 else "#d75b4f"
        ax.plot(x, y, color=line_color, linewidth=2.8, marker="o")
        ax.fill_between(x, y, 0, color=line_color, alpha=0.08)
        ax.axhline(0, color="#16161a", linewidth=1.0, alpha=0.3)
        if goal_balance > 0:
            ax.axhline(goal_balance, color="#18171d", linewidth=1.4, linestyle="--", alpha=0.6)
        ax.set_title("Saldo projetado ao longo do periodo", loc="left", fontsize=13, fontweight="bold")
        ax.grid(True, alpha=0.18)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", rotation=30)
    st.pyplot(fig, clear_figure=True)



def plot_expense_donut(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 4.7))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    if df.empty or float(df["value"].sum()) == 0:
        ax.text(0.5, 0.5, "Sem despesas no periodo.", ha="center", va="center")
        ax.axis("off")
    else:
        colors = ["#18171d", "#15a869", "#efb463", "#d75b4f", "#5f7ad8", "#b07bf4"]
        wedges, _ = ax.pie(
            df["value"].tolist(),
            startangle=90,
            colors=colors[: len(df)],
            wedgeprops=dict(width=0.36, edgecolor="white"),
        )
        ax.legend(wedges, df["bucket"].tolist(), loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False)
        ax.set_title("Despesas por categoria", loc="left", fontsize=13, fontweight="bold")
        ax.set_aspect("equal")
    st.pyplot(fig, clear_figure=True)



def render_goal_card(current_value: float, goal_value: float, note: str) -> None:
    tone_class = "tone-positive" if current_value >= max(goal_value, 0.0) else "tone-negative"
    progress = 0.0 if goal_value <= 0 else max(min(current_value / goal_value, 1.0), 0.0)
    st.markdown(
        f"""
        <div class="side-card">
            <div class="section-title">Meta de saldo</div>
            <div class="section-note">{escape(note)}</div>
            <div class="tile-grid">
                <div class="mini-tile">
                    <div class="tile-label">Saldo atual</div>
                    <div class="tile-value">{format_brl(current_value)}</div>
                </div>
                <div class="mini-tile">
                    <div class="tile-label">Meta</div>
                    <div class="tile-value">{format_brl(goal_value)}</div>
                </div>
            </div>
            <div class="progress-rail"><span class="progress-fill" style="width:{progress * 100:.1f}%"></span></div>
            <div class="pill {tone_class}" style="margin-top:0.8rem;">{'Meta coberta' if current_value >= goal_value else 'Abaixo da meta'}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )




def select_unit_top(units_df: pd.DataFrame) -> str:
    options = ["Consolidado"] + units_df["name"].tolist()
    return st.selectbox("Unidade de análise", options, index=0)



def get_unit_ids_from_filter(unit_filter: str, units_df: pd.DataFrame) -> List[int]:
    if unit_filter == "Consolidado":
        return units_df["id"].astype(int).tolist()
    row = units_df[units_df["name"] == unit_filter]
    return [int(row.iloc[0]["id"])] if not row.empty else []



def aggregate_settings(settings_list: List[Dict[str, float]]) -> Dict[str, float]:
    if not settings_list:
        return DEFAULT_SETTINGS.copy()
    out = {}
    for key in DEFAULT_SETTINGS:
        if key in {"reserve_months", "days_in_month"}:
            out[key] = int(round(sum(float(s[key]) for s in settings_list) / len(settings_list)))
        else:
            out[key] = float(sum(float(s[key]) for s in settings_list))
    out["reserve_months"] = max(1, int(out["reserve_months"]))
    out["days_in_month"] = max(1, int(out["days_in_month"]))
    out["ticket_goal"] = float(sum(float(s["ticket_goal"]) for s in settings_list) / len(settings_list))
    return out



def render_dashboard(engine: Engine, units_df: pd.DataFrame, unit_filter: str) -> None:
    st.subheader("Dashboard Principal")

    unit_ids = get_unit_ids_from_filter(unit_filter, units_df)
    today = date.today()
    default_start, default_end = month_bounds(today)

    c_top1, c_top2, c_top3 = st.columns([1.7, 1.2, 1.6])
    with c_top1:
        period_value = st.date_input(
            "Periodo de analise",
            value=(default_start, default_end),
            help="Escolha qualquer intervalo para recalcular saldo, metas e exportacao.",
        )
    with c_top2:
        mode = st.radio("Visao", ["Periodo selecionado", "Mes corrente"], horizontal=False, index=0)
    with c_top3:
        st.caption(
            "Saldo atual e meta de caixa ficam por unidade. No consolidado, o painel soma os valores configurados."
        )

    if mode == "Mes corrente":
        start_date, end_date = default_start, default_end
    else:
        start_date, end_date = normalize_date_range(period_value, default_start, default_end)

    settings_list = [fetch_settings(engine, unit_id) for unit_id in unit_ids] or [DEFAULT_SETTINGS.copy()]
    agg_settings = aggregate_settings(settings_list)
    targets = compute_targets(agg_settings)

    period_df = fetch_transactions(engine, unit_ids, start_date, end_date)
    metrics = period_metrics(period_df)
    daily_frame = daily_summary(period_df)
    expense_frame = build_expense_donut_frame(period_df)
    days_selected = period_days(start_date, end_date)

    period_df, balance_daily, balance_info = build_balance_projection(engine, unit_ids, period_df, end_date, agg_settings)
    export_df = build_export_frame(period_df)

    if balance_info["current_balance"] >= max(balance_info["goal_balance"], 0.0) and balance_info["goal_balance"] > 0:
        status_label = "Meta de saldo atingida"
        tone_class = "tone-positive"
    elif balance_info["current_balance"] >= 0:
        status_label = "Saldo positivo"
        tone_class = "tone-positive"
    else:
        status_label = "Saldo negativo"
        tone_class = "tone-negative"

    st.markdown(hero_card_html(unit_filter, balance_info, status_label, tone_class), unsafe_allow_html=True)

    target_period = targets.daily_target * days_selected
    metric_tiles = "".join(
        [
            metric_tile_html("Entradas operacionais", format_brl(metrics["revenue"]), "Receitas classificadas como operacionais."),
            metric_tile_html("Saidas operacionais", format_brl(metrics["expense"]), "Despesas e pagamentos do intervalo."),
            metric_tile_html(
                "Resultado operacional",
                format_brl(metrics["net"]),
                "Periodo no azul" if metrics["net"] >= 0 else "Periodo no vermelho",
                "tone-positive" if metrics["net"] >= 0 else "tone-negative",
            ),
            metric_tile_html("Meta proporcional", format_brl(target_period), f"{days_selected} dia(s) selecionado(s)."),
            metric_tile_html("Break-even mensal", format_brl(targets.break_even), "Custo fixo + variavel planejado."),
            metric_tile_html("Meta diaria", format_brl(targets.daily_target), "Ritmo diario sugerido para o caixa."),
        ]
    )
    st.markdown(
        f"""
        <div class="shell-card">
            <div class="section-title">Visao rapida</div>
            <div class="section-note">Cards inspirados no layout enviado, sem perder o controle operacional da aplicacao.</div>
            <div class="tile-grid">{metric_tiles}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    main_col, side_col = st.columns([2.1, 1.0])
    with main_col:
        st.markdown(
            """
            <div class="section-card">
                <div class="section-title">Saldo projetado</div>
                <div class="section-note">A linha considera o saldo atual informado pela proprietaria e recalcula o saldo ao longo das movimentacoes do periodo.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        plot_balance_flow(balance_daily, balance_info["goal_balance"])

        c_graph1, c_graph2 = st.columns([1.45, 1.0])
        with c_graph1:
            st.markdown(
                """
                <div class="section-card">
                    <div class="section-title">Money flow</div>
                    <div class="section-note">Entradas e saidas por dia para acompanhar o ritmo do caixa.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            plot_money_flow(daily_frame)
        with c_graph2:
            st.markdown(
                """
                <div class="section-card">
                    <div class="section-title">Despesas</div>
                    <div class="section-note">Peso das principais categorias de gasto no intervalo.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            plot_expense_donut(expense_frame)

        st.markdown("### Movimentacoes do periodo")
        if period_df.empty:
            st.info("Sem movimentacoes para o periodo selecionado.")
        else:
            table_df = period_df.copy()
            table_df["amount"] = table_df["amount"].map(format_brl)
            table_df["running_balance"] = table_df["running_balance"].map(format_brl)
            st.dataframe(
                table_df[["tx_date", "unit_name", "direction", "description", "category", "amount", "running_balance", "source_type"]],
                use_container_width=True,
                hide_index=True,
            )

    with side_col:
        render_goal_card(
            balance_info["current_balance"],
            balance_info["goal_balance"],
            "A meta ajuda a proprietaria a enxergar rapidamente se o caixa esta no nivel esperado.",
        )

        if unit_filter != "Consolidado" and unit_ids:
            unit_settings = fetch_settings(engine, unit_ids[0])
            with st.form(f"owner_balance_form_{unit_ids[0]}"):
                st.markdown("### Atualizar saldo")
                owner_current_balance = st.number_input(
                    "Saldo atual da conta",
                    value=float(unit_settings.get("owner_current_balance", 0.0)),
                    step=100.0,
                    format="%.2f",
                )
                owner_balance_goal = st.number_input(
                    "Meta de saldo",
                    value=float(unit_settings.get("owner_balance_goal", unit_settings.get("capital_giro_target", 0.0))),
                    min_value=0.0,
                    step=100.0,
                    format="%.2f",
                )
                save_balance = st.form_submit_button("Salvar saldo")
                if save_balance:
                    unit_settings["owner_current_balance"] = owner_current_balance
                    unit_settings["owner_balance_goal"] = owner_balance_goal
                    save_settings(engine, unit_ids[0], unit_settings)
                    st.success("Saldo da proprietaria atualizado.")
                    st.rerun()
        else:
            st.info("No consolidado, edite o saldo atual em Configuracoes de Custos por unidade.")

        st.markdown(transaction_feed_html(period_df), unsafe_allow_html=True)

        st.markdown("### Exportar")
        if export_df.empty:
            st.caption("Quando houver movimentacoes no periodo, a planilha organizada aparece aqui para download.")
        else:
            sheet_name = f"Mov_{start_date.strftime('%d%m')}_{end_date.strftime('%d%m')}"
            xlsx_bytes = dataframe_to_xlsx_bytes(export_df, sheet_name=sheet_name)
            csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
            filename_base = f"movimentacoes_{unit_filter.replace(' ', '_').lower()}_{start_date.isoformat()}_{end_date.isoformat()}"
            st.download_button(
                "Baixar planilha (.xlsx)",
                data=xlsx_bytes,
                file_name=f"{filename_base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            st.download_button(
                "Baixar CSV",
                data=csv_bytes,
                file_name=f"{filename_base}.csv",
                mime="text/csv",
                use_container_width=True,
            )




def render_manage_transactions(engine: Engine, unit_id: int) -> None:
    st.markdown("#### Corrigir ou excluir lançamentos")
    recent = fetch_recent_transactions(engine, unit_id, limit=80)
    if recent.empty:
        st.info("Não há lançamentos para editar nesta unidade.")
    else:
        recent = recent.copy()
        recent["label"] = recent.apply(
            lambda r: f"#{int(r['id'])} | {r['tx_date']} | {r['direction']} | {str(r['description'])[:55]} | {format_brl(float(r['amount']))}",
            axis=1,
        )

        selected_label = st.selectbox("Selecione um lançamento", recent["label"].tolist(), key=f"single_tx_{unit_id}")
        row = recent[recent["label"] == selected_label].iloc[0]

        with st.form("edit_transaction_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                edit_date = st.date_input("Data", value=row["tx_date"])
                edit_direction = st.selectbox(
                    "Tipo",
                    ["Entrada", "Saída"],
                    index=0 if row["direction"] == "Entrada" else 1,
                )
            with c2:
                edit_amount = st.number_input(
                    "Valor",
                    min_value=0.0,
                    value=float(abs(row["amount"])),
                    step=1.0,
                    format="%.2f",
                )
                edit_category = st.selectbox(
                    "Categoria",
                    CATEGORY_OPTIONS,
                    index=CATEGORY_OPTIONS.index(row["category"]) if row["category"] in CATEGORY_OPTIONS else 1,
                )
            with c3:
                edit_desc = st.text_input("Descrição", value=str(row["description"]))
                st.write("")
                st.write("")
                save_edit = st.form_submit_button("Salvar correção")

            if save_edit:
                if not str(edit_desc).strip():
                    st.error("A descrição não pode ficar em branco.")
                else:
                    update_transaction(
                        engine,
                        int(row["id"]),
                        unit_id,
                        edit_date,
                        edit_direction,
                        edit_desc,
                        float(edit_amount),
                        edit_category,
                    )
                    st.success("Lançamento corrigido com sucesso.")
                    st.rerun()

        if st.button("Excluir lançamento selecionado", type="secondary", key=f"delete_single_{unit_id}"):
            delete_transaction(engine, int(row["id"]))
            st.success("Lançamento excluído.")
            st.rerun()

    st.divider()
    st.markdown("#### Exclusão em lote por mês")

    ref_month = st.date_input(
        "Escolha um mês de referência",
        value=date.today(),
        key=f"bulk_month_{unit_id}",
    )

    month_df = fetch_transactions_by_month(engine, unit_id, ref_month)

    if month_df.empty:
        st.info("Nenhum lançamento encontrado neste mês.")
        return

    month_df = month_df.copy()
    month_df["label"] = month_df.apply(
        lambda r: f"#{int(r['id'])} | {r['tx_date']} | {r['direction']} | {str(r['description'])[:60]} | {format_brl(float(r['amount']))}",
        axis=1,
    )

    st.caption(f"Encontrados {len(month_df)} lançamentos no mês selecionado.")

    selected_ids = st.multiselect(
        "Selecione os lançamentos que quer excluir",
        options=month_df["id"].tolist(),
        format_func=lambda x: month_df.loc[month_df["id"] == x, "label"].iloc[0],
        key=f"bulk_delete_select_{unit_id}_{ref_month.strftime('%Y_%m')}",
    )

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Excluir selecionados", type="secondary", key=f"delete_selected_{unit_id}_{ref_month.strftime('%Y_%m')}"):
            deleted = delete_transactions(engine, selected_ids)
            st.success(f"{deleted} lançamento(s) excluído(s).")
            st.rerun()

    with c2:
        confirm_all = st.checkbox(
            "Confirmo que quero excluir tudo do mês",
            key=f"confirm_delete_all_{unit_id}_{ref_month.strftime('%Y_%m')}",
        )
        if st.button("Excluir tudo do mês", type="primary", key=f"delete_all_{unit_id}_{ref_month.strftime('%Y_%m')}"):
            if not confirm_all:
                st.error("Marque a confirmação antes de excluir tudo.")
            else:
                deleted = delete_transactions(engine, month_df["id"].tolist())
                st.warning(f"{deleted} lançamento(s) do mês foram excluídos.")
                st.rerun()



def render_upload_and_manual(engine: Engine, units_df: pd.DataFrame, unit_filter: str) -> None:
    st.subheader("Lançamentos e Upload")

    unit_options = units_df["name"].tolist()
    default_index = 0 if unit_filter == "Consolidado" else max(unit_options.index(unit_filter), 0) if unit_filter in unit_options else 0
    upload_unit_name = st.selectbox("Unidade de trabalho", unit_options, index=default_index)
    upload_unit_id = int(units_df.loc[units_df["name"] == upload_unit_name, "id"].iloc[0])

    st.markdown("#### Upload do PDF bancario")
    st.caption(
        "O sistema detecta automaticamente extratos Stone e Itau. "
        "Cada arquivo recebe um hash proprio para evitar duplicidade e permitir exclusao posterior."
    )
    uploaded = st.file_uploader("Envie o extrato em PDF", type=["pdf"])

    if uploaded is not None:
        if st.button("Processar PDF", type="primary"):
            temp_dir = APP_DATA_DIR / "temp_uploads"
            temp_dir.mkdir(exist_ok=True)
            temp_path = temp_dir / uploaded.name
            temp_path.write_bytes(uploaded.getbuffer())
            file_bytes = temp_path.read_bytes()
            file_hash = sha1_text(file_bytes.hex())
            detected_layout = detect_statement_layout(str(temp_path))
            bank_label = {"itau": "Ita?", "stone": "Stone"}.get(detected_layout, "Banco")
            parsed_df = parse_statement_pdf(str(temp_path), upload_unit_id, uploaded.name, file_hash)
            if parsed_df.empty:
                st.error("Nao encontrei movimentacoes nesse PDF. Confira se o arquivo esta legivel e tente novamente.")
            else:
                inserted, skipped = insert_transactions(engine, parsed_df)
                record_uploaded_file(engine, upload_unit_id, uploaded.name, file_hash, inserted, skipped)
                st.success(
                    f"Extrato {bank_label} processado para {upload_unit_name}. Inseridos: {inserted} | Ignorados: {skipped}."
                )
                st.rerun()

    st.markdown("#### Lançamento manual em dinheiro vivo")
    with st.form("manual_entry_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            manual_date = st.date_input("Data", value=date.today())
        with col2:
            manual_direction = st.selectbox("Tipo", ["Entrada", "Saída"])
        with col3:
            manual_amount = st.number_input("Valor (R$)", min_value=0.0, value=0.0, step=1.0, format="%.2f")

        manual_description = st.text_input("Descrição")
        manual_category = st.selectbox("Categoria", CATEGORY_OPTIONS)
        submitted = st.form_submit_button("Salvar lançamento")
        if submitted:
            if manual_amount <= 0:
                st.error("Informe um valor maior que zero.")
            elif not manual_description.strip():
                st.error("Informe uma descrição.")
            else:
                amount = abs(float(manual_amount))
                if manual_direction == "Saída":
                    amount *= -1
                tx_hash = sha1_text(
                    f"{upload_unit_id}|{manual_date.isoformat()}|{manual_direction}|{manual_description.upper()}|{abs(float(manual_amount)):.2f}|manual"
                )
                df = pd.DataFrame([
                    {
                        "unit_id": upload_unit_id,
                        "tx_date": manual_date.isoformat(),
                        "direction": manual_direction,
                        "description": normalize_text(manual_description),
                        "amount": amount,
                        "balance": None,
                        "category": manual_category,
                        "source_type": "manual",
                        "source_file": "manual",
                        "source_hash": None,
                        "tx_hash": tx_hash,
                        "raw_text": f"MANUAL | {manual_description}",
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    }
                ])
                inserted, _ = insert_transactions(engine, df)
                if inserted:
                    st.success("Lançamento manual salvo.")
                    st.rerun()
                else:
                    st.warning("Esse lançamento já existe ou não pôde ser salvo.")

    st.markdown("#### Corrigir ou excluir lançamentos")
    render_manage_transactions(engine, upload_unit_id)

    st.markdown("#### Últimos uploads")
    uploads = fetch_uploaded_files(engine, upload_unit_id)
    if uploads.empty:
        st.info("Ainda não houve upload nessa unidade.")
    else:
        st.dataframe(uploads, use_container_width=True, hide_index=True)
        uploads = uploads.copy().reset_index(drop=True)
        uploads["upload_label"] = uploads.apply(
            lambda r: f"#{int(r['id'])} | {r['file_name']} | {r['uploaded_at']} | +{int(r['rows_inserted'])} / -{int(r['rows_skipped'])}",
            axis=1,
        )
        selected_upload = st.selectbox(
            "Selecionar upload para excluir",
            uploads["upload_label"].tolist(),
        )
        if st.button("Excluir upload selecionado"):
            selected_row = uploads.loc[uploads["upload_label"] == selected_upload].iloc[0]
            deleted_tx = delete_uploaded_file(engine, int(selected_row["id"]))
            st.success(f"Upload excluído. {deleted_tx} lançamentos associados removidos.")
            st.rerun()



def render_settings(engine: Engine, units_df: pd.DataFrame, unit_filter: str) -> None:
    st.subheader("Configurações de Custos")

    unit_options = units_df["name"].tolist()
    default_index = 0 if unit_filter == "Consolidado" else unit_options.index(unit_filter) if unit_filter in unit_options else 0
    config_unit_name = st.selectbox("Unidade para edição", unit_options, index=default_index, key="config_unit")
    config_unit_id = int(units_df.loc[units_df["name"] == config_unit_name, "id"].iloc[0])

    settings = fetch_settings(engine, config_unit_id)
    st.caption(
        "Os valores abaixo atualizam em tempo real o ponto de equilíbrio e os termômetros. "
        "A base inicial do plano considera custos fixos de R$ 31.730, custos variáveis de R$ 8.500 e capital de giro-alvo de R$ 126.724,50."
    )

    with st.form("settings_form"):
        st.markdown("#### Custos fixos")
        c1, c2, c3 = st.columns(3)
        with c1:
            fixed_payroll = st.number_input("Funcionários", value=float(settings["fixed_payroll"]), min_value=0.0, step=50.0)
            fixed_royalties = st.number_input("Royalties da franquia", value=float(settings["fixed_royalties"]), min_value=0.0, step=50.0)
            fixed_brand_marketing = st.number_input("Taxa de marketing da marca", value=float(settings["fixed_brand_marketing"]), min_value=0.0, step=10.0)
            fixed_equipment_suppliers = st.number_input("Equipamentos e fornecedores operacionais", value=float(settings["fixed_equipment_suppliers"]), min_value=0.0, step=50.0)
        with c2:
            fixed_taxes = st.number_input("Impostos provisionados", value=float(settings["fixed_taxes"]), min_value=0.0, step=50.0)
            fixed_services = st.number_input("Serviços (internet, telefone, seguro)", value=float(settings["fixed_services"]), min_value=0.0, step=10.0)
            fixed_rent = st.number_input("Aluguel da loja", value=float(settings["fixed_rent"]), min_value=0.0, step=100.0)
            fixed_card_machine = st.number_input("Maquininha", value=float(settings["fixed_card_machine"]), min_value=0.0, step=10.0)
        with c3:
            fixed_accounting = st.number_input("Contabilidade", value=float(settings["fixed_accounting"]), min_value=0.0, step=10.0)
            fixed_system = st.number_input("Sistema de gestão", value=float(settings["fixed_system"]), min_value=0.0, step=10.0)
            fixed_own_marketing = st.number_input("Marketing próprio", value=float(settings["fixed_own_marketing"]), min_value=0.0, step=50.0)
            fixed_pro_labore = st.number_input("Pró-labore da proprietária", value=float(settings["fixed_pro_labore"]), min_value=0.0, step=100.0)

        st.markdown("#### Custos variáveis")
        v1, v2 = st.columns(2)
        with v1:
            variable_supplies = st.number_input("Insumos e compras operacionais", value=float(settings["variable_supplies"]), min_value=0.0, step=50.0)
        with v2:
            variable_other = st.number_input("Outros custos variáveis", value=float(settings["variable_other"]), min_value=0.0, step=50.0)

        st.markdown("#### Capital de giro e metas")
        g1, g2, g3 = st.columns(3)
        with g1:
            capital_giro_target = st.number_input("Capital de giro-alvo", value=float(settings["capital_giro_target"]), min_value=0.0, step=100.0)
        with g2:
            reserve_months = st.number_input("Meses para formar a reserva", value=int(settings["reserve_months"]), min_value=1, step=1)
        with g3:
            days_in_month = st.number_input("Dias no mes (meta diaria)", value=int(settings["days_in_month"]), min_value=1, step=1)

        ticket_goal = st.number_input("Ticket medio-alvo", value=float(settings["ticket_goal"]), min_value=1.0, step=1.0)

        st.markdown("#### Saldo da proprietaria")
        o1, o2 = st.columns(2)
        with o1:
            owner_current_balance = st.number_input(
                "Saldo atual da conta",
                value=float(settings.get("owner_current_balance", 0.0)),
                step=100.0,
                format="%.2f",
            )
        with o2:
            owner_balance_goal = st.number_input(
                "Meta de saldo da conta",
                value=float(settings.get("owner_balance_goal", settings.get("capital_giro_target", 0.0))),
                min_value=0.0,
                step=100.0,
                format="%.2f",
            )

        save = st.form_submit_button("Salvar configurações")

        new_settings = {
            "fixed_payroll": fixed_payroll,
            "fixed_royalties": fixed_royalties,
            "fixed_brand_marketing": fixed_brand_marketing,
            "fixed_equipment_suppliers": fixed_equipment_suppliers,
            "fixed_taxes": fixed_taxes,
            "fixed_services": fixed_services,
            "fixed_rent": fixed_rent,
            "fixed_card_machine": fixed_card_machine,
            "fixed_accounting": fixed_accounting,
            "fixed_system": fixed_system,
            "fixed_own_marketing": fixed_own_marketing,
            "fixed_pro_labore": fixed_pro_labore,
            "variable_supplies": variable_supplies,
            "variable_other": variable_other,
            "capital_giro_target": capital_giro_target,
            "reserve_months": int(reserve_months),
            "days_in_month": int(days_in_month),
            "ticket_goal": ticket_goal,
            "owner_current_balance": owner_current_balance,
            "owner_balance_goal": owner_balance_goal,
        }
        preview_targets = compute_targets(new_settings)
        st.info(
            f"Prévia: fixos {format_brl(preview_targets.fixed_total)}, variáveis {format_brl(preview_targets.variable_total)}, "
            f"break-even {format_brl(preview_targets.break_even)}, meta saudável {format_brl(preview_targets.healthy_target)}."
        )

        if save:
            save_settings(engine, config_unit_id, new_settings)
            st.success("Configurações salvas.")
            st.rerun()


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide", initial_sidebar_state="collapsed")
    inject_css()

    st.title("☕ Gestão Financeira das Franquias")
    st.caption("Dashboard, lançamentos, upload de extrato e custos com persistência em SQLite.")

    engine = get_engine()
    init_db(engine)
    units_df = fetch_units(engine)
    unit_filter = select_unit_top(units_df)

    tabs = st.tabs(["Dashboard Principal", "Lançamentos e Upload", "Configurações de Custos"])
    with tabs[0]:
        render_dashboard(engine, units_df, unit_filter)
    with tabs[1]:
        render_upload_and_manual(engine, units_df, unit_filter)
    with tabs[2]:
        render_settings(engine, units_df, unit_filter)


if __name__ == "__main__":
    main()
