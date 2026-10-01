#ifndef KB_ALL_PREFERENCES_H
#define KB_ALL_PREFERENCES_H
#include "preferences.h"
#define KB_ALL_MAX_POINTS 32
#define KB_ALL_REFERENCE_CURRENT 0
#define KB_ALL_REFERENCE_HOME 1
#define KB_ALL_REFERENCE_MANUAL 2
#define KB_ALL_PREFERENCES_KEY 12
#define KB_ALL_PREFERENCES_RECORD_BYTES 80
typedef struct {
  uint16_t ids[KB_ALL_MAX_POINTS];
  uint8_t count;
  uint8_t reference;
} kb_all_preferences_t;
typedef enum { KB_ALL_EMPTY=0,KB_ALL_SAVED=1,KB_ALL_INVALID=2 } kb_all_load_result_t;
void kb_all_preferences_default(kb_all_preferences_t *);
/* SAVED includes a deliberately empty selection. INVALID means a record or
 * read failure existed but neither bank validated; only EMPTY may seed
 * favourites. Reads keys 12/13 exactly once each; never writes or locates. */
kb_all_load_result_t kb_all_preferences_load(kb_all_preferences_t *,uint32_t *,uint8_t *,kb_pref_read_fn,void *);
bool kb_all_preferences_commit(kb_all_preferences_t *,const kb_all_preferences_t *,uint32_t *,uint8_t *,kb_pref_write_fn,void *);
#endif
