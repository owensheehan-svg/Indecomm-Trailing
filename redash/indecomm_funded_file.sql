-- Indecomm funded file: property + title agent (organization) for correspondent loans.
-- loanchannel 'Retail' = correspondent in Vesta.
-- Duplicate vesta_loan rows are de-duplicated in indecomm_export.py, not here.
WITH title_agent AS (
    SELECT loannumber, companyname, phone, emailaddress
    FROM (
        SELECT
            l.loannumber,
            a.companyname                                 AS companyname,
            COALESCE(a.phonenumber, a.mobilephonenumber)  AS phone,
            a.emailaddress                                AS emailaddress,
            ROW_NUMBER() OVER (
                PARTITION BY l.loannumber
                ORDER BY
                    CASE a.source
                        WHEN 'UserEntered'         THEN 1
                        WHEN 'IntegrationProvided' THEN 2
                        ELSE 3
                    END,
                    CASE WHEN a.companyname IS NOT NULL THEN 0 ELSE 1 END
            ) AS rn
        FROM vesta_loan l
        CROSS JOIN UNNEST(l.titleagents) AS t(a)
        WHERE l.loanchannel = 'Retail'
    )
    WHERE rn = 1
)
SELECT
    CAST(l.loannumber AS varchar)            AS loan_number,
    l.currentloanstagechangeddate            AS stage_changed,
    l.subjectproperty.address.line           AS property_address_line_1,
    l.subjectproperty.address.statecode      AS property_state,
    l.subjectproperty.address.zipcode        AS property_zip_code,
    l.subjectproperty.address.city           AS property_city,
    l.subjectproperty.address.county         AS property_county,
    ta.companyname                           AS organization_name,
    ta.phone                                 AS organization_phone,
    ta.emailaddress                          AS organization_email
FROM vesta_loan l
LEFT JOIN title_agent ta ON ta.loannumber = l.loannumber
WHERE l.loanchannel = 'Retail'
