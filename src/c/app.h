#ifndef KB_APP_H
#define KB_APP_H
#include <pebble.h>
#include "storage.h"
#include "preferences.h"
#define KB_MAX_POINTS 32
#define KB_SCREEN_HOME 0
#define KB_SCREEN_BOARD 1
#define KB_SCREEN_DETAILS 2
#define KB_SCREEN_MENU 3
#define KB_SCREEN_PICKER 4
#define KB_SCREEN_FAVOURITES 5
#define KB_SCREEN_GROUPS 6
#define KB_SCREEN_POINTS 7
#define KB_SCREEN_NEARBY 8
#define KB_SCREEN_CONTEXT 9
#define KB_SCREEN_SETTINGS 10
#define KB_SCREEN_STATUS 11
#define KB_SCREEN_OVERRIDE 12
#define KB_SCREEN_RESET 13
#define KB_SCREEN_RESTORE 14
#define KB_SCREEN_JAPANESE 15
typedef struct  {
  uint16_t id;
  uint32_t metres;
}
kb_near_t;
typedef struct  {
  kb_store_t store;
  kb_preferences_t prefs;
  Window *window;
  Layer *layer;
  GFont japanese;
  uint8_t *baseline_bytes,*cache;
  uint16_t point;
  uint8_t group;
  int screen,selected,scroll,return_screen,trip_context;
  kb_override_t override;
  kb_trip_t detail,board_focus;
  bool board_has_focus,board_expired,board_removed;
  bool phone_ready,checking,nearby_waiting,changed,first_use;
  int update_status,nearby_status;
  uint32_t request,location_request,location_version,location_stamp,accuracy,last_attempt,last_success;
  uint32_t pref_generation,active_version;
  uint8_t pref_slot;
  uint16_t catalogue_seq;
  kb_near_t nearby[KB_MAX_POINTS];
  unsigned nearby_count;
  int64_t location_started,check_started;
  char notice[80];
}
kb_app_t;
extern kb_app_t app;
const kb_dataset_t *app_dataset(void);
kb_query_t app_query(void);
bool app_point_exists(void *,uint16_t);
bool app_save_preferences(const kb_preferences_t *);
void app_check_updates(bool manual);
void app_request_location(void);
void app_restore_timetable(void);
void app_dismiss_hint(void);
void app_redraw(void);
void app_send_state(void);
void ui_init(void);
void ui_open(int);
void ui_refresh(void);
#endif
