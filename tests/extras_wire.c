/* Reads 28 wire bytes (decimal, whitespace separated) per line from stdin and
 * prints what the watch's extras parser makes of them. Used by test_train_settings.py. */
#include <stdio.h>
#include "../src/c/extras.h"
int main(void) {
  uint8_t b[KB_EXTRAS_WIRE_BYTES];
  for(;;) {
    for(unsigned i=0;i<KB_EXTRAS_WIRE_BYTES;i++) {
      unsigned v;
      if(scanf("%u",&v)!=1)return 0;
      b[i]=(uint8_t)v;
    }
    kb_extras_t e;
    if(!kb_extras_parse(&e,b,sizeof(b),NULL,NULL)){puts("reject");continue;}
    uint8_t again[KB_EXTRAS_WIRE_BYTES];
    kb_extras_encode(&e,again);
    int same=1;
    for(unsigned i=0;i<sizeof(b);i++)if(again[i]!=b[i])same=0;
    printf("flags=%u walk_jr=%u walk_hankyu=%u buttons=%u,%u,%u,%u same=%d\n",e.train_flags,KB_TRAIN_WALK(e.walk_jr),KB_TRAIN_WALK(e.walk_hankyu),
      e.buttons[0],e.buttons[1],e.buttons[2],e.buttons[3],same);
  }
}
