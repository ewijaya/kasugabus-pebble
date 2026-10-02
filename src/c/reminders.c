#include "app.h"
#include <stdio.h>
#include <string.h>
/* Leave-now reminders, the daily commute alarm, watch-side favourites and
 * the launcher App Glance. Wakeups are rebuilt from persisted state after
 * every change, so a cancelled or superseded alarm can never fire. */
#define KB_REMINDER_KEY 16
#define KB_REMINDER_BYTES 24
static uint16_t u16(const uint8_t *b) {
  return (uint16_t)(b[0]|(b[1]<<8));
}
static int32_t i32(const uint8_t *b) {
  return (int32_t)((uint32_t)b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24));
}
static void put16(uint8_t *b,uint16_t v) {
  b[0]=(uint8_t)v;b[1]=(uint8_t)(v>>8);
}
static void put32(uint8_t *b,int32_t v) {
  for(unsigned i=0;i<4;i++)b[i]=(uint8_t)((uint32_t)v>>(8*i));
}
static void save_reminders(void) {
  uint8_t b[KB_REMINDER_BYTES]={0};
  memcpy(b,"KBR1",4);
  if(app.reminder_active) {
    put32(b+4,(int32_t)app.reminder_departure);put32(b+8,(int32_t)app.reminder_leave);
    put16(b+12,app.reminder_point);b[14]=app.reminder_pattern;b[15]=1;
  }
  if(app.commute_departure) {
    put32(b+16,(int32_t)app.commute_departure);put16(b+20,app.commute_point);b[22]=app.commute_pattern;
  }
  if(persist_write_data(KB_REMINDER_KEY,b,sizeof(b))!=(int)sizeof(b))APP_LOG(APP_LOG_LEVEL_WARNING,"Reminder save failed");
}
void app_load_reminders(void) {
  uint8_t b[KB_REMINDER_BYTES]={0};
  if(persist_read_data(KB_REMINDER_KEY,b,sizeof(b))!=(int)sizeof(b)||memcmp(b,"KBR1",4))return;
  app.reminder_active=b[15]==1;
  if(app.reminder_active) {
    app.reminder_departure=i32(b+4);app.reminder_leave=i32(b+8);
    app.reminder_point=u16(b+12);app.reminder_pattern=b[14];
  }
  app.commute_departure=i32(b+16);app.commute_point=u16(b+20);app.commute_pattern=b[22];
}
int64_t app_leave_time(uint16_t point,int64_t departure) {
  int walk=kb_pref_walk(&app.prefs,point);
  return departure-((int64_t)(walk>0?walk:0)+app.prefs.bytes[4])*60;
}
static void schedule(int64_t when,int32_t cookie) {
  if(when<=time(NULL)+5)return;
  WakeupId id=wakeup_schedule((time_t)when,cookie,true);
  /* Another app may hold the same minute; an earlier buzz is the safe side. */
  if(id==E_RANGE)id=wakeup_schedule((time_t)(when-60),cookie,true);
  if(id<0)APP_LOG(APP_LOG_LEVEL_WARNING,"Wakeup %ld not scheduled: %ld",(long)cookie,(long)id);
}
/* First bus at or after the commute time on the next selected service day
 * whose leave time is still ahead. */
static bool next_commute(kb_trip_t *out) {
  const kb_extras_t *e=&app.extras;
  if(!(e->flags&KB_EXTRAS_COMMUTE)||!app_point_exists(NULL,e->commute_point))return false;
  int64_t now=time(NULL);
  int32_t today=kb_jst_day(now);
  for(int32_t day=today;day<today+KB_LOOKAHEAD_DAYS+1;day++) {
    if(!(e->commute_days&(1u<<kb_weekday(day))))continue;
    kb_query_t q=app_query();
    q.boarding_point_id=(uint8_t)e->commute_point;q.destination_group_id=0;
    q.now_utc=kb_service_epoch(day,e->commute_minute);
    kb_query_state_t state;
    kb_trip_t trip;
    if(kb_query_next(&q,NULL,&trip,&state)!=KB_QUERY_FOUND||trip.service_day!=day)continue;
    if(app_leave_time(trip.boarding_point_id,trip.departure_utc)<=now+30)continue;
    *out=trip;
    return true;
  }
  return false;
}
void app_reschedule_wakeups(void) {
  wakeup_cancel_all();
  int64_t now=time(NULL);
  if(app.reminder_active&&app.reminder_departure<=now)app.reminder_active=false;
  unsigned heads=app.extras.heads_up;
  if(app.reminder_active) {
    schedule(app.reminder_leave,KB_WAKE_LEAVE);
    if(heads)schedule(app.reminder_leave-(int64_t)heads*60,KB_WAKE_HEADS_UP);
  }
  kb_trip_t trip;
  /* Keep a commute trip whose leave time just fired until its departure so
   * the wakeup screen can still describe it. */
  if(app.commute_departure&&app.commute_departure>now&&app.reminder_kind>=KB_WAKE_COMMUTE) {
    /* After the heads-up, its leave-time buzz is still due. */
    schedule(app_leave_time(app.commute_point,app.commute_departure),KB_WAKE_COMMUTE);
  }
  else {
    app.commute_departure=0;
    if(next_commute(&trip)) {
      app.commute_departure=trip.departure_utc;app.commute_point=trip.boarding_point_id;app.commute_pattern=trip.pattern_id;
      int64_t leave=app_leave_time(trip.boarding_point_id,trip.departure_utc);
      schedule(leave,KB_WAKE_COMMUTE);
      if(heads)schedule(leave-(int64_t)heads*60,KB_WAKE_COMMUTE_HEADS_UP);
    }
  }
  save_reminders();
}
bool app_reminder_matches(const kb_trip_t *t) {
  return app.reminder_active&&t->departure_utc==app.reminder_departure&&
    t->boarding_point_id==app.reminder_point&&t->pattern_id==app.reminder_pattern;
}
bool app_set_reminder(const kb_trip_t *t) {
  int64_t leave=app_leave_time(t->boarding_point_id,t->departure_utc);
  if(leave<=time(NULL)+30)return false;
  app.reminder_active=true;
  app.reminder_departure=t->departure_utc;app.reminder_leave=leave;
  app.reminder_point=t->boarding_point_id;app.reminder_pattern=t->pattern_id;
  app_reschedule_wakeups();
  return true;
}
void app_cancel_reminder(void) {
  app.reminder_active=false;
  app_reschedule_wakeups();
}
void app_show_wakeup(int32_t cookie) {
  if(cookie<KB_WAKE_LEAVE||cookie>KB_WAKE_COMMUTE_HEADS_UP)return;
  app.reminder_kind=(int)cookie;
  uint16_t point=cookie>=KB_WAKE_COMMUTE?app.commute_point:app.reminder_point;
  if(app_point_exists(NULL,point))app.point=point;
  if(!quiet_time_is_active()) {
    if(cookie==KB_WAKE_LEAVE||cookie==KB_WAKE_COMMUTE)vibes_double_pulse();
    else vibes_short_pulse();
  }
  ui_open(KB_SCREEN_REMINDER);
  /* The commute alarm moves on to its next occurrence; a fired one-shot
   * stays visible in details until its departure passes. */
  app_reschedule_wakeups();
}
bool app_is_favourite(uint16_t id) {
  for(unsigned i=0;i<app.prefs.bytes[5];i++)if(kb_pref_favourite(&app.prefs,i)==id)return true;
  return false;
}
bool app_toggle_favourite(uint16_t id) {
  if(!id||!app_point_exists(NULL,id))return false;
  kb_preferences_t p=app.prefs;
  unsigned n=p.bytes[5],i=0;
  while(i<n&&kb_pref_favourite(&p,i)!=id)i++;
  if(i<n) {
    memmove(p.bytes+8+2*i,p.bytes+10+2*i,2*(n-1-i));
    p.bytes[8+2*(n-1)]=0;p.bytes[9+2*(n-1)]=0;p.bytes[5]=(uint8_t)(n-1);
  }
  else {
    if(n>=12)return false;
    put16(p.bytes+8+2*n,id);p.bytes[5]=(uint8_t)(n+1);
  }
  if(!app_save_preferences(&p))return false;
  app_send_state();
  return true;
}
/* Launcher glance: the next three buses at the home stop, each expiring at
 * its departure minute so the launcher advances without the app running. */
static void glance(AppGlanceReloadSession *session,size_t limit,void *ctx) {
  (void)ctx;
  kb_query_t q=app_query();
  kb_trip_t trip,previous;
  kb_query_state_t state;
  bool has_previous=false;
  for(size_t i=0;i<limit&&i<3;i++) {
    if(kb_query_next(&q,has_previous?&previous:NULL,&trip,&state)!=KB_QUERY_FOUND)break;
    previous=trip;has_previous=true;
    const kb_dataset_t *d=kb_trip_dataset(&q,&trip);
    kb_pattern_t pattern;
    kb_boarding_point_t point;
    if(!d||!kb_pattern_get(d,trip.pattern_id,&pattern)||!kb_boarding_point_get(d,trip.boarding_point_id,&point))break;
    int64_t sec=(trip.departure_utc+32400)%86400;
    char text[120];
    snprintf(text,sizeof(text),"%.12s %02d:%02d %.60s",pattern.route,(int)(sec/3600),(int)(sec/60%60),point.short_name);
    AppGlanceSlice slice={
      .layout={.icon=APP_GLANCE_SLICE_DEFAULT_ICON,.subtitle_template_string=text},
      .expiration_time=(time_t)(trip.departure_utc+59)
    };
    if(app_glance_add_slice(session,slice)!=APP_GLANCE_RESULT_SUCCESS)break;
  }
}
void app_reload_glance(void) {
  if(app_point_exists(NULL,app.point))app_glance_reload(glance,NULL);
}
