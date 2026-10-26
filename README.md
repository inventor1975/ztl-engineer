# ZTL Engineer

An engineering design stand for people: describe what you need in plain words, drop in a photo of a nameplate, a
datasheet PDF or your CAD export, and get a **proved** answer — the design works for every value the tolerances
allow, or it provably fails and the stand names the requirements that conflict, or the honest "can't vouch yet".

Meta's **Muse Spark** reads the photos and documents and turns the conversation into a formal design brick; the
**ZTL stand** judges it. Every value the model read is *dirty* until a person confirms it — the verdict stays
"on credit" until then, and changes on screen when you confirm or correct a value.

Built for the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026).

## What was built during the hackathon, and what was not

**Built during the hackathon (everything in this repository):** the web application, the Muse Spark agent
(reading photos/PDFs, building and repairing the brick from the conversation), the dirty→confirmed layer, the task
presets and hints, the progress view, the spending stop, and the help page. The repository was created after the
kickoff on Oct 26, 2026; its history is the record.

**Pre-existing, used as dependencies (not hackathon work):**
- [ZTL — Zero-Trust Logic](https://github.com/inventor1975/ZTL) (public since July 2026, Apache-2.0) — the logic
  and judge.
- [ztl-stand](https://github.com/inventor1975/ztl-stand) (public since Oct 20, 2026, Apache-2.0) — the design
  stand that proves or refutes a brick.

Both are by the same author and are installed beside this repository; nothing from them is copied here.

## Built with

Muse Spark 1.3 (Meta Model API). The code was written with Claude (Anthropic); the author is Vitaly Reznik.
