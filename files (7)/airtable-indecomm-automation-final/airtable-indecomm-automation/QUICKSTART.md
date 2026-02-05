# Quick Start Guide

## 5-Minute Setup

### 1. Create GitHub Repository
```bash
# On GitHub.com, create new repository: airtable-indecomm-automation
# Then locally:
git clone https://github.com/YOUR_ORG/airtable-indecomm-automation.git
cd airtable-indecomm-automation

# Add all files
git add .
git commit -m "Initial setup: Airtable + Vesta + Parseur automation"
git push
```

### 2. Add Required Secrets

Go to: **Repository → Settings → Secrets and variables → Actions**

Add these 7 secrets (one at a time):

```
AIRTABLE_TOKEN        → Your Airtable personal access token
MAIL_SERVER           → smtp.gmail.com (or your SMTP server)
MAIL_PORT             → 587
MAIL_USERNAME         → your.email@gmail.com
MAIL_PASSWORD         → [app password for Gmail]
MAIL_FROM             → your.email@gmail.com
MAIL_TO               → recipient@company.com
```

### 3. Test It

**Option 1: Wait for Monday 9 AM UTC**

**Option 2: Manual trigger now**
1. Go to **Actions** tab
2. Click **"Weekly Airtable to Indecomm Export"**
3. Click **"Run workflow"** button
4. Click green **"Run workflow"** button

### 4. Verify Results

Check email inbox for:
- Subject: "Weekly Indecomm Export - [number]"
- 2 attachments: Excel file + processing notes

## Data Source Requirements

Before running, ensure:

✅ **Airtable**:
- View `viww1LG42sIrTNGFc` filtered to relevant loans
- All loans have: Loan Number, Borrower Name, Loan Size, Funding Date, Investor

✅ **Parseur**:
- Closing disclosures sent to `cherubic.select.alligator@in.parseur.com`
- Documents processed and named with loan numbers
- Parsing template extracts: settlement_agent, settlement_phone, settlement_agent_email

✅ **Vesta**:
- Loans exist in Vesta with property information
- API returns subjectProperty.address fields

## Common Issues & Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| Workflow won't run | Check all 7 secrets are added correctly |
| No email received | Check spam folder, verify MAIL_TO address |
| Missing property data | Update Vesta API placeholders in script |
| Missing settlement data | Verify Parseur processed documents for those loan numbers |
| Gmail auth error | Use app-specific password, not regular password |

## Email Setup (Gmail)

1. Go to Google Account → Security
2. Enable 2-Step Verification
3. Go to App passwords
4. Generate new app password for "Mail"
5. Copy 16-character password
6. Use as `MAIL_PASSWORD` secret

## Changing Schedule

Edit `.github/workflows/weekly_export.yml`:

```yaml
schedule:
  - cron: '0 14 * * 5'  # Friday 2 PM UTC
```

Cron format: `minute hour day month weekday`
- `0 9 * * 1` = Monday 9 AM
- `0 14 * * 5` = Friday 2 PM  
- `0 8 1 * *` = 1st of month 8 AM

## Next Steps

1. ✅ Test with a real loan number
2. ✅ Verify Parseur has processed closing disclosures
3. ✅ Run manual workflow execution
4. ✅ Review output accuracy
5. ✅ Set recurring schedule

## Need Help?

- **Detailed docs**: See README.md
- **Logs**: Actions tab → select run → view logs
- **Errors**: Check processing_notes_*.txt in artifacts
