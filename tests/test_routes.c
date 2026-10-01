/* Explicit synthetic schedules only; production expectations come from JSON. */
#include "../src/c/engine.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint8_t *bytes; size_t size; kb_dataset_t data; } snapshot_t;
typedef struct {
  snapshot_t snapshots[5];
  uint8_t cache[KB_MAX_DATASET_BYTES];
  kb_dataset_t cached;
  bool future_enabled;
  int forced;
  unsigned calls, versions_seen;
} fixtures_t;

static void load(const char *path,snapshot_t *snapshot) {
  FILE *f=fopen(path,"rb");assert(f);
  assert(fseek(f,0,SEEK_END)==0);long size=ftell(f);assert(size>0&&size<=KB_MAX_DATASET_BYTES);
  rewind(f);snapshot->size=(size_t)size;snapshot->bytes=malloc(snapshot->size);assert(snapshot->bytes);
  assert(fread(snapshot->bytes,1,snapshot->size,f)==snapshot->size);assert(fclose(f)==0);
  assert(kb_dataset_open(&snapshot->data,snapshot->bytes,snapshot->size)==KB_OK);
}
static int32_t day(unsigned month,unsigned dom) {
  int32_t result;assert(kb_date_from_ymd(2026,month,dom,&result));return result;
}
static int64_t at(unsigned month,unsigned dom,unsigned hour,unsigned minute,unsigned second) {
  return kb_service_epoch(day(month,dom),(uint16_t)(hour*60+minute))+second;
}
static const kb_dataset_t *resolve(void *context,int32_t service_day) {
  fixtures_t *f=context;unsigned index=0;
  if(f->forced>=0)index=(unsigned)f->forced;
  else if(f->future_enabled)index=service_day>=day(10,5)?2:service_day>=day(10,3)?1:0;
  f->calls++;f->versions_seen|=1u<<index;
  memset(f->cache,0,sizeof(f->cache));
  memcpy(f->cache,f->snapshots[index].bytes,f->snapshots[index].size);
  assert(kb_dataset_open(&f->cached,f->cache,f->snapshots[index].size)==KB_OK);
  return &f->cached;
}
static kb_query_t query(fixtures_t *f,uint8_t point,int64_t now) {
  kb_query_t q;memset(&q,0,sizeof(q));q.resolve=resolve;q.context=f;q.boarding_point_id=point;q.now_utc=now;
  q.override.jst_day=KB_DATE_UNKNOWN;q.override.day_type=KB_DAY_UNKNOWN;return q;
}
static void is_route(kb_query_t *q,const kb_trip_t *trip,uint8_t operator_id,const char *number) {
  const kb_dataset_t *d=kb_trip_dataset(q,trip);kb_pattern_t p;
  assert(d&&d->release_version==trip->release_version&&kb_pattern_get(d,trip->pattern_id,&p));
  assert(p.operator_id==operator_id&&!strcmp(p.route,number));
}
static void test_catalog(fixtures_t *f) {
  const kb_dataset_t *d=&f->snapshots[0].data;
  const uint8_t operators[]={1,1,1,1,1,2,2,2,2};
  const char *numbers[]={"1","2","22","24","25","2","72","164","171"};
  assert(kb_route_count(d)==9);kb_route_t route;
  for(size_t i=0;i<9;i++) {
    assert(kb_route_at(d,i,&route));assert(route.operator_id==operators[i]&&!strcmp(route.number,numbers[i]));
  }
  assert(kb_route_count(NULL)==0&&!kb_route_at(NULL,0,&route));
  assert(!kb_route_at(d,9,&route)&&!kb_route_at(d,0,NULL));
  assert(kb_boarding_point_has_route(d,1,1,"2"));
  assert(kb_boarding_point_has_route(d,101,2,"2"));
  assert(!kb_boarding_point_has_route(d,1,2,"2"));
  assert(kb_boarding_point_has_route(d,2,1,"25"));
  assert(!kb_boarding_point_has_route(d,2,1,"22"));
  assert(kb_boarding_point_has_route(d,3,1,"22"));
  assert(!kb_boarding_point_has_route(d,3,1,"25")); /* downstream call is not a departure */
  assert(!kb_boarding_point_has_route(d,4,1,"25")); /* point exists but has no departures */
  assert(!kb_boarding_point_has_route(d,1,1,"999")); /* pattern exists but is unused */
  assert(!kb_boarding_point_has_route(NULL,1,1,"2"));
  assert(!kb_boarding_point_has_route(d,1,1,NULL)&&!kb_boarding_point_has_route(d,1,1,""));
  assert(!kb_boarding_point_has_route(d,255,1,"2"));
}
static void test_filter_and_due(fixtures_t *f) {
  kb_query_t q=query(f,2,at(10,1,10,32,1));kb_trip_t first,next;kb_query_state_t s;
  assert(kb_query_route_next(&q,1,"25",NULL,&first,&s)==KB_QUERY_FOUND);
  assert(first.minute==633&&first.pattern_id==1&&first.day_type==KB_DAY_WEEKDAY&&!s.today_no_service);
  is_route(&q,&first,1,"25");
  assert(kb_query_route_next(&q,1,"25",&first,&next,&s)==KB_QUERY_FOUND&&next.minute==634&&next.pattern_id==6);
  assert(!kb_trip_same_identity(&first,&next));is_route(&q,&next,1,"25");
  assert(kb_upcoming_route_at(&q,1,"25",1,&next,&s)==KB_QUERY_FOUND&&next.minute==634);
  assert(kb_query_route_next(&q,1,"22",NULL,&next,&s)==KB_QUERY_NO_MORE&&s.today_no_service);
  q.now_utc=at(10,1,10,33,59);
  assert(kb_query_route_next(&q,1,"25",NULL,&next,&s)==KB_QUERY_FOUND&&next.minute==633);
  uint32_t minutes=99;assert(kb_countdown(q.now_utc,next.departure_utc,&minutes)==KB_COUNTDOWN_DUE&&minutes==0);
  q.now_utc=at(10,1,10,34,0);
  assert(kb_query_route_next(&q,1,"25",NULL,&next,&s)==KB_QUERY_FOUND&&next.minute==634);
  q.destination_group_id=3;q.now_utc=at(10,1,10,32,1);
  assert(kb_upcoming_route_at(&q,1,"25",1,&next,&s)==KB_QUERY_FOUND&&next.minute==1505&&next.pattern_id==1);
  q.destination_group_id=0;
  q.boarding_point_id=1;q.now_utc=at(10,1,10,0,0);
  assert(kb_query_route_next(&q,1,"2",NULL,&next,&s)==KB_QUERY_FOUND&&next.minute==621);is_route(&q,&next,1,"2");
  assert(kb_query_route_next(&q,2,"2",NULL,&next,&s)==KB_QUERY_UNAVAILABLE);
  q.boarding_point_id=101;
  assert(kb_query_route_next(&q,2,"2",NULL,&next,&s)==KB_QUERY_FOUND&&next.minute==645);is_route(&q,&next,2,"2");
}
static void test_calendars(fixtures_t *f) {
  kb_query_t q=query(f,2,at(10,3,1,6,0));kb_trip_t t;kb_query_state_t s;
  assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_FOUND&&t.minute==700&&t.day_type==KB_DAY_SATURDAY);
  q.now_utc=at(10,4,2,0,0);
  assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_FOUND&&t.minute==800&&t.day_type==KB_DAY_SUNDAY_HOLIDAY);
  q.now_utc=at(11,3,2,0,0);
  assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_FOUND&&t.minute==800&&t.day_type==KB_DAY_SUNDAY_HOLIDAY);
  q.now_utc=at(10,12,0,0,0);
  assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_FOUND&&t.minute==633&&t.day_type==KB_DAY_WEEKDAY);
  q.now_utc=at(10,13,2,0,0);
  assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_FOUND&&s.today_no_service&&t.service_day==day(10,14));
  q=query(f,101,at(10,3,9,0,0));
  assert(kb_query_route_next(&q,2,"2",NULL,&t,&s)==KB_QUERY_FOUND&&s.today_no_service&&s.today_type==KB_DAY_SATURDAY&&t.service_day==day(10,5));
  q.override.jst_day=day(10,3);q.override.day_type=KB_DAY_WEEKDAY;
  assert(kb_query_route_next(&q,2,"2",NULL,&t,&s)==KB_QUERY_FOUND&&t.service_day==day(10,3)&&t.minute==645&&t.overridden&&s.override_used);
  q.now_utc=at(10,4,0,0,0);
  assert(kb_query_route_next(&q,2,"2",NULL,&t,&s)==KB_QUERY_FOUND&&t.service_day==day(10,5)&&!t.overridden&&!s.override_used);
  q=query(f,2,at(10,3,2,0,0));f->forced=3;
  assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_UNCONFIRMED&&s.coverage_limited&&s.first_unconfirmed_day==day(10,3));
  q.override.jst_day=day(10,3);q.override.day_type=KB_DAY_WEEKDAY;
  assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_FOUND&&t.minute==633&&t.overridden&&s.override_used&&s.coverage_limited);
  q.now_utc=at(10,4,0,0,0);
  assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_UNCONFIRMED&&!s.override_used);
  f->forced=4;q=query(f,2,at(10,1,0,0,0));
  assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_NO_MORE&&s.today_no_service&&!s.coverage_limited);
  f->forced=-1;
}
static void test_future_cache_and_removed_route(fixtures_t *f) {
  f->future_enabled=true;kb_route_t route;
  const kb_dataset_t *d=resolve(f,day(10,1));assert(kb_route_at(d,4,&route)&&!strcmp(route.number,"25"));
  const char *borrowed=route.number;char owned[16];snprintf(owned,sizeof(owned),"%s",borrowed);
  resolve(f,day(10,3));assert(strcmp(borrowed,owned)!=0); /* Demonstrate actual cache invalidation. */
  assert(!strcmp(owned,"25"));
  kb_query_t q=query(f,2,at(10,3,0,0,0));kb_trip_t t,after;kb_query_state_t s;
  f->calls=f->versions_seen=0;
  assert(kb_query_route_next(&q,1,owned,NULL,&t,&s)==KB_QUERY_FOUND);
  assert(t.release_version==1&&t.pattern_id==1&&t.minute==1505&&t.service_day==day(10,2));
  assert(f->calls>3&&(f->versions_seen&7)==7);is_route(&q,&t,1,owned);
  after=t;q.now_utc=at(10,3,1,6,0);
  assert(kb_query_route_next(&q,1,owned,&after,&t,&s)==KB_QUERY_FOUND&&t.release_version==2&&t.pattern_id==41&&t.minute==700);
  is_route(&q,&t,1,owned);assert(!strcmp(owned,"25"));
  q.now_utc=at(10,5,9,0,0);
  assert(kb_query_route_next(&q,1,owned,NULL,&t,&s)==KB_QUERY_NO_MORE&&s.today_no_service);
  assert(kb_upcoming_route_at(&q,1,owned,0,&t,&s)==KB_QUERY_NO_MORE);
  assert(kb_query_route_next(&q,1,"22",NULL,&t,&s)==KB_QUERY_FOUND&&t.pattern_id==84&&t.release_version==3);
  is_route(&q,&t,1,"22");
  d=resolve(f,day(10,5));assert(!kb_boarding_point_has_route(d,2,1,owned)&&kb_boarding_point_has_route(d,2,1,"22"));
  for(size_t i=0;i<kb_route_count(d);i++){assert(kb_route_at(d,i,&route));assert(route.operator_id!=1||strcmp(route.number,"25"));}
  f->future_enabled=false;
}
static void test_invalid_filters(fixtures_t *f) {
  kb_query_t q=query(f,2,at(10,1,0,0,0));kb_trip_t t;kb_query_state_t s;
  assert(kb_query_route_next(&q,1,NULL,NULL,&t,&s)==KB_QUERY_UNAVAILABLE);
  assert(kb_query_route_next(&q,1,"",NULL,&t,&s)==KB_QUERY_UNAVAILABLE);
  assert(kb_query_route_next(&q,2,"25",NULL,&t,&s)==KB_QUERY_UNAVAILABLE);
  assert(kb_query_route_next(&q,0,"25",NULL,&t,&s)==KB_QUERY_UNAVAILABLE);
  assert(kb_query_route_next(NULL,1,"25",NULL,&t,&s)==KB_QUERY_UNAVAILABLE);
  assert(kb_query_route_next(&q,1,"25",NULL,NULL,&s)==KB_QUERY_UNAVAILABLE);
  assert(kb_upcoming_route_at(&q,1,NULL,0,&t,&s)==KB_QUERY_UNAVAILABLE);
  assert(kb_upcoming_route_at(&q,1,"",0,&t,&s)==KB_QUERY_UNAVAILABLE);
  assert(kb_upcoming_route_at(&q,2,"25",0,&t,&s)==KB_QUERY_UNAVAILABLE);
  assert(kb_query_route_next(&q,1,"999",NULL,&t,&s)==KB_QUERY_NO_MORE);
  q.boarding_point_id=255;assert(kb_query_route_next(&q,1,"25",NULL,&t,&s)==KB_QUERY_UNAVAILABLE);
}
static void inspect(const kb_dataset_t *d) {
  for(size_t i=0;i<kb_route_count(d);i++) {
    kb_route_t route;assert(kb_route_at(d,i,&route));printf("R %u %s\n",route.operator_id,route.number);
  }
  for(size_t p=0;p<kb_boarding_point_count(d);p++) {
    kb_boarding_point_t point;assert(kb_boarding_point_at(d,p,&point));
    for(size_t i=0;i<kb_route_count(d);i++) {
      kb_route_t route;assert(kb_route_at(d,i,&route));
      printf("M %u %u %s %u\n",point.id,route.operator_id,route.number,
        (unsigned)kb_boarding_point_has_route(d,point.id,route.operator_id,route.number));
    }
  }
}
static const kb_dataset_t *single_snapshot(void *context,int32_t service_day) {
  (void)service_day;return context;
}
static void inspect_query(kb_dataset_t *d,uint8_t point,uint8_t operator_id,const char *number,int64_t now) {
  kb_query_t q;memset(&q,0,sizeof(q));q.resolve=single_snapshot;q.context=d;q.now_utc=now;q.boarding_point_id=point;
  q.override.jst_day=KB_DATE_UNKNOWN;q.override.day_type=KB_DAY_UNKNOWN;
  kb_trip_t trip,previous;bool have_previous=false;size_t rows=0;int32_t service_day=kb_jst_day(now);
  while(kb_query_route_next(&q,operator_id,number,have_previous?&previous:NULL,&trip,NULL)==KB_QUERY_FOUND) {
    if(trip.service_day>service_day)break;
    if(trip.service_day==service_day)printf("Q %u %u %u %u\n",trip.minute,trip.pattern_id,trip.service_id,(unsigned)trip.day_type);
    previous=trip;have_previous=true;assert(++rows<65536);
  }
}
int main(int argc,char **argv) {
  if(argc==7&&!strcmp(argv[1],"query")) {
    snapshot_t snapshot={0};load(argv[2],&snapshot);
    inspect_query(&snapshot.data,(uint8_t)strtoul(argv[3],NULL,10),(uint8_t)strtoul(argv[4],NULL,10),argv[5],strtoll(argv[6],NULL,10));
    free(snapshot.bytes);return 0;
  }
  if(argc==3&&!strcmp(argv[1],"inspect")) {
    snapshot_t snapshot={0};load(argv[2],&snapshot);inspect(&snapshot.data);free(snapshot.bytes);return 0;
  }
  assert(argc==7&&!strcmp(argv[1],"fixtures"));fixtures_t *f=calloc(1,sizeof(*f));assert(f);f->forced=-1;
  for(unsigned i=0;i<5;i++)load(argv[i+2],&f->snapshots[i]);
  test_catalog(f);test_filter_and_due(f);test_calendars(f);test_future_cache_and_removed_route(f);test_invalid_filters(f);
  for(unsigned i=0;i<5;i++)free(f->snapshots[i].bytes);
  free(f);puts("route fixtures passed");return 0;
}
