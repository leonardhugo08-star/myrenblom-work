# Automation Page Plan — Etsy API Approval

## Approach

Create a **separate page** `automation.html` (not a section in index.html) because:
- Etsy's redirect_uri points to `https://myrenblom.work/automation`
- Keeps portfolio clean; dedicated page for Etsy reviewers
- Reuses existing `styles.css` + adds automation-specific styles

## File Changes Summary

| File | Action |
|------|--------|
| `automation.html` | **CREATE** — new page |
| `styles.css` | **APPEND** — automation-specific styles |
| `script.js` | No changes needed (reveal observer works automatically) |
| `index.html` | No changes needed |

---

## 1. automation.html — Complete HTML

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content="Nordbloom Gallery — Personal Etsy shop automation tool by Myrenblom.work" />
    <title>Nordbloom Automation — Myrenblom.work</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <div class="noise" aria-hidden="true"></div>

    <header class="site-header">
      <div class="container nav">
        <a class="logo" href="/">Myrenblom.work</a>
        <nav class="nav-links">
          <a href="/">Portfolio</a>
          <a href="#features">Features</a>
          <a href="#connect">Connect</a>
          <a href="#privacy">Privacy</a>
        </nav>
      </div>
    </header>

    <main>
      <!-- HERO -->
      <section class="auto-hero" id="top">
        <div class="container">
          <p class="eyebrow">Personal Shop Tool</p>
          <h1>Nordbloom Gallery Automation</h1>
          <p class="lead">
            A private automation tool built to manage and optimize my Etsy shop,
            <strong>Nordbloom Gallery</strong>. This application connects to Etsy's API
            to streamline listing management, SEO optimization, and order workflows —
            exclusively for my own shop. It is not a commercial product or SaaS.
          </p>
        </div>
      </section>

      <!-- FEATURES -->
      <section class="section" id="features">
        <div class="container">
          <div class="section-head">
            <h2>What this tool does</h2>
            <p>Built for a single shop — Nordbloom Gallery — to automate repetitive Etsy tasks.</p>
          </div>
          <div class="grid auto-features">
            <div class="auto-feature-card reveal">
              <div class="auto-feature-icon">🔍</div>
              <h3>Bulk SEO Updates</h3>
              <p class="muted">
                Batch-update titles, tags, and descriptions across all active listings.
                Optimizes for Etsy search ranking using keyword research and competitive analysis.
              </p>
            </div>
            <div class="auto-feature-card reveal">
              <div class="auto-feature-icon">💰</div>
              <h3>Dynamic Pricing</h3>
              <p class="muted">
                Adjusts listing prices based on seasonal trends and competitor pricing data.
                Ensures competitive positioning while maintaining healthy margins.
              </p>
            </div>
            <div class="auto-feature-card reveal">
              <div class="auto-feature-icon">📦</div>
              <h3>Draft Publishing</h3>
              <p class="muted">
                Publishes draft listings in bulk with pre-configured metadata, pricing,
                and shipping profiles. Reduces manual clicks from dozens to one action.
              </p>
            </div>
            <div class="auto-feature-card reveal">
              <div class="auto-feature-icon">💌</div>
              <h3>Automated Thank-You Messages</h3>
              <p class="muted">
                Sends personalized thank-you messages to buyers after purchase,
                improving customer experience and encouraging repeat business.
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- OAUTH CONNECT -->
      <section class="section band" id="connect">
        <div class="container auto-connect-wrap">
          <div class="section-head">
            <h2>Connect with Etsy</h2>
            <p>Authorize this tool to access listing and order data from Nordbloom Gallery.</p>
          </div>
          <div class="auto-connect-card">
            <p class="muted">
              Clicking the button below will redirect you to Etsy's secure OAuth page.
              This tool requests the following permissions:
            </p>
            <ul class="auto-scope-list">
              <li><strong>listings_r</strong> — Read listing data (titles, tags, descriptions, status)</li>
              <li><strong>listings_w</strong> — Update listings (SEO fields, pricing, publish drafts)</li>
            </ul>
            <a
              class="btn"
              href="https://www.etsy.com/oauth/connect?response_type=code&redirect_uri=https://myrenblom.work/automation&scope=listings_r+listings_w&client_id=PLACEHOLDER"
            >
              Connect Etsy Account
            </a>
            <p class="auto-connect-note muted">
              Only the shop owner (Leo Myrenblom) uses this tool. No third-party access is granted.
            </p>
          </div>
        </div>
      </section>

      <!-- PRIVACY POLICY -->
      <section class="section" id="privacy">
        <div class="container">
          <div class="section-head">
            <h2>Privacy Policy</h2>
            <p>Last updated: February 2026</p>
          </div>
          <div class="auto-privacy">
            <h3>What data we access</h3>
            <p>
              This tool accesses Etsy listing data (titles, tags, descriptions, prices, status)
              and order data (buyer display name) exclusively for the Nordbloom Gallery shop
              through Etsy's official API.
            </p>

            <h3>How data is used</h3>
            <p>
              Data is used solely to automate shop management tasks: SEO optimization,
              pricing adjustments, draft publishing, and post-purchase thank-you messages.
              No data is sold, shared with third parties, or used for advertising.
            </p>

            <h3>Data storage</h3>
            <p>
              API tokens are stored securely on a private server accessible only to the shop owner.
              Listing data is cached temporarily during processing and not retained long-term.
              No buyer personal data (email, address) is stored.
            </p>

            <h3>Who has access</h3>
            <p>
              Only Leo Myrenblom (shop owner and developer) has access to this tool and its data.
              This is a personal tool, not a commercial service.
            </p>

            <h3>Data deletion</h3>
            <p>
              To request data deletion or revoke access, disconnect the app from your
              <a href="https://www.etsy.com/your/account/security" style="color: var(--accent); text-decoration: underline;">Etsy account settings</a>
              or contact the developer.
            </p>

            <h3>Contact</h3>
            <p>
              For privacy questions or support, email
              <a href="mailto:leonardhugo08@gmail.com" style="color: var(--accent); text-decoration: underline;">leonardhugo08@gmail.com</a>.
            </p>
          </div>
        </div>
      </section>

      <!-- SUPPORT -->
      <section class="cta" id="support">
        <div class="container cta-grid">
          <div>
            <h2>Support</h2>
            <p>Questions about this tool or the Nordbloom Gallery shop? Get in touch.</p>
          </div>
          <div class="cta-card">
            <p class="muted">Support Email</p>
            <p class="cta-email">leonardhugo08@gmail.com</p>
            <a class="btn" href="mailto:leonardhugo08@gmail.com">Contact Support</a>
          </div>
        </div>
      </section>
    </main>

    <footer class="footer">
      <div class="container auto-footer">
        <p>© 2026 Myrenblom.work — Automation Portfolio.</p>
        <p class="auto-etsy-disclaimer">
          The term "Etsy" is a trademark of Etsy, Inc. This application uses Etsy's API
          but is not endorsed or certified by Etsy, Inc.
        </p>
        <p>Based in Stockholm · <a href="mailto:leonardhugo08@gmail.com" style="color: var(--muted); text-decoration: underline;">leonardhugo08@gmail.com</a></p>
      </div>
    </footer>

    <script src="script.js"></script>
  </body>
</html>
```

---

## 2. CSS to Append to styles.css

Add the following at the end of `styles.css`:

```css
/* =============================================
   AUTOMATION PAGE STYLES
   ============================================= */

.auto-hero {
  padding: 5rem 0 3rem;
  text-align: center;
}

.auto-hero h1 {
  font-size: clamp(2.2rem, 4vw, 3.4rem);
  margin: 0 0 1.2rem;
}

.auto-hero .lead {
  max-width: 680px;
  margin: 0 auto;
}

.auto-features {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.auto-feature-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 2rem;
  box-shadow: var(--shadow);
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.auto-feature-icon {
  font-size: 2rem;
  margin-bottom: 1rem;
}

.auto-feature-card h3 {
  margin: 0 0 0.6rem;
  font-size: 1.2rem;
}

.auto-feature-card p {
  margin: 0;
}

.auto-connect-wrap {
  text-align: center;
}

.auto-connect-card {
  background: var(--card);
  border-radius: var(--radius);
  padding: 2.5rem;
  box-shadow: var(--shadow);
  max-width: 600px;
  margin: 0 auto;
  text-align: left;
}

.auto-scope-list {
  list-style: none;
  padding: 0;
  margin: 1.2rem 0 1.8rem;
}

.auto-scope-list li {
  padding: 0.5rem 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  font-size: 0.95rem;
}

.auto-connect-card .btn {
  display: block;
  text-align: center;
  width: 100%;
  margin-bottom: 1rem;
}

.auto-connect-note {
  font-size: 0.85rem;
  text-align: center;
}

.auto-privacy {
  background: var(--card);
  border-radius: var(--radius);
  padding: 2.5rem;
  box-shadow: var(--shadow);
  max-width: 720px;
}

.auto-privacy h3 {
  font-size: 1.1rem;
  margin: 1.8rem 0 0.5rem;
}

.auto-privacy h3:first-child {
  margin-top: 0;
}

.auto-privacy p {
  margin: 0 0 0.6rem;
  color: var(--muted);
  font-size: 0.95rem;
  line-height: 1.7;
}

.auto-footer {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  color: var(--muted);
  font-size: 0.85rem;
}

.auto-etsy-disclaimer {
  font-style: italic;
  opacity: 0.8;
}
```

---

## 3. JavaScript

No additional JavaScript needed. The existing `script.js` IntersectionObserver handles `.reveal` elements on any page.

---

## 4. Hosting / Routing Note

For `https://myrenblom.work/automation` to serve `automation.html`, either:
- **Netlify/Vercel**: Add a rewrite rule: `/automation` → `/automation.html`
- **Netlify `_redirects`**: `/automation /automation.html 200`
- **Or** create `automation/index.html` instead (directory-based routing)

Recommended: create the file as `automation/index.html` for zero-config hosting.

---

## 5. Etsy Requirement Checklist

| # | Etsy Requirement | Where Implemented | Status |
|---|---|---|---|
| 1 | Clear app description | `auto-hero` section — paragraph explaining personal shop automation tool | ✅ |
| 2 | Etsy trademark disclaimer in footer | `footer > .auto-etsy-disclaimer` — exact required text | ✅ |
| 3 | OAuth connect link/button | `#connect` section — full OAuth URL with scopes | ✅ |
| 4 | Feature list / screenshots showing what app does | `#features` section — 4 feature cards with descriptions | ✅ |
| 5 | Privacy Policy | `#privacy` section — inline, covers data access/use/storage/deletion | ✅ |
| 6 | Support email | `#support` section + privacy section + footer — leonardhugo08@gmail.com | ✅ |
| 7 | Own branding (not Etsy colors) | Uses existing Myrenblom.work palette (teal `#1f6f78`, warm `#df6b3f`, cream bg) — no Etsy orange | ✅ |

---

## 6. Section Order

1. **Header** — nav with links to Portfolio (home), Features, Connect, Privacy
2. **Hero** — app name, description, personal-use context
3. **Features** — 4-card grid (SEO, Pricing, Drafts, Thank-you messages)
4. **OAuth Connect** — scope explanation + connect button
5. **Privacy Policy** — inline, all required sections
6. **Support** — dark band with email CTA
7. **Footer** — copyright + Etsy disclaimer + contact

---

## 7. Before Going Live

1. Replace `PLACEHOLDER` in the OAuth URL with the actual Etsy API `client_id`
2. Decide hosting approach (recommend `automation/index.html`)
3. Verify redirect_uri in Etsy developer dashboard matches exactly: `https://myrenblom.work/automation`
