from datetime import date

import pandas as pd

from finance_core import (
    calculate_metrics,
    categorize_transaction,
    get_engine,
    init_db,
    insert_transaction,
    parse_brl,
    transaction_fingerprint,
)


def test_parse_brl():
    assert parse_brl("R$ 1.234,56") == 1234.56
    assert parse_brl("-850,00") == -850.0


def test_categorization():
    assert categorize_transaction("Fornecedor de café", -100) == "Fornecedores / Insumos"
    assert categorize_transaction("Venda no balcão", 250) == "Receita operacional"


def test_fingerprint_is_stable():
    a = transaction_fingerprint(1, date(2026, 7, 1), "Venda", 100.0)
    b = transaction_fingerprint(1, date(2026, 7, 1), " venda ", 100.0)
    assert a == b


def test_metrics():
    df = pd.DataFrame({"amount": [100.0, 50.0, -30.0]})
    metrics = calculate_metrics(df)
    assert metrics.revenue == 150.0
    assert metrics.expenses == 30.0
    assert metrics.net_result == 120.0
    assert metrics.average_ticket == 75.0


def test_database_deduplicates(tmp_path):
    engine = get_engine(tmp_path / "test.db")
    init_db(engine)

    inserted_first = insert_transaction(engine, 1, date(2026, 7, 1), "Venda balcão", 100.0)
    inserted_second = insert_transaction(engine, 1, date(2026, 7, 1), "Venda balcão", 100.0)

    assert inserted_first is True
    assert inserted_second is False
