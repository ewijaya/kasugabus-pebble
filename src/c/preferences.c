#include "preferences.h"
#include <string.h>
static uint16_t u16(const uint8_t *p) {
  return p[0]|((uint16_t)p[1]<<8);
}
static void put16(uint8_t *p,uint16_t n) {
  p[0]=n;
  p[1]=n>>8;
}
void kb_preferences_default(kb_preferences_t *p,uint16_t id) {
  memset(p,0,sizeof(*p));
  p->bytes[0]=1;
  p->bytes[1]=KB_PREF_AUTO;
  p->bytes[4]=2;
  p->bytes[5]=id?1:0;
  put16(p->bytes+2,id);
  put16(p->bytes+8,id);
}
uint16_t kb_pref_default(const kb_preferences_t *p) {
  return u16(p->bytes+2);
}
uint16_t kb_pref_favourite(const kb_preferences_t *p,unsigned n) {
  return n<p->bytes[5]?u16(p->bytes+8+2*n):0;
}
int kb_pref_walk(const kb_preferences_t *p,uint16_t id) {
  for(unsigned i=0;i<12;i++)if(u16(p->bytes+32+4*i)==id&&id)return p->bytes[34+4*i];
  return -1;
}
bool kb_preferences_parse(kb_preferences_t *out,const uint8_t *b,unsigned n,kb_id_exists_fn exists,void *ctx) {
  if(n!=80||b[0]!=1||(b[1]&~31)||b[4]>30||b[5]>12||b[6]||b[7])return false;
  if((b[1]&KB_PREF_NEARBY_START)&&!(b[1]&KB_PREF_LOCATION))return false;
  uint16_t id=u16(b+2);
  if(id&&exists&&!exists(ctx,id))return false;
  for(unsigned i=0;i<12;i++) {
    id=u16(b+8+2*i);
    if(i<b[5]) {
      if(!id||(exists&&!exists(ctx,id)))return false;
      for(unsigned j=0;j<i;j++)if(u16(b+8+2*j)==id)return false;
    }
    else if(id)return false;
    id=u16(b+32+4*i);
    if(b[35+4*i]||b[34+4*i]>120)return false;
    if(!id&&b[34+4*i])return false;
    if(id) {
      if(exists&&!exists(ctx,id))return false;
      for(unsigned j=0;j<i;j++)if(u16(b+32+4*j)==id)return false;
    }
  }
  memcpy(out->bytes,b,80);
  return true;
}
unsigned kb_pref_missing(const kb_preferences_t *p,kb_id_exists_fn exists,void *ctx) {
  unsigned n=0;
  if(kb_pref_default(p)&&!exists(ctx,kb_pref_default(p)))n++;
  for(unsigned i=0;i<p->bytes[5];i++)if(!exists(ctx,kb_pref_favourite(p,i)))n++;
  for(unsigned i=0;i<12;i++) {
    uint16_t id=u16(p->bytes+32+i*4);
    if(id&&!exists(ctx,id))n++;
  }
  return n;
}
static uint32_t pref_u32(const uint8_t *b) {
  return (uint32_t)b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);
}
static void pref_put32(uint8_t *b,uint32_t v) {
  for(unsigned i=0;i<4;i++)b[i]=v>>(8*i);
}
static uint32_t pref_crc(const uint8_t *b,size_t n) {
  uint32_t crc=0xffffffffu;
  for(size_t i=0;i<n;i++) {
    crc^=b[i];
    for(unsigned j=0;j<8;j++)crc=(crc>>1)^((0u-(crc&1))&0xedb88320u);
  }
  return ~crc;
}
kb_control_load_result_t kb_control_load(kb_control_t *out,uint32_t *generation,uint8_t *slot,kb_pref_read_fn read,void *ctx) {
  memset(out,0,sizeof(*out));
  kb_preferences_default(&out->preferences,1);
  *generation=0;
  *slot=0;
  kb_control_load_result_t result=KB_CONTROL_EMPTY;
  unsigned selected_rank=0;
  for(unsigned i=0;i<2;i++) {
    uint8_t bytes[108]={0};
    int length=read(ctx,10+i,bytes,sizeof(bytes));
    kb_control_t candidate={0};
    kb_control_load_result_t format;
    unsigned rank;
    if(length==108&&!memcmp(bytes,"KBW2",4)&&pref_crc(bytes,104)==pref_u32(bytes+104)) {
      candidate.update_request=pref_u32(bytes+100);
      format=KB_CONTROL_CURRENT;
      rank=3;
    }
    else if(length==104&&!memcmp(bytes,"KBW1",4)&&pref_crc(bytes,100)==pref_u32(bytes+100)) {
      format=KB_CONTROL_CURRENT;
      rank=2;
    }
    else if(length==92&&!memcmp(bytes,"KBP1",4)&&pref_crc(bytes,88)==pref_u32(bytes+88)) {
      format=KB_CONTROL_LEGACY;
      rank=1;
    }
    else continue;
    if(format==KB_CONTROL_CURRENT) {
      uint32_t flags=pref_u32(bytes+96);
      if(flags&~1u)continue;
      candidate.last_attempt=pref_u32(bytes+88);
      candidate.last_success=pref_u32(bytes+92);
      candidate.hint_seen=(flags&1u)!=0;
    }
    uint32_t stored_generation=pref_u32(bytes+4);
    if(!stored_generation||!kb_preferences_parse(&candidate.preferences,bytes+8,80,NULL,NULL))continue;
    if(stored_generation>*generation||(stored_generation==*generation&&rank>selected_rank)) {
      *out=candidate;
      *generation=stored_generation;
      *slot=i;
      result=format;
      selected_rank=rank;
    }
  }
  return result;
}
bool kb_control_commit(kb_control_t *out,const kb_control_t *candidate,uint32_t *generation,uint8_t *slot,kb_pref_write_fn write,void *ctx) {
  kb_preferences_t checked;
  if(*slot>1||*generation==UINT32_MAX||!kb_preferences_parse(&checked,candidate->preferences.bytes,80,NULL,NULL))return false;
  uint8_t bytes[108]={0};
  uint8_t next=1-*slot;
  memcpy(bytes,"KBW2",4);
  pref_put32(bytes+4,*generation+1);
  memcpy(bytes+8,candidate->preferences.bytes,80);
  pref_put32(bytes+88,candidate->last_attempt);
  pref_put32(bytes+92,candidate->last_success);
  pref_put32(bytes+96,candidate->hint_seen?1u:0u);
  pref_put32(bytes+100,candidate->update_request);
  pref_put32(bytes+104,pref_crc(bytes,104));
  if(write(ctx,10+next,bytes,sizeof(bytes))!=sizeof(bytes))return false;
  *out=*candidate;
  (*generation)++;
  *slot=next;
  return true;
}
void kb_preferences_load(kb_preferences_t *out,uint32_t *generation,uint8_t *slot,kb_pref_read_fn read,void *ctx) {
  kb_preferences_default(out,1);
  *generation=0;
  *slot=0;
  for(unsigned i=0;i<2;i++) {
    uint8_t b[92];
    kb_preferences_t p;
    if(read(ctx,10+i,b,sizeof(b))==sizeof(b)&&!memcmp(b,"KBP1",4)&&pref_crc(b,88)==pref_u32(b+88)&&pref_u32(b+4)>*generation&&kb_preferences_parse(&p,b+8,80,NULL,NULL)) {
      *out=p;
      *generation=pref_u32(b+4);
      *slot=i;
    }
  }
}
bool kb_preferences_commit(kb_preferences_t *out,const kb_preferences_t *candidate,uint32_t *generation,uint8_t *slot,kb_pref_write_fn write,void *ctx) {
  kb_preferences_t checked;
  if(!kb_preferences_parse(&checked,candidate->bytes,80,NULL,NULL)||*generation==UINT32_MAX)return false;
  uint8_t b[92]= {
    0
  },
  next=1-*slot;
  memcpy(b,"KBP1",4);
  pref_put32(b+4,*generation+1);
  memcpy(b+8,candidate->bytes,80);
  pref_put32(b+88,pref_crc(b,88));
  if(write(ctx,10+next,b,sizeof(b))!=sizeof(b))return false;
  *out=*candidate;
  (*generation)++;
  *slot=next;
  return true;
}
