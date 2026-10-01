#include "../src/c/storage.h"
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
static unsigned char memory[4096][256];static int sizes[4096],write_limit=-1,torn_bytes=-1,read_fail_key=-1;
static unsigned metadata_reads,legacy_reads,payload_reads,payload_bytes,write_calls,remove_calls,slot_reads[KB_STORE_SLOTS];
static int read_mem(void *c,uint32_t k,void *b,size_t n){(void)c;if(k>=KB_STORE_DIRECTORY_KEY&&k<KB_STORE_DIRECTORY_KEY+2)metadata_reads++;if(k>=KB_STORE_META_KEY&&k<KB_STORE_META_KEY+KB_STORE_SLOTS)legacy_reads++;if(k>=KB_STORE_DATA_KEY&&k<KB_STORE_DATA_KEY+KB_STORE_SLOTS*KB_STORE_STRIDE){payload_reads++;slot_reads[(k-KB_STORE_DATA_KEY)/KB_STORE_STRIDE]++;}if((int)k==read_fail_key||(read_fail_key==-2&&k>=KB_STORE_DIRECTORY_KEY&&k<KB_STORE_DIRECTORY_KEY+2))return -3;if(k>=4096||!sizes[k])return KB_STORE_NOT_FOUND;if(n>(size_t)sizes[k])n=sizes[k];if(k>=KB_STORE_DATA_KEY)payload_bytes+=n;memcpy(b,memory[k],n);return (int)n;}
static int write_mem(void *c,uint32_t k,const void *b,size_t n){(void)c;write_calls++;if(write_limit==0)return -6;if(write_limit>0)write_limit--;assert(k<4096&&n<=256);if(torn_bytes>=0){size_t short_n=(size_t)torn_bytes;if(short_n>n)short_n=n;memcpy(memory[k],b,short_n);sizes[k]=short_n;torn_bytes=-1;return (int)short_n;}memcpy(memory[k],b,n);sizes[k]=n;return n;}
static int remove_mem(void *c,uint32_t k){(void)c;remove_calls++;sizes[k]=0;return 0;}
static void put(unsigned char *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=v>>(i*8);}
static uint32_t get(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint8_t base[32768],candidate[32768],cache[32768];static size_t length;static int32_t day;static int64_t now;
static kb_store_io_t io={NULL,read_mem,write_mem,remove_mem,1048576};
static void revision(unsigned v,int offset){memcpy(candidate,base,length);put(candidate+16,v);put(candidate+124,day+offset);put(candidate+12,kb_crc32(candidate+16,length-16));}
static void begin(kb_store_t *s,unsigned session,unsigned version){assert(kb_store_begin(s,session,version,length,kb_crc32(candidate,length),now)==0);}
static void chunks(kb_store_t *s,unsigned session){for(unsigned seq=s->transfer.next_seq;seq*192<length;seq++){unsigned n=length-seq*192;if(n>192)n=192;assert(kb_store_chunk(s,session,seq,candidate+seq*192,n,now)==0);}}
static void reset_reads(void){metadata_reads=legacy_reads=payload_reads=payload_bytes=write_calls=remove_calls=0;memset(slot_reads,0,sizeof(slot_reads));}
static void empty_storage(void){memset(sizes,0,sizeof(sizes));write_limit=-1;torn_bytes=-1;read_fail_key=-1;reset_reads();}
/* Synthetic persisted revisions are isolated test copies of the supplied
 * baseline. Raw seeding also permits coherent descriptors with corrupt data. */
static void seed_legacy_candidate(unsigned slot,unsigned session){
 for(unsigned seq=0;seq*KB_CHUNK_SIZE<length;seq++){unsigned n=length-seq*KB_CHUNK_SIZE;if(n>KB_CHUNK_SIZE)n=KB_CHUNK_SIZE;assert(write_mem(NULL,KB_STORE_DATA_KEY+slot*KB_STORE_STRIDE+seq,candidate+seq*KB_CHUNK_SIZE,n)==(int)n);}
 uint8_t meta[40]={0};memcpy(meta,"KBS1",4);put(meta+4,get(candidate+16));put(meta+8,(uint32_t)length);put(meta+12,kb_crc32(candidate,length));put(meta+16,session);put(meta+20,get(candidate+124));put(meta+24,get(candidate+28));put(meta+36,kb_crc32(meta,36));assert(write_mem(NULL,KB_STORE_META_KEY+slot,meta,sizeof(meta))==sizeof(meta));
}
static void seed_candidate(unsigned slot,unsigned session){
 seed_legacy_candidate(slot,session);
 uint8_t directory[KB_STORE_DIRECTORY_SIZE]={0};
 if(sizes[KB_STORE_DIRECTORY_KEY]==KB_STORE_DIRECTORY_SIZE)memcpy(directory,memory[KB_STORE_DIRECTORY_KEY],sizeof(directory));
 memcpy(directory,"KBD2",4);directory[8]|=(uint8_t)(1u<<slot);
 memcpy(directory+12+24*slot,memory[KB_STORE_META_KEY+slot]+4,24);
 for(unsigned bank=0;bank<2;bank++){put(directory+4,get(directory+4)+1);put(directory+204,kb_crc32(directory,204));assert(write_mem(NULL,KB_STORE_DIRECTORY_KEY+bank,directory,sizeof(directory))==(int)sizeof(directory));}
 sizes[KB_STORE_META_KEY+slot]=0;
}
static void seed(unsigned slot,unsigned version,int offset,unsigned session){revision(version,offset);seed_candidate(slot,session);}
static void corrupt_payload(unsigned slot){memory[KB_STORE_DATA_KEY+slot*KB_STORE_STRIDE][30]^=1;}
static unsigned checked_count(const kb_store_t *s){unsigned n=0;for(unsigned i=0;i<KB_STORE_SLOTS;i++)if(s->slots[i].valid&&s->slots[i].checked)n++;return n;}
static unsigned chunk_count(void){return (unsigned)((length+KB_CHUNK_SIZE-1)/KB_CHUNK_SIZE);}
static void test_lazy_init_and_bounded_step(void){
 kb_store_t s;empty_storage();for(unsigned i=0;i<KB_STORE_SLOTS;i++)seed(i,i+2,(int)i,300+i);reset_reads();
 assert(kb_store_init(&s,io,base,length,cache));assert(metadata_reads==2&&legacy_reads==0&&payload_reads==0&&checked_count(&s)==0&&s.cache_slot==-1&&!s.legacy_migration);
 for(unsigned i=0;i<KB_STORE_SLOTS;i++)assert(s.slots[i].valid&&!s.slots[i].checked);
 reset_reads();assert(kb_store_resolve(&s,day)->release_version==2);assert(payload_reads==chunk_count()&&payload_bytes==length&&slot_reads[0]==chunk_count()&&checked_count(&s)==1);
 reset_reads();assert(kb_store_resolve(&s,day)->release_version==2&&payload_reads==0); /* Validated RAM cache needs no flash read. */
 for(unsigned step=1;step<KB_STORE_SLOTS;step++){
  reset_reads();assert(kb_store_check_next(&s));assert(payload_reads==chunk_count()&&payload_bytes==length&&checked_count(&s)==step+1);
  unsigned touched=0;for(unsigned i=0;i<KB_STORE_SLOTS;i++)if(slot_reads[i])touched++;assert(touched==1&&write_calls==0&&remove_calls==0);
 }
 reset_reads();assert(!kb_store_check_next(&s)&&payload_reads==0&&write_calls==0&&remove_calls==0);
}
static void test_sole_good_future_survives_unchecked_corrupt_corrections(void){
 kb_store_t s;empty_storage();seed(0,2,0,400);seed(1,3,1,401);seed(2,4,1,402);seed(3,5,1,403);
 for(unsigned i=4;i<KB_STORE_SLOTS;i++)seed(i,i+2,(int)i-2,400+i);corrupt_payload(2);corrupt_payload(3);
 assert(kb_store_init(&s,io,base,length,cache));assert(checked_count(&s)==0);
 revision(10,6);begin(&s,410,10);assert(s.recovery_notice&&(s.transfer.slot==2||s.transfer.slot==3));
 assert(s.slots[1].valid&&s.slots[1].checked);
 assert(kb_store_resolve(&s,day)->release_version==2&&kb_store_resolve(&s,day+1)->release_version==3);
 kb_store_abort(&s);assert(kb_store_pending(&s,day,NULL)==3);assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_resolve(&s,day+1)->release_version==3);
}
static void test_pending_and_duplicate_commit_validate_before_claim(void){
 kb_store_t s;int32_t effective;empty_storage();seed(0,2,0,500);seed(1,3,1,501);seed(2,4,1,502);corrupt_payload(2);
 assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_pending(&s,day,&effective)==3&&effective==day+1&&s.recovery_notice);
 assert(!s.slots[2].valid&&s.slots[1].checked&&!s.slots[0].checked);
 assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_commit(&s,502,now)==2&&!s.slots[2].valid&&s.recovery_notice);
 assert(kb_store_commit(&s,501,now)==4&&s.slots[1].checked);
 corrupt_payload(0);assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_commit(&s,500,now)==2);
 assert(kb_store_resolve(&s,day)->release_version==1);
}
static void test_eight_bad_descriptors_do_not_activate_baseline_early(void){
 kb_store_t s;empty_storage();for(unsigned i=0;i<KB_STORE_SLOTS;i++){
  seed(i,i+2,0,600+i);
 }
 for(unsigned bank=0;bank<2;bank++){uint8_t *directory=memory[KB_STORE_DIRECTORY_KEY+bank];for(unsigned i=0;i<KB_STORE_SLOTS;i++)put(directory+12+24*i+16,(uint32_t)(day-1));put(directory+204,kb_crc32(directory,204));}
 assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_resolve(&s,day-1)==NULL&&s.recovery_notice);
 for(unsigned i=0;i<KB_STORE_SLOTS;i++)assert(!s.slots[i].valid);
 assert(kb_store_resolve(&s,day)->release_version==1);
}
static void test_current_metadata_and_identity_after_pending_replaces_cache(void){
 kb_store_t s;empty_storage();seed(0,2,0,700);revision(3,1);put(candidate+40,(uint32_t)(day+1));put(candidate+44,(uint32_t)(day+7));put(candidate+12,kb_crc32(candidate+16,length-16));seed_candidate(1,701);
 assert(kb_store_init(&s,io,base,length,cache));const kb_dataset_t *d=kb_store_resolve(&s,day);assert(d&&d->release_version==2);
 uint32_t saved_version=d->release_version;int32_t saved_source=d->source_verified_on;
 assert(kb_store_pending(&s,day,NULL)==3&&s.cache_slot==1&&saved_version==2&&saved_source==day);
 d=kb_store_resolve(&s,day);assert(d&&d->release_version==2&&d->source_verified_on==saved_source);
 kb_query_t q={.resolve=kb_store_resolve,.context=&s,.now_utc=now,.boarding_point_id=1,.override={KB_DATE_UNKNOWN,KB_DAY_UNKNOWN}};kb_trip_t trip;
 assert(kb_query_home(&q,&trip,NULL)==KB_QUERY_FOUND&&trip.release_version==2);assert(kb_store_resolve(&s,day+1)->release_version==3);
 d=kb_trip_dataset(&q,&trip);assert(d&&d->release_version==2);reset_reads();assert(kb_store_resolve(&s,day)->release_version==2&&payload_reads==0);
}
static void test_checked_reload_still_validates_payload_and_schema(void){
 kb_store_t s;empty_storage();seed(0,2,0,800);seed(1,3,1,801);assert(kb_store_init(&s,io,base,length,cache));
 assert(kb_store_resolve(&s,day)->release_version==2&&s.slots[0].checked);assert(kb_store_pending(&s,day,NULL)==3&&s.cache_slot==1);
 corrupt_payload(0);reset_reads();assert(kb_store_resolve(&s,day)->release_version==1&&!s.slots[0].valid&&s.recovery_notice&&payload_reads>0);
 /* A matching outer CRC cannot make an incompatible schema usable. */
 empty_storage();revision(2,0);candidate[4]=2;seed_candidate(0,802);assert(kb_store_init(&s,io,base,length,cache));
 assert(kb_store_resolve(&s,day)->release_version==1&&!s.slots[0].valid&&s.recovery_notice);
}
static void test_capacity_and_newest_validate_all_candidates(void){
 kb_store_t s;empty_storage();for(unsigned i=0;i<KB_STORE_SLOTS;i++)seed(i,i+2,(int)i,900+i);
 assert(kb_store_init(&s,io,base,length,cache));assert(!kb_store_has_staging(&s,day)&&checked_count(&s)==0);
 revision(10,8);reset_reads();assert(kb_store_begin(&s,910,10,length,kb_crc32(candidate,length),now)==5);
 assert(checked_count(&s)==KB_STORE_SLOTS&&payload_reads==KB_STORE_SLOTS*chunk_count()&&write_calls==0&&remove_calls==0);
 for(unsigned i=0;i<KB_STORE_SLOTS;i++)assert(s.slots[i].valid);
 assert(kb_store_resolve(&s,day)->release_version==2&&kb_store_pending(&s,day,NULL)==3);
 corrupt_payload(7);assert(kb_store_init(&s,io,base,length,cache));reset_reads();assert(kb_store_newest(&s)==8&&!s.slots[7].valid&&s.recovery_notice);
 assert(checked_count(&s)==KB_STORE_SLOTS-1&&payload_reads==KB_STORE_SLOTS*chunk_count()&&write_calls==0&&remove_calls==0);
}
static void test_legacy_import_is_one_time_and_preserves_versions(void){
 kb_store_t s;empty_storage();revision(16,0);seed_legacy_candidate(0,1016);revision(17,1);seed_legacy_candidate(1,1017);reset_reads();
 assert(kb_store_init(&s,io,base,length,cache)&&s.legacy_migration);
 assert(metadata_reads==2&&legacy_reads==KB_STORE_SLOTS&&payload_reads==0&&write_calls==2&&remove_calls==KB_STORE_SLOTS);
 assert(s.directory_generation==2&&s.directory_masks[0]==3&&s.directory_masks[1]==3);
 for(unsigned i=0;i<KB_STORE_SLOTS;i++)assert(sizes[KB_STORE_META_KEY+i]==0);
 assert(kb_store_resolve(&s,day)->release_version==16&&kb_store_pending(&s,day,NULL)==17);
 reset_reads();assert(kb_store_init(&s,io,base,length,cache)&&!s.legacy_migration);
 assert(metadata_reads==2&&legacy_reads==0&&payload_reads==0&&write_calls==0&&remove_calls==0);
 assert(kb_store_resolve(&s,day)->release_version==16&&kb_store_resolve(&s,day+1)->release_version==17);
 /* A torn first migration leaves all legacy payloads and descriptors intact
  * and removes the incomplete new bank, allowing a clean retry on restart. */
 empty_storage();revision(16,0);seed_legacy_candidate(0,1016);torn_bytes=50;
 assert(kb_store_init(&s,io,base,length,cache)&&s.legacy_migration&&s.recovery_notice);
 assert(sizes[KB_STORE_DIRECTORY_KEY]==0&&sizes[KB_STORE_META_KEY]==40);
 assert(kb_store_resolve(&s,day)->release_version==16);
 assert(kb_store_init(&s,io,base,length,cache)&&s.legacy_migration&&kb_store_resolve(&s,day)->release_version==16);
 /* A complete first bank is enough to recover if its redundant copy fails. */
 empty_storage();revision(16,0);seed_legacy_candidate(0,1016);write_limit=1;
 assert(kb_store_init(&s,io,base,length,cache)&&s.directory_generation==1&&s.recovery_notice);write_limit=-1;
 assert(kb_store_init(&s,io,base,length,cache)&&!s.legacy_migration&&kb_store_resolve(&s,day)->release_version==16);
}
static void test_directory_bank_recovery_and_torn_commit(void){
 kb_store_t s;empty_storage();assert(kb_store_init(&s,io,base,length,cache));
 revision(2,0);begin(&s,1102,2);chunks(&s,1102);assert(kb_store_commit(&s,1102,now)==3);
 revision(3,1);begin(&s,1103,3);chunks(&s,1103);assert(kb_store_commit(&s,1103,now)==4);
 unsigned highest=KB_STORE_DIRECTORY_KEY+(unsigned)s.directory_bank;
 memory[highest][204]^=1;reset_reads();assert(kb_store_init(&s,io,base,length,cache)&&s.recovery_notice&&metadata_reads==2&&payload_reads==0);
 assert(kb_store_resolve(&s,day)->release_version==2&&kb_store_pending(&s,day,NULL)==0);
 revision(4,1);begin(&s,1104,4);chunks(&s,1104);torn_bytes=100;assert(kb_store_commit(&s,1104,now)==5);
 assert(kb_store_init(&s,io,base,length,cache)&&s.recovery_notice&&kb_store_resolve(&s,day)->release_version==2&&kb_store_pending(&s,day,NULL)==0);
 revision(4,1);begin(&s,1105,4);chunks(&s,1105);assert(kb_store_commit(&s,1105,now)==4);
 unsigned older=KB_STORE_DIRECTORY_KEY+(unsigned)(1-s.directory_bank);sizes[older]=0;
 assert(kb_store_init(&s,io,base,length,cache)&&kb_store_resolve(&s,day)->release_version==2&&kb_store_pending(&s,day,NULL)==4);
}
static void seed_reusable_bank(void){empty_storage();seed(0,2,0,1202);for(unsigned i=1;i<KB_STORE_SLOTS;i++)seed(i,i+2,1,1202+i);}
static void test_reuse_excludes_both_banks_before_overwrite(void){
 kb_store_t s;seed_reusable_bank();assert(kb_store_init(&s,io,base,length,cache));revision(10,1);reset_reads();begin(&s,1210,10);
 unsigned slot=(unsigned)s.transfer.slot,bit=1u<<slot;assert(slot==1&&write_calls==2);
 for(unsigned bank=0;bank<2;bank++)assert(!(memory[KB_STORE_DIRECTORY_KEY+bank][8]&bit));
 assert(kb_store_chunk(&s,1210,0,candidate,192,now)==0);
 memory[KB_STORE_DIRECTORY_KEY+s.directory_bank][204]^=1;
 assert(kb_store_init(&s,io,base,length,cache)&&s.recovery_notice&&!s.slots[slot].valid);
 assert(kb_store_resolve(&s,day)->release_version==2&&kb_store_pending(&s,day,NULL)==9);
 /* No payload is touched if either exclusion-bank write fails. The older
  * directory can still safely refer to the unchanged retired snapshot. */
 for(unsigned boundary=0;boundary<2;boundary++){
  seed_reusable_bank();assert(kb_store_init(&s,io,base,length,cache));revision(10,1);
  uint8_t prior[192];memcpy(prior,memory[KB_STORE_DATA_KEY+KB_STORE_STRIDE],sizeof(prior));
  if(boundary==0)torn_bytes=40;else write_limit=1;
  assert(kb_store_begin(&s,1220+boundary,10,length,kb_crc32(candidate,length),now)==5&&!s.transfer.running);write_limit=-1;
  assert(!memcmp(prior,memory[KB_STORE_DATA_KEY+KB_STORE_STRIDE],sizeof(prior)));
  if(boundary==1)memory[KB_STORE_DIRECTORY_KEY+s.directory_bank][204]^=1;
  assert(kb_store_init(&s,io,base,length,cache)&&s.recovery_notice);
  assert(kb_store_resolve(&s,day)->release_version==2&&kb_store_pending(&s,day,NULL)==9);
 }
}
static void test_restore_empty_banks_and_generation_bounds(void){
 kb_store_t s;empty_storage();seed(0,2,0,1302);seed(1,3,1,1303);assert(kb_store_init(&s,io,base,length,cache));reset_reads();
 assert(kb_store_restore(&s)&&write_calls==2&&payload_reads==0&&s.directory_masks[0]==0&&s.directory_masks[1]==0);
 memory[KB_STORE_DIRECTORY_KEY+s.directory_bank][204]^=1;
 assert(kb_store_init(&s,io,base,length,cache)&&s.recovery_notice&&kb_store_resolve(&s,day)->release_version==1&&kb_store_pending(&s,day,NULL)==0);
 /* Existing corrupt new banks never import stale legacy records. */
 revision(9,0);seed_legacy_candidate(0,1309);for(unsigned bank=0;bank<2;bank++)memory[KB_STORE_DIRECTORY_KEY+bank][0]^=1;
 assert(kb_store_init(&s,io,base,length,cache)&&!s.legacy_migration&&kb_store_resolve(&s,day)->release_version==1&&legacy_reads==0);
 empty_storage();seed(0,2,0,1302);assert(kb_store_init(&s,io,base,length,cache));write_limit=0;
 assert(!kb_store_restore(&s));write_limit=-1;assert(kb_store_init(&s,io,base,length,cache)&&kb_store_resolve(&s,day)->release_version==2);
 write_limit=1;assert(!kb_store_restore(&s));write_limit=-1;
 assert(kb_store_init(&s,io,base,length,cache)&&kb_store_resolve(&s,day)->release_version==1);
 for(unsigned bank=0;bank<2;bank++){uint8_t *b=memory[KB_STORE_DIRECTORY_KEY+bank];put(b+4,UINT32_MAX);b[8]=0;memset(b+12,0,192);put(b+204,kb_crc32(b,204));}
 assert(kb_store_init(&s,io,base,length,cache)&&s.directory_generation==UINT32_MAX);revision(4,0);reset_reads();
 assert(kb_store_begin(&s,1304,4,length,kb_crc32(candidate,length),now)==5&&!kb_store_restore(&s)&&write_calls==0);
}
static void test_directory_rejects_coherent_contradictions(void){
 kb_store_t s;empty_storage();seed(0,2,0,1402);
 /* An invalid entry length remains invalid even with a recomputed CRC. */
 uint8_t *highest=memory[KB_STORE_DIRECTORY_KEY+1];put(highest+16,KB_MAX_DATASET_BYTES+1);put(highest+204,kb_crc32(highest,204));
 assert(kb_store_init(&s,io,base,length,cache)&&s.recovery_notice&&kb_store_resolve(&s,day)->release_version==2);
 /* Conflicting equal-generation snapshots cannot arise from atomic writer. */
 memcpy(highest,memory[KB_STORE_DIRECTORY_KEY],KB_STORE_DIRECTORY_SIZE);put(highest+12,3);put(highest+204,kb_crc32(highest,204));
 assert(kb_store_init(&s,io,base,length,cache)&&s.recovery_notice&&s.directory_generation==UINT32_MAX&&kb_store_resolve(&s,day)->release_version==1);
 revision(4,0);assert(kb_store_begin(&s,1404,4,length,kb_crc32(candidate,length),now)==5);
}
static void test_read_failure_never_replaces_existing_directory(void){
 kb_store_t s;empty_storage();seed(0,2,0,1502);seed(1,3,1,1503);read_fail_key=-2;reset_reads();
 assert(kb_store_init(&s,io,base,length,cache)&&s.recovery_notice);
 assert(metadata_reads==2&&legacy_reads==0&&write_calls==0&&remove_calls==0&&kb_store_resolve(&s,day)->release_version==1);
 revision(4,0);assert(kb_store_begin(&s,1504,4,length,kb_crc32(candidate,length),now)==5&&!kb_store_restore(&s)&&write_calls==0);
 read_fail_key=-1;assert(kb_store_init(&s,io,base,length,cache)&&kb_store_resolve(&s,day)->release_version==2&&kb_store_pending(&s,day,NULL)==3);
 empty_storage();revision(16,0);seed_legacy_candidate(0,1516);revision(17,1);seed_legacy_candidate(1,1517);read_fail_key=KB_STORE_META_KEY+1;reset_reads();
 assert(kb_store_init(&s,io,base,length,cache)&&s.recovery_notice&&s.legacy_migration);
 assert(write_calls==0&&remove_calls==0&&sizes[KB_STORE_META_KEY+1]==40&&sizes[KB_STORE_DIRECTORY_KEY]==0);
 revision(18,1);assert(kb_store_begin(&s,1518,18,length,kb_crc32(candidate,length),now)==5&&!kb_store_restore(&s)&&write_calls==0);
 read_fail_key=-1;assert(kb_store_init(&s,io,base,length,cache)&&kb_store_resolve(&s,day)->release_version==16&&kb_store_pending(&s,day,NULL)==17);
}
int main(int argc,char **argv){assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);length=fread(base,1,sizeof(base),f);fclose(f);kb_dataset_t ds;assert(kb_dataset_open(&ds,base,length)==KB_OK);day=ds.effective_from;now=kb_service_epoch(day,600);kb_store_t s;assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_resolve(&s,day)->release_version==1);
 revision(2,0);begin(&s,22,2);assert(kb_store_chunk(&s,23,0,candidate,192,now)==2);assert(kb_store_chunk(&s,22,1,candidate+192,192,now)==1);assert(kb_store_chunk(&s,22,0,candidate,192,now)==0);assert(kb_store_chunk(&s,22,0,candidate,192,now)==0);assert(kb_store_commit(&s,22,now)==2);chunks(&s,22);assert(kb_store_commit(&s,22,now)==3);assert(kb_store_commit(&s,22,now)==3);assert(kb_store_resolve(&s,day)->release_version==2);
 revision(3,1);begin(&s,33,3);chunks(&s,33);assert(kb_store_commit(&s,33,now)==4);assert(kb_store_resolve(&s,day)->release_version==2);assert(kb_store_resolve(&s,day+1)->release_version==3);
 revision(4,2);begin(&s,44,4);assert(kb_store_chunk(&s,44,0,candidate,192,now)==0);assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_resolve(&s,day)->release_version==2);assert(kb_store_pending(&s,day,NULL)==3);
 begin(&s,45,4);chunks(&s,45);memory[1000+s.transfer.slot*256][30]^=1;assert(kb_store_commit(&s,45,now)==2);assert(kb_store_pending(&s,day,NULL)==3);
 begin(&s,46,4);chunks(&s,46);write_limit=0;assert(kb_store_commit(&s,46,now)==5);write_limit=-1;assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_resolve(&s,day)->release_version==2);assert(kb_store_pending(&s,day,NULL)==3);
 begin(&s,47,4);assert(kb_store_tick(&s,now+31));assert(!s.transfer.running);assert(kb_store_begin(&s,48,4,32769,0,now)==2);
 revision(4,0);begin(&s,49,4);chunks(&s,49);assert(kb_store_commit(&s,49,now)==2);assert(kb_store_pending(&s,day,NULL)==3);
 revision(5,1);begin(&s,50,5);chunks(&s,50);assert(kb_store_commit(&s,50,now)==4);revision(4,0);begin(&s,51,4);chunks(&s,51);assert(kb_store_commit(&s,51,now)==3);assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_resolve(&s,day)->release_version==4);assert(kb_store_resolve(&s,day+1)->release_version==5);
 /* Corrupt newest future payload: previous complete future remains valid. */
 for(int i=0;i<8;i++)if(s.slots[i].valid&&s.slots[i].version==5)corrupt_payload((unsigned)i);
 assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_resolve(&s,day)->release_version==4);assert(kb_store_resolve(&s,day+1)->release_version==3&&s.recovery_notice);
 kb_store_io_t small=io;small.capacity=4096;assert(kb_store_init(&s,small,base,length,cache));revision(6,2);assert(kb_store_begin(&s,66,6,length,kb_crc32(candidate,length),now)==5);
 /* Repeated future corrections cannot exhaust the slot bank: preserve the
  * winning future, one recovery copy, and the active date during staging. */
 memset(sizes,0,sizeof(sizes));assert(kb_store_init(&s,io,base,length,cache));
 revision(2,0);begin(&s,102,2);chunks(&s,102);assert(kb_store_commit(&s,102,now)==3);
 for(unsigned v=3;v<=20;v++){revision(v,1);assert(kb_store_has_staging(&s,day));begin(&s,100+v,v);chunks(&s,100+v);assert(kb_store_commit(&s,100+v,now)==4);assert(kb_store_resolve(&s,day)->release_version==2);assert(kb_store_pending(&s,day,NULL)==v);}
 revision(21,1);begin(&s,121,21);assert(kb_store_chunk(&s,121,0,candidate,192,now)==0);assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_pending(&s,day,NULL)==20);
 for(int i=0;i<8;i++)if(s.slots[i].valid&&s.slots[i].version==20)corrupt_payload((unsigned)i);
 assert(kb_store_init(&s,io,base,length,cache));assert(kb_store_resolve(&s,day)->release_version==2);assert(kb_store_pending(&s,day,NULL)==19);
 /* Distinct future effective dates remain protected when all eight slots
  * are genuinely necessary; expose the capacity state without eviction. */
 memset(sizes,0,sizeof(sizes));assert(kb_store_init(&s,io,base,length,cache));
 for(unsigned v=2;v<=9;v++){revision(v,v-2);begin(&s,200+v,v);chunks(&s,200+v);assert(kb_store_commit(&s,200+v,now)==(v==2?3:4));}
 assert(!kb_store_has_staging(&s,day));revision(10,8);assert(kb_store_begin(&s,210,10,length,kb_crc32(candidate,length),now)==5);assert(kb_store_resolve(&s,day)->release_version==2);assert(kb_store_pending(&s,day,NULL)==3);
 test_lazy_init_and_bounded_step();test_sole_good_future_survives_unchecked_corrupt_corrections();test_pending_and_duplicate_commit_validate_before_claim();test_eight_bad_descriptors_do_not_activate_baseline_early();test_current_metadata_and_identity_after_pending_replaces_cache();test_checked_reload_still_validates_payload_and_schema();test_capacity_and_newest_validate_all_candidates();
 test_legacy_import_is_one_time_and_preserves_versions();test_directory_bank_recovery_and_torn_commit();test_reuse_excludes_both_banks_before_overwrite();test_restore_empty_banks_and_generation_bounds();test_directory_rejects_coherent_contradictions();test_read_failure_never_replaces_existing_directory();
 puts("storage: transfer/recovery, 7 lazy-validation regressions, and 6 atomic-directory/migration suites PASS");return 0;}
