#!/usr/bin/env python3
"""
Weekly Indecomm Funded File export (correspondent loans).

Sources:
  Airtable Post-Close Tracker -> loan number, loan amount, borrower name,
                                 funding date (trigger date), investor
  Redash (Vesta data)         -> property address/state/zip/county,
                                 title agent (organization) name/phone/email,
                                 lien position (second lien flag, if the query returns it)

Date window (Funding Date, inclusive):
  - START_DATE / END_DATE env vars (YYYY-MM-DD) if either is set
  - otherwise the previous Monday-Sunday week
"""

import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from openpyxl import load_workbook
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError, GeocoderTimedOut

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AIRTABLE_TOKEN = os.environ.get('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = 'appgBl5EHB3qFtOPl'
AIRTABLE_TABLE_NAME = 'Post-Close Tracker'
AIRTABLE_VIEW = 'viww1LG42sIrTNGFc'

REDASH_BASE_URL = 'https://redash.withmultiply.com'
REDASH_API_KEY = os.environ.get('REDASH_API_KEY')
REDASH_QUERY_ID = os.environ.get('REDASH_QUERY_ID', '').strip()
REDASH_MAX_AGE_HOURS = 24  # warn if the cached Redash result is older than this

TEMPLATE_PATH = 'Funded_File_Template.xlsx'

# Value written to Channel Identifier for every row.
CHANNEL_IDENTIFIER = 'Retail'

START_DATE = os.environ.get('START_DATE', '').strip()
END_DATE = os.environ.get('END_DATE', '').strip()

# Template columns (1-based). All yellow-highlighted columns in the template.
COLUMN_MAP = {
    'Channel Identifier': 1,        # A
    'Loan Number': 2,               # B
    'Loan Amount': 5,               # E
    'Borrower Name': 14,            # N
    'Property Address Line 1': 15,  # O
    'Property State': 20,           # T
    'Property Zip Code': 21,        # U
    'Property County': 22,          # V
    'Trigger Date': 24,             # X
    'Organization Name': 34,        # AH
    'Organization Phone #': 36,     # AJ
    'Organization Email': 38,       # AL
    'Investor Name': 46,            # AT
    'Second Lien Flag': 62,         # BJ
}

# Optional column: add a lien column to the Redash query aliased as lien_position.
LIEN_COLUMN = 'lien_position'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def validate_date(value: str, label: str) -> Optional[str]:
    if not value:
        return None
    try:
        datetime.strptime(value, '%Y-%m-%d')
        return value
    except ValueError:
        print(f"ERROR: {label} must be YYYY-MM-DD (got '{value}')")
        sys.exit(1)


def resolve_date_window() -> (Optional[str], Optional[str]):
    """Manual inputs win; otherwise previous Monday through Sunday."""
    if START_DATE or END_DATE:
        return START_DATE or None, END_DATE or None
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    prev_monday = this_monday - timedelta(days=7)
    prev_sunday = this_monday - timedelta(days=1)
    return prev_monday.isoformat(), prev_sunday.isoformat()


def first(value: Any) -> Any:
    """Airtable lookup/rollup fields come back as lists."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


# ---------------------------------------------------------------------------
# Automation
# ---------------------------------------------------------------------------
class IndecommExport:
    def __init__(self, start: Optional[str], end: Optional[str]):
        self.start = start
        self.end = end
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.geolocator = Nominatim(user_agent='multiply_indecomm_export')
        self._county_cache: Dict[str, Optional[str]] = {}
        self.vesta: Dict[str, Dict] = {}
        self.has_lien_column = False

    def log_error(self, loan: str, field: str, msg: str):
        line = f"Loan {loan} - {field}: {msg}"
        self.errors.append(line)
        print(f"ERROR: {line}")

    def log_warning(self, loan: str, field: str, msg: str):
        line = f"Loan {loan} - {field}: {msg}"
        self.warnings.append(line)
        print(f"WARNING: {line}")

    # -- Airtable -----------------------------------------------------------
    def fetch_airtable_records(self) -> List[Dict]:
        url = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}'
        headers = {'Authorization': f'Bearer {AIRTABLE_TOKEN}'}

        conditions = []
        if self.start:
            conditions.append(f"IS_AFTER({{Funding Date}}, DATEADD('{self.start}', -1, 'days'))")
        if self.end:
            conditions.append(f"IS_BEFORE({{Funding Date}}, DATEADD('{self.end}', 1, 'days'))")
        formula = None
        if conditions:
            formula = conditions[0] if len(conditions) == 1 else f"AND({', '.join(conditions)})"
        print(f"Funding Date window: {self.start or 'beginning'} through {self.end or 'today'}")

        records, offset = [], None
        while True:
            params = {'view': AIRTABLE_VIEW}
            if formula:
                params['filterByFormula'] = formula
            if offset:
                params['offset'] = offset
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code != 200:
                raise Exception(f"Airtable API error: HTTP {resp.status_code}")
            data = resp.json()
            records.extend(data.get('records', []))
            offset = data.get('offset')
            if not offset:
                break
            time.sleep(0.2)

        print(f"Found {len(records)} records in Airtable")
        return records

    # -- Redash (Vesta) ----------------------------------------------------
    def load_redash(self):
        """Fetch the cached result of the Redash query; index one row per loan number."""
        url = f'{REDASH_BASE_URL}/api/queries/{REDASH_QUERY_ID}/results.json'
        resp = requests.get(url, params={'api_key': REDASH_API_KEY}, timeout=60)
        if resp.status_code in (401, 403, 404):
            raise Exception(f"Redash HTTP {resp.status_code} - check REDASH_API_KEY / REDASH_QUERY_ID")
        resp.raise_for_status()
        result = resp.json().get('query_result', {})
        rows = result.get('data', {}).get('rows', [])
        columns = {c.get('name') for c in result.get('data', {}).get('columns', [])}
        self.has_lien_column = LIEN_COLUMN in columns

        retrieved = result.get('retrieved_at')
        print(f"Redash query {REDASH_QUERY_ID}: {len(rows)} rows, retrieved_at {retrieved}")
        if retrieved:
            try:
                ts = datetime.fromisoformat(retrieved.replace('Z', '+00:00'))
                age_h = (datetime.now(ts.tzinfo) - ts).total_seconds() / 3600
                if age_h > REDASH_MAX_AGE_HOURS:
                    self.warnings.append(
                        f"Redash result is {age_h:.0f}h old - check the query's refresh schedule")
                    print(f"WARNING: Redash result is {age_h:.0f}h old")
            except ValueError:
                pass

        # Duplicate vesta_loan rows: keep the most complete row, then the latest stage change.
        def score(r):
            filled = sum(1 for k, v in r.items() if k != 'stage_changed' and v not in (None, ''))
            return (filled, str(r.get('stage_changed') or ''))

        for r in rows:
            ln = str(r.get('loan_number') or '').strip()
            if not ln:
                continue
            if ln not in self.vesta or score(r) > score(self.vesta[ln]):
                self.vesta[ln] = r

        if not self.has_lien_column:
            self.warnings.append(
                f"Redash query has no '{LIEN_COLUMN}' column; Second Lien Flag defaulted to N for all loans")

    def second_lien_flag(self, loan_number: str, row: Dict) -> str:
        if not self.has_lien_column:
            return 'N'
        val = row.get(LIEN_COLUMN)
        s = str(val or '').strip().lower().replace(' ', '').replace('_', '')
        if s in ('2', 'second', 'secondlien', 'subordinate', 'subordinatelien'):
            return 'Y'
        if s in ('1', 'first', 'firstlien'):
            return 'N'
        self.log_warning(loan_number, 'Second Lien Flag', f"Unrecognized or blank lien value '{val}'; defaulted to N")
        return 'N'

    # -- County fallback ----------------------------------------------------
    def county_from_zip(self, zip_code: Optional[str], city: Optional[str], state: Optional[str]) -> Optional[str]:
        """Geocode on ZIP (then city/state/ZIP). Never sends the street address."""
        key = f"{zip_code}|{city}|{state}"
        if key in self._county_cache:
            return self._county_cache[key]
        queries = []
        if zip_code:
            queries.append(f"{zip_code}, USA")
        if city and state and zip_code:
            queries.append(f"{city}, {state} {zip_code}, USA")
        county = None
        for q in queries:
            try:
                time.sleep(1.1)  # Nominatim limit: 1 req/sec
                loc = self.geolocator.geocode(q, addressdetails=True, country_codes='us', timeout=10)
                if loc and 'address' in loc.raw and loc.raw['address'].get('county'):
                    county = loc.raw['address']['county'].replace(' County', '').strip()
                    break
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                print(f"Geocoding error: {type(e).__name__}")
        self._county_cache[key] = county
        return county

    # -- Per-loan -----------------------------------------------------------
    def process_loan(self, record: Dict) -> Dict:
        fields = record.get('fields', {})
        loan_number = first(fields.get('Loan Number (from Data Input)')) or fields.get('Name', 'UNKNOWN')
        loan_number = str(loan_number)
        print(f"\nProcessing loan {loan_number}")

        result = {
            'Channel Identifier': CHANNEL_IDENTIFIER,
            'Loan Number': loan_number,
            'Loan Amount': first(fields.get('Loan Size')),
            'Borrower Name': fields.get('Name'),
            'Trigger Date': fields.get('Funding Date'),
            'Investor Name': first(fields.get('Investor')),
        }

        v = self.vesta.get(loan_number)
        if not v:
            self.log_warning(loan_number, 'Vesta', 'Not in Redash results; property, organization, lien columns blank')
            return result

        # Property
        line = v.get('property_address_line_1')
        city = v.get('property_city')
        state = v.get('property_state')
        zip_code = v.get('property_zip_code')
        county = v.get('property_county')

        result['Property Address Line 1'] = line
        result['Property State'] = state
        result['Property Zip Code'] = zip_code
        if not line:
            self.log_warning(loan_number, 'Property Address', 'Missing in Vesta')

        if county:
            result['Property County'] = str(county).replace(' County', '').strip()
        else:
            county = self.county_from_zip(zip_code, city, state)
            if county:
                result['Property County'] = county
            else:
                self.log_warning(loan_number, 'Property County', 'Missing in Vesta and geocoding failed')

        # Organization (title agent)
        result['Organization Name'] = v.get('organization_name')
        result['Organization Phone #'] = v.get('organization_phone')
        result['Organization Email'] = v.get('organization_email')
        if not any(result[c] for c in ('Organization Name', 'Organization Phone #', 'Organization Email')):
            self.log_warning(loan_number, 'Organization', 'No title agent in Vesta')
        else:
            for col in ('Organization Name', 'Organization Phone #', 'Organization Email'):
                if not result[col]:
                    self.log_warning(loan_number, col, 'Blank in Vesta')

        # Second lien
        result['Second Lien Flag'] = self.second_lien_flag(loan_number, v)
        return result

    # -- Output -------------------------------------------------------------
    def generate_excel(self, rows: List[Dict], path: str):
        if not os.path.exists(TEMPLATE_PATH):
            raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
        wb = load_workbook(TEMPLATE_PATH)
        ws = wb.active
        for r, loan in enumerate(rows, start=2):
            for field, col in COLUMN_MAP.items():
                val = loan.get(field)
                if val is not None:
                    ws.cell(row=r, column=col, value=val)
        wb.save(path)
        print(f"Excel saved: {path}")

    def generate_notes(self, path: str, loan_count: int):
        with open(path, 'w') as f:
            f.write("PROCESSING NOTES\n" + "=" * 60 + "\n\n")
            f.write(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            f.write(f"Funding Date window: {self.start or 'beginning'} through {self.end or 'today'}\n")
            f.write(f"Loans: {loan_count}\n\n")
            for label, items in (('ERRORS', self.errors), ('WARNINGS', self.warnings)):
                if items:
                    f.write(f"{label} ({len(items)}):\n" + "-" * 60 + "\n")
                    f.writelines(f"  {i}\n" for i in items)
                    f.write("\n")
                else:
                    f.write(f"No {label.lower()}.\n\n")
        print(f"Notes saved: {path}")

    def run(self):
        records = self.fetch_airtable_records()
        self.load_redash()
        rows = []
        for rec in records:
            try:
                rows.append(self.process_loan(rec))
            except Exception as e:
                ln = first(rec.get('fields', {}).get('Loan Number (from Data Input)')) or 'UNKNOWN'
                self.log_error(str(ln), 'Processing', type(e).__name__)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.generate_excel(rows, f'Funded_File_{ts}.xlsx')
        self.generate_notes(f'processing_notes_{ts}.txt', len(rows))
        print(f"\nDone. Loans: {len(rows)}  Errors: {len(self.errors)}  Warnings: {len(self.warnings)}")


if __name__ == '__main__':
    validate_date(START_DATE, 'START_DATE')
    validate_date(END_DATE, 'END_DATE')
    missing = [n for n, v in (('AIRTABLE_TOKEN', AIRTABLE_TOKEN),
                              ('REDASH_API_KEY', REDASH_API_KEY),
                              ('REDASH_QUERY_ID', REDASH_QUERY_ID)) if not v]
    if missing:
        print(f"ERROR: missing environment variable(s): {', '.join(missing)}")
        sys.exit(1)
    start, end = resolve_date_window()
    try:
        IndecommExport(start, end).run()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
