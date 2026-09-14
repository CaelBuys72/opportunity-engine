# Publish a generated kit on Whop — first-sale checklist

The engine takes you from opportunity → researched → curated → **generated product**
→ **creator shortlist + outreach drafts**. This is the manual "last mile": get the
product live on Whop and the outreach out the door. ~20–30 min the first time.

App: **https://opportunity-engine-pi.vercel.app** · Whop: **https://whop.com/dashboard**

---

## 0. Before you start
- [ ] You've **generated the product** for the opportunity (dashboard → open the
      opportunity → 📦 Product → shows `release_candidate` with a download link).
- [ ] **Read the ebook once.** It's LLM-generated — skim for accuracy, correct
      anything wrong, fix the voice. Do not sell something you haven't read.
- [ ] You have (or make) a Whop **business**: whop.com/start if you don't have one.

## 1. Get the files
- [ ] Dashboard → the opportunity → **📦 Product → Download product bundle (.zip)**.
- [ ] Unzip. You'll have: the **ebook PDF** (the main product) + the **editable
      tools** (`.xlsx`/`.csv`) + `START_HERE`.
- [ ] (Optional) Do any final visual polish on the PDF cover in Canva if you want —
      the content is done; this is just presentation.

## 2. Create the product on Whop
- [ ] whop.com/dashboard → your business → **Products → Create** (or "Create a
      product / access pass").
- [ ] **Title + description:** reuse the engine's copy — open the opportunity's
      🧪 Product Brief; use the `product_concept` as the title and
      `product_promise` / core transformation as the description/headline. (Tighten
      it; don't paste raw.)
- [ ] Keep visibility **hidden/draft** until everything below is done.

## 3. Attach the deliverable (the actual files)
- [ ] Add a **content / "Files" experience** to the product (Whop delivers digital
      files through an experience attached to the product — this is the step the API
      can't do for us).
- [ ] Upload the **ebook PDF** + the **tool spreadsheets** + `START_HERE`.
- [ ] Confirm a test buyer would actually receive/download them.

## 4. Set the price
- [ ] Add a **one-time pricing plan** (not subscription, unless you intend one).
- [ ] Price from the brief's `price_range` as a starting point. For a first
      info-product kit, a low, friction-free price to get the **first real sale +
      feedback** beats optimizing price before any signal exists.
- [ ] Currency: match your payout setup.

## 5. Publish
- [ ] Set visibility → **visible**, publish.
- [ ] Open the **public product URL** yourself and sanity-check the page, price,
      and (ideally via a test/discount) that the files deliver.
- [ ] Copy the **public product link** — you'll paste it into outreach.

## 6. Fire the outreach (from the engine)
- [ ] Dashboard → the opportunity → **🎯 Creators** (run **Find Creators** if you
      haven't) → **✉️ Outreach drafts → Draft Outreach**.
- [ ] For each draft: **Copy**, paste your **Whop product link** into it, personalise
      one line, and **send it yourself** (email if a public address was found, else
      DM on the creator's platform). *Never mass-automate sending — it gets accounts
      banned.*
- [ ] Mark each one **sent** (the status dropdown) so you can track replies.

## 7. Track + learn
- [ ] Log replies (mark **replied**) and any sale.
- [ ] The real questions this answers: **does anyone buy, and do creators bite?**
      That signal decides whether to (a) automate the Whop create-listing step,
      (b) make more products, or (c) change the offer.

---

### Honest notes
- **Whop labels change** — the exact menu names may differ from the above; the flow
  (create product → attach files via an experience → add price → publish) is stable.
- **Automating this later:** once you've done it once and have a Whop **API key +
  business ID (`biz_…`)**, the *create-listing* step is a quick, testable add
  (`POST https://api.whop.com/api/v1/products`). The **file upload stays manual** —
  Whop has no clean REST path for attaching the deliverable.
- **Commercial rights:** the ebook content (Groq) and cover (Cloudflare FLUX.1-schnell,
  Apache-2.0) are yours to sell. Still your call to verify each provider's current
  terms before scaling.
