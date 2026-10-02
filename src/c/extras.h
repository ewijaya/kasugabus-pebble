#ifndef KB_EXTRAS_H
#define KB_EXTRAS_H
#include "preferences.h"
/* Version 2.1 settings kept apart from the full 80-byte preferences record:
 * home button actions, extra home departures, reminders and stop profiles.
 * The phone sends these 28 wire bytes after the 80 preference bytes in one
 * SETTINGS message, so both records validate before either is saved. */
#define KB_EXTRAS_KEY 14 /* banks 14 and 15 */
#define KB_EXTRAS_WIRE_BYTES 28
#define KB_EXTRAS_RECORD_BYTES 40
#define KB_ACTION_NONE 0
#define KB_ACTION_NEXT 1
#define KB_ACTION_PREVIOUS 2
#define KB_ACTION_FAVOURITE 3
#define KB_ACTION_FLIP 4
#define KB_ACTION_NEARBY 5
#define KB_ACTION_ALL 6
#define KB_ACTION_BOARD 7
#define KB_ACTION_WATCHFACE 8
#define KB_ACTION_COUNT 9
#define KB_EXTRAS_PROFILES 1
#define KB_EXTRAS_COMMUTE 2
/* Back on home returns to the app list instead of the watchface. */
#define KB_EXTRAS_BACK_LAUNCHER 4
#define KB_BUTTON_UP 0
#define KB_BUTTON_DOWN 1
#define KB_BUTTON_HOLD_UP 2
#define KB_BUTTON_HOLD_DOWN 3
typedef struct {
  uint8_t buttons[4]; /* up, down, hold up, hold down */
  uint8_t flags;
  uint8_t more;       /* extra departures listed on home, 0..2 */
  uint8_t heads_up;   /* minutes before leave time, 0 = off, 0..30 */
  uint16_t profile_a,profile_b;
  uint8_t profile_a_hour,profile_b_hour;
  uint16_t commute_point,commute_minute;
  uint8_t commute_days; /* bit 0 Sunday .. bit 6 Saturday */
} kb_extras_t;
void kb_extras_default(kb_extras_t *);
/* Rejects unknown actions, out-of-range values, non-zero reserved bytes and,
 * when exists is supplied, unknown boarding points used by enabled features. */
bool kb_extras_parse(kb_extras_t *,const uint8_t *,unsigned,kb_id_exists_fn,void *);
void kb_extras_encode(const kb_extras_t *,uint8_t *);
/* SAVED or EMPTY; an invalid record loads the defaults. Reads keys 14/15. */
bool kb_extras_load(kb_extras_t *,uint32_t *,uint8_t *,kb_pref_read_fn,void *);
bool kb_extras_commit(kb_extras_t *,const kb_extras_t *,uint32_t *,uint8_t *,kb_pref_write_fn,void *);
/* The profile for a local hour: B from its start hour until A's, else A.
 * Returns 0 when profiles are off. */
uint16_t kb_extras_profile_point(const kb_extras_t *,unsigned hour);
#endif
