#include "../src/c/preferences.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static bool exists(void *ctx,uint16_t id){return id<=(uintptr_t)ctx;}
static uint8_t records[2][108];static int lengths[2];static bool fail_write;
static unsigned read_count,write_count,read_keys[8],short_write;
static int rd(void *c,uint32_t key,void *b,size_t n){(void)c;assert(key==10||key==11);if(read_count<8)read_keys[read_count]=key;read_count++;if(!lengths[key-10])return -9;size_t copied=(size_t)lengths[key-10];if(copied>n)copied=n;memcpy(b,records[key-10],copied);return (int)copied;}
static int wr(void *c,uint32_t key,const void *b,size_t n){(void)c;assert(key==10||key==11);write_count++;if(fail_write)return -6;size_t copied=short_write&&short_write<n?short_write:n;memcpy(records[key-10],b,copied);lengths[key-10]=(int)copied;return (int)copied;}
static void reset_records(void){memset(records,0,sizeof(records));memset(lengths,0,sizeof(lengths));fail_write=false;short_write=0;read_count=write_count=0;}
static void fixture_u32(uint8_t *bytes,uint32_t value){for(unsigned i=0;i<4;i++)bytes[i]=(uint8_t)(value>>(8*i));}
static uint32_t fixture_crc(const uint8_t *bytes,unsigned n){uint32_t crc=~0u;for(unsigned i=0;i<n;i++){crc^=bytes[i];for(unsigned bit=0;bit<8;bit++)crc=(crc&1)?(crc>>1)^0xedb88320u:crc>>1;}return ~crc;}
static void fix_crc(unsigned bank){unsigned prefix=lengths[bank]==108?104:lengths[bank]==104?100:88;fixture_u32(records[bank]+prefix,fixture_crc(records[bank],prefix));}
static void assert_control(const kb_control_t *left,const kb_control_t *right){assert(!memcmp(left->preferences.bytes,right->preferences.bytes,80));assert(left->last_attempt==right->last_attempt);assert(left->last_success==right->last_success);assert(left->update_request==right->update_request);assert(left->hint_seen==right->hint_seen);}
static void test_control_atomic_and_retained_fields(void){
  reset_records();kb_control_t current,candidate,reopened;uint32_t generation=99;uint8_t slot=1;
  assert(kb_control_load(&current,&generation,&slot,rd,NULL)==KB_CONTROL_EMPTY);
  assert(read_count==2&&read_keys[0]==10&&read_keys[1]==11);
  assert(generation==0&&slot==0&&kb_pref_default(&current.preferences)==1);
  assert(current.last_attempt==0&&current.last_success==0&&current.update_request==0&&!current.hint_seen);
  candidate=current;candidate.last_attempt=1790859000u;candidate.last_success=1790800000u;candidate.update_request=0x80000000u;candidate.hint_seen=true;
  candidate.preferences.bytes[32]=1;candidate.preferences.bytes[34]=7;
  assert(kb_control_commit(&current,&candidate,&generation,&slot,wr,NULL));
  assert(generation==1&&slot==1&&lengths[1]==108&&!memcmp(records[1],"KBW2",4));
  assert_control(&current,&candidate);
  candidate=current;candidate.preferences.bytes[4]=9;
  assert(kb_control_commit(&current,&candidate,&generation,&slot,wr,NULL));
  assert(current.last_attempt==1790859000u&&current.last_success==1790800000u&&current.update_request==0x80000000u&&current.hint_seen);
  candidate=current;candidate.last_attempt+=1000;candidate.last_success+=1500;
  assert(kb_control_commit(&current,&candidate,&generation,&slot,wr,NULL));
  assert(kb_pref_default(&current.preferences)==1&&kb_pref_walk(&current.preferences,1)==7&&current.preferences.bytes[4]==9);
  read_count=0;assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT);
  assert(read_count==2&&read_keys[0]==10&&read_keys[1]==11);assert_control(&reopened,&current);
  candidate=current;candidate.last_attempt+=2000;candidate.update_request++;candidate.preferences.bytes[34]=12;
  uint32_t saved_generation=generation;uint8_t saved_slot=slot;kb_control_t saved=current;
  fail_write=true;assert(!kb_control_commit(&current,&candidate,&generation,&slot,wr,NULL));
  assert_control(&current,&saved);assert(generation==saved_generation&&slot==saved_slot);
  fail_write=false;short_write=107;assert(!kb_control_commit(&current,&candidate,&generation,&slot,wr,NULL));
  assert_control(&current,&saved);assert(generation==saved_generation&&slot==saved_slot);
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT);assert_control(&reopened,&saved);
  short_write=0;assert(kb_control_commit(&current,&candidate,&generation,&slot,wr,NULL));
  records[slot][104]^=1;
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT);assert_control(&reopened,&saved);
  unsigned writes=write_count;candidate=reopened;candidate.preferences.bytes[1]=KB_PREF_NEARBY_START;
  assert(!kb_control_commit(&reopened,&candidate,&generation,&slot,wr,NULL)&&writes==write_count);
  assert_control(&reopened,&saved);
}
static void test_control_legacy_migration_and_generation(void){
  reset_records();kb_preferences_t legacy;kb_preferences_default(&legacy,101);
  legacy.bytes[5]=2;legacy.bytes[10]=102;legacy.bytes[32]=101;legacy.bytes[34]=8;
  legacy.bytes[36]=102;legacy.bytes[38]=0;uint32_t generation=0;uint8_t slot=0;
  assert(kb_preferences_commit(&legacy,&legacy,&generation,&slot,wr,NULL));
  kb_control_t current,candidate,reopened;
  read_count=0;assert(kb_control_load(&current,&generation,&slot,rd,NULL)==KB_CONTROL_LEGACY);
  assert(read_count==2&&generation==1&&slot==1);
  assert(kb_pref_default(&current.preferences)==101&&kb_pref_favourite(&current.preferences,1)==102);
  assert(kb_pref_walk(&current.preferences,101)==8&&kb_pref_walk(&current.preferences,102)==0);
  assert(current.last_attempt==0&&current.last_success==0&&current.update_request==0&&!current.hint_seen);
  candidate=current;candidate.last_attempt=1790800001u;candidate.last_success=1790790000u;candidate.update_request=22;candidate.hint_seen=true;
  assert(kb_control_commit(&current,&candidate,&generation,&slot,wr,NULL));
  read_count=0;assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT);
  assert(read_count==2&&generation==2&&slot==0);assert_control(&reopened,&candidate);
  /* At an equal generation the complete control record wins in either bank. */
  fixture_u32(records[0]+4,1);fix_crc(0);
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&slot==0);
  uint8_t swap[108];memcpy(swap,records[0],108);memcpy(records[0],records[1],108);memcpy(records[1],swap,108);
  lengths[0]=92;lengths[1]=108;
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&slot==1);
  assert_control(&reopened,&candidate);
  fixture_u32(records[1]+4,UINT32_MAX);fix_crc(1);
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&generation==UINT32_MAX);
  unsigned writes=write_count;assert(!kb_control_commit(&reopened,&candidate,&generation,&slot,wr,NULL)&&write_count==writes);
  assert_control(&reopened,&candidate);
}
static void test_control_invalid_records(void){
  reset_records();kb_control_t current,candidate,reopened;uint32_t generation=0;uint8_t slot=0;
  assert(kb_control_load(&current,&generation,&slot,rd,NULL)==KB_CONTROL_EMPTY);
  candidate=current;candidate.last_success=0xffffffffu;candidate.update_request=UINT32_MAX;candidate.hint_seen=true;
  assert(kb_control_commit(&current,&candidate,&generation,&slot,wr,NULL));
  candidate=current;candidate.last_attempt=0x80000000u;
  assert(kb_control_commit(&current,&candidate,&generation,&slot,wr,NULL));
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT);
  assert(reopened.last_success==0xffffffffu&&reopened.last_attempt==0x80000000u&&reopened.update_request==UINT32_MAX);
  uint8_t valid[108];memcpy(valid,records[slot],108);unsigned newest=slot;
  /* Valid checksums do not authorize malformed flags or preferences. */
  fixture_u32(records[newest]+96,2);fix_crc(newest);
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&generation==1);
  memcpy(records[newest],valid,108);records[newest][8+1]=KB_PREF_NEARBY_START;fix_crc(newest);
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&generation==1);
  memcpy(records[newest],valid,108);fixture_u32(records[newest]+4,0);fix_crc(newest);
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&generation==1);
  memcpy(records[newest],valid,108);records[newest][0]='X';fix_crc(newest);
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&generation==1);
  memset(records,0,sizeof(records));lengths[0]=lengths[1]=108;read_count=0;
  assert(kb_control_load(&reopened,&generation,&slot,rd,NULL)==KB_CONTROL_EMPTY&&read_count==2);
  assert(generation==0&&slot==0&&reopened.last_attempt==0&&reopened.last_success==0&&reopened.update_request==0&&!reopened.hint_seen);
  slot=2;unsigned writes=write_count;assert(!kb_control_commit(&reopened,&candidate,&generation,&slot,wr,NULL)&&write_count==writes);
}
/* Isolated compatibility fixtures use the documented three record formats. */
static void fixture_control(unsigned bank,unsigned rank,uint32_t generation,const kb_control_t *value){
  memset(records[bank],0,sizeof(records[bank]));
  memcpy(records[bank],rank==3?"KBW2":rank==2?"KBW1":"KBP1",4);
  fixture_u32(records[bank]+4,generation);memcpy(records[bank]+8,value->preferences.bytes,80);
  lengths[bank]=rank==3?108:rank==2?104:92;
  if(rank>=2){fixture_u32(records[bank]+88,value->last_attempt);fixture_u32(records[bank]+92,value->last_success);fixture_u32(records[bank]+96,value->hint_seen?1u:0u);}
  if(rank==3)fixture_u32(records[bank]+100,value->update_request);
  fix_crc(bank);
}
static void test_kbw1_compatibility_and_format_precedence(void){
  kb_control_t old={0},other={0},loaded;kb_preferences_default(&old.preferences,101);kb_preferences_default(&other.preferences,102);
  old.last_attempt=0x80000000u;old.last_success=UINT32_MAX;old.hint_seen=true;old.update_request=77;
  uint32_t generation;uint8_t slot;
  reset_records();fixture_control(1,2,7,&old);
  assert(kb_control_load(&loaded,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&generation==7&&slot==1);
  assert(read_count==2&&write_count==0&&loaded.update_request==0);
  kb_control_t expected=old;expected.update_request=0;assert_control(&loaded,&expected);
  expected.update_request=1;assert(kb_control_commit(&loaded,&expected,&generation,&slot,wr,NULL));
  assert(lengths[slot]==108&&!memcmp(records[slot],"KBW2",4));
  assert(kb_control_load(&loaded,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&generation==8);assert_control(&loaded,&expected);
  /* All format pairs select the richer record regardless of bank order. */
  for(unsigned higher=2;higher<=3;higher++)for(unsigned lower=1;lower<higher;lower++){
    reset_records();fixture_control(0,higher,7,&old);fixture_control(1,lower,7,&other);
    assert(kb_control_load(&loaded,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&slot==0&&generation==7);
    expected=old;expected.update_request=higher==3?77:0;assert_control(&loaded,&expected);
    uint8_t swap[108];memcpy(swap,records[0],108);memcpy(records[0],records[1],108);memcpy(records[1],swap,108);
    int length_swap=lengths[0];lengths[0]=lengths[1];lengths[1]=length_swap;
    assert(kb_control_load(&loaded,&generation,&slot,rd,NULL)==KB_CONTROL_CURRENT&&slot==1&&generation==7);assert_control(&loaded,&expected);
  }
  /* Generation ordering takes precedence over format richness. */
  reset_records();fixture_control(0,3,7,&old);fixture_control(1,1,8,&other);
  assert(kb_control_load(&loaded,&generation,&slot,rd,NULL)==KB_CONTROL_LEGACY&&generation==8&&slot==1);
  assert_control(&loaded,&other);
}
int main(void){kb_preferences_t a,b;kb_preferences_default(&a,1);assert(kb_pref_default(&a)==1);assert(kb_pref_walk(&a,1)==-1);assert(kb_preferences_parse(&b,a.bytes,80,exists,(void*)3));a.bytes[32]=1;a.bytes[34]=5;assert(kb_preferences_parse(&b,a.bytes,80,exists,(void*)3));assert(kb_pref_walk(&b,1)==5);a.bytes[34]=255;assert(!kb_preferences_parse(&b,a.bytes,80,exists,(void*)3));assert(kb_pref_walk(&b,1)==5);assert(!kb_preferences_parse(&b,a.bytes,79,exists,(void*)3));a.bytes[34]=5;a.bytes[5]=2;a.bytes[10]=1;assert(!kb_preferences_parse(&b,a.bytes,80,exists,(void*)3));assert(kb_pref_missing(&b,exists,(void*)0)==3);
 uint32_t generation=0;uint8_t slot=0;kb_preferences_default(&a,1);assert(kb_preferences_commit(&a,&b,&generation,&slot,wr,NULL));assert(generation==1&&kb_pref_walk(&a,1)==5);kb_preferences_t candidate=b;candidate.bytes[34]=8;fail_write=true;assert(!kb_preferences_commit(&a,&candidate,&generation,&slot,wr,NULL));assert(generation==1&&kb_pref_walk(&a,1)==5);kb_preferences_load(&a,&generation,&slot,rd,NULL);assert(generation==1&&kb_pref_walk(&a,1)==5);fail_write=false;assert(kb_preferences_commit(&a,&candidate,&generation,&slot,wr,NULL));assert(generation==2&&kb_pref_walk(&a,1)==8);records[slot][88]^=1;kb_preferences_load(&a,&generation,&slot,rd,NULL);assert(generation==1&&kb_pref_walk(&a,1)==5);test_control_atomic_and_retained_fields();test_control_legacy_migration_and_generation();test_control_invalid_records();test_kbw1_compatibility_and_format_precedence();puts("preferences/control: atomic banks, torn writes/checksums, durable uint32 requests, retained timestamps/settings, KBW2/KBW1/KBP1 compatibility and precedence, two-read load, generation/flags PASS");}
