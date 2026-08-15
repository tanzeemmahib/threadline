# THREADLINE art direction

On August 9, Higgsfield generated three visual-development frames for the initial redesign. The production site recreates those compositions with semantic React, CSS, and SVG; it does not display those three generated frames.

- Opening: monumental serif type, warm black stock, paper grain, tiny metadata, one oxidized-brass thread.
- Workbench: flat source documents, a typeset evidence matrix, thin rules, and a restrained disposition column.
- Safety: deep negative space, monumental abstention language, a real timeline gap, and a vertical audit rail.

The typography system combines Cormorant Garamond, Manrope, and IBM Plex Mono. Graphite, ivory, brass, rust, and sparing sage replace the prior cyan/blue system. Motion is limited to thread drawing, document alignment, masks, and restrained opacity/position changes, with a reduced-motion alternative.

The local reference frames live in `docs/art-direction/` and are excluded from the frontend public asset tree.

## August 11 cinematic atmosphere pass

The final cinematic pass used the authenticated Higgsfield CLI on a Plus plan for one new GPT Image 2 still and one Seedance 2.0 image-to-video job. The asset is deliberately atmospheric, not an interface replacement: it contains no readable text, faces or people, or fake UI. THREADLINE's headline, record fragments, evidence, controls, navigation, and workbench remain real semantic HTML/CSS/SVG.

The still job (`0fd7b390-90d3-4113-ae32-78a4ad36eaf2`) produced the 2688 x 1520 art-direction source at `docs/art-direction/higgsfield-hero-atmosphere-20260811.png`. Its exact submitted prompt was:

> Text-free cinematic background plate for a premium interactive documentary about fragmented identity records. Warm near-black archival space, matte charcoal-black table receding into darkness, abstract completely unprinted paper record fragments at different depths primarily on the right half and lower edge, subtle torn paper edges, faint non-readable map contour lines and registration marks, a single hair-thin oxidized brass physical fiber resting across selected paper edges, soft volumetric side light from upper right, restrained dust in the light, tactile physical imperfection, contemporary editorial composition, museum archive atmosphere, humanitarian field-record seriousness, center-left and upper-left kept dark and quiet for large real HTML typography, deep but stable cinematic lens depth, widescreen 16:9. Absolutely no people, faces, bodies, injuries, disaster imagery, fire, destruction, logos, letters, numbers, handwriting, type, readable text, fake interface, holograms, neon, blue or cyan glow, science fiction, cyberpunk, digital particles.

The video job (`5323d49c-fc0b-4608-884f-e40dad0e0afa`) produced a silent 1920 x 1080 source lasting 8.041667 seconds. Its exact submitted prompt was:

> Animate this exact text-free archival background as a living photograph. Extremely slow eight-second dolly push forward, no more than a subtle two-percent apparent scale change, with near-imperceptible lateral drift and stable framing. Papers remain anchored; only two or three paper edge corners shift microscopically. Very subtle multi-plane parallax among the right-side paper layers. Sparse physical dust moves slowly through the warm side light and the light intensity breathes almost imperceptibly. The thin brass fiber remains physical, matte, and non-glowing. Preserve the dark quiet left half for real HTML typography. No new objects, no people, no faces, no bodies, no text, no letters, no numbers, no logos, no interface, no disaster imagery, no dramatic action, no camera shake, no rotation, no fast zoom, no cuts, no morphing, no warping, no glowing effects. Keep the first and final framing closely aligned for loop-friendly silent background playback.

The 8,609,831-byte source MP4 is not shipped. The client receives a silent 1280 x 720 VP8 WebM (`frontend/public/media/threadline/hero-archive-loop.webm`, 278,404 bytes, approximately eight seconds) plus a 1920 x 1080 static WebP poster (`frontend/public/media/threadline/hero-archive-poster.webp`, 79,134 bytes). Mobile, `prefers-reduced-motion`, unsupported-video, and video-failure states use the static poster, so neither the generated motion nor successful video playback is required for the landing experience or product workflow.

| Asset | SHA-256 |
|---|---|
| `docs/art-direction/higgsfield-hero-atmosphere-20260811.png` | `826efd60648c673bc0b8f7fdb9fdcaa87a2ecadfcfd72dab4224f0d64fc552c8` |
| Unshipped Seedance source MP4 | `80865eb8acf4dcb7f3498d8f498b34771a90395c696238478064b0efc9d5f731` |
| `frontend/public/media/threadline/hero-archive-loop.webm` | `6e54c787086dd3d3b710235acae3383e030cb520398c59daa8b99f141bf9dd77` |
| `frontend/public/media/threadline/hero-archive-poster.webp` | `584085eb1454568a1d29139bec760c7e19053e9ccd8b00711c4104a542864581` |

The final production build, route smoke, six-width responsive matrix, reduced-motion path, forced-video-failure fallback, guided-workspace keyboard flow, and isolated HTTP integration smoke passed on August 11. Exact results remain in `docs/final-validation.md`; generation provenance alone is still not an efficacy or production-deployment claim.

## Implemented-product evidence

The following are browser captures of the native implementation, not Higgsfield outputs:

- `docs/product-screenshots/cinematic-landing-desktop.png`
- `docs/product-screenshots/cinematic-landing-mobile.png`
- `docs/product-screenshots/cinematic-workbench-transition.png`
- `docs/product-screenshots/cinematic-live-workspace.png`

They document the shipped React/CSS/SVG result at desktop and mobile widths. The separate `docs/art-direction/higgsfield-*.png` files are concept references only.
