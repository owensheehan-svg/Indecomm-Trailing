# Indecomm-Trailing

Weekly Funded File export to Indecomm (correspondent loans).

- Schedule: Mondays 09:00 UTC, exports loans funded the previous Monday through Sunday.
- Manual run: Actions -> Weekly Airtable to Indecomm Export -> Run workflow (optional start/end dates).
- Output: `Funded_File_<timestamp>.xlsx` and `processing_notes_<timestamp>.txt` as a workflow artifact.

Sources:
- Airtable Post-Close Tracker: loan number, amount, borrower, funding date, investor.
- Redash (Vesta data), query in `redash/indecomm_funded_file.sql`: property, county, title agent
  organization, optional lien position. The script reads the query's cached result, so the query
  needs a Redash refresh schedule that runs before the workflow.

Required repo secrets: `AIRTABLE_TOKEN`, `REDASH_API_KEY` (the query's API key), `REDASH_QUERY_ID`.
