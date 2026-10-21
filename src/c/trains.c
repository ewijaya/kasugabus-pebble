#include "trains.h"
#include "engine.h"
#include <string.h>
static uint16_t u16(const uint8_t *b) { return (uint16_t)(b[0]|(b[1]<<8)); }
static uint32_t u32(const uint8_t *b) {
  return (uint32_t)b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);
}
static bool read_exact(kb_train_read_fn read,void *ctx,size_t offset,void *buffer,size_t n) {
  return read(ctx,offset,buffer,n)==(int)n;
}
bool kb_trains_valid(kb_train_read_fn read,void *ctx,size_t size,int32_t *review_due) {
  uint8_t b[64];
  if(size<32||!read_exact(read,ctx,0,b,32)||memcmp(b,"KTR1",4)||u16(b+4)!=1||u16(b+6)!=32||u32(b+8)!=size)return false;
  uint32_t expected=u32(b+12),crc=UINT32_MAX;
  if(review_due)*review_due=(int32_t)u32(b+24);
  for(size_t at=16;at<size;) {
    size_t n=size-at<sizeof(b)?size-at:sizeof(b);
    if(!read_exact(read,ctx,at,b,n))return false;
    crc=kb_crc32_update(crc,b,n);
    at+=n;
  }
  return ~crc==expected;
}
/* The last string ends the table, so a short read there is expected. */
static bool read_string(kb_train_read_fn read,void *ctx,uint16_t offset,char *out,size_t n) {
  int got=read(ctx,offset,out,n-1);
  if(got<=0)return false;
  out[got]=0;
  return memchr(out,0,(size_t)got)!=NULL;
}
bool kb_trains_next(kb_train_read_fn read,void *ctx,uint8_t network,uint8_t direction,uint8_t day,
                    uint16_t ready,unsigned target,unsigned skip,kb_train_t *out) {
  uint8_t h[32],e[12];
  if(target>1||!read_exact(read,ctx,0,h,32))return false;
  unsigned sections=u16(h+28),patterns=u16(h+30);
  for(unsigned i=0;i<sections;i++) {
    if(!read_exact(read,ctx,32+4*patterns+12*i,e,12))return false;
    if(e[0]!=network||e[1]!=direction||e[2]!=day)continue;
    unsigned stride=e[3],count=u16(e+6);
    uint32_t at=u32(e+8);
    uint16_t minute=u16(e+4);
    uint8_t r[64];
    if(stride<4||stride>sizeof(r))return false;
    unsigned per=sizeof(r)/stride;
    for(unsigned j=0;j<count;j+=per) {
      unsigned n=count-j<per?count-j:per;
      if(!read_exact(read,ctx,at+stride*j,r,stride*n))return false;
      for(unsigned k=0;k<n;k++) {
        const uint8_t *t=r+stride*k;
        minute=(uint16_t)(minute+t[0]);
        uint8_t duration=t[2+target];
        if(minute<ready||!duration||skip--)continue;
        uint8_t p[4];
        if(t[1]>=patterns||!read_exact(read,ctx,32+4*t[1],p,4))return false;
        out->departure=minute;
        out->arrival=(uint16_t)(minute+duration);
        return read_string(read,ctx,u16(p),out->type,sizeof(out->type))&&
               read_string(read,ctx,u16(p+2),out->destination,sizeof(out->destination));
      }
    }
    return false;
  }
  return false;
}
unsigned kb_train_connect(kb_train_read_fn read,void *ctx,uint8_t day,uint8_t direction,unsigned target,
                          uint16_t trip_minute,const uint8_t minutes[2],const uint8_t walk[2],kb_leg_t legs[2]) {
  unsigned n=0;
  for(uint8_t s=0;s<2;s++) {
    if(!minutes[s])continue;
    kb_leg_t *l=&legs[n];
    l->network=s;
    l->at=(uint16_t)(trip_minute+minutes[s]);
    if(kb_trains_next(read,ctx,s,direction,day,(uint16_t)(l->at+walk[s]),target,0,&l->train))n++;
  }
  if(n==2&&legs[1].train.arrival<legs[0].train.arrival) {
    kb_leg_t t=legs[0];legs[0]=legs[1];legs[1]=t;
  }
  return n;
}
