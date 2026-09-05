# katkasabo.com

Static site for **katkasabo.com**, served by GitHub Pages.

- `/index.html` — root landing page
- `/30-day/` — the "30 Days, 100 Words" writing experiment (2 Sep – 1 Oct 2026)
- `CNAME.disabled` — the custom domain, parked

**Current state:** the custom domain is OFF so the site can be previewed at
<https://katkasabo.github.io/katkasabo-com/>. Once Cloudflare DNS points the apex at
GitHub Pages, turn it back on:

```
mv CNAME.disabled CNAME && git add CNAME && python3 publish.py push -m "Enable katkasabo.com"
gh api -X PUT repos/katkasabo/katkasabo-com/pages -f cname=katkasabo.com
gh api -X PUT repos/katkasabo/katkasabo-com/pages -F https_enforced=true
```

Cloudflare needs four A records on `@`, all **DNS only** (grey cloud, not proxied):
`185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
Leave the `www` CNAME alone, that is her beehiiv newsletter.

All internal links are **relative** (`../`, `30-day/`) so the site works at both addresses.

## How publishing works

`30-day/entries.json` is the **source of truth**. Shape:

```
entries: { "YYYY-MM-DD": { "posts": [ { title, body, words, images, comments } ] } }
```

A day holds a **list** of posts, because she sometimes posts twice in one day. Each post
carries its own later `comments`. Anchors are `#day-03` for the first post of a day and
`#day-03-2` for the second. Within a day, posts render newest first, same as the page.

`30-day/index.html` is **generated** from `template.html` + `entries.json`.
Never hand-edit `30-day/index.html`; edit the template or the data, then rebuild.

### Adding a day (the normal flow)

Katka pastes ~100 words into chat. Write them to a temp file, then:

```
python3 publish.py add --title "Her title" --body-file /tmp/day.txt --push
```

Defaults to today's date. Other options:

- `--day 7` or `--date 2026-09-08` to target a specific day
- `--new` publishes **another** post on a day that already has one. Without it, `add` on a
  day with several posts refuses rather than guessing; `--post N` edits post N.
- `--image inbox/photo.jpg` (repeatable) to attach images; they are copied into
  `30-day/img/`, renamed by date, and capped at 1600px by `sips`
- `--caption "..."` (repeatable, pairs with `--image` in order)
- `--push` commits and pushes; omit it to stage the change locally first

### Getting a photo in

Katka cannot paste image bytes into chat in a way that reaches disk. Drop-off points,
checked by `python3 publish.py inbox`:

1. **Drive** `Sabotage Works/03_Sales & Marketing/02_Content Series/30 day blog/` — where
   she actually uploads. Also `Sabotage Works/blog-inbox/`.
2. `inbox/` in this repo (gitignored)
3. `~/Downloads` and `~/Desktop` — for AirDrop and screenshots

She says where the picture is; run `publish.py inbox`, confirm which file, then pass it
with `--image`. HEIC from an iPhone is converted to JPEG automatically, images over
1600px are downscaled, and a processed file that ends up heavier than the original is
discarded in favour of the original.

**Warning: the Google Drive mounts are unreliable.** There are two mounts whose names
differ only by a narrow no-break space (U+202F) before AM, and folders come and go from
the filesystem view. When a path that should exist reports "No such file or directory",
do not keep retrying the mount. Use the Google Drive MCP instead: `search_files` to find
it, `download_file_content` to get base64 (it will exceed the token cap and be written to
a tool-results file), then decode that file to disk with Python. That path is reliable.

### Commenting on a day

Katka often has a follow-up a day or two later. These are **her own later notes**, not
reader comments, and they render under the entry with a teal rule and a "Later" label.
Their words count toward the running total.

```
python3 publish.py comment --day 1 --body-file /tmp/note.txt --push
```

- `--day N` / `--date YYYY-MM-DD` picks which day it hangs off (default: today)
- `--post N` picks which post that day; the default is the day's **latest** post
- `--on YYYY-MM-DD` dates the note itself (default: today)
- `--image` / `--caption` work exactly as they do for an entry
- Comments survive a re-publish of the same day, so `add` never wipes them

Reader comments would need a backend and are deliberately not built. If she asks for
those, that is a different conversation (Giscus on GitHub Discussions is the cheap option).

### Other commands

```
python3 publish.py inbox     # recent images across all drop-off points
python3 publish.py status    # the 30-day board in the terminal
python3 publish.py build     # regenerate index.html
python3 publish.py push -m "message"
```

## House rules

- Nominal target is 100 words, but entries run short and that is fine. The site reports
  every word count the same way and never flags one as off target. Do not reintroduce
  that; she does not want the page editorialising about her own writing.
- **No em dashes** in any of Katka's published writing. Commas or parentheses.
- Entry bodies support blank-line paragraphs, `**bold**`, `*italic*`, and
  `[text](url)` links. Everything else is escaped.
- **Inline images.** A line containing only `[[img N]]` drops the post's Nth image at that
  point in the text, full text-column width, caption underneath. N is the 1-based position
  in the order the `--image` flags were passed. Images not referenced inline still render
  in a group at the foot of the post, centred and height-capped. The markers do not count
  as words.

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
