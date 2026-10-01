#ifndef KB_PREFERENCES_H
#define KB_PREFERENCES_H
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#define KB_PREF_BYTES 80
#define KB_PREF_AUTO 1
#define KB_PREF_LOCATION 2
#define KB_PREF_NEARBY_START 4
#define KB_PREF_CONTRAST 8
#define KB_PREF_REDUCED_MOTION 16
#define KB_TEXT_STANDARD 0
#define KB_TEXT_LARGE 1
#define KB_TEXT_EXTRA_LARGE 2
#define KB_THEME_NEON_DARK 0
#define KB_THEME_NEON_LIGHT 1
#define KB_THEME_HIGH_CONTRAST_DARK 2
#define KB_THEME_HIGH_CONTRAST_LIGHT 3
typedef bool (*kb_id_exists_fn)(void *,uint16_t);
typedef struct  {
  uint8_t bytes[KB_PREF_BYTES];
}
kb_preferences_t;
void kb_preferences_default(kb_preferences_t *,uint16_t);
/* Schema 1 upgrades in memory to schema 2 with Large text; schema 2 uses
 * bytes 6/7 for size/theme. Theme always determines KB_PREF_CONTRAST. */
bool kb_preferences_parse(kb_preferences_t *,const uint8_t *,unsigned,kb_id_exists_fn,void *);
uint16_t kb_pref_default(const kb_preferences_t *);
uint16_t kb_pref_favourite(const kb_preferences_t *,unsigned);
unsigned kb_pref_text_size(const kb_preferences_t *);
unsigned kb_pref_theme(const kb_preferences_t *);
/* Validates and normalizes the record before changing appearance. Invalid
 * records or appearance values leave the caller's preferences unchanged. */
bool kb_pref_set_appearance(kb_preferences_t *,unsigned,unsigned);
int kb_pref_walk(const kb_preferences_t *,uint16_t);
unsigned kb_pref_missing(const kb_preferences_t *,kb_id_exists_fn,void *);
typedef int (*kb_pref_read_fn)(void *, uint32_t, void *, size_t);
typedef int (*kb_pref_write_fn)(void *, uint32_t, const void *, size_t);
typedef struct {
  kb_preferences_t preferences;
  uint32_t last_attempt;
  uint32_t last_success;
  uint32_t update_request;
  bool hint_seen;
} kb_control_t;
typedef enum {
  KB_CONTROL_EMPTY=0,
  KB_CONTROL_CURRENT=1,
  KB_CONTROL_LEGACY=2
} kb_control_load_result_t;
/* Reads keys10/11 exactly once each. LEGACY permits one caller-owned migration
 * of the old timestamp/hint keys; EMPTY must not trigger those extra reads.
 * KBW2 stores the durable request; KBW1 loads as CURRENT with request zero.
 * Equal generations prefer KBW2, then KBW1, then KBP1. */
kb_control_load_result_t kb_control_load(kb_control_t *, uint32_t *, uint8_t *, kb_pref_read_fn, void *);
bool kb_control_commit(kb_control_t *, const kb_control_t *, uint32_t *, uint8_t *, kb_pref_write_fn, void *);
/* Legacy KBP1 APIs retained for existing callers and migration fixtures. */
void kb_preferences_load(kb_preferences_t *, uint32_t *, uint8_t *, kb_pref_read_fn, void *);
bool kb_preferences_commit(kb_preferences_t *, const kb_preferences_t *, uint32_t *, uint8_t *, kb_pref_write_fn, void *);
#endif
