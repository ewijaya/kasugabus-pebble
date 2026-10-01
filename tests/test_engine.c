/* All schedule values below belong to explicitly named synthetic fixtures. */
#include "../src/c/engine.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { kb_dataset_t baseline,future,unknown,no_service; uint8_t *buffers[4]; bool future_enabled; bool use_unknown; bool use_no_service; int32_t effective; unsigned resolve_calls,future_calls; int32_t latest_day; } fixtures_t;
static const kb_dataset_t *resolve(void *ctx,int32_t day) {
  fixtures_t *f=(fixtures_t *)ctx;
  f->resolve_calls++;
  if(day>f->latest_day)f->latest_day=day;
  if(f->use_unknown) return &f->unknown;
  if(f->use_no_service) return &f->no_service;
  if(f->future_enabled&&day>=f->effective)f->future_calls++;
  return f->future_enabled&&day>=f->effective?&f->future:&f->baseline;
}
static void load(const char *path,kb_dataset_t *d,uint8_t **storage) {
  FILE *fp=fopen(path,"rb"); assert(fp); assert(fseek(fp,0,SEEK_END)==0); long length=ftell(fp); assert(length>0); rewind(fp);
  *storage=(uint8_t *)malloc((size_t)length); assert(*storage); assert(fread(*storage,1,(size_t)length,fp)==(size_t)length); fclose(fp);
  assert(kb_dataset_open(d,*storage,(size_t)length)==KB_OK);
}
static int32_t date_day(int y,unsigned m,unsigned d) { int32_t result; assert(kb_date_from_ymd(y,m,d,&result)); return result; }
static int64_t at(int y,unsigned m,unsigned d,unsigned h,unsigned min,unsigned sec) { return kb_service_epoch(date_day(y,m,d),(uint16_t)(h*60+min))+sec; }
static kb_trip_t next(kb_query_t *q,kb_query_state_t *s) { kb_trip_t t; assert(kb_query_next(q,NULL,&t,s)==KB_QUERY_FOUND); return t; }
static void test_dates(void) {
  int32_t day; assert(!kb_date_from_ymd(2100,2,29,&day)); assert(!kb_date_from_ymd(2026,13,1,&day)); assert(!kb_date_from_ymd(2026,4,31,&day));
  assert(kb_date_from_ymd(2000,2,29,&day)); assert(kb_weekday(date_day(1970,1,1))==4);
  assert(kb_jst_day(-32401)==-1); assert(kb_jst_day(-32400)==0);
  assert(kb_jst_day(at(2026,10,1,23,59,59))==date_day(2026,10,1));
  assert(kb_jst_day(at(2026,10,2,0,0,0))==date_day(2026,10,2));
  for(day=date_day(1900,1,1);day<=date_day(2200,12,31);day++) { int y; unsigned m,d; int32_t again; kb_date_to_ymd(day,&y,&m,&d); assert(kb_date_from_ymd(y,m,d,&again)); assert(day==again); }
}
static void test_minutes(void) {
  uint32_t min=999; int64_t dep=at(2026,10,1,10,33,0);
  assert(kb_countdown(dep-59,dep,&min)==KB_COUNTDOWN_MINUTES&&min==1);
  assert(kb_countdown(dep-60,dep,&min)==KB_COUNTDOWN_MINUTES&&min==1);
  assert(kb_countdown(dep-61,dep,&min)==KB_COUNTDOWN_MINUTES&&min==2);
  assert(kb_countdown(dep,dep,&min)==KB_COUNTDOWN_DUE&&min==0);
  assert(kb_countdown(dep+59,dep,&min)==KB_COUNTDOWN_DUE);
  assert(kb_countdown(dep+60,dep,&min)==KB_COUNTDOWN_EXPIRED);
}
static void test_crc(void) {
  static const uint8_t vector[]="123456789";
  assert(kb_crc32(NULL,0)==0);
  assert(kb_crc32(vector,sizeof(vector)-1)==UINT32_C(0xcbf43926));
}
static void test_schedule(fixtures_t *f) {
  kb_query_t q; kb_query_state_t s; kb_trip_t t,previous; int64_t leave;
  memset(&q,0,sizeof(q)); q.resolve=resolve; q.context=f; q.boarding_point_id=1; q.override.jst_day=KB_DATE_UNKNOWN; q.override.day_type=KB_DAY_UNKNOWN;
  q.now_utc=at(2026,10,1,10,32,1); t=next(&q,&s); assert(t.minute==633&&t.day_type==KB_DAY_WEEKDAY&&!s.today_no_service);
  q.now_utc=at(2026,10,1,10,33,59); t=next(&q,&s); assert(t.minute==633);
  previous=t; assert(kb_leave_by(&t,KB_CONTEXT_SAVED_ORIGIN,5,2,&leave)); assert(leave==at(2026,10,1,10,26,0));
  assert(!kb_leave_by(&t,KB_CONTEXT_NEARBY,5,2,&leave)); assert(!kb_leave_by(&t,KB_CONTEXT_AT_STOP,5,2,&leave));
  assert(kb_upcoming_at(&q,1,&t,&s)==KB_QUERY_FOUND&&t.minute==634); assert(!kb_trip_same_identity(&previous,&t));
  q.now_utc=at(2026,10,1,10,34,0); t=next(&q,&s); assert(t.minute==634); assert(kb_query_next(&q,&previous,&t,&s)==KB_QUERY_FOUND&&t.minute==634);
  q.destination_group_id=2; t=next(&q,&s); assert(t.minute==1505&&t.pattern_id==1); q.destination_group_id=0;
  q.now_utc=at(2026,10,3,0,0,0); t=next(&q,&s); assert(t.service_day==date_day(2026,10,2)&&t.minute==1505);
  q.now_utc=at(2026,10,3,1,5,59); t=next(&q,&s); assert(t.minute==1505);
  q.now_utc=at(2026,10,3,1,6,0); t=next(&q,&s); assert(t.service_day==date_day(2026,10,3)&&t.day_type==KB_DAY_SATURDAY&&t.minute==700);
  q.now_utc=at(2026,10,4,0,0,0); t=next(&q,&s); assert(t.day_type==KB_DAY_SUNDAY_HOLIDAY&&t.minute==800);
  assert(kb_calendar_day(&f->baseline,1,date_day(2026,10,12))==KB_DAY_WEEKDAY); /* exact operator exception wins holiday */
  assert(kb_calendar_day(&f->baseline,2,date_day(2026,10,12))==KB_DAY_SUNDAY_HOLIDAY);
  assert(kb_calendar_day(&f->baseline,1,date_day(2026,11,3))==KB_DAY_SUNDAY_HOLIDAY);
  assert(kb_calendar_day(&f->baseline,1,date_day(2026,10,13))==KB_DAY_NONE);
  assert(kb_calendar_day(&f->baseline,2,date_day(2026,10,14))==KB_DAY_UNKNOWN);
  q.boarding_point_id=101; q.now_utc=at(2026,10,3,9,0,0); t=next(&q,&s); assert(s.today_no_service&&t.service_day==date_day(2026,10,5)&&t.service_id==4);
  q.boarding_point_id=1; t=next(&q,&s); assert(!s.today_no_service&&t.service_day==date_day(2026,10,3)); /* one operator's NONE does not hide another */
  q.now_utc=at(2026,10,13,9,0,0); t=next(&q,&s); assert(s.today_no_service&&t.service_day==date_day(2026,10,14));
  q.now_utc=at(2026,10,1,23,59,59); q.override.jst_day=date_day(2026,10,1); q.override.day_type=KB_DAY_SUNDAY_HOLIDAY; t=next(&q,&s); assert(s.override_used); /* browsing does not extend override */
  q.now_utc=at(2026,10,2,0,0,0); t=next(&q,&s); assert(!s.override_used&&s.today_type==KB_DAY_WEEKDAY&&t.minute==1505);
  q.override.jst_day=KB_DATE_UNKNOWN; q.override.day_type=KB_DAY_UNKNOWN;
  f->future_enabled=true; q.now_utc=at(2026,10,3,0,0,0); t=next(&q,&s); assert(t.minute==1505&&t.release_version==1&&t.service_day==date_day(2026,10,2)); /* previous snapshot overnight remains */
  const kb_dataset_t *resolved=kb_trip_dataset(&q,&t); assert(resolved&&resolved->release_version==1);
  q.now_utc=at(2026,10,3,2,0,0); t=next(&q,&s); assert(t.release_version==2&&t.service_day==date_day(2026,10,3)); f->future_enabled=false;
  f->use_unknown=true; q.now_utc=at(2026,10,3,2,0,0); assert(kb_query_next(&q,NULL,&t,&s)==KB_QUERY_UNCONFIRMED&&s.coverage_limited&&s.first_unconfirmed_day==date_day(2026,10,3));
  q.override.jst_day=date_day(2026,10,3); q.override.day_type=KB_DAY_WEEKDAY; t=next(&q,&s); assert(t.minute==633&&t.overridden&&s.override_used&&s.coverage_limited);
  q.now_utc=at(2026,10,4,0,0,0); assert(kb_query_next(&q,NULL,&t,&s)==KB_QUERY_UNCONFIRMED&&!s.override_used); f->use_unknown=false;
  q.override.jst_day=KB_DATE_UNKNOWN; q.override.day_type=KB_DAY_UNKNOWN; q.now_utc=at(2026,12,1,2,0,0); assert(kb_query_next(&q,NULL,&t,&s)==KB_QUERY_UNCONFIRMED);
  f->use_no_service=true; q.now_utc=at(2026,10,1,0,0,0); assert(kb_query_next(&q,NULL,&t,&s)==KB_QUERY_NO_MORE&&s.today_no_service&&!s.coverage_limited); f->use_no_service=false;
  q.boarding_point_id=250; assert(kb_query_next(&q,NULL,&t,&s)==KB_QUERY_UNAVAILABLE);
}
static void test_metadata(fixtures_t *f) {
  kb_boarding_point_t bp; kb_pattern_t pat; kb_operator_t op; kb_stop_group_t group; kb_source_t src;
  assert(kb_boarding_point_count(&f->baseline)==2); assert(kb_operator_count(&f->baseline)==2); assert(kb_stop_group_count(&f->baseline)==3);
  assert(kb_boarding_point_get(&f->baseline,1,&bp)&&!bp.has_coordinate&&bp.latitude_e6==KB_COORD_UNKNOWN);
  assert(kb_boarding_point_get(&f->baseline,101,&bp)&&bp.has_coordinate&&bp.latitude_e6==34800000);
  assert(kb_pattern_get(&f->baseline,1,&pat)&&!strcmp(pat.route,"25")&&strstr(pat.route_transitions,"22"));
  assert(kb_pattern_calls(&f->baseline,1,2)&&!kb_pattern_calls(&f->baseline,2,2));
  assert(kb_operator_get(&f->baseline,2,&op)&&op.id==2&&!strcmp(op.name,"Fixture Hankyu"));
  assert(kb_stop_group_get(&f->baseline,1,&group)&&!strcmp(group.name_ja,"架空停留所"));
  assert(kb_source_at(&f->baseline,0,&src)&&src.revision_on==date_day(2026,9,1));
  assert(!kb_pattern_get(&f->baseline,250,&pat)); assert(!kb_source_at(&f->baseline,99,&src));
}
static kb_query_result_t home_parity(kb_query_t *q) {
  kb_trip_t full,home;
  kb_query_state_t full_state,home_state;
  kb_query_result_t a=kb_query_next(q,NULL,&full,&full_state),b=kb_query_home(q,&home,&home_state);
  assert(a==b);
  assert(full_state.today_type==home_state.today_type);
  assert(full_state.today_no_service==home_state.today_no_service);
  assert(full_state.override_used==home_state.override_used);
  if(a==KB_QUERY_FOUND) {
    assert(kb_trip_same_identity(&full,&home));
    assert(full.day_type==home.day_type&&full.overridden==home.overridden);
  } else {
    assert(full_state.coverage_limited==home_state.coverage_limited);
    assert(full_state.first_unconfirmed_day==home_state.first_unconfirmed_day);
  }
  return b;
}
static void test_home_query(fixtures_t *f) {
  kb_query_t q;
  kb_trip_t t;
  kb_query_state_t s;
  memset(&q,0,sizeof(q)); q.resolve=resolve; q.context=f; q.boarding_point_id=1;
  q.override.jst_day=KB_DATE_UNKNOWN; q.override.day_type=KB_DAY_UNKNOWN;
  q.now_utc=at(2026,10,1,10,32,1); f->future_enabled=true;
  assert(home_parity(&q)==KB_QUERY_FOUND);
  f->resolve_calls=f->future_calls=0; f->latest_day=INT32_MIN;
  assert(kb_query_home(&q,&t,&s)==KB_QUERY_FOUND&&t.minute==633);
  assert(f->resolve_calls==4&&f->future_calls==0&&f->latest_day==date_day(2026,10,1));
  f->resolve_calls=f->future_calls=0; f->latest_day=INT32_MIN;
  assert(kb_query_next(&q,NULL,&t,&s)==KB_QUERY_FOUND&&t.minute==633);
  assert(f->resolve_calls==11&&f->future_calls>0&&f->latest_day==date_day(2026,10,8));
  /* A prior-snapshot overnight trip still needs today's calendar status. */
  q.now_utc=at(2026,10,3,0,0,0); assert(home_parity(&q)==KB_QUERY_FOUND);
  assert(kb_query_home(&q,&t,&s)==KB_QUERY_FOUND&&t.release_version==1&&t.minute==1505&&s.today_type==KB_DAY_SATURDAY&&!s.today_no_service);
  q.now_utc=at(2026,10,3,1,6,0); assert(home_parity(&q)==KB_QUERY_FOUND);
  f->future_enabled=false; q.boarding_point_id=101; q.now_utc=at(2026,10,3,9,0,0);
  assert(home_parity(&q)==KB_QUERY_FOUND); assert(kb_query_home(&q,&t,&s)==KB_QUERY_FOUND&&s.today_no_service&&t.service_day==date_day(2026,10,5));
  q.boarding_point_id=1; q.now_utc=at(2026,10,13,0,0,0);
  assert(home_parity(&q)==KB_QUERY_FOUND); assert(kb_query_home(&q,&t,&s)==KB_QUERY_FOUND&&t.minute==1505&&s.today_type==KB_DAY_NONE&&s.today_no_service);
  f->use_unknown=true; q.now_utc=at(2026,10,3,2,0,0); assert(home_parity(&q)==KB_QUERY_UNCONFIRMED);
  q.override.jst_day=date_day(2026,10,3); q.override.day_type=KB_DAY_WEEKDAY;
  assert(home_parity(&q)==KB_QUERY_FOUND);
  assert(kb_query_home(&q,&t,&s)==KB_QUERY_FOUND&&s.override_used&&!s.coverage_limited);
  assert(kb_query_next(&q,NULL,&t,&s)==KB_QUERY_FOUND&&s.override_used&&s.coverage_limited); /* full diagnostics unchanged */
  q.now_utc=at(2026,10,4,0,0,0); assert(home_parity(&q)==KB_QUERY_UNCONFIRMED);
  f->use_unknown=false; f->use_no_service=true; q.override.day_type=KB_DAY_UNKNOWN;
  q.now_utc=at(2026,10,1,0,0,0); assert(home_parity(&q)==KB_QUERY_NO_MORE); f->use_no_service=false;
  q.boarding_point_id=250; assert(home_parity(&q)==KB_QUERY_UNAVAILABLE);
}
int main(int argc,char **argv) {
  assert(argc==5); fixtures_t f; memset(&f,0,sizeof(f));
  load(argv[1],&f.baseline,&f.buffers[0]); load(argv[2],&f.future,&f.buffers[1]); load(argv[3],&f.unknown,&f.buffers[2]); load(argv[4],&f.no_service,&f.buffers[3]);
  f.effective=date_day(2026,10,3); test_dates(); test_minutes(); test_crc(); test_metadata(&f); test_schedule(&f); test_home_query(&f);
  for(unsigned i=0;i<4;i++) free(f.buffers[i]); puts("engine fixture tests passed"); return 0;
}
