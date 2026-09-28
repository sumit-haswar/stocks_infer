"""Read the supplied universe workbook without changing its held-out split."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile


XML = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EXPECTED_HEADERS = (
    "Ticker", "Company name", "Line of business", "What the company does",
    "Sector", "Size group", "Style proxy", "Test set", "Framework consideration",
    "Exchange", "Company profile source", "Size ETF", "Style ETFs", "Holdings date",
)
SETS = frozenset({"Development", "Evaluation", "Difficult case"})


@dataclass(frozen=True)
class UniverseCompany:
    ticker: str
    name: str
    line_of_business: str
    description: str
    sector: str
    size_group: str
    style_proxy: str
    test_set: str
    framework_consideration: str
    exchange: str
    profile_url: str
    workbook_row: int


def load_universe(path: Path) -> tuple[UniverseCompany, ...]:
    """Read the known Companies sheet; fail when its columns or split change."""
    with ZipFile(path) as workbook:
        names = set(workbook.namelist())
        if not {"xl/workbook.xml", "xl/worksheets/sheet1.xml"} <= names:
            raise ValueError("missing Companies worksheet")
        sheets = ET.fromstring(workbook.read("xl/workbook.xml")).find(XML + "sheets")
        if sheets is None or not list(sheets) or list(sheets)[0].get("name") != "Companies":
            raise ValueError("Companies must be the first worksheet")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in item.iter(XML + "t")) for item in root]
        root = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        sheet_data = root.find(XML + "sheetData")
        if sheet_data is None:
            raise ValueError("Companies worksheet is empty")
        rows: dict[int, dict[str, str]] = {}
        for row in sheet_data:
            number = int(row.get("r"))
            cells: dict[str, str] = {}
            for cell in row:
                column = re.match(r"[A-Z]+", cell.get("r", ""))
                if column is None:
                    continue
                value = cell.find(XML + "v")
                inline = cell.find(XML + "is")
                raw = (value.text or "") if value is not None else (
                    "".join(t.text or "" for t in inline.iter(XML + "t")) if inline is not None else ""
                )
                cells[column.group()] = shared[int(raw)] if cell.get("t") == "s" and raw else raw
            rows[number] = cells
    letters = "ABCDEFGHIJKLMN"
    if tuple(rows.get(6, {}).get(letter, "") for letter in letters) != EXPECTED_HEADERS:
        raise ValueError("Companies sheet headers changed; review the importer")
    result: list[UniverseCompany] = []
    for number in sorted(rows):
        if number <= 6 or not rows[number].get("A"):
            continue
        row = rows[number]
        if row.get("H") not in SETS or not all(row.get(letter) for letter in "ABCDJ"):
            raise ValueError(f"incomplete universe company at row {number}")
        result.append(UniverseCompany(
            ticker=row["A"].strip().upper(), name=row["B"].strip(),
            line_of_business=row["C"].strip(), description=row["D"].strip(),
            sector=row.get("E", ""), size_group=row.get("F", ""),
            style_proxy=row.get("G", ""), test_set=row["H"],
            framework_consideration=row.get("I", ""), exchange=row["J"].strip(),
            profile_url=row.get("K", ""), workbook_row=number,
        ))
    tickers = [item.ticker for item in result]
    if len(tickers) != len(set(tickers)):
        raise ValueError("duplicate ticker in Companies sheet")
    if Counter(item.test_set for item in result) != {"Development": 30, "Evaluation": 60, "Difficult case": 10}:
        raise ValueError("expected 30 development, 60 evaluation, and 10 difficult companies")
    return tuple(result)


def match_sec_identifiers(companies: tuple[UniverseCompany, ...], sec_tickers: dict) -> dict[str, int]:
    """Require one exact ticker/exchange match; never guess from company names."""
    fields = sec_tickers.get("fields")
    if not isinstance(fields, list) or not {"ticker", "cik", "exchange"} <= set(fields):
        raise ValueError("unexpected SEC ticker file structure")
    position = {name: fields.index(name) for name in ("ticker", "cik", "exchange")}
    indexed: dict[str, list[tuple[int, str]]] = {}
    for row in sec_tickers.get("data", []):
        indexed.setdefault(str(row[position["ticker"]]).upper(), []).append(
            (int(row[position["cik"]]), str(row[position["exchange"]]))
        )
    matched: dict[str, int] = {}
    for company in companies:
        choices = indexed.get(company.ticker, [])
        if len(choices) != 1 or choices[0][1].upper() != company.exchange.upper():
            raise ValueError(f"SEC identifier needs review: {company.ticker} ({company.exchange}); matches={choices}")
        matched[company.ticker] = choices[0][0]
    return matched
