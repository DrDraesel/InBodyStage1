# IMW website-based service education catalog

Reviewed October 8, 2026 against the supplied [IMW website](https://www.innovativemedicalwellness.com/en) and its linked department pages. Listings are evidence of public advertising, not independently verified staffing, current operational capacity, stock, appointments, prices, regulatory approval or clinical effectiveness. No other similarly named clinic was used as a source.

| Education route | Published source | Before individualizing |
| --- | --- | --- |
| Chiropractic / rehabilitation | [Department page](https://www.innovativemedicalwellness.com/en/chiropractic-and-physical-therapy) | Pain, mobility, injury and functional examination |
| Weight-management assessment | [Department page](https://www.innovativemedicalwellness.com/en/weight-loss-programs) | Goals, metabolic history and prescriber evaluation |
| Hormone consultation | [Department page](https://www.innovativemedicalwellness.com/en/anti-aging-medicine) | Symptoms, labs, indication and contraindication review |
| Lifestyle / wellness | [Department page](https://www.innovativemedicalwellness.com/en/biohacking-and-optimization) | Goals and evidence-based, device-specific assessment |
| Joint / musculoskeletal review | [Department page](https://www.innovativemedicalwellness.com/en/regenerative-medicine) | Diagnosis, examination and procedure-specific evidence |
| Infusion assessment | [Department page](https://www.innovativemedicalwellness.com/en/iv-therapy) | Medical indication, relevant labs and interaction review |
| Brain-health assessment | [Department page](https://www.innovativemedicalwellness.com/en/brain-health) | Symptoms and dedicated domain evaluation |
| Post-injury review | [Department page](https://www.innovativemedicalwellness.com/en/personal-injury) | Injury history, examination and documentation |
| Hair / aesthetic consultation | [Department page](https://www.innovativemedicalwellness.com/en/aesthetic-treatments) | Patient-requested goal and dedicated assessment |
| Pelvic-health consultation | [VTone page](https://www.innovativemedicalwellness.com/en/v-tone) | Symptoms, assessment and confirmation of operational details |
| ExoMind consultation | [Homepage service link](https://www.innovativemedicalwellness.com/en) | Dedicated medical assessment and device eligibility |
| Exosome evidence review | [Weight-management page](https://www.innovativemedicalwellness.com/en/weight-loss-programs) | Independent evidence and regulatory review; not an automatic recommendation |

## Findings retained rather than guessed

- The weight-management page explicitly discusses semaglutide and metabolic testing. Tirzepatide and specific peptide protocols were not verified on the pages reviewed; they are not asserted as website-confirmed clinic offerings.
- The VTone page contains a `[Medspa Name]` placeholder. Its advertised treatment is retained, with operational confirmation required.
- General hair-transplant discussion does not establish that IMW performs transplant surgery. The catalog uses a hair-restoration consultation instead.
- General chiropractic pricing text is not treated as a verified clinic quote. Catalog prices remain null.
- Some website descriptions make broad benefit claims. The app retains the service identity and source link, not those claims as clinical evidence.
- Exosome infusion advertising is separated from evidence review. [FDA's safety notice](https://www.fda.gov/safety/medical-product-safety-information/public-safety-alert-due-marketing-unapproved-stem-cell-and-exosome-products) describes unapproved exosome products and the absence of approved products. No automated exosome treatment recommendation is made.

## Application behavior

The catalog is versioned in `backend/clinic_services.py` and stored with each analysis. Requested service topics mark education interests. Reported pain/balance concerns can identify a rehabilitation assessment topic; they do not select a procedure. Every route retains needed assessment, reviewer requirement, website source and an explicit unverified-availability status. Education comes before service selection. No manipulative urgency, invented benefit, package price, booking, marketing message or external routing is introduced. Later clinic training can supply reviewed indications, operational availability, approved protocols and transparent prices without rewriting the source evidence.
