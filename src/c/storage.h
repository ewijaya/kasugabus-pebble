#ifndef KB_STORAGE_H
#define KB_STORAGE_H
#include "engine.h"
#define KB_STORE_SLOTS 8
#define KB_CHUNK_SIZE 192
/* Two atomic directory records fit the SDK's 256-byte value limit. */
#define KB_STORE_DIRECTORY_KEY 90
#define KB_STORE_DIRECTORY_SIZE 208
/* Pebble's E_DOES_NOT_EXIST; other negative read results are I/O failures. */
#define KB_STORE_NOT_FOUND (-9)
#define KB_STORE_META_KEY 900
#define KB_STORE_DATA_KEY 1000
#define KB_STORE_STRIDE 256
#define KB_STORAGE_REQUIRED (KB_STORE_SLOTS * KB_MAX_DATASET_BYTES + 4096)
typedef struct  {
  void *context;
  /* Return bytes read, KB_STORE_NOT_FOUND for an absent key, or another
   * negative code on failure. Absence alone permits legacy migration. */
  int (*read)(void *,uint32_t,void *,size_t);
  int (*write)(void *,uint32_t,const void *,size_t);
  int (*remove)(void *,uint32_t);
  size_t capacity;
}
kb_store_io_t;
typedef struct  {
  /* valid: committed descriptor candidate; checked: payload validated this run.
   * No unchecked payload may be returned or advertised as ready. */
  bool valid,checked;
  uint32_t version,length,crc,session;
  int32_t effective_from,valid_until;
}
kb_slot_t;
typedef struct  {
  kb_store_io_t io;
  kb_dataset_t baseline,cached;
  uint8_t *cache;
  int cache_slot;
  kb_slot_t slots[KB_STORE_SLOTS];
  bool baseline_valid,recovery_notice,capacity_ok;
  /* Legacy import is a one-time startup cost, separate from normal launch. */
  bool legacy_migration;
  uint32_t directory_generation;
  int8_t directory_bank;
  uint8_t directory_masks[2];
  struct  {
    bool running;
    uint32_t session,version,length,crc,received;
    uint16_t next_seq;
    int slot;
    int64_t last_activity;
  }
  transfer;
}
kb_store_t;
bool kb_store_init(kb_store_t *,kb_store_io_t,const uint8_t *,size_t,uint8_t *);
/* Validate at most one unchecked descriptor candidate; true means work done.
 * May replace the shared cache. Call between UI events before starting a write. */
bool kb_store_check_next(kb_store_t *);
const kb_dataset_t *kb_store_resolve(void *,int32_t);
uint32_t kb_store_pending(kb_store_t *,int32_t,int32_t *);
uint32_t kb_store_newest(kb_store_t *);
bool kb_store_has_staging(kb_store_t *,int32_t);
int kb_store_begin(kb_store_t *,uint32_t,uint32_t,uint32_t,uint32_t,int64_t);
int kb_store_chunk(kb_store_t *,uint32_t,uint16_t,const uint8_t *,size_t,int64_t);
int kb_store_commit(kb_store_t *,uint32_t,int64_t);
bool kb_store_tick(kb_store_t *,int64_t);
void kb_store_abort(kb_store_t *);
bool kb_store_restore(kb_store_t *);
#endif
