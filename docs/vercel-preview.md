# Vercel visual preview

This hosting target contains **synthetic visual demonstration data only**. The clinical Python application, database, source uploads, API tokens and AI provider are not deployed to Vercel.

`vercel.json` selects the Other framework, runs `node scripts/build-preview.mjs`, and publishes `dist-preview`. The build has no npm dependencies and does not execute Python. The precomputed JSON fixtures come from the existing synthetic local pipeline. It does not read a clinic database or runtime directory.

The hosted interface supports patient/encounter selection, history, measured facts, trend metric selection, display comparisons, both summaries, provenance, structured-result export, a fixed sample import, and a demonstration review. Preview changes stay in page memory and reset when the page reloads. Source-file imports, arbitrary edits, clinical corrections, new patients, paid AI calls and live API connections are unavailable. The page clearly identifies this as a visual preview.

## Deploy from the private GitHub repository

1. Sign in to Vercel and import the `InBodyStage1` repository.
2. Keep the project root as the repository root. `vercel.json` supplies the static build configuration.
3. Do not add clinical credentials or environment variables. Deploy the synthetic preview.
4. Verify the resulting deployment: both patient selectors, history, trend selections, comparison, summary tabs, sample import, and simulated review.

If connecting the GitHub integration requires granting new repository access, select only `InBodyStage1` and review the actual requested permissions. The existing build does not automatically grant access.

A signed-in Vercel CLI can also deploy from the repository root with `vercel`. No token is included in the source. The source repository is https://github.com/DrDraesel/InBodyStage1 . Vercel account access and deployment remain pending; no Vercel deployment URL is being claimed.

## Local visual preview

```bash
node scripts/build-preview.mjs
python -m http.server 8081 --directory dist-preview --bind 127.0.0.1
```

Open localhost port 8081. The generated standalone `InBodyStage1_Visual_Preview.html` can also be opened directly from a local download. Its embedded data is synthetic; it makes no application API requests.

## Checks

```bash
node tests/test_preview.cjs
node tests/test_frontend.cjs
node --check preview/demo-adapter.js
node scripts/build-preview.mjs
```

The static preview has been built and its view model exercised. Browser layout/interactive QA and a live Vercel deployment remain unverified. The Vercel configuration follows the official project configuration contract: https://vercel.com/docs/project-configuration/vercel-json .
