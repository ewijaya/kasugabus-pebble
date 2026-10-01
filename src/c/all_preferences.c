#include "all_preferences.h"
#include <string.h>
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
void kb_all_preferences_default(kb_all_preferences_t *p) {
  memset(p,0,sizeof(*p));
  p->reference=KB_ALL_REFERENCE_MANUAL;
}
static bool valid(const kb_all_preferences_t *p) {
  if(p->count>KB_ALL_MAX_POINTS||p->reference>KB_ALL_REFERENCE_MANUAL)return false;
  for(unsigned i=0;i<KB_ALL_MAX_POINTS;i++) {
    if(i>=p->count) {
      if(p->ids[i])return false;
    }
    else {
      if(!p->ids[i]||p->ids[i]>255)return false;
      for(unsigned j=0;j<i;j++)if(p->ids[j]==p->ids[i])return false;
    }
  }
  return true;
}
kb_all_load_result_t kb_all_preferences_load(kb_all_preferences_t *out,uint32_t *generation,uint8_t *slot,kb_pref_read_fn read,void *context) {
  kb_all_preferences_default(out);
  *generation=0;*slot=0;
  bool present=false;
  for(unsigned i=0;i<2;i++) {
    uint8_t b[KB_ALL_PREFERENCES_RECORD_BYTES+1]={0};
    int n=read(context,KB_ALL_PREFERENCES_KEY+i,b,sizeof(b));
    if(n==-9)continue;
    present=true;
    if(n!=KB_ALL_PREFERENCES_RECORD_BYTES||
      memcmp(b,"KBA1",4)||b[8]!=1||b[11]||crc(b,76)!=u32(b+76)||!u32(b+4))continue;
    kb_all_preferences_t candidate={0};candidate.reference=b[9];candidate.count=b[10];
    for(unsigned n=0;n<KB_ALL_MAX_POINTS;n++)candidate.ids[n]=b[12+2*n]|((uint16_t)b[13+2*n]<<8);
    if(!valid(&candidate))continue;
    if(u32(b+4)>*generation) {
      *out=candidate;*generation=u32(b+4);*slot=(uint8_t)i;
    }
  }
  return *generation?KB_ALL_SAVED:present?KB_ALL_INVALID:KB_ALL_EMPTY;
}
bool kb_all_preferences_commit(kb_all_preferences_t *out,const kb_all_preferences_t *candidate,uint32_t *generation,uint8_t *slot,kb_pref_write_fn write,void *context) {
  if(!valid(candidate)||*generation==UINT32_MAX||*slot>1)return false;
  uint8_t b[KB_ALL_PREFERENCES_RECORD_BYTES]={0};
  memcpy(b,"KBA1",4);put32(b+4,*generation+1);b[8]=1;b[9]=candidate->reference;b[10]=candidate->count;
  for(unsigned i=0;i<candidate->count;i++) {
    b[12+2*i]=(uint8_t)candidate->ids[i];b[13+2*i]=(uint8_t)(candidate->ids[i]>>8);
  }
  put32(b+76,crc(b,76));uint8_t next=(uint8_t)(1-*slot);
  if(write(context,KB_ALL_PREFERENCES_KEY+next,b,sizeof(b))!=(int)sizeof(b))return false;
  *out=*candidate;(*generation)++;*slot=next;
  return true;
}
