# Breaking Walls website

Static rebuild of www.breakingwalls.co. The October Squarespace capture is preserved, and the November 2026 local version adds the Simulation and Robotics content to the same site.
Plain HTML/CSS/JS, no framework, no build step needed to publish.

## Layout

```
site/                 <- the website. Publish this folder as-is.
  index.html          landing page (/)
  home/ about/ ...    one folder per page (clean URLs: /about, /venus ...)
  blog/ news/         blog posts and news items
  assets/css/site.css all styles (palette, type, grid, components)
  assets/js/site.js   menu, galleries, fade-ins, contact form
  assets/img/         images (optimized; big GIFs converted to MP4)
  assets/video/       background + trailer videos (MP4, posters)
  assets/fonts/       Poppins + Epilogue (self-hosted, SIL OFL)
  404.html robots.txt sitemap.xml _redirects
tools/build.py        one-time converter: Squarespace capture -> site/
tools/i18n.py         builds site/fr/ from i18n/fr.json + adds the language switcher
i18n/fr.json          French translations (edit here)
Preview site.command  double-click to preview the site locally on a Mac
```

`_capture/` (raw Squarespace export, ~800 MB) and `_work/` are kept locally but
not in git. You only need them to re-run `tools/build.py`. From now on, edit the
files in `site/` directly.

## Unified site

- The bilingual portal `/` and `/fr/` lead to the existing Games portfolio (`/home`, `/fr/home`) or Simulation (`/simulation/`, `/fr/simulation/`).
- Robotics lives at `/simulation/robotics/` and `/fr/simulation/robotics/`. The public Simulation content is adapted from the separate Breaking Walls .ca site's main and Robotics pages. The old React app is not deployed by this repository.
- Edit the managed page copy in `tools/unify_site.py` and run `python3 tools/unify_site.py`. The existing translation command also regenerates those pages after refreshing the games translations.
- Publish only `site/` on the new host, preserving existing Games, support, and press URLs. Once the unified .co site is live on HTTPS, configure permanent redirects for the former .ca website: `/` to `https://www.breakingwalls.co/simulation/`, and `/robotics` to `https://www.breakingwalls.co/simulation/robotics/`. Configure these at the .ca host, not in the .co site. Preserve .ca mail records, and do not redirect separate apps or subdomains as part of this change. The simulation contact still uses `info@breakingwalls.ca`.
- Verify both locales, the old press/support URLs, the .ca redirects and the contact email after the host switch. The repo makes no DNS, hosting or mail changes.

## Preview locally

```
cd site
python3 -m http.server 8000
# open http://localhost:8000
```

## Hosting (pick one later)

Any static host works. Point it at the `site/` folder, no build command.

| Host | Settings |
| --- | --- |
| Cloudflare Pages | Build command: none, output dir: `site` |
| Netlify | Publish dir: `site` (the `_redirects` file is picked up) |
| GitHub Pages | Deploy `site/` via an Actions workflow, or move it to `/docs` |
| Any web server | Upload the contents of `site/` to the web root |

## Things to do before cancelling Squarespace

1. **Contact form.** Squarespace processed the About page form. Now it opens
   the visitor's email app (to info@breakingwalls.co) as a fallback. For a real
   form, create a free endpoint (Formspree, Basin, or Netlify Forms) and paste
   its URL into `FORM_ENDPOINT` at the bottom of `site/assets/js/site.js`.
2. **French version.** Done: every page has a French copy under `/fr/`
   (e.g. /fr/about), with the English/Français switcher in the header.
   Translations live in `i18n/fr.json` (English -> French, HTML kept). To fix
   wording, edit that file and run `python3 tools/i18n.py apply`. After adding
   or changing English text, run `python3 tools/i18n.py extract` first to see
   which strings need a translation.
3. **Domain / DNS.** Find out where breakingwalls.co is registered (Squarespace
   Domains or elsewhere). Check the domain renewal and DNS separately from website hosting; keep existing mail records intact.
4. **Email.** If @breakingwalls.co mail (Google Workspace, etc.) is billed
   through Squarespace, move that subscription first. MX records must be
   copied to the new DNS.
5. **Point DNS** to the new host, check HTTPS, then cancel Squarespace.
6. Optional: export blog/form data from Squarespace (Settings > Import/Export)
   for your records.

## Notes on the rebuild

- Layout uses the same 24-column fluid grid as Squarespace, so each section is
  positioned exactly like the original on desktop and mobile. The per-section
  grid rules sit in a `<style>` tag at the end of each section.
- Squarespace's animated WebGL backgrounds are replaced by light CSS versions
  (same colors, similar look).
- Instagram/Twitter embed blocks became "Follow us" buttons (the old embeds
  were Squarespace-only).
- One link on /news/new-projects points to `/bioverse`, which does not exist on
  the live site either.
