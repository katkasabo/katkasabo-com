# katkasabo.com

Static site for **katkasabo.com**, served by GitHub Pages.

- `/index.html` — root landing page
- `/30-day/` — the "30 Days, 100 Words" writing experiment (2 Sep – 1 Oct 2026)
- `CNAME` — custom domain (katkasabo.com)

## How publishing works

`30-day/entries.json` is the **source of truth**.
`30-day/index.html` is **generated** from `template.html` + `entries.json`.
Never hand-edit `30-day/index.html`; edit the template or the data, then rebuild.

### Adding a day (the normal flow)

Katka pastes ~100 words into chat. Write them to a temp file, then:

```
python3 publish.py add --title "Her title" --body-file /tmp/day.txt --push
```

Defaults to today's date. Other options:

- `--day 7` or `--date 2026-09-08` to target a specific day
- `--image inbox/photo.jpg` (repeatable) to attach images; they are copied into
  `30-day/img/`, renamed by date, and capped at 1600px by `sips`
- `--caption "..."` (repeatable, pairs with `--image` in order)
- `--push` commits and pushes; omit it to stage the change locally first

### Getting a photo in

Katka cannot paste image bytes into chat in a way that reaches disk. Drop-off points,
checked by `python3 publish.py inbox`:

1. **Drive** `Sabotage Works/blog-inbox/` — works from the phone (Google Drive app ->
   Sabotage Works -> blog-inbox -> Upload). This is the phone-to-Mac path.
2. `inbox/` in this repo (gitignored)
3. `~/Downloads` and `~/Desktop` — for AirDrop and screenshots

She says "the picture is in blog-inbox" (or names the file); run `publish.py inbox`,
confirm which file, then pass it with `--image`. HEIC from an iPhone is converted to
JPEG automatically.

### Other commands

```
python3 publish.py inbox     # recent images across all drop-off points
python3 publish.py status    # the 30-day board in the terminal
python3 publish.py build     # regenerate index.html
python3 publish.py push -m "message"
```

## House rules

- Target is 100 words, ±15. `publish.py` prints a warning outside that band and the
  page shows the count in muted grey instead of teal.
- **No em dashes** in any of Katka's published writing. Commas or parentheses.
- Entry bodies support blank-line paragraphs, `**bold**`, `*italic*`, and
  `[text](url)` links. Everything else is escaped.

## Design system

Sabotage Works tokens, lifted from sabotageworks.com:

| token | light | dark |
|---|---|---|
| background (warm gray) | `#F5F0EB` | `#1F1F1F` |
| card | `#FAF7F5` | `#262626` |
| ink (charcoal) | `#1F1F1F` | `#F5F0EB` |
| muted | `#666666` | `#CCB299` |
| border | `#E2D9D4` | `#333333` |
| sabotage red (primary) | `#E74040` | same |
| cherry | `#A93232` | same |
| teal (accent) | `#2EC2B3` | same |
| blush (secondary) | `#F5C7BD` | `#4A2E2A` |

Gradient `linear-gradient(135deg,#E74040,#A93232)`, glow `0 0 40px rgba(231,64,64,.30)`,
radius `.5rem`. Headings **Montserrat 700**, body **Lato**, labels/numbers system mono.

## Local preview

```
python3 -m http.server 8731
```
Then http://localhost:8731/30-day/
