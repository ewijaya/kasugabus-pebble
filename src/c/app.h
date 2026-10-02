#ifndef KB_APP_H
#define KB_APP_H
#include <pebble.h>
#include "storage.h"
#include "preferences.h"
#include "all_preferences.h"
#include "extras.h"
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
#define KB_SCREEN_TEXT_SIZE 16
#define KB_SCREEN_THEME 17
#define KB_SCREEN_ROUTES 18
#define KB_SCREEN_ROUTE_POINTS 19
#define KB_SCREEN_ALL_REFERENCE 20
#define KB_SCREEN_ALL_POINTS 21
#define KB_SCREEN_ALL_BOARD 22
#define KB_SCREEN_ALL_INFO 23
#define KB_SCREEN_HELP 24
#define KB_SCREEN_BUTTONS 25
#define KB_SCREEN_REMINDER 26
/* Wakeup cookies: one-shot or commute, leave time or earlier heads-up. */
#define KB_WAKE_LEAVE 1
#define KB_WAKE_HEADS_UP 2
#define KB_WAKE_COMMUTE 3
#define KB_WAKE_COMMUTE_HEADS_UP 4
typedef struct  {
  uint16_t id;
  uint32_t metres;
}
kb_near_t;
typedef struct  {
  kb_store_t store;
  kb_preferences_t prefs;
  kb_all_preferences_t all_prefs;
  Window *window;
  Layer *layer;
  GFont japanese;
  unsigned japanese_size;
  uint8_t *cache;
  uint16_t point;
  uint8_t group;
  uint8_t route_operator;
  char route_number[1024];
  bool route_filter;
  int screen,selected,scroll,return_screen,trip_context,detail_origin,all_info_return,all_info_selected;
  kb_override_t override;
  kb_trip_t detail,board_focus;
  bool board_has_focus,board_expired,board_removed;
  bool phone_ready,checking,nearby_waiting,changed,first_use;
  bool all_waiting,all_session;
  int update_status,nearby_status;
  uint32_t request,location_request,location_version,location_stamp,accuracy,last_attempt,last_success;
  uint32_t pref_generation,active_version;
  uint8_t pref_slot;
  uint32_t all_generation,all_request,all_version,all_stamp,all_accuracy;
  uint8_t all_slot;
  int all_status;
  int64_t all_started;
  kb_near_t all_nearby[KB_MAX_POINTS];
  unsigned all_nearby_count;
  uint16_t all_point_focus;
  uint16_t catalogue_seq;
  kb_near_t nearby[KB_MAX_POINTS];
  unsigned nearby_count;
  int64_t location_started,check_started;
  char notice[80];
  kb_extras_t extras;
  uint32_t extras_generation;
  uint8_t extras_slot;
  /* Home browsing: 0 is the soonest bus; reset after 30 idle seconds. */
  int home_offset;
  int64_t home_offset_at;
  /* One-shot reminder and the scheduled commute trip, persisted at key 16. */
  bool reminder_active;
  int64_t reminder_departure,reminder_leave,commute_departure;
  uint16_t reminder_point,commute_point;
  uint8_t reminder_pattern,commute_pattern;
  int reminder_kind;
}
kb_app_t;
extern kb_app_t app;
const kb_dataset_t *app_dataset(void);
kb_query_t app_query(void);
bool app_point_exists(void *,uint16_t);
bool app_save_preferences(const kb_preferences_t *);
void app_check_updates(bool manual);
void app_request_location(void);
void app_request_all_location(void);
void app_clear_all_distances(unsigned);
uint32_t app_all_distance(uint16_t);
bool app_save_all_preferences(const kb_all_preferences_t *);
void app_restore_timetable(void);
void app_dismiss_hint(void);
void app_redraw(void);
void app_send_state(void);
bool app_save_extras(const kb_extras_t *);
bool app_toggle_favourite(uint16_t);
bool app_is_favourite(uint16_t);
int64_t app_leave_time(uint16_t point,int64_t departure);
bool app_set_reminder(const kb_trip_t *);
void app_cancel_reminder(void);
bool app_reminder_matches(const kb_trip_t *);
void app_reschedule_wakeups(void);
void app_load_reminders(void);
void app_show_wakeup(int32_t cookie);
void app_reload_glance(void);
void ui_init(void);
void ui_open(int);
void ui_refresh(void);
void ui_apply_appearance(void);
void ui_remember_all_point(void);
#endif
