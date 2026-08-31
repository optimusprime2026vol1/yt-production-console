# YT production console

Automated pipeline for a faceless long-form YouTube channel, with humans
deciding at three fixed points: topic approval, QC review, and publish.

- **Start here:** [`SYSTEM_PLAN.md`](./SYSTEM_PLAN.md) — full architecture, stages, and build order
- **Setup:** [`CREDENTIALS.md`](./CREDENTIALS.md) — ordered secrets checklist, add one at a time
- **Dashboard:** [`index.html`](./index.html) — Topic approval + QC review (enable GitHub Pages to get a live URL)
- **Automation status:** [`VOICEOVER.md`](./VOICEOVER.md) — current voiceover production log

Built incrementally through a Claude conversation. Each stage in `.github/workflows/`
is wired to a script in `scripts/` and only runs once its required secret exists.
