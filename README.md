# Breaking Walls website

Static rebuild of www.breakingwalls.co, migrated off Squarespace (October 2026).
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
```

`_capture/` (raw Squarespace export, ~800 MB) and `_work/` are kept locally but
not in git. You only need them to re-run `tools/build.py`. From now on, edit the
files in `site/` directly.

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
2. **French version.** The live site used Squarespace's built-in Weglot
   switcher, and only headings/menus were translated. That integration goes
   away with Squarespace, so the rebuild is English only.
3. **Domain / DNS.** Find out where breakingwalls.co is registered (Squarespace
   Domains or elsewhere). If it is at Squarespace, transfer it out *before*
   cancelling, or the site and any email on that domain can break.
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
