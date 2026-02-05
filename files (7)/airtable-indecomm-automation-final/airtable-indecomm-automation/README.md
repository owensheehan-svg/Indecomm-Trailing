# Airtable to Indecomm Weekly Automation

Automated weekly export of correspondent mortgage loan data from multiple sources (Airtable, Vesta LOS, Parseur) to Excel format for Indecomm trailing document management.

## Overview

This automation consolidates loan data from three sources:
- **Airtable**: Post-close tracker data (loan numbers, amounts, borrower names, investors, dates)
- **Vesta LOS**: Property information (address, state, zip, county)
- **Parseur**: Settlement agent details from parsed closing disclosures (name, phone, email)

The system generates a weekly Excel file in Indecomm's required format and emails it for trailing document processing.

## System Architecture

```
┌─────────────┐
│  Airtable   │ → Loan metadata
│ Post-Close  │   (loan #, amount, borrower, dates)
└──────┬──────┘
       │
       ├─────→ ┌──────────────────┐
       │       │   Python Script   │ → Excel Generation
┌──────┴─────┐ │  (GitHub Actions) │   (Indecomm format)
│  Vesta LOS │ └────────┬─────────┘
│  API       │          │
└──────┬─────┘          ↓
       │         ┌─────────────┐
       └────→────┤   Email     │ → stakeholders@company.com
                 │ Notification │
┌──────────┐    └─────────────┘
│ Parseur  │ → Settlement agent data
│ Mailbox  │   (parsed from PDFs)
└──────────┘
```

## Data Flow

1. **Airtable Query**: Fetch loans from filtered view `viww1LG42sIrTNGFc`
2. **Vesta Lookup**: For each loan number, retrieve property details via API
3. **Parseur Lookup**: For each loan number, retrieve parsed settlement agent data
4. **Excel Generation**: Populate Indecomm template with combined data
5. **Email Delivery**: Send Excel + processing notes to recipients

## Setup Instructions

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_ORG/airtable-indecomm-automation.git
cd airtable-indecomm-automation
```

### 2. Add Files to Repository

Ensure these files are in the repository root:
- `airtable_vesta_parseur_automation.py` (main script)
- `Funded_File_Template.xlsx` (Indecomm Excel template)
- `requirements.txt` (Python dependencies)
- `.github/workflows/weekly_export.yml` (GitHub Actions workflow)
- `README.md` (this file)

### 3. Configure GitHub Secrets

Navigate to: **Repository → Settings → Secrets and variables → Actions**

Add the following secrets:

#### Required Secrets

| Secret Name | Description | Example |
|------------|-------------|---------|
| `AIRTABLE_TOKEN` | Airtable personal access token | `patXXXXXXXXXXXXXXXX` |
| `MAIL_SERVER` | SMTP server address | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USERNAME` | Email username | `automation@company.com` |
| `MAIL_PASSWORD` | Email password or app-specific password | `xxxxxxxxxxxx` |
| `MAIL_FROM` | Sender email address | `automation@company.com` |
| `MAIL_TO` | Recipient email(s), comma-separated | `team@company.com,manager@company.com` |

**Note**: API keys for Vesta and Parseur are currently hardcoded in the script. Move to environment variables in production:

```python
# In airtable_vesta_parseur_automation.py, change:
VESTA_API_KEY = os.environ.get('VESTA_API_KEY')
PARSEUR_API_KEY = os.environ.get('PARSEUR_API_KEY')
```

Then add `VESTA_API_KEY` and `PARSEUR_API_KEY` to GitHub secrets.

### 4. Email Configuration Examples

#### Gmail
```
MAIL_SERVER: smtp.gmail.com
MAIL_PORT: 587
MAIL_USERNAME: your.email@gmail.com
MAIL_PASSWORD: [16-character app password]
```

**Generate Gmail app password**: Google Account → Security → 2-Step Verification → App passwords

#### Outlook/Office 365
```
MAIL_SERVER: smtp.office365.com
MAIL_PORT: 587
MAIL_USERNAME: your.email@outlook.com
MAIL_PASSWORD: [your password]
```

#### SendGrid
```
MAIL_SERVER: smtp.sendgrid.net
MAIL_PORT: 587
MAIL_USERNAME: apikey
MAIL_PASSWORD: [SendGrid API key]
```

### 5. Schedule Configuration

**Current schedule**: Every Monday at 9 AM UTC

To modify, edit `.github/workflows/weekly_export.yml`:

```yaml
schedule:
  - cron: '0 9 * * 1'  # Minute Hour Day Month DayOfWeek
```

**Schedule examples**:
- `0 9 * * 1` - Every Monday at 9 AM UTC
- `0 14 * * 5` - Every Friday at 2 PM UTC
- `0 8 1,15 * *` - 1st and 15th of each month at 8 AM UTC
- `0 10 * * 1-5` - Every weekday at 10 AM UTC

**Timezone conversion** (schedule uses UTC):
- EST (UTC-5): Add 5 hours to local time
- CST (UTC-6): Add 6 hours to local time
- PST (UTC-8): Add 8 hours to local time

Example: 10 AM EST = 3 PM UTC = `0 15 * * *`

### 6. Manual Execution

Trigger workflow manually:
1. Go to **Actions** tab
2. Select **"Weekly Airtable to Indecomm Export"**
3. Click **"Run workflow"** → **"Run workflow"**

### 7. Monitoring Results

After each run:
- **Email**: Check recipient inbox for Excel file and processing notes
- **Artifacts**: Actions → workflow run → Artifacts section (retained 30 days)
- **Logs**: Actions tab → select run → view detailed execution logs

## Data Sources Configuration

### Airtable
- **Base ID**: `appgBl5EHB3qFtOPl`
- **Table**: `Post-Close Tracker`
- **View**: `viww1LG42sIrTNGFc` (filtered to relevant loans)

**Fields extracted**:
- Loan Number (from Data Input)
- Name (Borrower Name)
- Loan Size
- Funding Date (Trigger Date)
- Investor

### Vesta LOS
- **Base URL**: `https://multiply.beta.vesta.com/api`
- **Endpoint**: `GET /v1/loans/{loanId}`
- **Version**: `26.1` (header: `X-Api-Version`)
- **Authentication**: Bearer token in Authorization header

**Fields extracted**:
- `subjectProperty.address.line` → Property Address Line 1
- `subjectProperty.address.state` → Property State
- `subjectProperty.address.zipCode` → Property Zip Code
- `subjectProperty.address.city` → Used for county geocoding
- County: Derived via geocoding (Nominatim/OpenStreetMap) using zip code

### Parseur
- **Mailbox**: `cherubic-select-alligator`
- **Email**: `cherubic.select.alligator@in.parseur.com`

**Fields extracted**:
- `settlement_agent` → Organization Name
- `settlement_phone` → Organization Phone #
- `settlement_agent_email` → Organization Email

**Document matching**: Links to loans by document name = loan number

## Excel Output Mapping

The script populates 13 columns in the Indecomm template:

| Column | Field Name | Source |
|--------|-----------|--------|
| 1 | Channel Identifier | Hardcoded: "INDECOMM" |
| 2 | Loan Number | Airtable: Loan Number (from Data Input) |
| 5 | Loan Amount | Airtable: Loan Size |
| 14 | Borrower Name | Airtable: Name |
| 15 | Property Address Line 1 | Vesta: subjectProperty.address.line |
| 20 | Property State | Vesta: subjectProperty.address.state |
| 21 | Property Zip Code | Vesta: subjectProperty.address.zipCode |
| 22 | Property County | Geocoded from zip code (Nominatim) |
| 24 | Trigger Date | Airtable: Funding Date |
| 34 | Organization Name | Parseur: settlement_agent |
| 36 | Organization Phone # | Parseur: settlement_phone |
| 38 | Organization Email | Parseur: settlement_agent_email |
| 46 | Investor Name | Airtable: Investor |

## File Outputs

Each run generates:
- `Funded_File_YYYYMMDD_HHMMSS.xlsx` - Populated Excel report
- `processing_notes_YYYYMMDD_HHMMSS.txt` - Processing log with errors/warnings

## Error Handling

The script logs two types of issues:

**ERRORS**: Critical missing data that impacts accuracy
- Missing API responses
- Failed data lookups
- Missing required fields

**WARNINGS**: Non-critical issues
- API unavailable (graceful degradation)
- Optional fields missing
- Data validation notices

All errors and warnings are:
1. Printed to console (visible in GitHub Actions logs)
2. Written to `processing_notes_*.txt`
3. Included in email for review

## Troubleshooting

### Workflow Fails Immediately
- Verify all GitHub secrets are configured
- Check Airtable token has read access to base
- Confirm email credentials are correct

### No Data from Vesta
- Verify API key is valid
- Check API endpoint structure (placeholder needs updating)
- Review Vesta field name mappings

### No Data from Parseur
- Confirm PDFs were sent to `cherubic.select.alligator@in.parseur.com`
- Check Parseur mailbox processed documents successfully
- Verify loan numbers match between systems

### Missing Settlement Agent Data
- Check if Parseur has processed the closing disclosure
- Verify document name contains loan number
- Review Parseur parsing template for accuracy

### Email Not Received
- Check spam/junk folder
- Verify `MAIL_TO` address is correct
- Review workflow logs for SMTP errors
- Ensure app-specific passwords are used (Gmail)

### Schedule Not Triggering
- GitHub Actions may have delays (up to 15 minutes)
- Check Actions tab → workflow run history
- Verify cron syntax is correct
- Ensure repository is not private (or has Actions enabled)

## Security Best Practices

- Never commit API keys or tokens to repository
- Use GitHub secrets for all credentials
- Rotate API keys quarterly
- Use app-specific passwords for email when available
- Limit Airtable token permissions to read-only
- Review GitHub Actions logs for exposed credentials

## Maintenance

### Weekly Checklist
- Monitor workflow execution in Actions tab
- Review `processing_notes_*.txt` for recurring errors
- Verify all loans have complete data in output

### Monthly Maintenance
- Check for updates to Python dependencies
- Review and update Parseur parsing templates
- Validate Vesta API field mappings still accurate
- Test email delivery to ensure inbox not filtering

### Quarterly Tasks
- Rotate API keys (Airtable, Vesta, Parseur)
- Update email passwords
- Review error patterns and optimize data sources
- Archive old workflow run artifacts

## Development

### Local Testing

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variable:
```bash
export AIRTABLE_TOKEN="your_token_here"
```

3. Run script:
```bash
python airtable_vesta_parseur_automation.py
```

### Adding New Fields

To add fields to the Excel output:

1. Update `column_map` in `generate_excel()` method
2. Add field extraction in `process_loan()` method
3. Update README documentation

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review GitHub Actions logs for detailed error messages
3. Contact IT/DevOps team with processing notes file

## License

Internal use only - Company confidential
