"""Fetch candidate data from FEC bulk data files (no API key needed)."""

import csv
import io
import zipfile

import httpx

from src.db.models import Candidate


# FEC bulk data: candidate master file
# https://www.fec.gov/data/browse-data/?tab=bulk-data
BULK_CANDIDATE_URL = "https://www.fec.gov/files/bulk-downloads/2026/cn26.zip"

# Map FEC office codes
OFFICE_MAP = {"S": "Senate", "H": "House", "P": "President"}
INCUMBENT_MAP = {"I": "Incumbent", "C": "Challenger", "O": "Open Seat"}

# Column positions in the FEC candidate master file (pipe-delimited)
# CAND_ID|CAND_NAME|CAND_PTY_AFFILIATION|CAND_ELECTION_YR|CAND_OFFICE_ST|
# CAND_OFFICE|CAND_OFFICE_DISTRICT|CAND_ICI|CAND_STATUS|CAND_PCC|CAND_ST1|
# CAND_ST2|CAND_CITY|CAND_ST|CAND_ZIP
FIELDS = [
    "candidate_id", "name", "party", "election_year", "office_state",
    "office", "district", "incumbent_challenge", "status", "pcc",
    "street1", "street2", "city", "state", "zip"
]

# Party code mapping (common ones)
PARTY_FULL = {
    "DEM": "DEMOCRATIC PARTY",
    "REP": "REPUBLICAN PARTY",
    "LIB": "LIBERTARIAN PARTY",
    "GRE": "GREEN PARTY",
    "IND": "INDEPENDENT",
    "CON": "CONSTITUTION PARTY",
    "NNE": "NO PARTY AFFILIATION",
    "UNK": "UNKNOWN",
}


def fetch_bulk_candidates(office_filter: str | None = None) -> list[Candidate]:
    """Download and parse the FEC bulk candidate file.

    Args:
        office_filter: "S" for Senate, "H" for House, or None for all
    """
    print(f"Downloading FEC bulk data from {BULK_CANDIDATE_URL}...")
    resp = httpx.get(BULK_CANDIDATE_URL, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()

    candidates = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # The zip contains a single pipe-delimited text file
        for filename in zf.namelist():
            with zf.open(filename) as f:
                text = f.read().decode("utf-8", errors="replace")
                reader = csv.reader(io.StringIO(text), delimiter="|")
                for row in reader:
                    if len(row) < 8:
                        continue

                    record = dict(zip(FIELDS, row))
                    office_code = record.get("office", "")

                    if office_filter and office_code != office_filter:
                        continue

                    # Parse name (format: "LASTNAME, FIRSTNAME MIDDLE")
                    full_name = record.get("name", "")
                    parts = full_name.split(", ", 1)
                    last_name = parts[0].strip().title() if parts else ""
                    first_name = parts[1].strip().title() if len(parts) > 1 else ""
                    # Clean up first name (remove suffixes like JR, SR, III)
                    if first_name:
                        fname_parts = first_name.split()
                        first_name = fname_parts[0] if fname_parts else first_name
                    display_name = f"{first_name} {last_name}".strip()

                    party_code = record.get("party", "")

                    candidate = Candidate(
                        fec_candidate_id=record.get("candidate_id", ""),
                        name=display_name or full_name.title(),
                        first_name=first_name,
                        last_name=last_name,
                        party=party_code,
                        party_full=PARTY_FULL.get(party_code, party_code),
                        office=OFFICE_MAP.get(office_code, office_code),
                        state=record.get("office_state", ""),
                        district=record.get("district") if office_code == "H" else None,
                        incumbent_status=INCUMBENT_MAP.get(
                            record.get("incumbent_challenge", ""),
                            record.get("incumbent_challenge", ""),
                        ),
                        election_year=2026,
                        roster_source="fec_bulk",
                    )
                    candidates.append(candidate)

    print(f"  Parsed {len(candidates)} candidates from bulk data")
    return candidates
