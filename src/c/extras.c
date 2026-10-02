#include "extras.h"
#include <string.h>
static uint16_t u16(const uint8_t *b) {
  return (uint16_t)(b[0]|(b[1]<<8));
}
static void put16(uint8_t *b,uint16_t v) {
  b[0]=(uint8_t)v;b[1]=(uint8_t)(v>>8);
}
static uint32_t u32(const uint8_t *b) {
  return (uint32_t)b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);
}
static void put32(uint8_t *b,uint32_t value) {
  for(unsigned i=0;i<4;i++)b[i]=(uint8_t)(value>>(8*i));
}
static uint32_t crc(const uint8_t *b,unsigned n) {
  uint32_t value=UINT32_MAX;
  for(unsigned i=0;i<n;i++) {
    value^=b[i];
    for(unsigned bit=0;bit<8;bit++)value=(value>>1)^((0u-(value&1u))&0xedb88320u);
  }
  return ~value;
}
void kb_extras_default(kb_extras_t *e) {
  memset(e,0,sizeof(*e));
  e->buttons[KB_BUTTON_UP]=KB_ACTION_FAVOURITE;
  e->buttons[KB_BUTTON_DOWN]=KB_ACTION_NEXT;
  e->buttons[KB_BUTTON_HOLD_UP]=KB_ACTION_FLIP;
  e->buttons[KB_BUTTON_HOLD_DOWN]=KB_ACTION_NEARBY;
  e->more=2;
  e->profile_a_hour=4;
  e->profile_b_hour=15;
  e->commute_minute=8*60;
  e->commute_days=0x3e; /* Monday to Friday */
}
bool kb_extras_parse(kb_extras_t *out,const uint8_t *b,unsigned n,kb_id_exists_fn exists,void *ctx) {
  if(n!=KB_EXTRAS_WIRE_BYTES||b[0]!=1)return false;
  for(unsigned i=1;i<=4;i++)if(b[i]>=KB_ACTION_COUNT)return false;
  if(b[5]&~(KB_EXTRAS_PROFILES|KB_EXTRAS_COMMUTE)||b[6]>2||b[7]>30)return false;
  if(b[10]>23||b[11]||b[14]>23||b[15]||b[20]>127)return false;
  for(unsigned i=21;i<KB_EXTRAS_WIRE_BYTES;i++)if(b[i])return false;
  kb_extras_t e;
  memset(&e,0,sizeof(e));
  memcpy(e.buttons,b+1,4);
  e.flags=b[5];e.more=b[6];e.heads_up=b[7];
  e.profile_a=u16(b+8);e.profile_a_hour=b[10];
  e.profile_b=u16(b+12);e.profile_b_hour=b[14];
  e.commute_point=u16(b+16);e.commute_minute=u16(b+18);e.commute_days=b[20];
  if(e.commute_minute>=24*60)return false;
  if(e.flags&KB_EXTRAS_PROFILES) {
    if(!e.profile_a||!e.profile_b||e.profile_a_hour==e.profile_b_hour)return false;
    if(exists&&(!exists(ctx,e.profile_a)||!exists(ctx,e.profile_b)))return false;
  }
  if(e.flags&KB_EXTRAS_COMMUTE) {
    if(!e.commute_point||!e.commute_days)return false;
    if(exists&&!exists(ctx,e.commute_point))return false;
  }
  *out=e;
  return true;
}
void kb_extras_encode(const kb_extras_t *e,uint8_t *b) {
  memset(b,0,KB_EXTRAS_WIRE_BYTES);
  b[0]=1;
  memcpy(b+1,e->buttons,4);
  b[5]=e->flags;b[6]=e->more;b[7]=e->heads_up;
  put16(b+8,e->profile_a);b[10]=e->profile_a_hour;
  put16(b+12,e->profile_b);b[14]=e->profile_b_hour;
  put16(b+16,e->commute_point);put16(b+18,e->commute_minute);b[20]=e->commute_days;
}
bool kb_extras_load(kb_extras_t *out,uint32_t *generation,uint8_t *slot,kb_pref_read_fn read,void *context) {
  kb_extras_default(out);
  *generation=0;*slot=0;
  for(unsigned i=0;i<2;i++) {
    uint8_t b[KB_EXTRAS_RECORD_BYTES+1]={0};
    int n=read(context,KB_EXTRAS_KEY+i,b,sizeof(b));
    if(n!=KB_EXTRAS_RECORD_BYTES||memcmp(b,"KBX1",4)||!u32(b+4)||
       crc(b,KB_EXTRAS_RECORD_BYTES-4)!=u32(b+KB_EXTRAS_RECORD_BYTES-4))continue;
    /* Boarding points are checked at use: a timetable update must not
     * discard every other extra setting. */
    kb_extras_t candidate;
    if(!kb_extras_parse(&candidate,b+8,KB_EXTRAS_WIRE_BYTES,NULL,NULL))continue;
    if(u32(b+4)>*generation) {
      *out=candidate;*generation=u32(b+4);*slot=(uint8_t)i;
    }
  }
  return *generation!=0;
}
bool kb_extras_commit(kb_extras_t *out,const kb_extras_t *candidate,uint32_t *generation,uint8_t *slot,kb_pref_write_fn write,void *context) {
  uint8_t b[KB_EXTRAS_RECORD_BYTES]={0};
  kb_extras_t checked;
  kb_extras_encode(candidate,b+8);
  if(!kb_extras_parse(&checked,b+8,KB_EXTRAS_WIRE_BYTES,NULL,NULL)||*generation==UINT32_MAX||*slot>1)return false;
  memcpy(b,"KBX1",4);put32(b+4,*generation+1);
  put32(b+KB_EXTRAS_RECORD_BYTES-4,crc(b,KB_EXTRAS_RECORD_BYTES-4));
  uint8_t next=(uint8_t)(*generation?1-*slot:0);
  if(write(context,KB_EXTRAS_KEY+next,b,sizeof(b))!=(int)sizeof(b))return false;
  *out=checked;(*generation)++;*slot=next;
  return true;
}
uint16_t kb_extras_profile_point(const kb_extras_t *e,unsigned hour) {
  if(!(e->flags&KB_EXTRAS_PROFILES))return 0;
  unsigned a=e->profile_a_hour,b=e->profile_b_hour;
  bool in_b=a<b?(hour>=b||hour<a):(hour>=b&&hour<a);
  return in_b?e->profile_b:e->profile_a;
}
