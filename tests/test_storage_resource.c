/* Portable single-cache resource regressions. Synthetic revisions exist only
 * in test persistence; the supplied production bundle is never modified. */
#include "../src/c/storage.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint8_t records[4096][256],bundle[KB_MAX_DATASET_BYTES];
static uint8_t candidate[KB_MAX_DATASET_BYTES],cache[KB_MAX_DATASET_BYTES];
static size_t sizes[4096],length;
static unsigned reads,resource_reads,resource_bytes;
static int write_fail,partial_write;
static int32_t day;
static int64_t now;
typedef struct { const uint8_t *bytes; int mode; } resource_t;
static resource_t resource;

static uint32_t get32(const uint8_t *p) {
  return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;
}
static void put32(uint8_t *p,uint32_t value) {
  for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(value>>(8*i));
}
static int read_record(void *context,uint32_t key,void *buffer,size_t size) {
  (void)context;reads++;
  assert(key<4096);
  if(!sizes[key])return KB_STORE_NOT_FOUND;
  if(size>sizes[key])size=sizes[key];
  memcpy(buffer,records[key],size);
  return (int)size;
}
static int write_record(void *context,uint32_t key,const void *buffer,size_t size) {
  (void)context;
  assert(key<4096&&size<=256);
  if(write_fail)return -6;
  if(partial_write&&size>1) { size/=2;partial_write=0; }
  memcpy(records[key],buffer,size);sizes[key]=size;
  return (int)size;
}
static int remove_record(void *context,uint32_t key) {
  (void)context;assert(key<4096);sizes[key]=0;return 0;
}
static int read_resource(void *context,void *buffer,size_t size) {
  resource_t *r=context;
  resource_reads++;
  assert(size==length);
  if(r->mode==-1)return -3;
  if(r->mode==1)size/=2;
  memcpy(buffer,r->bytes,size);resource_bytes+=(unsigned)size;
  if(r->mode==2)((uint8_t *)buffer)[size-1]^=1;
  return (int)size;
}
static kb_store_io_t io={NULL,read_record,write_record,remove_record,1048576};
static void empty(void) {
  memset(sizes,0,sizeof(sizes));memset(cache,0xa5,sizeof(cache));
  reads=resource_reads=resource_bytes=0;write_fail=partial_write=0;
  resource.bytes=bundle;resource.mode=0;
}
static bool init(kb_store_t *store) {
  return kb_store_init_reader(store,io,read_resource,&resource,length,cache);
}
static void revision(uint32_t version,int offset) {
  memcpy(candidate,bundle,length);
  put32(candidate+16,version);
  put32(candidate+124,(uint32_t)(day+offset));
  put32(candidate+40,(uint32_t)(day+offset));
  put32(candidate+12,kb_crc32(candidate+16,length-16));
}
static void chunks(kb_store_t *store,uint32_t session) {
  for(unsigned sequence=0;(size_t)sequence*KB_CHUNK_SIZE<length;sequence++) {
    size_t offset=(size_t)sequence*KB_CHUNK_SIZE,size=length-offset;
    if(size>KB_CHUNK_SIZE)size=KB_CHUNK_SIZE;
    assert(kb_store_chunk(store,session,(uint16_t)sequence,candidate+offset,size,now)==0);
  }
}
static void install(kb_store_t *store,uint32_t version,int offset) {
  revision(version,offset);
  assert(kb_store_begin(store,500+version,version,(uint32_t)length,kb_crc32(candidate,length),now)==0);
  chunks(store,500+version);
  assert(kb_store_commit(store,500+version,now)==(offset>1?4:3));
}
static const kb_dataset_t *resolved(kb_store_t *store,int offset,uint32_t version) {
  const kb_dataset_t *data=kb_store_resolve(store,day+offset);
  assert(data&&data->release_version==version&&data->bytes==cache);
  assert(kb_dataset_open(&(kb_dataset_t){0},data->bytes,data->size)==KB_OK);
  assert(!strcmp(kb_coverage_id(data),"minami-kasugaoka-v1"));
  return data;
}
static void corrupt_version(kb_store_t *store,uint32_t version) {
  bool found=false;
  for(unsigned i=0;i<KB_STORE_SLOTS;i++)if(store->slots[i].valid&&store->slots[i].version==version) {
    records[KB_STORE_DATA_KEY+i*KB_STORE_STRIDE][30]^=1;found=true;
  }
  assert(found);
}
static void seed_pair(kb_store_t *store) {
  assert(init(store));install(store,3,2);install(store,2,1);
}
static void baseline_cache_and_read_counts(void) {
  kb_store_t store;empty();assert(init(&store));
  assert(resource_reads==1&&resource_bytes==length&&store.cache_slot==KB_STORE_CACHE_BASELINE);
  assert(store.baseline.bytes==cache&&store.cached.bytes==NULL);
  resolved(&store,0,1);resolved(&store,0,1);
  assert(resource_reads==1&&!memcmp(cache,bundle,length));
  assert(kb_store_resolve(&store,day-1)==NULL&&resource_reads==1);
  revision(2,1);
  assert(kb_store_begin(&store,502,2,(uint32_t)length,kb_crc32(candidate,length),now)==0);
  assert(kb_store_chunk(&store,502,0,candidate,KB_CHUNK_SIZE,now)==0);
  kb_store_abort(&store);resolved(&store,0,1);
  assert(store.cache_slot==KB_STORE_CACHE_BASELINE&&resource_reads==1);
  assert(kb_store_restore(&store));resolved(&store,0,1);assert(resource_reads==1);
}
static void baseline_current_future_alternation(void) {
  kb_store_t store;empty();seed_pair(&store);
  assert(resource_reads==1);
  const kb_dataset_t *data=resolved(&store,1,2);assert(data->source_verified_on==day+1);
  resolved(&store,2,3);assert(resource_reads==1);
  data=resolved(&store,0,1);assert(data->source_verified_on==day&&resource_reads==2);
  assert(!memcmp(cache,bundle,length));
  unsigned before=reads;resolved(&store,0,1);assert(reads==before&&resource_reads==2);
  assert(kb_store_pending(&store,day+1,NULL)==3&&store.cache_slot==KB_STORE_CACHE_BASELINE);
  resolved(&store,0,1);assert(resource_reads==2);
  resolved(&store,1,2);resolved(&store,2,3);resolved(&store,0,1);
  assert(resource_reads==3&&store.baseline.release_version==1&&store.baseline.source_verified_on==day);
  before=resource_reads;assert(init(&store));assert(resource_reads==before+1&&store.cache_slot==KB_STORE_CACHE_BASELINE);
  assert(!store.slots[0].checked&&!store.slots[1].checked);
  resolved(&store,1,2);assert(kb_store_pending(&store,day+1,NULL)==3);
  resolved(&store,0,1);assert(resource_reads==before+2);
}
static void corrupted_snapshots_recover_baseline_and_older_future(void) {
  kb_store_t store;empty();seed_pair(&store);install(&store,4,2);
  corrupt_version(&store,4);corrupt_version(&store,2);
  assert(init(&store));unsigned before=resource_reads;
  resolved(&store,1,1);assert(store.recovery_notice&&resource_reads==before+1);
  resolved(&store,2,3);assert(kb_store_pending(&store,day+1,NULL)==3);
  resolved(&store,1,1);assert(resource_reads==before+2);
  assert(kb_store_restore(&store));resolved(&store,2,1);
  assert(kb_store_pending(&store,day+1,NULL)==0);
}
static void failed_reload_never_returns_stale_metadata(void) {
  kb_store_t store;empty();seed_pair(&store);
  for(int mode=-1;mode<=2;mode++) {
    if(mode==0)continue;
    resolved(&store,1,2);resource.mode=mode;
    unsigned before=resource_reads;
    assert(kb_store_resolve(&store,day)==NULL&&resource_reads==before+1);
    assert(store.cache_slot==KB_STORE_CACHE_INVALID&&store.baseline_valid&&store.recovery_notice);
    resource.mode=0;resolved(&store,0,1);
    assert(resource_reads==before+2&&store.cache_slot==KB_STORE_CACHE_BASELINE&&!memcmp(cache,bundle,length));
  }
  /* A different, internally valid resource is not the bundle validated at init. */
  resolved(&store,2,3);revision(8,0);resource.bytes=candidate;
  assert(kb_store_resolve(&store,day)==NULL&&store.cache_slot==KB_STORE_CACHE_INVALID);
  resource.bytes=bundle;resolved(&store,0,1);
}
static void invalid_or_partial_initial_resource(void) {
  kb_store_t store;empty();
  for(int mode=-1;mode<=2;mode++) {
    if(mode==0)continue;
    /* Cache already contains a valid bundle: a short read must not parse it. */
    memcpy(cache,bundle,length);resource.mode=mode;
    assert(!init(&store)&&!store.baseline_valid&&store.cache_slot==KB_STORE_CACHE_INVALID);
    assert(kb_store_resolve(&store,day)==NULL&&store.recovery_notice);
  }
  resource.mode=0;unsigned before=resource_reads;
  assert(!kb_store_init_reader(&store,io,read_resource,&resource,KB_HEADER_SIZE-1,cache));
  assert(!kb_store_init_reader(&store,io,read_resource,&resource,KB_MAX_DATASET_BYTES+1,cache));
  assert(!kb_store_init_reader(&store,io,NULL,&resource,length,cache));
  assert(!kb_store_init_reader(&store,io,read_resource,&resource,length,NULL));
  assert(resource_reads==before&&!store.baseline_valid&&store.directory_generation==UINT32_MAX);
  assert(kb_store_begin(&store,555,2,(uint32_t)length,0,now)==5);
  /* A transient initial resource failure does not hide intact downloads. */
  empty();seed_pair(&store);resource.mode=1;
  assert(!init(&store)&&!store.baseline_valid&&store.cache_slot==KB_STORE_CACHE_INVALID);
  resolved(&store,1,2);resolved(&store,2,3);
  assert(kb_store_resolve(&store,day)==NULL);
  /* Structural validity does not waive minimum app/coverage policy. */
  empty();revision(1,0);put32(candidate+20,2);put32(candidate+12,kb_crc32(candidate+16,length-16));
  resource.bytes=candidate;assert(!init(&store)&&!store.baseline_valid);
  memcpy(candidate,bundle,length);
  size_t coverage=get32(candidate+52)+(uint32_t)candidate[48]+((uint32_t)candidate[49]<<8);
  candidate[coverage]='x';put32(candidate+12,kb_crc32(candidate+16,length-16));
  assert(!init(&store)&&!store.baseline_valid);
}
static void interrupted_failed_and_corrupt_candidates_preserve_pair(void) {
  kb_store_t store;empty();seed_pair(&store);
  revision(4,2);
  assert(kb_store_begin(&store,504,4,(uint32_t)length,kb_crc32(candidate,length),now)==0);
  assert(kb_store_chunk(&store,504,0,candidate,KB_CHUNK_SIZE,now)==0);
  assert(init(&store));resolved(&store,1,2);assert(kb_store_pending(&store,day+1,NULL)==3);
  assert(kb_store_begin(&store,505,4,(uint32_t)length,kb_crc32(candidate,length),now)==0);
  chunks(&store,505);records[KB_STORE_DATA_KEY+(unsigned)store.transfer.slot*KB_STORE_STRIDE][30]^=1;
  assert(kb_store_commit(&store,505,now)==2&&store.cache_slot==KB_STORE_CACHE_INVALID);
  resolved(&store,0,1);resolved(&store,1,2);resolved(&store,2,3);
  assert(kb_store_begin(&store,506,4,(uint32_t)length,kb_crc32(candidate,length),now)==0);
  chunks(&store,506);partial_write=1;assert(kb_store_commit(&store,506,now)==5);
  assert(init(&store));resolved(&store,1,2);resolved(&store,2,3);
  assert(kb_store_begin(&store,507,4,(uint32_t)length,kb_crc32(candidate,length),now)==0);
  write_fail=1;assert(kb_store_chunk(&store,507,0,candidate,KB_CHUNK_SIZE,now)==5);write_fail=0;
  assert(init(&store));resolved(&store,1,2);resolved(&store,2,3);resolved(&store,0,1);
}
static void query_results_match_permanent_baseline_across_cache_reuse(void) {
  static uint8_t separate_cache[KB_MAX_DATASET_BYTES];
  kb_store_t shared,separate;empty();seed_pair(&shared);
  assert(kb_store_init(&separate,io,bundle,length,separate_cache));
  const uint16_t points[]={1,2,3,4,5,6,7,8,9,101,102,103,104,105,106};
  kb_query_t query={.resolve=kb_store_resolve,.context=&shared,.boarding_point_id=1,
    .override={KB_DATE_UNKNOWN,KB_DAY_UNKNOWN}};
  kb_query_t reference=query;reference.context=&separate;
  for(int offset=0;offset<=2;offset++) {
    query.now_utc=reference.now_utc=kb_service_epoch(day+offset,1438);
    kb_trip_t previous={0};bool after=false;
    for(unsigned index=0;index<4;index++) {
      kb_trip_t actual,expected;kb_query_state_t actual_state,expected_state;
      kb_query_result_t result=kb_query_merged_next(&query,points,NULL,15,after?&previous:NULL,&actual,&actual_state);
      kb_query_result_t wanted=kb_query_merged_next(&reference,points,NULL,15,after?&previous:NULL,&expected,&expected_state);
      assert(result==wanted&&actual_state.today_type==expected_state.today_type&&actual_state.coverage_limited==expected_state.coverage_limited);
      if(result!=KB_QUERY_FOUND)break;
      assert(kb_trip_same_identity(&actual,&expected));
      const kb_dataset_t *data=kb_trip_dataset(&query,&actual);
      assert(data&&data->release_version==actual.release_version);
      kb_pattern_t pattern;assert(kb_pattern_get(data,actual.pattern_id,&pattern)&&pattern.route[0]);
      /* A status check can replace the cache before Details resolves its trip. */
      kb_store_pending(&shared,day+1,NULL);
      data=kb_trip_dataset(&query,&actual);assert(data&&data->release_version==actual.release_version);
      previous=actual;after=true;
    }
    kb_trip_t actual,expected;
    assert(kb_query_home(&query,&actual,NULL)==kb_query_home(&reference,&expected,NULL));
    assert(kb_trip_same_identity(&actual,&expected));
  }
}
int main(int argc,char **argv) {
  assert(argc==2);FILE *input=fopen(argv[1],"rb");assert(input);
  length=fread(bundle,1,sizeof(bundle),input);assert(!ferror(input)&&feof(input));fclose(input);
  kb_dataset_t data;assert(kb_dataset_open(&data,bundle,length)==KB_OK&&data.release_version==1);
  day=data.effective_from;now=kb_service_epoch(day+1,600);
  baseline_cache_and_read_counts();baseline_current_future_alternation();
  corrupted_snapshots_recover_baseline_and_older_future();failed_reload_never_returns_stale_metadata();
  invalid_or_partial_initial_resource();interrupted_failed_and_corrupt_candidates_preserve_pair();
  query_results_match_permanent_baseline_across_cache_reuse();
  puts("storage resource: 7 single-cache/init/alternation/recovery/read-count/transfer/merged-query suites PASS");
  return 0;
}
