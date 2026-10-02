#include "../src/c/extras.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t store[2][64];
static int lengths[2];
static int fail_writes;
static int rd(void *c,uint32_t k,void *b,size_t n) {
  (void)c;
  if(k<KB_EXTRAS_KEY||k>KB_EXTRAS_KEY+1||!lengths[k-KB_EXTRAS_KEY])return -9;
  int len=lengths[k-KB_EXTRAS_KEY];
  memcpy(b,store[k-KB_EXTRAS_KEY],(size_t)len<n?(size_t)len:n);
  return len;
}
static int wr(void *c,uint32_t k,const void *b,size_t n) {
  (void)c;
  if(fail_writes)return -1;
  memcpy(store[k-KB_EXTRAS_KEY],b,n);lengths[k-KB_EXTRAS_KEY]=(int)n;
  return (int)n;
}
static bool exists(void *c,uint16_t id) {
  (void)c;
  return id==1||id==2||id==101;
}
int main(void) {
  kb_extras_t e,out;
  uint8_t b[KB_EXTRAS_WIRE_BYTES];
  kb_extras_default(&e);
  assert(e.buttons[KB_BUTTON_UP]==KB_ACTION_FAVOURITE&&e.buttons[KB_BUTTON_DOWN]==KB_ACTION_NEXT);
  assert(e.buttons[KB_BUTTON_HOLD_UP]==KB_ACTION_FLIP&&e.buttons[KB_BUTTON_HOLD_DOWN]==KB_ACTION_NEARBY);
  assert(e.more==2&&!e.flags);
  /* Round trip, including enabled features with known points. */
  e.flags=KB_EXTRAS_PROFILES|KB_EXTRAS_COMMUTE;
  e.profile_a=1;e.profile_b=2;e.commute_point=101;e.commute_minute=7*60+40;e.heads_up=5;
  kb_extras_encode(&e,b);
  assert(kb_extras_parse(&out,b,sizeof(b),exists,NULL));
  assert(!memcmp(&out,&e,sizeof(e)));
  /* Rejections: length, schema, action, reserved, ranges, unknown points. */
  assert(!kb_extras_parse(&out,b,sizeof(b)-1,exists,NULL));
  uint8_t bad[KB_EXTRAS_WIRE_BYTES];
  unsigned offsets[]={0,1,5,6,7,10,11,14,15,20,21,27};
  uint8_t values[]={2,KB_ACTION_COUNT,4,3,31,24,1,24,1,128,1,1};
  for(unsigned i=0;i<sizeof(offsets)/sizeof(offsets[0]);i++) {
    memcpy(bad,b,sizeof(b));bad[offsets[i]]=values[i];
    assert(!kb_extras_parse(&out,bad,sizeof(bad),exists,NULL));
  }
  memcpy(bad,b,sizeof(b));bad[18]=0xa0;bad[19]=0x05; /* 1440 */
  assert(!kb_extras_parse(&out,bad,sizeof(bad),exists,NULL));
  memcpy(bad,b,sizeof(b));bad[16]=9; /* unknown commute point */
  assert(!kb_extras_parse(&out,bad,sizeof(bad),exists,NULL));
  assert(kb_extras_parse(&out,bad,sizeof(bad),NULL,NULL));
  memcpy(bad,b,sizeof(b));bad[14]=bad[10]; /* equal profile hours */
  assert(!kb_extras_parse(&out,bad,sizeof(bad),exists,NULL));
  memcpy(bad,b,sizeof(b));bad[20]=0; /* commute without days */
  assert(!kb_extras_parse(&out,bad,sizeof(bad),exists,NULL));
  /* Disabled features ignore their unused points. */
  memcpy(bad,b,sizeof(b));bad[5]=0;bad[8]=0;bad[16]=0;bad[20]=0;
  assert(kb_extras_parse(&out,bad,sizeof(bad),exists,NULL));
  /* Profiles: A from its hour until B's, including wrap past midnight. */
  e.profile_a_hour=4;e.profile_b_hour=15;
  assert(kb_extras_profile_point(&e,8)==1&&kb_extras_profile_point(&e,15)==2&&kb_extras_profile_point(&e,2)==2);
  e.profile_a_hour=20;e.profile_b_hour=6;
  assert(kb_extras_profile_point(&e,7)==2&&kb_extras_profile_point(&e,21)==1&&kb_extras_profile_point(&e,3)==1);
  e.flags=0;
  assert(kb_extras_profile_point(&e,8)==0);
  /* Persistence: empty loads defaults, banks alternate, newest wins,
   * corruption falls back to the other bank, failed writes keep state. */
  uint32_t gen;uint8_t slot;
  assert(!kb_extras_load(&out,&gen,&slot,rd,NULL)&&out.more==2&&!gen);
  kb_extras_default(&e);e.more=1;
  assert(kb_extras_commit(&out,&e,&gen,&slot,wr,NULL)&&gen==1&&slot==0);
  e.more=0;
  assert(kb_extras_commit(&out,&e,&gen,&slot,wr,NULL)&&gen==2&&slot==1);
  assert(kb_extras_load(&out,&gen,&slot,rd,NULL)&&gen==2&&slot==1&&out.more==0);
  store[1][20]^=1;
  assert(kb_extras_load(&out,&gen,&slot,rd,NULL)&&gen==1&&slot==0&&out.more==1);
  fail_writes=1;e.more=2;
  assert(!kb_extras_commit(&out,&e,&gen,&slot,wr,NULL)&&gen==1&&out.more==1);
  fail_writes=0;
  e.buttons[0]=KB_ACTION_COUNT;
  assert(!kb_extras_commit(&out,&e,&gen,&slot,wr,NULL));
  printf("extras: defaults, round trip, 16 rejections, profiles, two-bank persistence PASS\n");
  return 0;
}
