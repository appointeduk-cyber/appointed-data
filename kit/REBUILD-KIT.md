# Appointed: rebuild kit

Everything needed to rebuild Appointed's emails, sign-up and website from scratch, on beehiiv's free plan or on another tool (Ghost, Kit, Buttondown, Substack). Last updated 18 October 2026.

## The short version

| Piece | Where it lives | Survives the beehiiv trial ending? |
|---|---|---|
| Website (homepage, Distress Index, How we work, Privacy) | GitHub Pages: https://appointeduk-cyber.github.io/appointed-data/ | Yes. Free and nothing to do with beehiiv. |
| Data and the Distress Index | GitHub, updated every night automatically | Yes |
| Sign-up box on the website | beehiiv embedded form | Yes. Embedded forms work on every beehiiv plan. |
| Backup sign-up link | https://appointed.beehiiv.com/subscribe | Yes |
| Welcome email | beehiiv: Settings → Emails → Welcome email | Yes. Free-plan feature. |
| Weekly email template "Appointed weekly" | beehiiv: Templates | The template stays, and you can keep using it in beehiiv's editor. Only Claude's ability to edit it directly stops. |
| Logo files | Drive: Appointed → Brand, and the website's assets folder | Yes |

If anything in beehiiv is ever lost, rebuild it from the sections below. Each takes a few minutes.

## 1. Brand

- **Font:** Inter (free, Google Fonts). Headings weight 800 to 900, body 400.
- **Colours:**

| Use | Hex |
|---|---|
| Ink (text, logo) | #0A1014 |
| Secondary text | #3A4552 |
| Muted text | #6B7480 |
| Lines and borders | #DDE1E6 |
| Page background | #F7F7F5 |
| Brand blue (buttons, highlight handles) | #1B82FD |
| Link blue | #1667C9 |
| Highlight box (the "selected text" look) | #D0E6FD |
| Navy (dark panels) | #14202E |

- **The highlight device:** one word or phrase shown as if selected in a text editor: pale blue box (#D0E6FD), a thin blue bar at each end, with a dot on top of the left bar and under the right bar (#1B82FD). Used on "distressed assets" and "Five deals" on the website and in the logo.
- **Logo files:** appointed-logo.svg / .png (dark text, for light backgrounds), appointed-logo-dark.svg (for dark backgrounds), appointed-icon-512 (square icon), appointed-social-1200x630.png (link preview image).

## 2. Weekly email template ("Appointed weekly")

**Subject line:** `[Headline] | Appointed`
**Preview text:** `This week: [x] administrations, the Distress Index at [index], and five deals worth your time.`

**Theme settings:** font Inter; headings #0A1014; links #1667C9; buttons #1B82FD with white text.

**Layout, top to bottom:**

1. Logo image (appointed-logo.png), left-aligned, 40% width.
2. Small grey line: `Issue [n] · Monday [date] · The UK's distressed assets, every week`
3. Divider.
4. Big heading: `[This week's headline]`
5. **Numbers box** (light grey #F7F7F5, rounded corners), two rows of two:
   - `[n]` Administrations · `[n]` Liquidations (CVL)
   - `[n]` Winding-up orders · `[n]` Winding-up petitions
6. Small grey line: `Counted from notices in The Gazette, [date] to [date].`
7. `[Summary article, 300 to 450 words. What happened this week, which sectors and regions stood out, any pattern linking the deals, what the petitions suggest for the weeks ahead, and which kind of buyer is best placed.]`
8. Heading: **The Distress Index**
9. **Index box** (white, thin grey border, rounded):
   - Big number `[index]`, then `[up/down] [x] on four weeks ago`
   - `UK company insolvencies over the last four weeks. 100 = the 2024 to 2025 average. Above 100 means more insolvencies than that.`
   - `Administrations [index] · Liquidations [index] · Winding-up orders [index] · Petitions [index]`
   - `[One or two sentences: what moved the index this week, and which regions are running hottest.]`
   - Blue button **See the live index and regions** → https://appointeduk-cyber.github.io/appointed-data/distress-index.html
10. Heading: **This week's top 5**, then a numbered list of five: `[Trading name] · [process] · [place] · [score]/5`
11. Heading: **Deal 1 of 5: [Trading name]**, then a white bordered box with these lines:
    - `[Company name] · Overall [score] / 5` (grey)
    - **Snapshot:** [Process] · Appointed [date] · [Location] · [Sector] · [Asset type]
    - **What's for sale:** [One or two sentences.]
    - **Scale:** [Sites, staff, turnover from the latest accounts, with the year.]
    - **Track record:** [Two to four dated facts from Companies House and The Gazette.]
    - **Read:** [Label] · [one short reason]
    - **Sale route:** [How it is being sold, and any deadline.]
    - **Timing:** [Fast / Medium / Slow] · [reason]
    - **Who it suits:** [Type of buyer.]
    - **Key risks:** [One or two concrete risks.]
    - **Our view:** [One or two sentences.]
    - **Scorecard:** Value [n] · Accessibility [n] · Competition [n] · Timing [n]
    - **Enquiries:** [Office holder firm] · [switchboard] · [general enquiries email] · Gazette notice (link)
12. Small grey note: `[Copy the heading and box above for deals 2 to 5.]`
13. Heading: **Other leads this week**, with four small headings, each followed by bullets of `[Company], [place]: [process]; [what's there].`
    - Property · Businesses and brands · Digital assets · Equipment and stock
14. Heading: **Early warnings**
    - Grey line: `These are winding-up petitions, not insolvencies. Many are paid or dismissed.`
    - Bullets: **[Company]**, [place]: petition presented [date]. *[History line, e.g. "no earlier Gazette notices; accounts on time for five years".]*
15. Heading: **Dates to watch**, then a three-column table: Date · Event · Source (gov.uk / bankofengland.co.uk only).
16. Divider.
17. Small grey disclaimer: `Appointed is compiled from public records, chiefly The Gazette and Companies House. It is information, not investment advice, and we do not value assets or arrange sales. Always check details directly with the office holder. Spotted an error? Reply to this email and we'll correct it.`

## 3. Welcome email

**Subject:** You're in. Here's what lands on Monday
**Preview text:** Every Monday: the insolvencies, the index, and five deals worth your time.

**Body:**

> Thanks for subscribing to Appointed.
>
> Every Monday you'll get the week's UK company insolvencies counted, the Appointed Distress Index (one number for how much business distress there is, by region), and the five deals worth your time: what's for sale, the deadline, and who to call.
>
> One tip: move this email into your main inbox so Monday's issue doesn't get lost.
>
> Got a question or spotted something we missed? Just reply.
>
> Appointed

## 4. Sending details (beehiiv: Settings → Emails)

- Sender name: Appointed
- Reply-to: appointeduk@gmail.com
- Footer copyright: © 2026 Appointed
- **Still to do:** add a postal address (UK law and spam rules need one; until then beehiiv shows its own New York address). A PO box or virtual office address is fine.

## 5. Website sign-up box

- beehiiv form name: **Website sign-up (inline)**, ID 44b92ab1-152f-4e27-ad60-f5a2ec067a3a
- Look: one row, email box plus button. Placeholder "Your work email". Button "Subscribe free", blue #1B82FD, white bold Inter text, 6px rounded corners. Email box has a thin ink-coloured border.
- After signing up: "You're in. Check your inbox for a welcome email."
- **Code on the website** (homepage, inside the box with id "signup"):

```html
<script async src="https://subscribe-forms.beehiiv.com/v3/loader.js" data-beehiiv-form="44b92ab1-152f-4e27-ad60-f5a2ec067a3a"></script>
```

If the form is ever deleted: in beehiiv go to Grow → Subscribe forms → New form, choose Inline, set the look above, publish, copy its embed code, and swap the form ID in the website's index.html.

**If you leave beehiiv:** export your subscribers (Audience → Subscribers → Export CSV), import them into the new tool, and replace the code above with the new tool's embed code. Nothing else on the website changes.

## 6. Website

- Address: https://appointeduk-cyber.github.io/appointed-data/
- Files: in the GitHub repo appointeduk-cyber/appointed-data, folder `docs/`
  - index.html (homepage), distress-index.html, how-we-work.html, privacy.html
  - assets/site.css (shared look), assets/ (logos)
  - data/ (written automatically every night; don't edit by hand)
- To change wording: open the file on github.com, click the pencil icon, edit, then "Commit changes". The site updates within a minute or two.
- Still to do: a custom domain (e.g. appointed.co.uk) can be pointed at it later for free, apart from the domain itself.

## 7. Rules that apply to everything above

- Gus approves everything before it goes out. Drafts only.
- No names or personal details of individuals.
- Never call a company with only a petition "insolvent".
- No judging directors, no speculation, no valuations, no investment advice.
- Economic events "coincide with", never "cause".
- Economic facts only from the Events Register (official sources).
- The watchlist stays private.
