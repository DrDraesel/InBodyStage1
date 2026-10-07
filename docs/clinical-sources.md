# Versioned clinical references

Checked October 7, 2026 against primary sources. This initial configuration intentionally has a small clinical scope.

- CDC, Adult BMI Categories, subject-matter review March 19, 2024: https://www.cdc.gov/bmi/adult-calculator/bmi-categories.html . Adult screening categories apply at age 20 and older. The configured review rules flag BMI below 18.5 or at least 25; they do not diagnose a condition or characterize urgency. An unknown age causes these rules to be skipped.
- AMA, June 14, 2023 BMI policy announcement: https://www.ama-assn.org/press-center/ama-press-releases/ama-adopts-new-policy-clarifying-role-bmi-measure-medicine . Used as contextual guidance about considering other measures alongside BMI; no numeric AMA body-composition threshold is inferred.
- Official InBody integration guide: https://usa.developers.lookinbody.com/guide . Account access, approval, API keys and an IP whitelist are required. Live response mapping and vendor-specific webhook authentication remain deliberately unimplemented pending account-specific documentation and sample responses.

No CMS threshold is configured. No universal phase-angle, ECW/TBW, body-fat, visceral-fat or muscle-mass cutoff is guessed. Missing manufacturer references mean those metrics may have no reference flag. “No configured finding” must never be represented as “normal.”

Source-reported device intervals are preserved with source/version and used only after measurement confirmation. Their clinical applicability must still be reviewed. Different device and clinical intervals remain distinct findings. Numerical trends have no improving/worsening labels without an approved change criterion.

Before clinical deployment, a qualified reviewer must approve rules and populations, add appropriate supported criteria, evaluate source-report layouts, and maintain dated rule revisions.
