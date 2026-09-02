#!/usr/bin/env python3
"""
30 Days, 100 Words -- publishing tool.

  python3 publish.py add  --title "..." --body-file draft.txt [--image inbox/a.jpg]
  python3 publish.py add  --date 2026-09-05 --title "..." --body "text here"
  python3 publish.py build
  python3 publish.py status
  python3 publish.py push

entries.json is the source of truth. index.html is always generated from
template.html + entries.json, so never hand-edit index.html.
"""
import argparse, datetime, html, json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "30-day")
DATA = os.path.join(SITE, "entries.json")
TPL  = os.path.join(SITE, "template.html")
OUT  = os.path.join(SITE, "index.html")
IMGD = os.path.join(SITE, "img")
TARGET_WORDS = 100
DRIVE = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-katka@sabotageworks.com"
    " (6-3-26 8:09 AM)/My Drive/Sabotage Works/blog-inbox")
INBOXES = [
    ("blog-inbox (Drive)", DRIVE),
    ("inbox/", os.path.join(ROOT, "inbox")),
    ("Downloads", os.path.expanduser("~/Downloads")),
    ("Desktop", os.path.expanduser("~/Desktop")),
]
IMG_EXT = (".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp")
TOLERANCE = 15  # +/- words before we flag it

# ---------- data ----------

def load():
    with open(DATA) as f:
        return json.load(f)

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

def words(text):
    return len([w for w in re.split(r"\s+", text.strip()) if w])

# ---------- images ----------

def ingest_image(src, date_iso, idx):
    if not os.path.exists(src):
        sys.exit("image not found: %s" % src)
    os.makedirs(IMGD, exist_ok=True)
    ext = os.path.splitext(src)[1].lower()
    # iPhone HEIC and everything else lands as jpeg; sips handles the conversion.
    keep = ext if ext in (".png", ".gif", ".svg", ".webp") else ".jpg"
    name = "%s-%d%s" % (date_iso, idx, keep)
    dest = os.path.join(IMGD, name)
    if ext in (".heic", ".heif") or (keep == ".jpg" and ext != ".jpg" and ext != ".jpeg"):
        subprocess.run(["sips", "-s", "format", "jpeg", src, "--out", dest],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        shutil.copyfile(src, dest)
    if keep in (".jpg", ".png"):
        # cap the long edge so pages stay light
        subprocess.run(["sips", "-Z", "1600", dest],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if keep == ".jpg":
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "72",
                            dest, "--out", dest],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    kb = os.path.getsize(dest) // 1024
    print("  image -> 30-day/img/%s (%d KB)" % (name, kb))
    return "img/" + name

# ---------- rendering ----------

def render_body(text):
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    out = []
    for b in blocks:
        b = html.escape(b).replace("\n", "<br>")
        b = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", b)
        b = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", b)
        b = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
                   r'<a href="\2" rel="noopener">\1</a>', b)
        out.append("<p>%s</p>" % b)
    return "\n        ".join(out)

DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def render_calendar(d, today):
    start, n = start_date(d), d["days"]
    end = start + datetime.timedelta(days=n - 1)
    grid_start = start - datetime.timedelta(days=start.weekday())
    grid_end = end + datetime.timedelta(days=(6 - end.weekday()))
    cells = []
    cur = grid_start
    while cur <= grid_end:
        iso = cur.isoformat()
        entry = d["entries"].get(iso)
        cls = ["cell"]
        if cur < start or cur > end:
            cls.append("void")
        elif entry:
            cls.append("written")
            if entry.get("images"):
                cls.append("has-img")
        elif cur < today:
            cls.append("missed")
        elif cur > today:
            cls.append("future")
        if cur == today:
            cls.append("today")
        # Month label only where it earns its place: the 1st, and the very first cell.
        show_mon = cur.day == 1 or cur == grid_start
        inner = '<span class="n">%d</span>' % cur.day
        if show_mon:
            inner += '<span class="d">%s</span>' % cur.strftime("%b")
        if entry:
            cells.append('<a class="%s" href="#day-%02d" data-date="%s" title="%s">%s</a>'
                         % (" ".join(cls), day_number(d, cur), iso,
                            html.escape(entry.get("title", "")), inner))
        else:
            cells.append('<div class="%s" data-date="%s">%s</div>'
                         % (" ".join(cls), iso, inner))
        cur += datetime.timedelta(days=1)
    dow = "".join("<span>%s</span>" % x for x in DOW)
    return ('<div class="cal">\n      <div class="dow">%s</div>\n'
            '      <div class="grid">\n        %s\n      </div>\n    </div>'
            % (dow, "\n        ".join(cells)))

def render_entries(d):
    items = sorted(d["entries"].items(), reverse=True)
    if not items:
        return ('<div class="empty"><b>Nothing published yet.</b>'
                'Day 1 goes up on 2 September 2026.</div>')
    out = []
    for iso, e in items:
        date = datetime.date.fromisoformat(iso)
        n = day_number(d, date)
        wc = e.get("words") or words(e.get("body", ""))
        off = "" if abs(wc - TARGET_WORDS) <= TOLERANCE else " off"
        figs = ""
        if e.get("images"):
            parts = []
            for im in e["images"]:
                src = im["src"] if isinstance(im, dict) else im
                cap = im.get("caption", "") if isinstance(im, dict) else ""
                cap_html = ("<figcaption>%s</figcaption>" % html.escape(cap)) if cap else ""
                parts.append('<figure><img src="%s" alt="%s" loading="lazy">%s</figure>'
                             % (html.escape(src), html.escape(cap or e.get("title", "")), cap_html))
            figs = '\n      <div class="e-figs">%s</div>' % "".join(parts)
        title = ('<h3 class="e-title">%s</h3>' % html.escape(e["title"])) if e.get("title") else ""
        out.append(
            '<article class="entry" id="day-%02d">\n'
            '      <div class="e-head">\n'
            '        <span class="day-no">Day %02d</span>\n'
            '        <span class="e-date">%s</span>\n'
            '        <a class="e-permalink" href="#day-%02d">#</a>\n'
            '        <span class="e-wc%s">%d words</span>\n'
            '      </div>\n'
            '      %s\n      <div class="e-body">\n        %s\n      </div>%s\n'
            '    </article>'
            % (n, n, date.strftime("%A, %-d %B %Y"), n, off, wc,
               title, render_body(e.get("body", "")), figs))
    return "\n    ".join(out)

def render_stats(d, today):
    start, n = start_date(d), d["days"]
    written = len(d["entries"])
    elapsed = max(0, min(n, (today - start).days + 1))
    streak = 0
    cur = today
    while cur >= start:
        if cur.isoformat() in d["entries"]:
            streak += 1
        elif cur != today:  # today not yet written does not break the streak
            break
        cur -= datetime.timedelta(days=1)
    total = sum(e.get("words") or words(e.get("body", "")) for e in d["entries"].values())
    left = n - elapsed
    cells = [
        ("on" if written else "", written, "of %d written" % n),
        ("on" if streak > 1 else "", streak, "day streak"),
        ("", "{:,}".format(total), "words so far"),
        ("", max(0, left), "days to go"),
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
        print("built 30-day/index.html  (%d entries)" % len(d["entries"]))
    return d

# ---------- git ----------

def git(*a, check=True):
    return subprocess.run(["git", "-C", ROOT] + list(a), check=check,
                          capture_output=True, text=True)

def push(msg):
    git("add", "-A")
    st = git("status", "--porcelain").stdout.strip()
    if not st:
        print("nothing to push")
        return
    git("commit", "-m", msg)
    r = git("push", check=False)
    if r.returncode != 0:
        print(r.stderr.strip())
        sys.exit("push failed")
    print("pushed: %s" % msg)
    print("live in ~1 min at https://katkasabo.com/30-day/")

# ---------- commands ----------

def cmd_add(args):
    d = load()
    if args.day:
        date = date_for_day(d, args.day)
    elif args.date:
        date = datetime.date.fromisoformat(args.date)
    else:
        date = datetime.date.today()
    iso = date.isoformat()
    n = day_number(d, date)
    if not (1 <= n <= d["days"]):
        sys.exit("%s is outside the 30-day window (day %d)" % (iso, n))

    if args.body_file:
        with open(args.body_file) as f:
            body = f.read()
    elif args.body:
        body = args.body
    else:
        print("paste the entry, then Ctrl-D:")
        body = sys.stdin.read()
    body = body.strip()
    if not body:
        sys.exit("empty entry")

    existed = iso in d["entries"]
    images = []
    if args.image:
        for i, src in enumerate(args.image, 1):
            rel = ingest_image(src, iso, i)
            cap = ""
            if args.caption and len(args.caption) >= i:
                cap = args.caption[i - 1]
            images.append({"src": rel, "caption": cap} if cap else {"src": rel})
    elif existed and not args.drop_images:
        images = d["entries"][iso].get("images", [])

    wc = words(body)
    d["entries"][iso] = {
        "title": args.title or "",
        "body": body,
        "words": wc,
        "images": images,
        "published": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    save(d)
    build(quiet=True)
    flag = "" if abs(wc - TARGET_WORDS) <= TOLERANCE else "   <- off target"
    print("%s Day %02d  %s" % ("updated" if existed else "added  ", n, iso))
    print("  %d words%s" % (wc, flag))
    if args.title:
        print("  \"%s\"" % args.title)
    if args.push:
        push("Day %02d: %s" % (n, args.title or iso))

def cmd_inbox(args):
    """List recent images across every drop-off point, newest first."""
    now = datetime.datetime.now()
    found = []
    for label, d in INBOXES:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.lower().endswith(IMG_EXT):
                continue
            full = os.path.join(d, fn)
            age = now - datetime.datetime.fromtimestamp(os.path.getmtime(full))
            if age.days > args.days:
                continue
            found.append((age, label, full, os.path.getsize(full) // 1024))
    if not found:
        print("no images in the last %d days. Drop-off points:" % args.days)
        for label, d in INBOXES:
            print("  %-20s %s" % (label, d))
        return
    found.sort()
    print("recent images (newest first):")
    for age, label, full, kb in found[:args.limit]:
        h = age.days * 24 + age.seconds // 3600
        when = "%dd ago" % age.days if age.days else ("%dh ago" % h if h else "just now")
        print("  [%-18s] %-9s %5d KB  %s" % (label, when, kb, full))


def cmd_status(args):
    d = load()
    today = datetime.date.today()
    start, n = start_date(d), d["days"]
    print("30 Days, 100 Words   %s -> %s"
          % (start.strftime("%-d %b"), (start + datetime.timedelta(days=n-1)).strftime("%-d %b %Y")))
    for i in range(1, n + 1):
        date = date_for_day(d, i)
        e = d["entries"].get(date.isoformat())
        if e:
            mark, note = "[x]", "%3d words  %s" % (e.get("words", 0), e.get("title", ""))
        elif date < today:
            mark, note = "[ ]", "missed"
        elif date == today:
            mark, note = "[>]", "TODAY -- not written yet"
        else:
            mark, note = "[ ]", ""
        print(" %s Day %02d  %s  %s" % (mark, i, date.strftime("%a %d %b"), note))

def main():
    p = argparse.ArgumentParser(description="30 Days, 100 Words")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="add or update a day's entry")
    a.add_argument("--date"); a.add_argument("--day", type=int)
    a.add_argument("--title"); a.add_argument("--body"); a.add_argument("--body-file")
    a.add_argument("--image", action="append")
    a.add_argument("--caption", action="append")
    a.add_argument("--drop-images", action="store_true")
    a.add_argument("--push", action="store_true")
    a.set_defaults(fn=cmd_add)

    b = sub.add_parser("build", help="regenerate index.html")
    b.set_defaults(fn=lambda args: build())

    i = sub.add_parser("inbox", help="list recent images ready to attach")
    i.add_argument("--days", type=int, default=7)
    i.add_argument("--limit", type=int, default=15)
    i.set_defaults(fn=cmd_inbox)

    s = sub.add_parser("status", help="show the 30-day board in the terminal")
    s.set_defaults(fn=cmd_status)

    u = sub.add_parser("push", help="commit and push")
    u.add_argument("-m", "--message", default="update")
    u.set_defaults(fn=lambda args: (build(quiet=True), push(args.message)))

    args = p.parse_args()
    args.fn(args)

if __name__ == "__main__":
    main()
