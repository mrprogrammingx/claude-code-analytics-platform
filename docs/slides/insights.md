# Slide 1 — Executive Summary

- Title: Claude Code Usage — Key Findings
- Bullet points:
  - Total events processed: (sample dataset count)
  - Average tokens per session and top user roles consuming tokens
  - Peak usage hours and a short actionable recommendation (e.g., scale infra at X times)
- Speaker notes: 30s summary framing business impact — cost & UX implications

# Slide 2 — Deep Dive Metrics

- Visuals:
  - Time-series: events per hour (line chart)
  - Bar chart: tokens consumed by user role
- Key callouts:
  - Where token usage spikes (models, features)
  - Common code-generation patterns (if observable)
- Speaker notes: 45s to walk through charts and explain SQL used for aggregates

# Slide 3 — Actionable Recommendations & Demo

- Bullets:
  - Recommendations (e.g., add rate-limiting, optimize expensive prompts, schedule maintenance during low usage)
  - Quick demo steps: open dashboard, show top users table, run safe SQL preview
- Speaker notes: 45s demo checklist; close with next steps
