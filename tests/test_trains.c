/* KTR1 reader and connection logic against the committed data/trains.bin.
 * Output is compared with tools/train_build.py's independent decoder. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../src/c/trains.h"
#include "../src/c/engine.h"
static const uint8_t *image;
static size_t image_size;
static unsigned reads;
static int read_image(void *ctx,size_t offset,void *buffer,size_t length) {
  (void)ctx;reads++;
  if(offset>=image_size)return -1;
  if(length>image_size-offset)length=image_size-offset;
  memcpy(buffer,image+offset,length);
  return (int)length;
}
static uint8_t *load(const char *path,size_t *n) {
  FILE *f=fopen(path,"rb");assert(f);
  fseek(f,0,SEEK_END);*n=(size_t)ftell(f);rewind(f);
  uint8_t *b=malloc(*n);assert(b&&fread(b,1,*n,f)==*n);fclose(f);return b;
}
static void hm(char *out,unsigned minute) { sprintf(out,"%u:%02u",minute/60,minute%60); }
int main(int argc,char **argv) {
  assert(argc>=2);
  uint8_t *data=load(argv[1],&image_size);
  image=data;
  int32_t review=0;
  assert(kb_trains_valid(read_image,NULL,image_size,&review)&&review==20878);
  assert(!kb_trains_valid(read_image,NULL,image_size-1,NULL));
  if(argc==2) {
    /* Self-checks that need no oracle. */
    kb_train_t t;
    assert(kb_trains_next(read_image,NULL,KB_TRAIN_JR,KB_TRAIN_OSAKA,KB_TRAIN_WEEKDAY,0,0,0,&t));
    assert(t.departure==5*60+6&&t.arrival>t.departure&&t.type[0]&&t.destination[0]);
    /* Later than the last train of the day: none. */
    assert(!kb_trains_next(read_image,NULL,KB_TRAIN_JR,KB_TRAIN_OSAKA,KB_TRAIN_WEEKDAY,25*60,0,0,&t));
    /* Bad arguments and a reader that fails never produce a train. */
    assert(!kb_trains_next(read_image,NULL,2,0,1,0,0,0,&t)&&!kb_trains_next(read_image,NULL,0,0,3,0,0,0,&t));
    assert(!kb_trains_next(read_image,NULL,0,0,1,0,2,0,&t)&&!kb_trains_next(read_image,NULL,0,KB_TRAIN_OSAKA,1,0,1,0,&t));
    uint8_t flipped[64];memcpy(flipped,data,sizeof(flipped));flipped[20]^=1;
    image=flipped;image_size=sizeof(flipped);assert(!kb_trains_valid(read_image,NULL,image_size,NULL));
    puts("trains self-checks passed");
    return 0;
  }
  if(!strcmp(argv[2],"connect")) {
    /* stdin: "day direction target trip_minute jr hankyu walk_jr walk_hankyu". */
    unsigned day,direction,target,trip,jr,hk,wj,wh;
    while(scanf("%u %u %u %u %u %u %u %u",&day,&direction,&target,&trip,&jr,&hk,&wj,&wh)==8) {
      uint8_t minutes[2]={(uint8_t)jr,(uint8_t)hk},walk[2]={(uint8_t)wj,(uint8_t)wh};
      kb_leg_t legs[2];
      unsigned n=kb_train_connect(read_image,NULL,(uint8_t)day,(uint8_t)direction,target,(uint16_t)trip,minutes,walk,legs);
      printf("%u",n);
      for(unsigned i=0;i<n;i++) {
        char a[16],b[16],x[16];
        hm(x,legs[i].at);hm(a,legs[i].train.departure);hm(b,legs[i].train.arrival);
        printf(" %u@%s:%s|%s|%s|%s",legs[i].network,x,a,b,legs[i].train.type,legs[i].train.destination);
      }
      puts("");
    }
    free(data);
    return 0;
  }
  /* "network direction day ready target skip" lines on stdin. */
  unsigned network,direction,day,ready,target,skip;
  while(scanf("%u %u %u %u %u %u",&network,&direction,&day,&ready,&target,&skip)==6) {
    kb_train_t t;char a[16],b[16];
    if(kb_trains_next(read_image,NULL,(uint8_t)network,(uint8_t)direction,(uint8_t)day,(uint16_t)ready,target,skip,&t)) {
      hm(a,t.departure);hm(b,t.arrival);
      printf("%s|%s|%s|%s\n",a,b,t.type,t.destination);
    }
    else puts("none");
  }
  free(data);
  return 0;
}
