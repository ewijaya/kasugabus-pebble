# Selected: 1 — Neon Express

The owner chose this design on 2026-10-01. All ten original concept images
remain in the parent directory, together with the comparison gallery and
their original prompts. They are enlarged previews, not watch-sized assets.

`neon-express-master.png` is the initial transparent white edit made with the
built-in `image_gen` tool from `../01-neon-express.png`. Native launcher review
showed that white disappeared on an unselected white row. The selected final
master is **`neon-express-black-master.png`**, corrected using the same tool.
The actual build resource is
`../../../resources/images/kasugabus-menu-icon.png`: a **25 × 25 PNG** with
transparency, resampled using the already installed ImageMagick:

```sh
magick artifacts/icon-options/selected/neon-express-black-master.png \
  -filter Point -resize '25x25!' resources/images/kasugabus-menu-icon.png
```

The SDK maps the image into its own palette and the launcher tints luminance.
The final installed app was inspected on actual emulator
[selected](../../screenshots/emery_launcher_neon_selected.png) and
[unselected](../../screenshots/emery_launcher_neon_unselected.png) rows. The
owner confirmed the icon is visible on the physical Time 2 v4.38.4. These
checks apply to PBW SHA-256
`4679b90e11353358a85c629ceeb926cfd564556666158899d1d633bdd329f6d6`.
The resource package grew by 136 bytes from the pre-icon acceptance build.

## Initial transparency prompt

```text
Use case: background-extraction and precise-object-edit.
Edit target: the attached selected "Neon Express" KasugaBus launcher icon.
Preserve its identity: centered FRONT VIEW BUS, stepped chamfered top corners, one short wide destination-sign cutout, broad windshield opening, two side mirrors, two square headlights, and two short flat wheels.
Remove ALL black background and black negative-space areas, including windshield and other openings, to genuine alpha transparency. Output ONLY a pure white bus glyph on transparent background. Preserve the square white headlight centers surrounded by transparent square borders.
Finalize as a clean coarse pixel-art silhouette with solid flat white fill, perfectly crisp square pixel steps, no noise, no glow, no shadow, no gray paint, no thin lines, no photorealism. Work to a logical 25 by 25 grid, primary bus frame thickness approximately2gridpixels. Mirrors and wheels chunky and recognizable.
The full bus (including mirrors and wheels) occupies approximately23 of25 logical pixels across and21 of25 pixels high, centered, with about1pixel of transparent margin around its widest points. Use a square canvas. No text, labels or other imagery. This will be resized for a 25x25 Pebble watch launcher resource, so prioritize exact simplified geometry and clean negative space while keeping the chosen design recognizable.
```
