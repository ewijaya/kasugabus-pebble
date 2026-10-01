# KasugaBus launcher icon: installed SDK inspection

Inspected on 2026-10-01 using Pebble Tool **5.0.40**, active SDK **4.33.1**,
on macOS arm64. KasugaBus targets Emery only. This inspection read installed
files and the firmware ELF locally; it did not attach to or operate an emulator,
change resources/source, or build an icon candidate.

The inspection below established the constraints before integration. The
owner subsequently selected **1 — Neon Express**. The final 25 × 25 transparent
black glyph is integrated in PBW SHA-256
`4679b90e11353358a85c629ceeb926cfd564556666158899d1d633bdd329f6d6`.
Actual [selected](screenshots/emery_launcher_neon_selected.png) and
[unselected](screenshots/emery_launcher_neon_unselected.png) emulator captures
were inspected. The owner also confirmed the bus icon is visible and
highlighted on Time 2 v4.38.4; remote captures returned the watchface, so no
physical launcher screenshot is claimed. See [installation evidence](physical-neon-installation.json).

## Actual launcher size: 25 × 25 pixels

The default launcher calls `prv_create_glance_icon` at **0x000c5eb2**. After
loading the icon as a KinoReel, it reads the image dimensions and checks both
width and height against:

- **25 pixels** for current binaries;
- **28 pixels** only when `use_legacy_28x28_icon_size_limit` is true.

An oversized reel is destroyed and the caller uses a fallback icon. This is
not an automatic resize. Use an actual **25 × 25 PNG canvas**, rather than a
25-pixel drawing inside a larger transparent canvas.

`launcher_app_glance_generic_create` at **0x0002620c** compares the app's binary
SDK compatibility version with `app_glance_min_supported_sdk_version` at
**0x00147f4c**, whose bytes are `{5, 80}`. A strictly older version enables the
legacy 28-pixel limit.

The installed Emery `pebble_process_info.h` defines the produced binary's SDK
version as `{0x5, 0x6a}` = **5.106**, so this project uses the **25-pixel** path.
The package's `sdkVersion: "3"` does not make its compiled binary older than
5.80. `build/emery/appinfo.auto.c` uses these installed compatibility macros.

### Correction of the earlier 32-pixel observation

`app_menu_data_source_get_node_icon` at **0x0001fc24** loads a bitmap and clips
its bounds against `icon_clip` at **0x001478cc**, a GRect `{0, 0, 32, 32}`.
The process header also describes `icon_resource_id` as a 32 × 32 icon.
Those observations do **not** establish the default launcher acceptance limit:
the later generic-glance validation above rejects an image larger than 25
pixels for this SDK build. The initial 32-pixel guidance was corrected after
tracing that actual default-launcher path.

## Launcher color and transparency

Emery is a color platform. Bitmap resources support 64 opaque RGB colors:
each channel is reduced to **0, 85, 170, or 255**. Alpha has the same four
levels, corresponding to transparent, approximately 33%, approximately 66%,
and opaque. The SDK defaults to nearest-color reduction.

However, the default launcher **does not faithfully preserve icon hue**:

- `launcher_app_glance_structured_draw_icon` at **0x00026e64** creates a
  luminance-tint lookup using opaque black `GColor` **0xc0**, then draws with
  processors via `kino_reel_draw_processed`.
- `prv_strucutred_glance_icon_bitmap_processor_pre_func` at **0x000c61c4**
  (the misspelling is the actual symbol name) sets the bitmap compositing mode
  to **GCompOpTintLuminance**, enum value **7**, and applies the configured tint.
- `prv_structured_glance_icon_draw_command_processor_process_command` at
  **0x000c61fe** also remaps fill and stroke colors through
  `gcolor_perform_lookup_using_color_luminance_and_multiply_alpha` at
  **0x0002d934**.

Design the launcher candidates as clear monochrome shapes with transparency.
Colorful versions can be concept art, but should not be presented as faithful
launcher renderings. Fine strokes, small lettering, and smooth gradients need
care at 25 pixels. The runtime checks above establish selected/unselected
appearance for this candidate. An initial white glyph disappeared on the
unselected white row and was replaced before physical installation.

## Resource declaration and build behavior

A viable entry under `package.json` → `pebble.resources.media` is:

```json
{
  "type": "bitmap",
  "name": "MENU_ICON",
  "file": "images/kasugabus-menu-icon.png",
  "menuIcon": true,
  "memoryFormat": "Smallest",
  "storageFormat": "png"
}
```

The file is relative to the project's `resources/` directory. This declaration
is now in `package.json`; generated app information uses `RESOURCE_ID_MENU_ICON`.

`generate_appinfo.py` maps the single marked resource to
`RESOURCE_ID_MENU_ICON`; marking more than one resource raises an error. The
resource schema accepts `bitmap`, `menuIcon`, PNG/PBI storage, and palette
memory formats. `BitmapResourceGenerator` defaults to `Smallest` memory format;
on Emery it defaults to PNG storage because the platform has at least 32 KiB
of application memory. Palette formats preserve transparency. Non-palettized
`1Bit` should not be chosen for an icon that needs alpha transparency.

The inspected build generators do not enforce the default launcher's 25-pixel
limit. Successful resource conversion/build alone would therefore not prove
that a custom icon is used in the launcher.

## Exact installed evidence paths

SDK root:

```text
/Users/e_wijaya_ap/Library/Application Support/Pebble SDK/SDKs/4.33.1
```

Paths relative to that root:

| Evidence | Path / location |
| --- | --- |
| Actual compiled launcher behavior and symbols above | `sdk-core/pebble/emery/qemu/emery_sdk_debug.elf` |
| Read-only local debugger | `toolchain/arm-none-eabi/bin/arm-none-eabi-gdb` |
| Binary compatibility version 5.106 | `sdk-core/pebble/emery/include/pebble_process_info.h`, lines 176–177 |
| Broader 32-pixel header comment | Same header, lines 224 and 262 |
| RGB/alpha channel format | `sdk-core/pebble/emery/include/pebble.h`, lines 3522–3530 |
| Palette levels and nearest conversion | `sdk-core/pebble/common/tools/pebble_image_routines.py`, lines 19–46 |
| Resource schema | `sdk-core/pebble/common/tools/schemas/resource_types.json`, lines 5–24 |
| Menu-icon ID selection and duplicate rejection | `sdk-core/pebble/common/tools/generate_appinfo.py`, lines 89–101 |
| Memory/storage format choice and PNG/PBI conversion | `sdk-core/pebble/common/waftools/resources/resource_map/resource_generator_bitmap.py`, lines 25–27, 81–96, 150–182 |
| Emery color/platform capabilities | `sdk-core/pebble/common/tools/pebble_sdk_platform.py`, lines 133–174 |

The ELF's debug information identifies the default launcher source as
`../src/fw/apps/system/launcher/default/app_glance_generic.c` and its structured
renderer as the neighboring launcher implementation. Those firmware source
files are not claimed to be installed locally; the conclusions use the
installed ELF's symbols, constants, types and instructions.

## Reproducible read-only commands

These commands load the local ELF only. They contain **no `target remote`**, so
they do not connect to a running emulator or watch.

```sh
pebble --version
ICON_SDK_ROOT='/Users/e_wijaya_ap/Library/Application Support/Pebble SDK/SDKs/4.33.1'
ICON_GDB="$ICON_SDK_ROOT/toolchain/arm-none-eabi/bin/arm-none-eabi-gdb"
ICON_ELF="$ICON_SDK_ROOT/sdk-core/pebble/emery/qemu/emery_sdk_debug.elf"

"$ICON_GDB" -q -batch "$ICON_ELF" \
  -ex 'disassemble prv_create_glance_icon' \
  -ex 'disassemble launcher_app_glance_generic_create' \
  -ex 'info symbol *((unsigned int *)0x262a0)' \
  -ex 'x/2ub *((unsigned int *)0x262a0)' \
  -ex 'disassemble app_menu_data_source_get_node_icon' \
  -ex 'info symbol *((unsigned int *)0x1fc54)' \
  -ex 'x/4hd *((unsigned int *)0x1fc54)'

"$ICON_GDB" -q -batch "$ICON_ELF" \
  -ex 'ptype GCompOp' \
  -ex 'disassemble launcher_app_glance_structured_draw_icon' \
  -ex 'disassemble prv_strucutred_glance_icon_bitmap_processor_pre_func' \
  -ex 'disassemble prv_structured_glance_icon_draw_command_processor_process_command' \
  -ex 'disassemble gcolor_perform_lookup_using_color_luminance_and_multiply_alpha'

rg -n 'PROCESS_INFO_CURRENT_SDK_VERSION|icon_resource_id' \
  "$ICON_SDK_ROOT/sdk-core/pebble/emery/include/pebble_process_info.h"
rg -n 'menuIcon|icon_resource_id' \
  "$ICON_SDK_ROOT/sdk-core/pebble/common/tools/generate_appinfo.py"
rg -n 'memory_format|storage_format|crop=False|is_color' \
  "$ICON_SDK_ROOT/sdk-core/pebble/common/waftools/resources/resource_map/resource_generator_bitmap.py"
```

Addresses are specific to this installed firmware ELF and should be re-derived
if the SDK firmware changes. Future icon edits still require build validation
and actual launcher inspection, as performed for this candidate.
