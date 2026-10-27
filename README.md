# ZTL Engineer

An engineering design stand for people: describe what you need in plain words, drop in a photo of a nameplate, a
datasheet PDF or your CAD export, and get a **proved** answer — the design works for every value the tolerances
allow, or it provably fails and the stand names the requirements that conflict, or the honest "can't vouch yet".

Meta's **Muse Spark** reads the photos and documents and turns the conversation into a formal design brick; the
**ZTL stand** judges it. Every value the model read is listed with where it came from, marked "AI read"; correct
any of them and press Recalculate to judge again.

Built for the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026).

## What was built during the hackathon, and what was not

**Built during the hackathon (everything in this repository):** the web application, the Muse Spark agent
(reading photos/PDFs, building and repairing the brick from the conversation), the "AI read" values with Recalculate, the task
presets and hints, the progress view, the spending stop, and the help page. The repository was created after the
kickoff on Oct 26, 2026; its history is the record.

**Pre-existing, used as dependencies (not hackathon work):**
- [ZTL — Zero-Trust Logic](https://github.com/inventor1975/ZTL) (public since July 2026, Apache-2.0) — the logic
  and judge.
- [ztl-stand](https://github.com/inventor1975/ztl-stand) (public since Oct 20, 2026, Apache-2.0) — the design
  stand that proves or refutes a brick.

Both are by the same author and are installed beside this repository; nothing from them is copied here.

## Run it

Clone [ZTL](https://github.com/inventor1975/ZTL) and [ztl-stand](https://github.com/inventor1975/ztl-stand) beside
this repository, put a Meta Model API key in `META_API_KEY` or `~/.config/meta-api-key`, then:

    python3 server.py            # http://localhost:8090

## Use it from any AI agent (MCP)

`mcp_server.py` makes ZTL Engineer an MCP server (stdio, standard library only), so an AI agent can ask for an
independent check before it tells a person "this will work":

- `brick_format` — the stand's brick format, so the agent can write the problem itself;
- `check_design` — the ZTL stand judges a brick: EARNED / REFUTED with a failing point / OPEN; no AI, no API cost;
- `ask_engineer` — the whole road in plain words with files: Muse Spark reads, the stand judges (uses Meta API credit).

For example, in Claude Desktop's `claude_desktop_config.json`:

    {"mcpServers": {"ztl-engineer": {"command": "python3", "args": ["/path/to/ztl-engineer/mcp_server.py"]}}}

## Security

- **Local only.** The server listens on 127.0.0.1 and answers only this machine's browser: a request whose Host or
  Origin is not localhost, or a POST that is not JSON, is refused (another web page open in the same browser cannot
  drive it). There are no accounts: do not put it on the internet as it is — anyone who could reach it could read
  sessions and spend the API key's credit (a spending stop, $100 by default, `ZTL_ENGINEER_SPEND_CAP_USD`, is the
  only limit).
- **A brick is data, never code.** Uploaded bricks and the bricks the model writes (a datasheet may carry hidden
  instructions) are checked by the stand before anything reads them: their expressions may be arithmetic over names
  only — no attributes, indexing, strings or other Python (ztl-stand `ustand/safeexpr.py`); a system of components
  may not name files outside its own folder, and one given as data names none.
- **Uploaded files** are stored under `runs/<session>/files/` with a cleaned name (no folders, quotes or line breaks).

## Built with

Muse Spark 1.3 (Meta Model API). The code was written with Claude (Anthropic); the author is Vitaly Reznik.
