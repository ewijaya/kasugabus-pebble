/* Schema 2 station-minute lookup on a synthetic compiled fixture. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../src/c/engine.h"
static uint8_t *load(const char *path,size_t *n) {
  FILE *f=fopen(path,"rb"); assert(f);
  fseek(f,0,SEEK_END); *n=(size_t)ftell(f); rewind(f);
  uint8_t *b=malloc(*n); assert(b&&fread(b,1,*n,f)==*n); fclose(f); return b;
}
static bool lookup(const kb_dataset_t *d,uint8_t point,uint16_t minute,uint8_t pattern,uint8_t service,uint8_t out[2]) {
  kb_trip_t t; memset(&t,0,sizeof(t));
  t.boarding_point_id=point; t.minute=minute; t.pattern_id=pattern; t.service_id=service;
  return kb_trip_station_minutes(d,&t,out);
}
int main(int argc,char **argv) {
  assert(argc==3);
  size_t n2,n1; uint8_t *two=load(argv[1],&n2),*one=load(argv[2],&n1),m[2];
  kb_dataset_t d;
  assert(kb_dataset_open(&d,two,n2)==KB_OK&&d.schema==2&&d.minimum_app_version>=KB_DATA_LEVEL);
  /* JR and Hankyu: 12 min, then 6 minutes later. */
  assert(lookup(&d,1,633,1,1,m)&&m[0]==12&&m[1]==18);
  /* JR only (a route that ends at JR Ibaraki). */
  assert(lookup(&d,1,634,2,1,m)&&m[0]==9&&m[1]==0);
  /* Largest representable values: 31 min to JR, Hankyu 10 later. */
  assert(lookup(&d,1,700,1,2,m)&&m[0]==31&&m[1]==41);
  /* Rows past the table, rows without times, unknown trips and Hankyu Bus. */
  assert(!lookup(&d,1,800,1,3,m)&&!lookup(&d,1,1505,1,1,m));
  assert(!lookup(&d,101,640,3,4,m)&&!lookup(&d,1,633,1,2,m)&&!lookup(&d,1,633,2,1,m));
  assert(!kb_trip_station_minutes(NULL,NULL,m)&&!kb_trip_station_minutes(&d,NULL,m));
  /* The same trips in schema 1 data have no station times. */
  assert(kb_dataset_open(&d,one,n1)==KB_OK&&d.schema==1&&!lookup(&d,1,633,1,1,m));
  puts("station minutes tests passed");
  return 0;
}
