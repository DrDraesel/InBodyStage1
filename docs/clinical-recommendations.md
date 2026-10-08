# Comprehensive clinical recommendation drafts

Each new analysis includes `recommendation_plan`, a versioned discussion draft for medical/family-medicine, functional-health and Chiropractic Physical Medicine review. These are reasoning perspectives, not claims that an MD or a live specialist AI examined the patient. The default engine is deterministic; a configured AI provider can select evidence-linked clinician rationale sentences but cannot invent prescriptions or values.

Nine domains: medical/metabolic review; functional nutrition/recovery; upper-limb training; lower-limb training; balance/gait; aerobic/resistance conditioning; lifestyle/sleep/adherence; peptides/prescription options; reassessment/outcomes. Each identifies its rationale, linked verified metrics, options, required assessment, reviewer and references.

The blue dashboard's **Recommendations · draft** tab displays the plan. **Add / update clinical context** records goals, activity, pain, falls/balance concerns, pregnancy/breastfeeding, cardiovascular symptoms and history/medication review. Saving appends a new analysis and leaves earlier context and plans intact. Unknown answers remain unknown; entered history is not independently verified. Reported pain, instability or cardiovascular symptoms add assessment requirements. A source review never converts the discussion draft into a treatment order.

## Segmental reasoning

Only comparable verified left/right lean-mass pairs produce an observation. The display reports the absolute difference divided by the larger segment estimate, multiplied by 100. This descriptive calculation has no asserted clinical cutoff and does not establish weakness, balance impairment, injury or a need to preferentially train one side. Strength, range of motion, pain and functional testing determine exercise selection. Missing or unverified measurements do not generate an asymmetry.

## Peptide discussion

Body composition does not establish an indication. Approved prescription weight-management options can be discussion topics when appropriate, but the engine does not establish eligibility, choose a drug, supply a dose, or issue a prescription. BPC-157, CJC-1295 and ipamorelin remain evidence-review topics with FDA safety limitations, rather than routine recovery or longevity recommendations. Current label, indication, product status, interactions, contraindications and monitoring require a qualified prescriber's review. Regulatory summaries must be refreshed before clinical use.

## References and limitations

Reference snapshot checked October 8, 2026: [CDC adult activity](https://www.cdc.gov/physical-activity-basics/guidelines/adults.html), [CDC older-adult activity](https://www.cdc.gov/physical-activity-basics/guidelines/older-adults.html), [NIDDK weight-management planning](https://www.niddk.nih.gov/health-information/weight-management/choosing-a-safe-successful-weight-loss-program), [NIDDK prescription medication review](https://www.niddk.nih.gov/health-information/weight-management/prescription-medications-treat-overweight-obesity), [FDA peptide safety information](https://www.fda.gov/drugs/human-drug-compounding/certain-bulk-drug-substances-use-compounding-may-present-significant-safety-risks), [InBody 380 manual](https://inbodyusa.zendesk.com/hc/en-us/articles/26353282696084-InBody-380-User-s-Manual).

Exercise examples and targeted-review questions are clinical discussion templates, not validated individualized protocols. InBody does not replace an examination, diagnose endocrine/nutrient disorders or measure balance. The implementation has synthetic automated tests; live model execution, clinical effectiveness, production use and autonomous treatment approval are not validated. Structured result exports preserve drafts, references, context and earlier analysis versions for Coherence handoff; no direct Cortex/Vault connection is added.
