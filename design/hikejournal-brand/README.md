# HikeJournal artwork

The November 10, 2026 Android alignment uses the corrected Theresa asset bundle
`HikeJournal_Theresa_Fixed` and its `Hike_Journal-Interface.ai` source. The
`brand-guide/` sheets and corrected logo exports are retained here for reference.
Some supplied filenames still begin `Hiking_Journal`; the new lettering itself
reads **Hike Journal**. Legacy exports remain for the existing Web assets.

## Android conventions

- Every standalone page mark uses `Hiking_Journal-Color-Icon-Logo.svg`: fern
  outline, forest fill, and white interior bars. Do not tint it solid white.
- The app wordmark is the same supplied mark beside **HikeJournal** on one
  line. The old stacked “Hiking Journal” raster is no longer bundled at runtime.
- The Illustrator metadata explicitly names **Quicksand-Light** and the
  Quicksand variable-font file. It does not identify every outlined or
  rasterized typeface in the screen references. Android uses real static
  instances at weights 400, 500, 600, and 700, created from the Google Fonts
  Quicksand variable font. Its license is in `fonts/Quicksand-OFL.txt`.
  The packaged derivative's primary family name is **HikeJournal Rounded**,
  respecting Quicksand's reserved font name; glyphs and metrics are unchanged.
  Optional vendor/designer URL name records (IDs 11/12) are removed from the
  packaged instances because their HTTP metadata triggers the release artifact
  scanner. Author, copyright, and license records are preserved.
  The editorial Cormorant Garamond family was retained from the existing app,
  not positively identified from the Illustrator metadata. It has real 400/600/700
  instances; assigning several weights to its light default does not work.
  Both font licenses are retained in `fonts/` and bundled in Android's
  `assets/licenses/` directory.
- Navigation drawables preserve the supplied SVG path coordinates, colors,
  and fill rules as Android vectors. Do not trace or rescale raster icons.
- The header texture comes from `icons/svg/HJ-Green-Pattern.svg`, cropped to
  the first 780 × 440 source units and rendered at 1560 × 880. Keep the source
  artwork's 5% contour opacity without a second opacity/gradient overlay.
- Forest `#324223`, fern `#AECE76`, orange `#D17D42`, and parchment `#F5F1E7`
  remain the core palette. Featured dates and the Hikes add action share the
  orange token. Header lettering is white, with bold Quicksand titles.

The large Illustrator source is kept in the supplied local bundle; it is not
required at runtime. Android visual evidence uses local test photos and does
not connect to or modify a journal account.
