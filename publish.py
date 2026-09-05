#!/usr/bin/env python3
"""
Everything Is Fair Game -- publishing tool.

  python3 publish.py add     --title "..." --body-file draft.txt [--image a.jpg] [--push]
  python3 publish.py add     --new --title "..." --body-file draft.txt   # 2nd post same day
  python3 publish.py comment --day 1 --body-file note.txt
  python3 publish.py status | build | inbox | push

entries.json is the source of truth. index.html is generated from template.html,
so never hand-edit index.html.

Shape of entries.json:
  entries: { "YYYY-MM-DD": { "posts": [ {title, body, words, images, comments} ] } }
A day can hold several posts. Each post can carry later "comments" of her own.
Every word, post or comment, counts toward the running total.
"""
import argparse, datetime, html, json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "30-day")
DATA = os.path.join(SITE, "entries.json")
TPL  = os.path.join(SITE, "template.html")
OUT  = os.path.join(SITE, "index.html")
IMGD = os.path.join(SITE, "img")

DRIVE_BLOG = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-katka@sabotageworks.com (6-3-26 8:09 AM)"
    "/My Drive/Sabotage Works/03_Sales & Marketing/02_Content Series/30 day blog")
INBOXES = [
    ("30 day blog (Drive)", DRIVE_BLOG),
    ("inbox/", os.path.join(ROOT, "inbox")),
    ("Downloads", os.path.expanduser("~/Downloads")),
    ("Desktop", os.path.expanduser("~/Desktop")),
]
IMG_EXT = (".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp")

# ---------- data ----------

def migrate(d):
    """Old shape put one post's fields straight on the day. Wrap them in posts[]."""
    changed = False
    for iso, day in d["entries"].items():
        if "posts" not in day:
            d["entries"][iso] = {"posts": [day]}
            changed = True
    return changed

def load():
    with open(DATA) as f:
        d = json.load(f)
    if migrate(d):
        save(d)
    return d

def save(d):
    with open(DATA, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")

def start_date(d):
    return datetime.date.fromisoformat(d["start"])

def day_number(d, date):
    return (date - start_date(d)).days + 1

def date_for_day(d, n):
    return start_date(d) + datetime.timedelta(days=n - 1)

def posts(day):
    return day.get("posts", [])

def words(text):
    text = re.sub(r"^\[\[img\s+\d+\]\]$", "", text, flags=re.M)
    return len([w for w in re.split(r"\s+", text.strip()) if w])

def post_words(p):
    """A post's words plus every word she added to it later."""
    total = p.get("words") or words(p.get("body", ""))
    for c in p.get("comments") or []:
        total += c.get("words") or words(c.get("body", ""))
    return total

def day_words(day):
    return sum(post_words(p) for p in posts(day))

def resolve_date(d, args):
    if getattr(args, "day", None):
        return date_for_day(d, args.day)
    if getattr(args, "date", None):
        return datetime.date.fromisoformat(args.date)
    return datetime.date.today()

# ---------- images ----------

def long_edge(path):
    r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                       capture_output=True, text=True)
    dims = [int(x.split(":")[1]) for x in r.stdout.splitlines()
            if ":" in x and x.split(":")[1].strip().isdigit()]
    return max(dims) if dims else None

def ingest_image(src, slot, idx):
    if not os.path.exists(src):
        sys.exit("image not found: %s" % src)
    os.makedirs(IMGD, exist_ok=True)
    ext = os.path.splitext(src)[1].lower()
    keep = ext if ext in (".png", ".gif", ".svg", ".webp") else ".jpg"
    dest = os.path.join(IMGD, "%s-%d%s" % (slot, idx, keep))

    needs_convert = ext not in (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp")
    if needs_convert:
        subprocess.run(["sips", "-s", "format", "jpeg", src, "--out", dest],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        shutil.copyfile(src, dest)

    # Only touch the pixels when the image is genuinely too big. Re-encoding an
    # already-optimised file makes it larger, not smaller.
    if keep in (".jpg", ".png") and (long_edge(dest) or 0) > 1600:
        subprocess.run(["sips", "-Z", "1600", dest],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if keep == ".jpg":
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "72",
                            dest, "--out", dest],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Never ship something heavier than what she handed us.
    if not needs_convert and os.path.getsize(dest) > os.path.getsize(src):
        shutil.copyfile(src, dest)

    print("  image -> 30-day/img/%s (%d KB)"
          % (os.path.basename(dest), os.path.getsize(dest) // 1024))
    return "img/" + os.path.basename(dest)

def ingest_all(images, captions, slot):
    out = []
    for i, src in enumerate(images or [], 1):
        rel = ingest_image(src, slot, i)
        cap = captions[i - 1] if captions and len(captions) >= i else ""
        out.append({"src": rel, "caption": cap} if cap else {"src": rel})
    return out

# ---------- rendering ----------

def render_body(text, images=None):
    """Returns (html, indices_used). A line of just [[img N]] drops image N in place."""
    out, used = [], set()
    for b in [x.strip() for x in re.split(r"\n\s*\n", text.strip()) if x.strip()]:
        m = IMG_TOKEN.match(b)
        if m:
            i = int(m.group(1))
            if images and 1 <= i <= len(images):
                used.add(i)
                out.append(render_figs([images[i - 1]], "", inline=True).strip())
            continue
        b = html.escape(b).replace("\n", "<br>")
        b = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", b)
        b = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", b)
        b = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
                   r'<a href="\2" rel="noopener">\1</a>', b)
        out.append("<p>%s</p>" % b)
    return "\n        ".join(out), used

IMG_TOKEN = re.compile(r"^\[\[img\s+(\d+)\]\]$")

def render_figs(images, fallback_alt, inline=False):
    if not images:
        return ""
    parts = []
    for im in images:
        src = im["src"] if isinstance(im, dict) else im
        cap = im.get("caption", "") if isinstance(im, dict) else ""
        cap_html = ("<figcaption>%s</figcaption>" % html.escape(cap)) if cap else ""
        parts.append('<figure><img src="%s" alt="%s" loading="lazy">%s</figure>'
                     % (html.escape(src), html.escape(cap or fallback_alt), cap_html))
    return '\n      <div class="e-figs%s">%s</div>' % (" inline" if inline else "", "".join(parts))

def render_comments(p):
    cs = p.get("comments") or []
    if not cs:
        return ""
    out = []
    for c in cs:
        c_body, c_used = render_body(c.get("body", ""), c.get("images"))
        c_left = [im for i, im in enumerate(c.get("images") or [], 1) if i not in c_used]
        when = c.get("date", "")
        try:
            when = datetime.date.fromisoformat(when).strftime("%-d %B")
        except ValueError:
            pass
        out.append(
            '<div class="comment">\n'
            '          <div class="c-head">\n'
            '            <span class="c-label">Later</span>\n'
            '            <span class="c-date">%s</span>\n'
            '            <span class="c-wc">%d words</span>\n'
            '          </div>\n'
            '          <div class="c-body">\n            %s\n          </div>%s\n'
            '        </div>'
            % (html.escape(when), c.get("words") or words(c.get("body", "")),
               c_body, render_figs(c_left, "")))
    return ('\n      <div class="e-comments">\n        %s\n      </div>'
            % "\n        ".join(out))

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def render_calendar(d, today):
    start, n = start_date(d), d["days"]
    end = start + datetime.timedelta(days=n - 1)
    grid_start = start - datetime.timedelta(days=start.weekday())
    grid_end = end + datetime.timedelta(days=(6 - end.weekday()))
    cells, cur = [], grid_start
    while cur <= grid_end:
        iso = cur.isoformat()
        day = d["entries"].get(iso)
        ps = posts(day) if day else []
        cls = ["cell"]
        if cur < start or cur > end:
            cls.append("void")
        elif ps:
            cls.append("written")
            if any(p.get("images") for p in ps):
                cls.append("has-img")
            if len(ps) > 1:
                cls.append("multi")
        elif cur < today:
            cls.append("missed")
        elif cur > today:
            cls.append("future")
        if cur == today:
            cls.append("today")
        # Month label only where it earns its place: the 1st, and the very first cell.
        inner = '<span class="n">%d</span>' % cur.day
        if cur.day == 1 or cur == grid_start:
            inner += '<span class="d">%s</span>' % cur.strftime("%b")
        if len(ps) > 1:
            inner += '<span class="x">%d</span>' % len(ps)
        if ps:
            titles = " / ".join(p.get("title", "") for p in ps if p.get("title"))
            cells.append('<a class="%s" href="#day-%02d" data-date="%s" title="%s">%s</a>'
                         % (" ".join(cls), day_number(d, cur), iso, html.escape(titles), inner))
        else:
            cells.append('<div class="%s" data-date="%s">%s</div>' % (" ".join(cls), iso, inner))
        cur += datetime.timedelta(days=1)
    return ('<div class="cal">\n      <div class="dow">%s</div>\n'
            '      <div class="grid">\n        %s\n      </div>\n    </div>'
            % ("".join("<span>%s</span>" % x for x in DOW), "\n        ".join(cells)))

def render_entries(d):
    days = sorted(d["entries"].items(), reverse=True)
    if not days:
        return ('<div class="empty"><b>Nothing published yet.</b>'
                'Day 1 goes up on 2 September 2026.</div>')
    out = []
    for iso, day in days:
        date = datetime.date.fromisoformat(iso)
        n = day_number(d, date)
        ps = posts(day)
        # Newest first within the day, same as the page as a whole.
        for rev_i, p in enumerate(reversed(ps)):
            i = len(ps) - rev_i                      # 1-based position in publish order
            anchor = "day-%02d" % n if i == 1 else "day-%02d-%d" % (n, i)
            body_html, used = render_body(p.get("body", ""), p.get("images"))
            leftover = [im for j, im in enumerate(p.get("images") or [], 1) if j not in used]
            ordinal = ('<span class="e-nth">%d of %d</span>' % (i, len(ps))) if len(ps) > 1 else ""
            title = ('<h3 class="e-title">%s</h3>' % html.escape(p["title"])) if p.get("title") else ""
            out.append(
                '<article class="entry" id="%s">\n'
                '      <div class="e-head">\n'
                '        <span class="day-no">Day %02d</span>%s\n'
                '        <span class="e-date">%s</span>\n'
                '        <a class="e-permalink" href="#%s">#</a>\n'
                '        <span class="e-wc">%d words</span>\n'
                '      </div>\n'
                '      %s\n      <div class="e-body">\n        %s\n      </div>%s%s\n'
                '    </article>'
                % (anchor, n, ordinal, date.strftime("%A, %-d %B %Y"), anchor,
                   p.get("words") or words(p.get("body", "")), title,
                   body_html,
                   render_figs(leftover, p.get("title", "")),
                   render_comments(p)))
    return "\n    ".join(out)

def render_stats(d, today):
    start, n = start_date(d), d["days"]
    written = sum(1 for day in d["entries"].values() if posts(day))
    elapsed = max(0, min(n, (today - start).days + 1))
    streak, cur = 0, today
    while cur >= start:
        if posts(d["entries"].get(cur.isoformat(), {})):
            streak += 1
        elif cur != today:      # today not yet written does not break the streak
            break
        cur -= datetime.timedelta(days=1)
    total = sum(day_words(day) for day in d["entries"].values())
    cells = [
        ("on" if written else "", written, "of %d written" % n),
        ("on" if streak > 1 else "", streak, "day streak"),
        ("", "{:,}".format(total), "words so far"),
        ("", max(0, n - elapsed), "days to go"),
    ]
    return ('<div class="stats">%s</div>' %
            "".join('<div class="stat %s"><b>%s</b><span>%s</span></div>' % c for c in cells))

def build(quiet=False):
    d = load()
    today = datetime.date.today()
    with open(TPL) as f:
        page = f.read()
    page = page.replace("<!--STATS-->", render_stats(d, today))
    page = page.replace("<!--CALENDAR-->", render_calendar(d, today))
    page = page.replace("<!--ENTRIES-->", render_entries(d))
    with open(OUT, "w") as f:
        f.write(page)
    if not quiet:
        print("built 30-day/index.html  (%d posts across %d days)"
              % (sum(len(posts(x)) for x in d["entries"].values()), len(d["entries"])))
    return d

# ---------- git ----------

def git(*a, check=True):
    return subprocess.run(["git", "-C", ROOT] + list(a), check=check,
                          capture_output=True, text=True)

def push(msg):
    git("add", "-A")
    if not git("status", "--porcelain").stdout.strip():
        print("nothing to push")
        return
    git("commit", "-m", msg)
    r = git("push", check=False)
    if r.returncode != 0:
        print(r.stderr.strip())
        sys.exit("push failed")
    print("pushed: %s" % msg)
    print("live in ~1 min at https://katkasabo.github.io/katkasabo-com/30-day/")

# ---------- commands ----------

def read_body(args, what="entry"):
    if args.body_file:
        with open(args.body_file) as f:
            body = f.read()
    elif args.body:
        body = args.body
    else:
        print("paste the %s, then Ctrl-D:" % what)
        body = sys.stdin.read()
    body = body.strip()
    if not body:
        sys.exit("empty %s" % what)
    return body

def cmd_add(args):
    d = load()
    date = resolve_date(d, args)
    iso, n = date.isoformat(), day_number(d, resolve_date(d, args))
    if not (1 <= n <= d["days"]):
        sys.exit("%s is outside the 30-day window (day %d)" % (iso, n))
    body = read_body(args)

    day = d["entries"].setdefault(iso, {"posts": []})
    ps = day["posts"]
    if args.new:
        idx = len(ps)                       # append
    elif args.post:
        idx = args.post - 1
        if not (0 <= idx < len(ps)):
            sys.exit("day %d has %d post(s); --post %d is out of range" % (n, len(ps), args.post))
    else:
        idx = 0
        if len(ps) > 1:
            sys.exit("day %d already has %d posts. Use --new to add another, "
                     "or --post N to edit one." % (n, len(ps)))
    existed = idx < len(ps)

    slot = iso if idx == 0 else "%s-p%d" % (iso, idx + 1)
    if args.image:
        images = ingest_all(args.image, args.caption, slot)
    elif existed and not args.drop_images:
        images = ps[idx].get("images", [])
    else:
        images = []

    post = {
        "title": args.title or "",
        "body": body,
        "words": words(body),
        "images": images,
        "comments": ps[idx].get("comments", []) if existed else [],
        "published": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    if existed:
        ps[idx] = post
    else:
        ps.append(post)
    save(d)
    build(quiet=True)
    label = "post %d of %d" % (idx + 1, len(ps)) if len(ps) > 1 else "post"
    print("%s Day %02d  %s  (%s)" % ("updated" if existed else "added  ", n, iso, label))
    print("  %d words" % post["words"])
    if args.title:
        print('  "%s"' % args.title)
    if args.push:
        push("Day %02d: %s" % (n, args.title or iso))

def cmd_comment(args):
    """Attach a later note to a post. Its words count toward the total."""
    d = load()
    date = resolve_date(d, args)
    iso = date.isoformat()
    day = d["entries"].get(iso)
    if not day or not posts(day):
        sys.exit("no post on %s yet, publish the day first" % iso)
    ps = posts(day)
    idx = (args.post - 1) if args.post else (len(ps) - 1)   # default: the day's latest post
    if not (0 <= idx < len(ps)):
        sys.exit("day has %d post(s); --post %d is out of range" % (len(ps), args.post))

    body = read_body(args, "comment")
    p = ps[idx]
    p.setdefault("comments", [])
    slot = "%s-p%d-c%d" % (iso, idx + 1, len(p["comments"]) + 1)
    when = args.on or datetime.date.today().isoformat()
    p["comments"].append({
        "date": when,
        "body": body,
        "words": words(body),
        "images": ingest_all(args.image, args.caption, slot),
        "published": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    save(d)
    build(quiet=True)
    n = day_number(d, date)
    where = "Day %02d" % n + (" post %d" % (idx + 1) if len(ps) > 1 else "")
    print("comment #%d on %s (%s)" % (len(p["comments"]), where, iso))
    print("  %d words, dated %s" % (words(body), when))
    print("  post total now %d words" % post_words(p))
    if args.push:
        push("Day %02d: comment" % n)

def cmd_inbox(args):
    now, found = datetime.datetime.now(), []
    for label, dpath in INBOXES:
        if not os.path.isdir(dpath):
            continue
        try:
            names = os.listdir(dpath)
        except OSError:
            continue        # the Drive mounts drop out; not worth failing over
        for fn in names:
            if not fn.lower().endswith(IMG_EXT):
                continue
            full = os.path.join(dpath, fn)
            age = now - datetime.datetime.fromtimestamp(os.path.getmtime(full))
            if age.days <= args.days:
                found.append((age, label, full, os.path.getsize(full) // 1024))
    if not found:
        print("no images in the last %d days. Drop-off points:" % args.days)
        for label, dpath in INBOXES:
            print("  %-22s %s" % (label, dpath))
        print("\nIf the Drive folder looks empty, the mount is flaking. Use the Google")
        print("Drive MCP (search_files + download_file_content) instead. See CLAUDE.md.")
        return
    found.sort()
    print("recent images (newest first):")
    for age, label, full, kb in found[:args.limit]:
        h = age.days * 24 + age.seconds // 3600
        when = "%dd ago" % age.days if age.days else ("%dh ago" % h if h else "just now")
        print("  [%-20s] %-9s %5d KB  %s" % (label, when, kb, full))

def cmd_status(args):
    d = load()
    today = datetime.date.today()
    start, n = start_date(d), d["days"]
    print("Everything Is Fair Game   %s -> %s"
          % (start.strftime("%-d %b"), (start + datetime.timedelta(days=n-1)).strftime("%-d %b %Y")))
    for i in range(1, n + 1):
        date = date_for_day(d, i)
        day = d["entries"].get(date.isoformat())
        ps = posts(day) if day else []
        if ps:
            nc = sum(len(p.get("comments") or []) for p in ps)
            bits = []
            if len(ps) > 1:
                bits.append("%d posts" % len(ps))
            if nc:
                bits.append("%d comment%s" % (nc, "" if nc == 1 else "s"))
            extra = ("  (" + ", ".join(bits) + ")") if bits else ""
            titles = " / ".join(p.get("title", "") for p in ps if p.get("title"))
            mark, note = "[x]", "%3d words  %s%s" % (day_words(day), titles, extra)
        elif date < today:
            mark, note = "[ ]", "missed"
        elif date == today:
            mark, note = "[>]", "TODAY -- not written yet"
        else:
            mark, note = "[ ]", ""
        print(" %s Day %02d  %s  %s" % (mark, i, date.strftime("%a %d %b"), note))
    total = sum(day_words(x) for x in d["entries"].values())
    print("\n %d words total" % total)

def main():
    p = argparse.ArgumentParser(description="Everything Is Fair Game")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="publish a post")
    a.add_argument("--date"); a.add_argument("--day", type=int)
    a.add_argument("--new", action="store_true", help="another post on a day that already has one")
    a.add_argument("--post", type=int, help="edit post N of that day")
    a.add_argument("--title"); a.add_argument("--body"); a.add_argument("--body-file")
    a.add_argument("--image", action="append"); a.add_argument("--caption", action="append")
    a.add_argument("--drop-images", action="store_true")
    a.add_argument("--push", action="store_true")
    a.set_defaults(fn=cmd_add)

    c = sub.add_parser("comment", help="add a later note to a post")
    c.add_argument("--date"); c.add_argument("--day", type=int)
    c.add_argument("--post", type=int, help="which post that day (default: the latest)")
    c.add_argument("--on", help="date the note is dated (default: today)")
    c.add_argument("--body"); c.add_argument("--body-file")
    c.add_argument("--image", action="append"); c.add_argument("--caption", action="append")
    c.add_argument("--push", action="store_true")
    c.set_defaults(fn=cmd_comment)

    b = sub.add_parser("build", help="regenerate index.html")
    b.set_defaults(fn=lambda args: build())

    i = sub.add_parser("inbox", help="list recent images ready to attach")
    i.add_argument("--days", type=int, default=7); i.add_argument("--limit", type=int, default=15)
    i.set_defaults(fn=cmd_inbox)

    s = sub.add_parser("status", help="show the board in the terminal")
    s.set_defaults(fn=cmd_status)

    u = sub.add_parser("push", help="commit and push")
    u.add_argument("-m", "--message", default="update")
    u.set_defaults(fn=lambda args: (build(quiet=True), push(args.message)))

    args = p.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()
