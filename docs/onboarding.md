# Client onboarding checklist

Everything to collect before the first crawl, and why each item matters. The
order matters: items 1–3 block the audit, the rest improve it.

---

## 1. The client's own domain

The exact domain to audit, including whether it's `www` or not, and whether
any content lives on a separate subdomain (`blog.example.com`, `docs.example.com`).

**Why it matters:** the crawler treats one domain as one site. Content on a
subdomain won't be discovered unless it's listed explicitly, and a client
whose entire blog is on a subdomain would otherwise look like they publish
nothing.

---

## 2. Competitor list — named, 5 to 10

Ask the client who *they* consider competitors, rather than picking from
search results. The two lists are often different, and the client's version
is the one they care about.

**Why it matters:** the whole analysis compares against these specific sites.
Wrong list, wrong report. Also confirm which are direct competitors versus
aspirational ones — a small studio benchmarked against a giant will show
enormous "gaps" that aren't realistic to close.

---

## 3. Written go-ahead on crawl scope

Confirm in writing: which sites, roughly how many pages each, and that
crawling is limited to public pages that `robots.txt` permits.

**Why it matters:** it's their engagement, their reputation attached to the
traffic. The crawler already respects robots.txt and rate limits, but the
client should know what's being fetched on their behalf.

---

## 4. Google Search Console — read-only access *(highly recommended)*

Ask for **read-only** access to the client's Search Console property.

**Why it matters:** this is the single biggest free upgrade available. Search
Console is Google's own first-party data for the client's site: the actual
queries they appear for, real impressions, real average position, real
click-through rate. Nothing you can buy is more accurate for their own site.

It's free, it has a free API, and requesting it is completely standard
practice for SEO work — clients expect to be asked.

**Limitation to set expectations on:** it only ever covers sites the client
owns. There is no equivalent for competitors, so competitor-side analysis
stays with what we crawl.

*How they grant it:* Search Console → Settings → Users and permissions →
Add user → your email → permission level **Restricted**.

---

## 5. Target topics or keywords *(optional)*

Any topics the client already knows they want to rank for or be known for.

**Why it matters:** turns a general gap report into a focused one. Without
it, the report covers whatever competitors publish; with it, priorities can
be weighted toward what the client actually cares about.

---

## 6. Point of contact and delivery format

Who receives the report, and whether they want PDF, a live walkthrough call,
or both.

---

## Setting up the client config

Once items 1–3 are in, create `clients/<name>.json`:

```json
{
  "client": { "name": "Acme Studio", "start_url": "https://www.acmestudio.com/" },
  "competitors": [
    { "name": "Rival One", "start_url": "https://www.rivalone.com/" },
    { "name": "Rival Two", "start_url": "https://www.rivaltwo.com/" }
  ],
  "max_pages_per_site": 25
}
```

Then run the whole audit with one command:

```
.venv\Scripts\python scripts\run_audit.py clients\acme.json
```

**On `max_pages_per_site`:** 10 is fine for a demo; a paid audit should be
25–50. Higher means a longer crawl but a fairer picture — with a low cap,
which pages get sampled varies between runs, and for monitoring that shows up
as pages appearing and disappearing.

---

## Before sending anything to the client

- [ ] Citation check passed with **0 fabricated** (`run_audit.py` enforces this)
- [ ] Skim the report for claims that read oddly — the checker catches invented
      URLs, not misread content
- [ ] Confirm no competitor is described using facts that aren't in the crawl
- [ ] Open the HTML deliverable and check the "what this does not include"
      section survived, so nobody assumes rankings were measured
