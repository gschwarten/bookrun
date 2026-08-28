# Lovable Product Feedback: OG Meta Tags & Link Previews on SPAs

## The Problem

When you share a Lovable-hosted page URL (e.g. `geoff.lovable.app/bookrun`) on iMessage, Slack, Twitter, LinkedIn, or Facebook, the link preview is either blank or shows generic/incorrect metadata. This is because social media crawlers don't execute JavaScript — they read the raw HTML. Since Lovable is a React SPA, the HTML served for any route is the same shell with no page-specific OG tags.

## Why It Matters

- **Sharing is how apps grow.** If I text a friend "check out this app I made" and the link preview is blank, it looks broken. They're less likely to tap it.
- **For businesses it's worse.** If you're running ads or sharing landing pages (e.g. a healthcare startup linking to `akidorecovery.com/intake`), a missing or wrong preview kills trust and conversion.
- **It undermines the whole Lovable value prop.** Lovable makes it easy to build and ship. But if the thing you ship can't be shared properly, there's a gap in the last mile.

## What I Tried

1. **Setting OG tags via Lovable's page settings** — Didn't work. The tags either weren't injected server-side or weren't picked up by crawlers.
2. **Adding meta tags directly in the page component** — React renders these client-side, so crawlers never see them.
3. **Prerender.io** — Would work, but requires control over the server/CDN to route bot traffic. Lovable users don't have that access.

## What Would Fix It

Lovable needs to handle OG tags **server-side** for each route. When a crawler (or any request) hits a Lovable URL, the server should inject the correct `<meta>` tags into the HTML `<head>` before sending the response. This is a solved problem — here's how others do it:

- **Next.js / Vercel**: `generateMetadata()` or the `<Head>` component renders meta tags server-side per route.
- **Netlify**: Supports `_headers` and `_redirects` files, plus prerendering for bots.
- **Cloudflare Workers**: Can intercept requests and inject meta tags for crawler user-agents.

### Suggested Implementation

The simplest version for Lovable:

1. Let users define per-page metadata in the Lovable page settings (title, description, OG image).
2. On the server, when serving any route, read the page config and inject the corresponding `<meta>` tags into the HTML shell before sending it.
3. This doesn't require full SSR — just a lightweight server-side template injection for the `<head>` section.

### Bonus: OG Image Generation

An even better feature would be auto-generating OG images from page content (like Vercel's `@vercel/og`). But just getting basic title/description tags working server-side would be a huge win.

## My Workaround

I deployed the backend separately on Render (which serves real HTML with proper OG tags) and use that URL for sharing. The Lovable page exists at `geoff.lovable.app/bookrun` but I can't share it because the link preview is broken. This defeats the purpose of having it on my Lovable site.

## Summary

Lovable is great for building. But if I can't share what I build with a proper link preview, I end up hosting elsewhere anyway. Server-side OG tag injection per route would close this gap and is table stakes for any platform where users ship public-facing pages.
