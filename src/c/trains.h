#ifndef KB_TRAINS_H
#define KB_TRAINS_H
/* Reader and connection logic for the bundled KTR1 train table
 * (tools/train_build.py, docs/TRAIN_CONNECTIONS_DESIGN.md). Everything is read
 * through a callback in small pieces, so nothing here allocates or depends on
 * the Pebble SDK and the host tests can drive it directly. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define KB_TRAIN_JR 0
#define KB_TRAIN_HANKYU 1
#define KB_TRAIN_OSAKA 0
#define KB_TRAIN_KYOTO 1
/* Day types in the table: 1 weekday, 2 Saturday/Sunday/holiday. */
#define KB_TRAIN_WEEKDAY 1
#define KB_TRAIN_WEEKEND 2
typedef int (*kb_train_read_fn)(void *context,size_t offset,void *buffer,size_t length);
typedef struct {
  uint16_t departure,arrival; /* service-day minutes (24:xx > 1440) */
  char type[20],destination[20];
} kb_train_t;
typedef struct {
  uint8_t network;  /* KB_TRAIN_JR or KB_TRAIN_HANKYU */
  uint16_t at;      /* minute the bus reaches this station */
  kb_train_t train; /* first train that can be caught from there */
} kb_leg_t;
/* Checks magic, length and the CRC of the whole table in small chunks and
 * returns the day (since 1970-01-01) the data should next be reviewed. */
bool kb_trains_valid(kb_train_read_fn,void *,size_t size,int32_t *review_due);
/* The skip-th train (0 = first) leaving at or after ready that reaches the
 * list's first (target 0) or second (target 1) stop. */
bool kb_trains_next(kb_train_read_fn,void *,uint8_t network,uint8_t direction,uint8_t day,
                    uint16_t ready,unsigned target,unsigned skip,kb_train_t *);
/* Connection from one bus. minutes[0]/[1] are the bus's minutes to JR and
 * Hankyu (0 = no call, from kb_trip_station_minutes); walk[] are the minutes
 * from the bus stop to each platform. Returns 0..2 legs, earliest arrival
 * first (ties favour JR). A station with no catchable train is left out. */
unsigned kb_train_connect(kb_train_read_fn,void *,uint8_t day,uint8_t direction,unsigned target,
                          uint16_t trip_minute,const uint8_t minutes[2],const uint8_t walk[2],kb_leg_t legs[2]);
#endif
