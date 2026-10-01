/* Synthetic merged queries and immutable-identity checks with a reused cache. */
#include "../src/c/engine.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { uint8_t bytes[KB_MAX_DATASET_BYTES];size_t size;kb_dataset_t data; } snapshot_t;
typedef struct {snapshot_t base,future;uint8_t bytes[KB_MAX_DATASET_BYTES];kb_dataset_t cached;bool has_future;} fixture_t;
static fixture_t fixture;
static void load(const char *path,snapshot_t *s) {
 FILE *file=fopen(path,"rb");assert(file);s->size=fread(s->bytes,1,sizeof(s->bytes),file);assert(!ferror(file));fclose(file);
 assert(kb_dataset_open(&s->data,s->bytes,s->size)==KB_OK);
}
static const kb_dataset_t *resolve(void *context,int32_t day) {
 fixture_t *f=context;snapshot_t *s=f->has_future&&day>=f->future.data.effective_from?&f->future:&f->base;
 memset(f->bytes,0,sizeof(f->bytes));memcpy(f->bytes,s->bytes,s->size);
 assert(kb_dataset_open(&f->cached,f->bytes,s->size)==KB_OK);return &f->cached;
}
int main(int argc,char **argv) {
 assert(argc>=7);load(argv[1],&fixture.base);
 if(strcmp(argv[2],"-")){load(argv[2],&fixture.future);fixture.has_future=true;}
 kb_query_t q;memset(&q,0,sizeof(q));q.resolve=resolve;q.context=&fixture;q.now_utc=strtoll(argv[3],NULL,10);
 q.override.jst_day=atoi(argv[4]);q.override.day_type=(kb_day_type_t)atoi(argv[5]);q.destination_group_id=(uint8_t)atoi(argv[6]);
 size_t count=0;uint16_t ids[KB_MERGED_MAX_POINTS];uint32_t distances[KB_MERGED_MAX_POINTS];
 for(int i=7;i+1<argc;i+=2){assert(count<KB_MERGED_MAX_POINTS);ids[count]=(uint16_t)atoi(argv[i]);distances[count]=(uint32_t)strtoul(argv[i+1],NULL,10);count++;}
 kb_trip_t trip,after;bool prior=false;kb_query_state_t state;
 int result=kb_query_merged_next(&q,ids,distances,count,NULL,&trip,&state);
 printf("S %d %d %d %d %d %d\n",result,state.today_type,state.today_no_service,state.override_used,state.coverage_limited,state.first_unconfirmed_day);
 if(count==1&&ids[0]&&ids[0]<=255) {
  q.boarding_point_id=(uint8_t)ids[0];kb_trip_t single;
  int single_result=kb_query_next(&q,NULL,&single,NULL);
  if(result==KB_QUERY_FOUND) {
   assert(single_result==KB_QUERY_FOUND&&kb_trip_same_identity(&single,&trip));
   kb_pattern_t p;const kb_dataset_t *d=kb_trip_dataset(&q,&trip);assert(kb_pattern_get(d,trip.pattern_id,&p));
   uint8_t operator_id=p.operator_id;char number[1024];snprintf(number,sizeof(number),"%s",p.route);
   assert(kb_query_route_next(&q,operator_id,number,NULL,&single,NULL)==KB_QUERY_FOUND);
   assert(kb_trip_same_identity(&single,&trip));
  }else assert(single_result!=KB_QUERY_FOUND);
 }
 for(size_t i=0;i<64;i++) {
  result=kb_query_merged_next(&q,ids,distances,count,prior?&after:NULL,&trip,NULL);
  if(result!=KB_QUERY_FOUND)break;
  if(i<10){kb_trip_t indexed;assert(kb_upcoming_merged_at(&q,ids,distances,count,i,&indexed,NULL)==KB_QUERY_FOUND);assert(kb_trip_same_identity(&indexed,&trip));}
  printf("T %lld %d %u %u %u %u %u %d %d\n",(long long)trip.departure_utc,trip.service_day,trip.release_version,trip.minute,trip.boarding_point_id,trip.pattern_id,trip.service_id,trip.day_type,trip.overridden);
  assert(!prior||!kb_trip_same_identity(&after,&trip));
  const kb_dataset_t *d=kb_trip_dataset(&q,&trip);kb_pattern_t pattern;assert(d&&kb_pattern_get(d,trip.pattern_id,&pattern));
  after=trip;prior=true;
 }
 assert(kb_query_merged_next(NULL,ids,distances,count,NULL,&trip,NULL)==KB_QUERY_UNAVAILABLE);
 assert(kb_query_merged_next(&q,ids,distances,33,NULL,&trip,NULL)==KB_QUERY_UNAVAILABLE);
 assert(kb_query_merged_next(&q,NULL,NULL,1,NULL,&trip,NULL)==KB_QUERY_UNAVAILABLE);
 assert(kb_query_merged_next(&q,NULL,NULL,0,NULL,&trip,NULL)==KB_QUERY_NO_MORE);
 assert(kb_query_merged_next(&q,ids,distances,count,NULL,NULL,NULL)==KB_QUERY_UNAVAILABLE);
 return 0;
}
