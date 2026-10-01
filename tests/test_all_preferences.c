#include "../src/c/all_preferences.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t records[2][81];
static int lengths[2],failure;
static unsigned reads,writes,short_write;
static int read_record(void *ctx,uint32_t key,void *b,size_t n) {
  (void)ctx;assert(key==12||key==13);assert(n==81);reads++;
  unsigned bank=key-12;if(!lengths[bank])return -9;
  memcpy(b,records[bank],(size_t)lengths[bank]);return lengths[bank];
}
static int write_record(void *ctx,uint32_t key,const void *b,size_t n) {
  (void)ctx;assert(key==12||key==13);assert(n==80);writes++;
  if(failure)return -6;
  unsigned bank=key-12,length=short_write?short_write:80;
  memcpy(records[bank],b,length);lengths[bank]=(int)length;return (int)length;
}
static uint32_t crc(const uint8_t *b,unsigned n) {
  uint32_t value=~0u;
  for(unsigned i=0;i<n;i++){value^=b[i];for(unsigned bit=0;bit<8;bit++)value=(value&1u)?(value>>1)^0xedb88320u:value>>1;}
  return ~value;
}
static void put32(uint8_t *b,uint32_t value){for(unsigned i=0;i<4;i++)b[i]=(uint8_t)(value>>(8*i));}
static void fix(unsigned bank){put32(records[bank]+76,crc(records[bank],76));}
static void same(const kb_all_preferences_t *a,const kb_all_preferences_t *b){assert(a->reference==b->reference&&a->count==b->count&&!memcmp(a->ids,b->ids,sizeof(a->ids)));}
int main(void) {
  kb_all_preferences_t current,candidate,loaded;
  uint32_t generation=99;uint8_t slot=1;
  assert(!kb_all_preferences_load(&current,&generation,&slot,read_record,NULL));
  assert(reads==2&&writes==0&&generation==0&&slot==0);
  assert(current.reference==KB_ALL_REFERENCE_MANUAL&&current.count==0);
  candidate=current;candidate.reference=KB_ALL_REFERENCE_CURRENT;candidate.count=32;
  for(unsigned i=0;i<32;i++)candidate.ids[i]=(uint16_t)(255-i);
  assert(kb_all_preferences_commit(&current,&candidate,&generation,&slot,write_record,NULL));
  assert(generation==1&&slot==1&&lengths[1]==80&&!memcmp(records[1],"KBA1",4));same(&current,&candidate);
  reads=0;assert(kb_all_preferences_load(&loaded,&generation,&slot,read_record,NULL));
  assert(reads==2&&writes==1);same(&loaded,&candidate);
  /* A stored empty selection is valid and must never be mistaken for first use. */
  kb_all_preferences_default(&candidate);candidate.reference=KB_ALL_REFERENCE_HOME;
  assert(kb_all_preferences_commit(&current,&candidate,&generation,&slot,write_record,NULL));
  assert(kb_all_preferences_load(&loaded,&generation,&slot,read_record,NULL)&&generation==2);
  same(&loaded,&candidate);assert(loaded.count==0);
  kb_all_preferences_t saved=current;uint32_t saved_generation=generation;uint8_t saved_slot=slot;
  candidate=saved;candidate.count=2;candidate.ids[0]=101;candidate.ids[1]=2;
  failure=1;assert(!kb_all_preferences_commit(&current,&candidate,&generation,&slot,write_record,NULL));
  same(&current,&saved);assert(generation==saved_generation&&slot==saved_slot);failure=0;
  /* Every incomplete write leaves the previous empty selection recoverable. */
  for(unsigned n=1;n<80;n++) {
    short_write=n;assert(!kb_all_preferences_commit(&current,&candidate,&generation,&slot,write_record,NULL));
    same(&current,&saved);assert(generation==saved_generation&&slot==saved_slot);
    reads=0;assert(kb_all_preferences_load(&loaded,&generation,&slot,read_record,NULL)&&reads==2);
    same(&loaded,&saved);
  }
  short_write=0;assert(kb_all_preferences_commit(&current,&candidate,&generation,&slot,write_record,NULL));
  assert(kb_all_preferences_load(&loaded,&generation,&slot,read_record,NULL));same(&loaded,&candidate);
  uint8_t good[80];memcpy(good,records[slot],80);unsigned newest=slot;
  unsigned mutations[][2]={{0,'X'},{8,2},{9,3},{10,33},{11,1},{12,0},{14,101},{16,3},{13,1}};
  for(unsigned i=0;i<sizeof(mutations)/sizeof(mutations[0]);i++) {
    memcpy(records[newest],good,80);records[newest][mutations[i][0]]=(uint8_t)mutations[i][1];fix(newest);
    assert(kb_all_preferences_load(&loaded,&generation,&slot,read_record,NULL)&&generation==2);same(&loaded,&saved);
  }
  memcpy(records[newest],good,80);records[newest][79]^=1;
  assert(kb_all_preferences_load(&loaded,&generation,&slot,read_record,NULL)&&generation==2);same(&loaded,&saved);
  /* No malformed candidate can change live selection or issue any write. */
  kb_all_preferences_t bad=candidate;bad.reference=3;unsigned before=writes;
  assert(!kb_all_preferences_commit(&loaded,&bad,&generation,&slot,write_record,NULL)&&writes==before);same(&loaded,&saved);
  bad=candidate;bad.count=33;assert(!kb_all_preferences_commit(&loaded,&bad,&generation,&slot,write_record,NULL));
  bad=candidate;bad.ids[1]=bad.ids[0];assert(!kb_all_preferences_commit(&loaded,&bad,&generation,&slot,write_record,NULL));
  bad=candidate;bad.ids[0]=256;assert(!kb_all_preferences_commit(&loaded,&bad,&generation,&slot,write_record,NULL));
  bad=candidate;bad.ids[2]=3;assert(!kb_all_preferences_commit(&loaded,&bad,&generation,&slot,write_record,NULL));
  slot=2;assert(!kb_all_preferences_commit(&loaded,&candidate,&generation,&slot,write_record,NULL)&&writes==before);
  slot=0;generation=UINT32_MAX;
  assert(!kb_all_preferences_commit(&loaded,&candidate,&generation,&slot,write_record,NULL)&&writes==before);
  /* Equal generations have deterministic bank-zero precedence. */
  memcpy(records[0],good,80);memcpy(records[1],good,80);lengths[0]=lengths[1]=80;
  assert(kb_all_preferences_load(&loaded,&generation,&slot,read_record,NULL)&&slot==0);same(&loaded,&candidate);
  records[0][0]=records[1][0]='X';reads=0;
  assert(kb_all_preferences_load(&loaded,&generation,&slot,read_record,NULL)==KB_ALL_INVALID&&reads==2);
  assert(loaded.count==0&&loaded.reference==KB_ALL_REFERENCE_MANUAL&&generation==0);
  memcpy(records[0],good,80);lengths[0]=81;lengths[1]=0;
  assert(kb_all_preferences_load(&loaded,&generation,&slot,read_record,NULL)==KB_ALL_INVALID);
  assert(loaded.count==0&&loaded.reference==KB_ALL_REFERENCE_MANUAL);
  puts("all preferences: two-read/no-write load, empty-selection preservation, 32 IDs and references, all79 torn-write boundaries, CRC/schema/duplicate validation and generation protection PASS");
}
