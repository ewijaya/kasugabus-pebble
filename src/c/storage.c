#include "storage.h"
#include <string.h>
static uint32_t get32(const uint8_t *p) {
  return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
static void put32(uint8_t *p,uint32_t n) {
  for(int i=0;i<4;i++)p[i]=(uint8_t)(n>>(i*8));
}
static uint32_t key(int slot,unsigned seq) {
  return KB_STORE_DATA_KEY+slot*KB_STORE_STRIDE+seq;
}
static void decode_entry(kb_slot_t *m,const uint8_t *b) {
  memset(m,0,sizeof(*m));
  m->version=get32(b);
  m->length=get32(b+4);
  m->crc=get32(b+8);
  m->session=get32(b+12);
  m->effective_from=(int32_t)get32(b+16);
  m->valid_until=(int32_t)get32(b+20);
  m->valid=m->length>=KB_HEADER_SIZE&&m->length<=KB_MAX_DATASET_BYTES;
}
static bool directory_valid(const uint8_t *b,int n) {
  if(n!=KB_STORE_DIRECTORY_SIZE||memcmp(b,"KBD2",4)||!get32(b+4)||b[9]||b[10]||b[11]||kb_crc32(b,204)!=get32(b+204))return false;
  for(int i=0;i<KB_STORE_SLOTS;i++) {
    const uint8_t *entry=b+12+24*i;
    if(b[8]&(1u<<i)) {
      uint32_t length=get32(entry+4);
      if(length<KB_HEADER_SIZE||length>KB_MAX_DATASET_BYTES)return false;
    }
    else for(int j=0;j<24;j++)if(entry[j])return false;
  }
  return true;
}
/* Write an alternate bank without changing the caller's in-memory slots.
 * A replacement publishes a newly validated payload; exclusions retire slots
 * before their data records can be reused. Every other descriptor is copied. */
static bool write_directory(kb_store_t *s,int replace,const kb_slot_t *replacement,uint8_t exclude) {
  if(s->directory_generation==UINT32_MAX)return false;
  uint8_t b[KB_STORE_DIRECTORY_SIZE]={0};
  memcpy(b,"KBD2",4);
  put32(b+4,s->directory_generation+1);
  for(int i=0;i<KB_STORE_SLOTS;i++) {
    const kb_slot_t *m=i==replace?replacement:&s->slots[i];
    if(!m||!m->valid||(exclude&(1u<<i)))continue;
    b[8]|=(uint8_t)(1u<<i);
    uint8_t *entry=b+12+24*i;
    put32(entry,m->version);
    put32(entry+4,m->length);
    put32(entry+8,m->crc);
    put32(entry+12,m->session);
    put32(entry+16,(uint32_t)m->effective_from);
    put32(entry+20,(uint32_t)m->valid_until);
  }
  put32(b+204,kb_crc32(b,204));
  int bank=s->directory_bank==0?1:0;
  if(s->io.write(s->io.context,KB_STORE_DIRECTORY_KEY+bank,b,sizeof(b))!=(int)sizeof(b))return false;
  s->directory_generation++;
  s->directory_bank=(int8_t)bank;
  s->directory_masks[bank]=b[8];
  return true;
}
static void retire_legacy(kb_store_t *s) {
  /* New directory keys are never deleted, including Restore. Once they exist
   * legacy records cannot be re-imported after an ordinary restart. */
  for(int i=0;i<KB_STORE_SLOTS;i++)s->io.remove(s->io.context,KB_STORE_META_KEY+i);
}
static int select_for_day(kb_store_t *s,int32_t day) {
  int chosen=-1;
  int32_t effective=INT32_MIN;
  uint32_t version=0;
  if(s->baseline_valid&&s->baseline.effective_from<=day) {
    effective=s->baseline.effective_from;
    version=s->baseline.release_version;
  }
  for(int i=0;i<KB_STORE_SLOTS;i++) {
    kb_slot_t *m=&s->slots[i];
    if(m->valid&&m->effective_from<=day&&(m->effective_from>effective||(m->effective_from==effective&&m->version>version))) {
      chosen=i;
      effective=m->effective_from;
      version=m->version;
    }
  }
  return chosen;
}
static bool load_slot(kb_store_t *s,int slot) {
  if(s->cache_slot==slot)return true;
  s->cache_slot=KB_STORE_CACHE_INVALID;
  kb_slot_t *m=&s->slots[slot];
  for(uint32_t n=0,seq=0;n<m->length;seq++) {
    unsigned len=m->length-n;
    if(len>KB_CHUNK_SIZE)len=KB_CHUNK_SIZE;
    if(s->io.read(s->io.context,key(slot,seq),s->cache+n,len)!=(int)len)return false;
    n+=len;
  }
  if(kb_crc32(s->cache,m->length)!=m->crc||kb_dataset_open(&s->cached,s->cache,m->length)!=KB_OK)return false;
  if(s->cached.release_version!=m->version||s->cached.effective_from!=m->effective_from||s->cached.valid_until!=m->valid_until||s->cached.minimum_app_version>1||strcmp(kb_coverage_id(&s->cached),"minami-kasugaoka-v1"))return false;
  m->checked=true;
  s->cache_slot=slot;
  return true;
}
static bool check_slot(kb_store_t *s,int slot) {
  kb_slot_t *m=&s->slots[slot];
  if(!m->valid)return false;
  if(m->checked||load_slot(s,slot))return true;
  m->valid=false;
  s->recovery_notice=true;
  return false;
}
bool kb_store_check_next(kb_store_t *s) {
  for(int i=0;i<KB_STORE_SLOTS;i++)if(s->slots[i].valid&&!s->slots[i].checked) {
    check_slot(s,i);
    return true;
  }
  return false;
}
static void check_all(kb_store_t *s) {
  /* Before eviction/version decisions, do not let two corrupt newer
   * descriptors make the sole good older future copy appear disposable. */
  while(kb_store_check_next(s)) { }
}
static bool init_store(kb_store_t *s,kb_store_io_t io,const uint8_t *baseline,size_t len,uint8_t *cache,kb_baseline_read_fn read,void *context) {
  memset(s,0,sizeof(*s));
  s->io=io;
  s->cache=cache;
  s->cache_slot=KB_STORE_CACHE_INVALID;
  s->baseline_read=read;
  s->baseline_context=context;
  s->directory_bank=-1;
  s->capacity_ok=io.capacity>=KB_STORAGE_REQUIRED;
  s->baseline_valid=kb_dataset_open(&s->baseline,baseline,len)==KB_OK&&s->baseline.minimum_app_version<=1&&!strcmp(kb_coverage_id(&s->baseline),"minami-kasugaoka-v1");
  if(read&&s->baseline_valid) {
    s->baseline_crc=kb_crc32(baseline,len);
    s->cache_slot=KB_STORE_CACHE_BASELINE;
  }
  uint8_t banks[2][KB_STORE_DIRECTORY_SIZE];
  bool any=false,valid[2],read_failed=false;
  for(int bank=0;bank<2;bank++) {
    int n=io.read(io.context,KB_STORE_DIRECTORY_KEY+bank,banks[bank],sizeof(banks[bank]));
    any|=n!=KB_STORE_NOT_FOUND;
    read_failed|=n<0&&n!=KB_STORE_NOT_FOUND;
    valid[bank]=directory_valid(banks[bank],n);
    if(n!=KB_STORE_NOT_FOUND&&!valid[bank])s->recovery_notice=true;
    if(valid[bank]) {
      s->directory_masks[bank]=banks[bank][8];
      uint32_t generation=get32(banks[bank]+4);
      if(generation>s->directory_generation) {
        s->directory_generation=generation;
        s->directory_bank=(int8_t)bank;
      }
    }
  }
  if(valid[0]&&valid[1]&&get32(banks[0]+4)==get32(banks[1]+4)&&memcmp(banks[0],banks[1],sizeof(banks[0]))) {
    /* Equal generations with different contents cannot arise from this writer.
     * Do not choose an arbitrary contradictory directory. */
    s->directory_bank=-1;
    s->directory_generation=UINT32_MAX;
    s->recovery_notice=true;
  }
  /* Unknown descriptors after a transient read failure must not be discarded
   * by a subsequent update. Exhaustion is also a safe write-disabled state. */
  if(read_failed)s->directory_generation=UINT32_MAX;
  if(s->directory_bank>=0) {
    const uint8_t *b=banks[s->directory_bank];
    for(int i=0;i<KB_STORE_SLOTS;i++)if(b[8]&(1u<<i))decode_entry(&s->slots[i],b+12+24*i);
  }
  else if(!any) {
    /* Pre-release KBS1 compatibility. A normal restart reads only two banks;
     * this import and retirement is deliberately a one-time startup path. */
    bool import_ok=true;
    for(int i=0;i<KB_STORE_SLOTS;i++) {
      uint8_t b[40];
      int n=io.read(io.context,KB_STORE_META_KEY+i,b,sizeof(b));
      if(n<0) {
        if(n!=KB_STORE_NOT_FOUND) {
          import_ok=false;
          s->recovery_notice=true;
        }
        continue;
      }
      s->legacy_migration=true;
      if(n!=40||memcmp(b,"KBS1",4)||kb_crc32(b,36)!=get32(b+36)) {
        s->recovery_notice=true;
        continue;
      }
      decode_entry(&s->slots[i],b+4);
      if(!s->slots[i].valid)s->recovery_notice=true;
    }
    if(!import_ok) {
      /* A failed read is not evidence that an old descriptor is absent. */
      s->directory_generation=UINT32_MAX;
    }
    else if(write_directory(s,-1,NULL,0)) {
      if(write_directory(s,-1,NULL,0))retire_legacy(s);
      else s->recovery_notice=true;
    }
    else {
      /* A short first import must not prevent a later retry of intact legacy
       * data. No payload or legacy descriptor has been modified. */
      io.remove(io.context,KB_STORE_DIRECTORY_KEY);
      s->recovery_notice=true;
    }
  }
  /* Historical/future snapshots do not delay first paint. Resolve and pending
   * validate their winning payload before use; BEGIN validates every remaining
   * candidate before it may erase/reuse storage. */
  return s->baseline_valid;
}
bool kb_store_init(kb_store_t *s,kb_store_io_t io,const uint8_t *baseline,size_t len,uint8_t *cache) {
  return init_store(s,io,baseline,len,cache,NULL,NULL);
}
bool kb_store_init_reader(kb_store_t *s,kb_store_io_t io,kb_baseline_read_fn read,void *context,size_t len,uint8_t *cache) {
  if(!s)return false;
  if(!cache) {
    memset(s,0,sizeof(*s));
    s->io=io;
    s->directory_generation=UINT32_MAX;
    s->directory_bank=-1;
    s->cache_slot=KB_STORE_CACHE_INVALID;
    s->recovery_notice=true;
    return false;
  }
  /* Do not parse stale/partial cache contents after a failed resource read.
   * Persisted snapshots still initialize and can recover an unavailable bundle. */
  const uint8_t *baseline=NULL;
  if(read&&cache&&len>=KB_HEADER_SIZE&&len<=KB_MAX_DATASET_BYTES&&read(context,cache,len)==(int)len)baseline=cache;
  bool valid=init_store(s,io,baseline,len,cache,read,context);
  if(!valid)s->recovery_notice=true;
  return valid;
}
static const kb_dataset_t *resolve_baseline(kb_store_t *s,int32_t day) {
  if(!s->baseline_valid||s->baseline.effective_from>day)return NULL;
  if(s->baseline_read&&s->cache_slot!=KB_STORE_CACHE_BASELINE) {
    s->cache_slot=KB_STORE_CACHE_INVALID;
    if(s->baseline_read(s->baseline_context,s->cache,s->baseline.size)!=(int)s->baseline.size||kb_crc32(s->cache,s->baseline.size)!=s->baseline_crc) {
      s->recovery_notice=true;
      return NULL;
    }
    s->cache_slot=KB_STORE_CACHE_BASELINE;
  }
  return &s->baseline;
}
const kb_dataset_t *kb_store_resolve(void *ctx,int32_t day) {
  kb_store_t *s=ctx;
  for(int tries=0;tries<KB_STORE_SLOTS;tries++) {
    int slot=select_for_day(s,day);
    if(slot<0)return resolve_baseline(s,day);
    if(load_slot(s,slot))return &s->cached;
    s->slots[slot].valid=false;
    s->recovery_notice=true;
  }
  return resolve_baseline(s,day);
}
uint32_t kb_store_pending(kb_store_t *s,int32_t day,int32_t *effective) {
  for(int tries=0;tries<KB_STORE_SLOTS;tries++) {
    int candidate=-1;
    uint32_t version=0;
    int32_t first=INT32_MAX;
    for(int i=0;i<KB_STORE_SLOTS;i++) {
      kb_slot_t *m=&s->slots[i];
      if(m->valid&&m->effective_from>day&&(m->effective_from<first||(m->effective_from==first&&m->version>version))) {
        first=m->effective_from;
        version=m->version;
        candidate=i;
      }
    }
    if(candidate<0)break;
    if(check_slot(s,candidate)) {
      if(effective)*effective=first;
      return version;
    }
  }
  if(effective)*effective=INT32_MAX;
  return 0;
}
uint32_t kb_store_newest(kb_store_t *s) {
  check_all(s);
  uint32_t n=s->baseline_valid?s->baseline.release_version:0;
  for(int i=0;i<KB_STORE_SLOTS;i++)if(s->slots[i].valid&&s->slots[i].version>n)n=s->slots[i].version;
  return n;
}
static int staging_slot(kb_store_t *s,int32_t day) {
  bool protect[KB_STORE_SLOTS]= {
    0
  };
  for(int d=0;d<=2;d++) {
    int i=select_for_day(s,day-d);
    if(i>=0)protect[i]=true;
  }
  /* Keep each future effective-date winner and its newest recovery copy.
   * Older corrections for the same date are already superseded, so they
   * may stage another candidate without sacrificing usable future data. */
  for(int i=0;i<KB_STORE_SLOTS;i++)if(s->slots[i].valid&&s->slots[i].effective_from>day) {
    unsigned newer=0;
    for(int j=0;j<KB_STORE_SLOTS;j++)if(s->slots[j].valid&&s->slots[j].effective_from==s->slots[i].effective_from&&s->slots[j].version>s->slots[i].version)newer++;
    if(newer<2)protect[i]=true;
  }
  /* Also retain the newest previous revision as a recoverable dataset. */  int current=select_for_day(s,day),previous=-1;
  uint32_t v=0;
  for(int i=0;i<KB_STORE_SLOTS;i++)if(i!=current&&s->slots[i].valid&&s->slots[i].effective_from<=day&&s->slots[i].version>v) {
    v=s->slots[i].version;
    previous=i;
  }
  if(previous>=0)protect[previous]=true;
  for(int i=0;i<KB_STORE_SLOTS;i++)if(!s->slots[i].valid)return i;
  int oldest=-1;
  for(int i=0;i<KB_STORE_SLOTS;i++)if(!protect[i]&&(oldest<0||s->slots[i].version<s->slots[oldest].version))oldest=i;
  return oldest;
}
bool kb_store_has_staging(kb_store_t *s,int32_t day) {
  return s->capacity_ok&&staging_slot(s,day)>=0;
}
int kb_store_begin(kb_store_t *s,uint32_t session,uint32_t version,uint32_t length,uint32_t crc,int64_t now) {
  if(!session||length<KB_HEADER_SIZE||length>KB_MAX_DATASET_BYTES)return 2;
  if(!s->capacity_ok)return 5;
  if(s->transfer.running) {
    if(s->transfer.session==session&&s->transfer.version==version&&s->transfer.length==length&&s->transfer.crc==crc) {
      s->transfer.last_activity=now;
      return 0;
    }
    return 2;
  }
  if(s->directory_generation==UINT32_MAX)return 5;
  check_all(s);
  /* Version ordering is checked against the same applicability range at commit:
  * a current snapshot can arrive while a larger future version is stored. */  for(int i=0;i<KB_STORE_SLOTS;i++)if(s->slots[i].valid&&s->slots[i].version==version)return 2;
  if(s->baseline_valid&&version<=s->baseline.release_version)return 2;
  int slot=staging_slot(s,kb_jst_day(now));
  if(slot<0)return 5;
  uint8_t bit=(uint8_t)(1u<<slot);
  if((s->directory_masks[0]|s->directory_masks[1])&bit) {
    /* Both banks must stop referring to a reused payload before its first
     * chunk changes. Otherwise recovery from a torn newer bank could revive
     * a descriptor whose data have already been overwritten. */
    if(s->directory_generation>UINT32_MAX-2)return 5;
    if(!write_directory(s,-1,NULL,bit))return 5;
    s->slots[slot].valid=false;
    if(s->cache_slot==slot)s->cache_slot=-1;
    if(!write_directory(s,-1,NULL,bit))return 5;
  }
  s->slots[slot].valid=false;
  if(s->cache_slot==slot)s->cache_slot=-1;
  memset(&s->transfer,0,sizeof(s->transfer));
  s->transfer.running=true;
  s->transfer.session=session;
  s->transfer.version=version;
  s->transfer.length=length;
  s->transfer.crc=crc;
  s->transfer.slot=slot;
  s->transfer.last_activity=now;
  return 0;
}
int kb_store_chunk(kb_store_t *s,uint32_t session,uint16_t seq,const uint8_t *bytes,size_t len,int64_t now) {
  if(!s->transfer.running||session!=s->transfer.session||!bytes)return 2;
  uint32_t offset=(uint32_t)seq*KB_CHUNK_SIZE;
  if(offset>=s->transfer.length)return 2;
  size_t expected=s->transfer.length-offset;
  if(expected>KB_CHUNK_SIZE)expected=KB_CHUNK_SIZE;
  if(len!=expected)return 2;
  if(seq<s->transfer.next_seq) {
    uint8_t prior[KB_CHUNK_SIZE];
    if(s->io.read(s->io.context,key(s->transfer.slot,seq),prior,len)!=(int)len||memcmp(prior,bytes,len))return 2;
    s->transfer.last_activity=now;
    return 0;
  }
  if(seq!=s->transfer.next_seq)return 1;
  if(s->io.write(s->io.context,key(s->transfer.slot,seq),bytes,len)!=(int)len) {
    kb_store_abort(s);
    return 5;
  }
  s->transfer.next_seq++;
  s->transfer.received+=len;
  s->transfer.last_activity=now;
  return 0;
}
int kb_store_commit(kb_store_t *s,uint32_t session,int64_t now) {
  if(!s->transfer.running) {
    for(int i=0;i<KB_STORE_SLOTS;i++)if(s->slots[i].valid&&s->slots[i].session==session&&check_slot(s,i))return s->slots[i].effective_from>kb_jst_day(now)?4:3;
    return 2;
  }
  if(session!=s->transfer.session||s->transfer.received!=s->transfer.length)return 2;
  int slot=s->transfer.slot;
  kb_slot_t candidate= {
    .valid=true,.checked=true,.version=s->transfer.version,
    .length=s->transfer.length,.crc=s->transfer.crc,.session=session
  };
  s->cache_slot=-1;
  for(uint32_t off=0,seq=0;off<candidate.length;seq++) {
    unsigned n=candidate.length-off;
    if(n>KB_CHUNK_SIZE)n=KB_CHUNK_SIZE;
    if(s->io.read(s->io.context,key(slot,seq),s->cache+off,n)!=(int)n) {
      kb_store_abort(s);
      return 2;
    }
    off+=n;
  }
  if(kb_crc32(s->cache,candidate.length)!=candidate.crc||kb_dataset_open(&s->cached,s->cache,candidate.length)!=KB_OK) {
    kb_store_abort(s);
    return 2;
  }
  if(s->cached.minimum_app_version>1||strcmp(kb_coverage_id(&s->cached),"minami-kasugaoka-v1")) {
    kb_store_abort(s);
    return 6;
  }
  if(s->cached.release_version!=candidate.version) {
    kb_store_abort(s);
    return 2;
  }
  candidate.effective_from=s->cached.effective_from;
  candidate.valid_until=s->cached.valid_until;
  for(int i=0;i<KB_STORE_SLOTS;i++)if(s->slots[i].valid&&s->slots[i].effective_from<=candidate.effective_from&&s->slots[i].version>=candidate.version) {
    kb_store_abort(s);
    return 2;
  }
  /* A newer current correction must not mask a still-valid pending release.
  * Publishers transfer its newer future companion first. */  for(int i=0;i<KB_STORE_SLOTS;i++)if(s->slots[i].valid&&s->slots[i].effective_from>kb_jst_day(now)) {
    int applicable=select_for_day(s,s->slots[i].effective_from);
    if(applicable>=0&&candidate.effective_from<=kb_jst_day(now)&&candidate.version>=s->slots[applicable].version&&candidate.valid_until>=s->slots[i].effective_from) {
      kb_store_abort(s);
      return 2;
    }
  }
  int active=select_for_day(s,kb_jst_day(now));
  if(active>=0&&candidate.effective_from<=kb_jst_day(now)&&candidate.effective_from<s->slots[active].effective_from) {
    kb_store_abort(s);
    return 2;
  }
  /* The alternate directory is the only commit point. Its own CRC rejects a
   * torn bank; full validation rejects a torn payload before use on restart. */
  if(!write_directory(s,slot,&candidate,0)) {
    kb_store_abort(s);
    return 5;
  }
  s->slots[slot]=candidate;
  s->cache_slot=slot;
  s->transfer.running=false;
  return candidate.effective_from>kb_jst_day(now)?4:3;
}
bool kb_store_tick(kb_store_t *s,int64_t now) {
  if(s->transfer.running&&(now-s->transfer.last_activity>30||now<s->transfer.last_activity)) {
    kb_store_abort(s);
    return true;
  }
  return false;
}
void kb_store_abort(kb_store_t *s) {
  s->transfer.running=false;
  /* Chunk writes touch persistence, not RAM. Preserve an untouched resource
   * cache; COMMIT/load_slot already invalidate it before reading any payload. */
  if(s->cache_slot!=KB_STORE_CACHE_BASELINE)s->cache_slot=KB_STORE_CACHE_INVALID;
}
bool kb_store_restore(kb_store_t *s) {
  kb_store_abort(s);
  s->recovery_notice=true;
  if(s->directory_generation>UINT32_MAX-2)return false;
  if(!write_directory(s,-1,NULL,UINT8_MAX))return false;
  for(int i=0;i<KB_STORE_SLOTS;i++)s->slots[i].valid=false;
  if(!write_directory(s,-1,NULL,UINT8_MAX))return false;
  retire_legacy(s);
  return true;
}
