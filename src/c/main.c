#include "app.h"
#include "policies.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
kb_app_t app;
static kb_control_t s_control;
static AppTimer *s_deadline;
static bool s_auto_waiting;
static bool s_request_hello;
static bool s_cancel_phone_update;
static bool s_startup_handled;
static AppTimer *s_begin_timer;
static uint32_t s_cancelled_session;
static struct {
  bool active;
  uint32_t session,version,length,crc;
} s_begin;
static int p_read(void *c,uint32_t k,void *b,size_t n) {
  (void)c;
  return persist_read_data(k,b,n);
}
static int p_write(void *c,uint32_t k,const void *b,size_t n) {
  (void)c;
  return persist_write_data(k,b,n);
}
static int p_remove(void *c,uint32_t k) {
  (void)c;
  return persist_delete(k);
}
static int baseline_read(void *context,void *buffer,size_t length) {
  return (int)resource_load((ResHandle)context,(uint8_t *)buffer,length);
}
static uint32_t u32(const uint8_t *b) {
  return (uint32_t)b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);
}
static uint16_t u16(const uint8_t *b) {
  return b[0]|((uint16_t)b[1]<<8);
}
static void put32(uint8_t *b,uint32_t n) {
  for(int i=0;i<4;i++)b[i]=n>>(8*i);
}
static void put16(uint8_t *b,uint16_t n) {
  b[0]=n;
  b[1]=n>>8;
}
const kb_dataset_t *app_dataset(void) {
  return kb_store_resolve(&app.store,kb_jst_day(time(NULL)));
}
bool app_point_exists(void *ctx,uint16_t id) {
  (void)ctx;
  const kb_dataset_t *d=app_dataset();
  kb_boarding_point_t p;
  return id<=255&&d&&kb_boarding_point_get(d,id,&p);
}
kb_query_t app_query(void) {
  return(kb_query_t) {
    .resolve=kb_store_resolve,.context=&app.store,.now_utc=time(NULL),.boarding_point_id=app.point,.override=app.override
  };
}
void app_redraw(void) {
  if(app.layer)layer_mark_dirty(app.layer);
}
static bool save_control(const kb_control_t *candidate) {
  bool ok=kb_control_commit(&s_control,candidate,&app.pref_generation,&app.pref_slot,p_write,NULL);
  if(ok) {
    app.prefs=s_control.preferences;
    app.last_attempt=s_control.last_attempt;
    app.last_success=s_control.last_success;
    app.request=s_control.update_request;
    app.first_use=!s_control.hint_seen;
  }
  return ok;
}
bool app_save_preferences(const kb_preferences_t *p) {
  bool disabling_location=(app.prefs.bytes[1]&KB_PREF_LOCATION)&&!(p->bytes[1]&KB_PREF_LOCATION);
  kb_control_t candidate=s_control;
  candidate.preferences=*p;
  bool ok=save_control(&candidate);
  if(ok)ui_apply_appearance();
  if(ok&&disabling_location) {
    app.location_request++;
    app.nearby_waiting=false;
    app.nearby_count=0;
    app.nearby_status=8;
    app_clear_all_distances(8);
  }
  if(!ok)snprintf(app.notice,sizeof(app.notice),"Settings not saved");
  return ok;
}
void app_clear_all_distances(unsigned status) {
  ui_remember_all_point();
  app.all_request++;
  app.all_waiting=false;app.all_nearby_count=0;app.all_version=0;
  app.all_stamp=0;app.all_accuracy=0;app.all_status=(int)status;
  if(app.screen==KB_SCREEN_ALL_BOARD||app.screen==KB_SCREEN_ALL_POINTS)ui_refresh();
}
static void log_all_ids(void) {
  if(!app.all_prefs.count)APP_LOG(APP_LOG_LEVEL_INFO,"All ids0 empty");
  for(unsigned start=0;start<app.all_prefs.count;start+=16) {
    char ids[70];unsigned used=0;ids[0]=0;
    for(unsigned i=start;i<app.all_prefs.count&&i<start+16;i++)used+=(unsigned)snprintf(ids+used,sizeof(ids)-used,"%s%u",i==start?"":" ",app.all_prefs.ids[i]);
    APP_LOG(APP_LOG_LEVEL_INFO,"All ids%u %s",start,ids);
  }
}
uint32_t app_all_distance(uint16_t id) {
  if(!(app.prefs.bytes[1]&KB_PREF_LOCATION)||app.all_prefs.reference==KB_ALL_REFERENCE_MANUAL||
    app.all_waiting||app.all_status>1||!app.all_stamp||app.all_version!=app.active_version)return UINT32_MAX;
  if(app.all_prefs.reference==KB_ALL_REFERENCE_CURRENT&&time(NULL)-(int64_t)app.all_stamp>120)return UINT32_MAX;
  for(unsigned i=0;i<app.all_nearby_count;i++)if(app.all_nearby[i].id==id)return app.all_nearby[i].metres;
  return UINT32_MAX;
}
bool app_save_extras(const kb_extras_t *candidate) {
  if(!kb_extras_commit(&app.extras,candidate,&app.extras_generation,&app.extras_slot,p_write,NULL)) {
    snprintf(app.notice,sizeof(app.notice),"Settings not saved");return false;
  }
  app_reschedule_wakeups();
  return true;
}
bool app_save_all_preferences(const kb_all_preferences_t *candidate) {
  bool changed=app.all_prefs.reference!=candidate->reference;
  if(!kb_all_preferences_commit(&app.all_prefs,candidate,&app.all_generation,&app.all_slot,p_write,NULL)) {
    snprintf(app.notice,sizeof(app.notice),"Selection not saved");return false;
  }
  app.notice[0]=0;
  if(changed)app_clear_all_distances(2);
  APP_LOG(APP_LOG_LEVEL_INFO,"All saved generation%lu reference%u count%u",(unsigned long)app.all_generation,app.all_prefs.reference,app.all_prefs.count);
  log_all_ids();
  return true;
}
void app_dismiss_hint(void) {
  if(!app.first_use)return;
  kb_control_t candidate=s_control;
  candidate.hint_seen=true;
  if(!save_control(&candidate))s_control.hint_seen=true;
  /* A failed hint-only save must not repeatedly interrupt this session. */
  app.first_use=false;
}
static void load_preferences(void) {
  kb_control_load_result_t loaded=kb_control_load(&s_control,&app.pref_generation,&app.pref_slot,p_read,NULL);
  if(loaded==KB_CONTROL_LEGACY) {
    /* Migrate only the unpublished earlier journal; ordinary launches perform
     * two bounded control reads, not separate history/hint field searches. */
    uint8_t b[4];
    kb_control_t candidate=s_control;
    if(p_read(NULL,20,b,sizeof(b))==sizeof(b))candidate.last_attempt=u32(b);
    if(p_read(NULL,21,b,sizeof(b))==sizeof(b))candidate.last_success=u32(b);
    candidate.hint_seen=persist_exists(23);
    if(!save_control(&candidate)) {
      s_control=candidate;
      snprintf(app.notice,sizeof(app.notice),"Settings migration needs retry");
    }
  }
  app.prefs=s_control.preferences;
  app.last_attempt=s_control.last_attempt;
  app.last_success=s_control.last_success;
  app.request=s_control.update_request;
  app.first_use=!s_control.hint_seen;
  app.point=kb_pref_default(&app.prefs);
}
static void load_all_preferences(void) {
  kb_all_load_result_t loaded=kb_all_preferences_load(&app.all_prefs,&app.all_generation,&app.all_slot,p_read,NULL);
  if(loaded==KB_ALL_EMPTY) {
    for(unsigned i=0;i<app.prefs.bytes[5];i++)app.all_prefs.ids[app.all_prefs.count++]=kb_pref_favourite(&app.prefs,i);
  }
  else if(loaded==KB_ALL_INVALID)snprintf(app.notice,sizeof(app.notice),"All selection needs recovery");
  APP_LOG(APP_LOG_LEVEL_INFO,"All loaded generation%lu reference%u count%u",(unsigned long)app.all_generation,app.all_prefs.reference,app.all_prefs.count);
  log_all_ids();
}
/* Small FIFO: protocol ACKs and commands share the AppMessage outbox. */ typedef struct  {
  uint16_t present;
  uint32_t value[14];
  uint16_t len;
  uint8_t data[256];
  bool automatic;
  uint8_t retries;
}
message_t;
static message_t s_queue[8];
static unsigned s_head,s_count;
static bool s_sending;
static AppTimer *s_send_retry;
static void send_next(void);
static void failed(DictionaryIterator *,AppMessageResult,void *);
static void send_retry(void *ctx) {
  (void)ctx;
  s_send_retry=NULL;
  send_next();
}
static message_t *enqueue(unsigned type) {
  if(s_count==8)return NULL;
  message_t *m=&s_queue[(s_head+s_count)%8];
  memset(m,0,sizeof(*m));
  m->present=1;
  m->value[0]=type;
  s_count++;
  return m;
}
static void field(message_t *m,unsigned k,uint32_t v) {
  if(m) {
    m->present|=1u<<k;
    m->value[k]=v;
  }
}
static void bytes(message_t *m,const void *b,unsigned n) {
  if(m&&n<=sizeof(m->data)) {
    memcpy(m->data,b,n);
    m->len=n;
  }
}
static bool location_message_active(const message_t *m) {
  if(m->value[0]==14)return app.all_waiting&&m->value[8]==app.all_request&&m->value[3]==app.all_version&&m->value[13]==app.all_prefs.reference;
  if(m->value[0]==9)return app.nearby_waiting&&m->value[8]==app.location_request&&m->value[3]==app.location_version;
  return true;
}
static void send_next(void) {
  if(s_sending)return;
  while(s_count&&!location_message_active(&s_queue[s_head])) {
    s_head=(s_head+1)%8;s_count--;
  }
  if(!s_count)return;
  DictionaryIterator *it;
  AppMessageResult r=app_message_outbox_begin(&it);
  if(r!=APP_MSG_OK) {
    failed(NULL,r,NULL);
    return;
  }
  message_t *m=&s_queue[s_head];
  for(unsigned k=0;k<14;k++)if(m->present&(1u<<k))dict_write_uint32(it,k,m->value[k]);
  if(m->len)dict_write_data(it,6,m->data,m->len);
  s_sending=true;
  r=app_message_outbox_send();
  if(r!=APP_MSG_OK) {
    s_sending=false;
    failed(NULL,r,NULL);
  }
}
static void ack(uint32_t session,uint16_t seq,int status,unsigned phase) {
  message_t *m=enqueue(8);
  field(m,1,session);
  field(m,2,seq);
  field(m,7,status);
  field(m,13,phase);
  send_next();
}
static void settings_ack(uint32_t token,int status) {
  message_t *m=enqueue(8);field(m,8,token);field(m,7,status);field(m,13,11);send_next();
}
static unsigned s_catalogue_index;
static uint32_t s_catalogue_version;
static bool s_catalogue_pending;
static void catalogue_next(void) {
  if(!s_catalogue_pending||s_count>5)return;
  const kb_dataset_t *d=app_dataset();
  if(!d||d->release_version!=s_catalogue_version) {
    s_catalogue_pending=false;
    return;
  }
  uint8_t b[256];
  unsigned len=0;
  size_t count=kb_boarding_point_count(d);
  while(s_catalogue_index<count) {
    kb_boarding_point_t p;
    kb_operator_t o;
    kb_boarding_point_at(d,s_catalogue_index,&p);
    kb_operator_get(d,p.operator_id,&o);
    char label[92];
    snprintf(label,sizeof(label),"%s | %s | %s",p.short_name,p.direction,o.short_name);
    unsigned n=strlen(label);
    if(len+3+n>sizeof(b))break;
    put16(b+len,p.id);
    b[len+2]=n;
    memcpy(b+len+3,label,n);
    len+=3+n;
    s_catalogue_index++;
  }
  message_t *m=enqueue(13);
  field(m,3,d->release_version);
  field(m,2,app.catalogue_seq++);
  field(m,7,s_catalogue_index>=count);
  bytes(m,b,len);
  s_catalogue_pending=s_catalogue_index<count;
  send_next();
}
void app_send_state(void) {
  const kb_dataset_t *d=app_dataset();
  uint32_t version=d?d->release_version:0;
  message_t *m=enqueue(2);
  field(m,3,version);
  field(m,8,app.request);
  field(m,9,app.last_success);
  field(m,12,kb_store_pending(&app.store,kb_jst_day(time(NULL)),NULL));
  field(m,13,app.prefs.bytes[1]);
  if(s_cancel_phone_update&&m) {
    field(m,7,2);
    s_cancel_phone_update=false;
  }
  else if(s_request_hello&&m) {
    field(m,7,1);
    s_request_hello=false;
  }
  field(m,4,KB_MAX_DATASET_BYTES);
  uint8_t state_bytes[KB_PREF_BYTES+KB_EXTRAS_WIRE_BYTES];
  memcpy(state_bytes,app.prefs.bytes,KB_PREF_BYTES);
  kb_extras_encode(&app.extras,state_bytes+KB_PREF_BYTES);
  bytes(m,state_bytes,sizeof(state_bytes));
  s_catalogue_index=0;
  app.catalogue_seq=0;
  s_catalogue_version=version;
  s_catalogue_pending=d!=NULL;
  send_next();
}
static void deadline(void *ctx);
static void ensure_deadline(void) {
  if(!s_deadline)s_deadline=app_timer_register(1000,deadline,NULL);
}
static void begin_reply(int status) {
  ack(s_begin.session,0,status,5);
  APP_LOG(APP_LOG_LEVEL_INFO,"Update begin v%lu bytes%lu status%d",(unsigned long)s_begin.version,(unsigned long)s_begin.length,status);
  s_begin.active=false;
  app.checking=status==0;
  app.update_status=status==0?8:status==6?6:5;
  if(!status)ensure_deadline();
  app_redraw();
}
static void prepare_begin(void *context) {
  (void)context;
  s_begin_timer=NULL;
  if(!s_begin.active)return;
  /* A historical payload never blocks first paint. Before choosing a staging
   * slot, validate one retained snapshot per event-loop turn so buttons can
   * run between reads and no unchecked recovery copy can be evicted. */
  if(kb_store_check_next(&app.store)) {
    s_begin_timer=app_timer_register(1,prepare_begin,NULL);
    if(!s_begin_timer)begin_reply(5);
    return;
  }
  app.check_started=time(NULL);
  begin_reply(kb_store_begin(&app.store,s_begin.session,s_begin.version,s_begin.length,s_begin.crc,app.check_started));
}
void app_restore_timetable(void) {
  kb_control_t candidate=s_control;
  if(candidate.update_request==UINT32_MAX) {
    app.update_status=10;
    snprintf(app.notice,sizeof(app.notice),"Restore request limit reached");
    return;
  }
  candidate.update_request++;
  if(!save_control(&candidate)) {
    app.update_status=10;
    snprintf(app.notice,sizeof(app.notice),"Restore could not save; retry");
    return;
  }
  /* Restore can be confirmed while a deferred BEGIN is validating retained
   * data. Cancel that job and reject its queued retries before removing slots. */
  if(s_begin_timer)app_timer_cancel(s_begin_timer);
  s_begin_timer=NULL;
  if(s_begin.active) {
    s_cancelled_session=s_begin.session;
    ack(s_begin.session,0,2,5);
    APP_LOG(APP_LOG_LEVEL_INFO,"Restore cancelled deferred BEGIN session%lu",(unsigned long)s_begin.session);
  }
  else if(app.store.transfer.running)s_cancelled_session=app.store.transfer.session;
  s_begin.active=false;
  s_auto_waiting=false;
  app.checking=false;
  /* Invalidate a phone download which has not sent BEGIN yet, including any
   * old BEGIN already queued before the phone receives our cancellation. */
  s_cancel_phone_update=true;
  bool restored=kb_store_restore(&app.store);
  app.update_status=restored?9:10;
  snprintf(app.notice,sizeof(app.notice),restored?"Bundled timetable restored":"Restore incomplete; retry");
  app.changed=true;
  app.nearby_count=0;
  app.nearby_waiting=false;
  app.nearby_status=2;
  app_clear_all_distances(2);
  app_send_state();
}
void app_check_updates(bool manual) {
  if(app.checking||app.store.transfer.running) {
    snprintf(app.notice,sizeof(app.notice),"Check already running");
    app_redraw();
    return;
  }
  if(!app.phone_ready) {
    app.update_status=4;
    snprintf(app.notice,sizeof(app.notice),"Phone not ready");
    if(manual&&connection_service_peek_pebble_app_connection()) {
      s_request_hello=true;
      app_send_state();
      snprintf(app.notice,sizeof(app.notice),"Connecting; SELECT to retry");
    }
    app_redraw();
    return;
  }
  uint32_t now=(uint32_t)time(NULL);
  if(!manual&&!kb_auto_check_eligible(app.prefs.bytes[1]&KB_PREF_AUTO,app.phone_ready,app.checking||app.store.transfer.running,app.last_attempt,now))return;
  if(s_control.update_request==UINT32_MAX) {
    app.update_status=5;
    snprintf(app.notice,sizeof(app.notice),"Update request limit reached");
    app_redraw();
    return;
  }
  message_t *m=enqueue(3);
  if(!m)return;
  kb_control_t candidate=s_control;
  candidate.update_request++;
  if(!manual)candidate.last_attempt=now;
  if(!save_control(&candidate)) {
    s_count--;
    app.update_status=5;
    snprintf(app.notice,sizeof(app.notice),"Cannot save update request");
    app_redraw();
    return;
  }
  field(m,8,app.request);
  field(m,7,manual?1:0);
  m->automatic=!manual;
  app.checking=true;
  app.check_started=now;
  app.update_status=0;
  send_next();
  ensure_deadline();
  app_redraw();
}
void app_request_location(void) {
  app_clear_all_distances(2);
  app.nearby_waiting=false;
  app.trip_context=KB_CONTEXT_NEARBY;
  if(!(app.prefs.bytes[1]&KB_PREF_LOCATION)) {
    app.nearby_status=8;
    app_redraw();
    return;
  }
  if(!app.phone_ready) {
    app.nearby_status=5;
    if(connection_service_peek_pebble_app_connection()) {
      s_request_hello=true;
      app_send_state();
    }
    app_redraw();
    return;
  }
  const kb_dataset_t *d=app_dataset();
  if(!d) {
    app.nearby_status=7;
    return;
  }
  uint8_t b[256];
  unsigned n=0;
  /* Favourite order stabilizes uncertain distances. */  uint8_t ids[KB_MAX_POINTS];
  unsigned count=0;
  for(unsigned i=0;i<app.prefs.bytes[5];i++)ids[count++]=kb_pref_favourite(&app.prefs,i);
  for(size_t i=0;i<kb_boarding_point_count(d)&&count<KB_MAX_POINTS;i++) {
    kb_boarding_point_t p;
    kb_boarding_point_at(d,i,&p);
    bool found=false;
    for(unsigned j=0;j<count;j++)if(ids[j]==p.id)found=true;
    if(!found)ids[count++]=p.id;
  }
  for(unsigned i=0;i<count;i++) {
    kb_boarding_point_t p;
    if(kb_boarding_point_get(d,ids[i],&p)&&p.has_coordinate&&n+10<=sizeof(b)) {
      put16(b+n,p.id);
      put32(b+n+2,p.latitude_e6*10);
      put32(b+n+6,p.longitude_e6*10);
      n+=10;
    }
  }
  if(!n) {
    app.nearby_status=7;
    app_redraw();
    return;
  }
  app.location_request++;
  app.location_version=d->release_version;
  message_t *m=enqueue(9);
  field(m,8,app.location_request);
  field(m,3,d->release_version);
  bytes(m,b,n);
  app.nearby_waiting=true;
  app.location_started=time(NULL);
  send_next();
  ensure_deadline();
  app_redraw();
}
void app_request_all_location(void) {
  app.location_request++;app.nearby_waiting=false;app.nearby_count=0;app.nearby_status=2;
  app_clear_all_distances(2);
  if(app.all_prefs.reference==KB_ALL_REFERENCE_MANUAL) {app_redraw();return;}
  if(!(app.prefs.bytes[1]&KB_PREF_LOCATION)) {app.all_status=8;app_redraw();return;}
  if(!app.phone_ready) {
    app.all_status=5;
    if(connection_service_peek_pebble_app_connection()) {s_request_hello=true;app_send_state();}
    app_redraw();return;
  }
  const kb_dataset_t *d=app_dataset();
  if(!d) {app.all_status=7;app_redraw();return;}
  uint8_t b[256];unsigned n=0;
  for(size_t i=0;i<kb_boarding_point_count(d);i++) {
    kb_boarding_point_t p;kb_boarding_point_at(d,i,&p);
    if(p.has_coordinate&&n+10<=sizeof(b)) {
      put16(b+n,p.id);put32(b+n+2,p.latitude_e6*10);put32(b+n+6,p.longitude_e6*10);n+=10;
    }
  }
  if(!n) {app.all_status=7;app_redraw();return;}
  message_t *m=enqueue(14);
  if(!m) {app.all_status=5;app_redraw();return;}
  app.all_version=d->release_version;app.active_version=d->release_version;
  field(m,8,app.all_request);field(m,3,app.all_version);field(m,13,app.all_prefs.reference);
  bytes(m,b,n);app.all_waiting=true;app.all_started=time(NULL);send_next();ensure_deadline();app_redraw();
}
static void deadline(void *ctx) {
  (void)ctx;
  s_deadline=NULL;
  int64_t now=time(NULL);
  bool changed=false;
  if(kb_store_tick(&app.store,now)) {
    app.update_status=5;
    app.checking=false;
    snprintf(app.notice,sizeof(app.notice),"Transfer interrupted; retry");
    changed=true;
  }
  if(app.nearby_waiting&&now-app.location_started>=16) {
    app.nearby_waiting=false;
    app.nearby_status=4;
    changed=true;
  }
  if(app.all_waiting&&now-app.all_started>=16) {app_clear_all_distances(4);changed=true;}
  if(app.checking&&now-app.check_started>90&&!app.store.transfer.running) {
    app.checking=false;
    app.update_status=5;
    changed=true;
  }
  if(s_auto_waiting&&app.phone_ready&&!s_catalogue_pending&&!s_count) {
    s_auto_waiting=false;
    app_check_updates(false);
  }
  if(app.checking||app.store.transfer.running||app.nearby_waiting||app.all_waiting||(s_auto_waiting&&app.phone_ready))ensure_deadline();
  if(changed)app_redraw();
}
static bool number(DictionaryIterator *it,unsigned key,uint32_t *out) {
  Tuple *t=dict_find(it,key);
  if(!t||(t->type!=TUPLE_UINT&&t->type!=TUPLE_INT)||(t->length!=1&&t->length!=2&&t->length!=4))return false;
  *out=t->length==1?t->value->uint8:t->length==2?t->value->uint16:t->value->uint32;
  return true;
}
static void inbox(DictionaryIterator *it,void *ctx) {
  (void)ctx;
  uint32_t type=0,session=0,seq=0,status=0,version=0,length=0,crc=0,request=0,stamp=0,accuracy=0,flags=0;
  number(it,0,&type);
  number(it,1,&session);
  number(it,2,&seq);
  number(it,3,&version);
  number(it,4,&length);
  number(it,5,&crc);
  number(it,7,&status);
  number(it,8,&request);
  number(it,9,&stamp);
  number(it,10,&accuracy);
  number(it,13,&flags);
  Tuple *data=dict_find(it,6);
  bool payload=data&&data->type==TUPLE_BYTE_ARRAY;
  int64_t now=time(NULL);
  if(type==1) {
    app.phone_ready=true;
    app_send_state();
    s_auto_waiting=true;
    ensure_deadline();
    if(!s_startup_handled) {
      s_startup_handled=true;
      if((app.prefs.bytes[1]&(KB_PREF_LOCATION|KB_PREF_NEARBY_START))==(KB_PREF_LOCATION|KB_PREF_NEARBY_START)&&app.screen==KB_SCREEN_NEARBY)app_request_location();
    }
    /* Nearby opened before the phone was ready: ask again now it is. A
     * startup request above is already waiting and is not repeated. */
    if(app.screen==KB_SCREEN_NEARBY&&app.nearby_status==5&&!app.nearby_waiting&&(app.prefs.bytes[1]&KB_PREF_LOCATION))app_request_location();
  }
  else if(type==4) {
    if(request!=app.request||!app.checking)return;
    if(status>8)return;
    app.update_status=status;
    if(status==2||status==3) {
      if(stamp&&stamp<=(uint32_t)now+300) {
        kb_control_t candidate=s_control;
        candidate.last_success=stamp;
        if(!save_control(&candidate))snprintf(app.notice,sizeof(app.notice),"Check time could not be saved");
      }
      app.checking=false;
    }
    else if(status>=4&&status<=7)app.checking=false;
  }
  else if(type==5) {
    if(!number(it,8,&request)||request!=app.request) {
      ack(session,0,2,5);
      APP_LOG(APP_LOG_LEVEL_INFO,"Rejected obsolete BEGIN session%lu",(unsigned long)session);
    }
    else if(session&&session==s_cancelled_session)ack(session,0,2,5);
    else if(s_begin.active) {
      if(session!=s_begin.session||version!=s_begin.version||length!=s_begin.length||crc!=s_begin.crc)ack(session,0,2,5);
      /* A matching retry receives the one eventual completion ACK. */
    }
    else {
      s_begin.active=true;
      s_begin.session=session;
      s_begin.version=version;
      s_begin.length=length;
      s_begin.crc=crc;
      app.update_status=8;
      app.checking=true;
      app.check_started=now;
      s_begin_timer=app_timer_register(1,prepare_begin,NULL);
      if(!s_begin_timer)begin_reply(5);
    }
  }
  else if(type==6) {
    app.check_started=now;
    int r=payload&&seq<=65535?kb_store_chunk(&app.store,session,seq,data->value->data,data->length,now):2;
    ack(session,seq,r,6);
  }
  else if(type==7) {
    app.check_started=now;
    int r=kb_store_commit(&app.store,session,now);
    ack(session,65535,r,7);
    if(r==3||r==4) {
      app.changed=true;
      app.nearby_count=0;
      app.nearby_waiting=false;
      app.nearby_status=2;
      app_clear_all_distances(2);
      if(app.screen==KB_SCREEN_NEARBY)app.selected=0;
      app.update_status=3;
      snprintf(app.notice,sizeof(app.notice),r==4?"Future timetable ready":"Timetable updated");
      ui_refresh();
    }
    else {
      app.update_status=r==6?6:5;
      app.checking=false;
    }
    APP_LOG(APP_LOG_LEVEL_INFO,"Update commit session%lu status%d heap%lu",(unsigned long)session,r,(unsigned long)heap_bytes_free());
  }
  else if(type==10) {
    const kb_dataset_t *d=app_dataset();
    if(!(app.prefs.bytes[1]&KB_PREF_LOCATION)||request!=app.location_request||!app.nearby_waiting||!d||version!=d->release_version||version!=app.location_version||status>9)return;
    if(stamp>(uint32_t)now+30)return;
    unsigned count=payload?data->length/6:0;
    if((payload&&data->length%6)||count>KB_MAX_POINTS)return;
    kb_near_t temp[KB_MAX_POINTS];
    for(unsigned i=0;i<count;i++) {
      temp[i].id=u16(data->value->data+6*i);
      temp[i].metres=u32(data->value->data+6*i+2);
      kb_boarding_point_t p;
      if(!kb_boarding_point_get(d,temp[i].id,&p)||!p.has_coordinate||temp[i].metres>40075000)return;
      for(unsigned j=0;j<i;j++)if(temp[j].id==temp[i].id)return;
    }
    uint16_t focus=app.screen==KB_SCREEN_NEARBY&&app.selected>0&&app.selected<=(int)app.nearby_count?app.nearby[app.selected-1].id:0;
    memcpy(app.nearby,temp,count*sizeof(*temp));
    app.nearby_count=count;
    app.nearby_status=status;
    APP_LOG(APP_LOG_LEVEL_INFO,"Nearby status%lu count%u accuracy%lu reason%lu",(unsigned long)status,count,(unsigned long)accuracy,(unsigned long)flags);
    if(status==0&&(!stamp||now-stamp>120))app.nearby_status=2;
    else if(status==0&&accuracy>100)app.nearby_status=1;
    app.location_stamp=stamp;
    app.accuracy=accuracy;
    app.nearby_waiting=false;
    bool kept=false;
    for(unsigned i=0;i<count;i++)if(temp[i].id==focus) {
      app.selected=i+1;
      kept=true;
    }
    if(app.screen==KB_SCREEN_NEARBY&&!kept&&app.selected>(int)count)app.selected=0;
  }
  else if(type==11) {
    kb_preferences_t p;
    kb_extras_t e=app.extras;
    int result=2;
    /* 80 preference bytes, optionally followed by the 28 extras bytes; both
     * validate before either record is written. */
    bool with_extras=payload&&data->length==KB_PREF_BYTES+KB_EXTRAS_WIRE_BYTES;
    if(payload&&(data->length==KB_PREF_BYTES||with_extras)&&
       kb_preferences_parse(&p,data->value->data,KB_PREF_BYTES,app_point_exists,NULL)&&
       (!with_extras||kb_extras_parse(&e,data->value->data+KB_PREF_BYTES,KB_EXTRAS_WIRE_BYTES,app_point_exists,NULL))) {
      result=app_save_preferences(&p)&&(!with_extras||app_save_extras(&e))?0:5;
      if(!result)snprintf(app.notice,sizeof(app.notice),"Settings saved");
    }
    else snprintf(app.notice,sizeof(app.notice),"Settings rejected");
    if(number(it,8,&request))settings_ack(request,result);
    app_send_state();
  }
  else if(type==15) {
    const kb_dataset_t *d=app_dataset();
    if(!number(it,8,&request)||!number(it,3,&version)||!number(it,7,&status)||
      !(app.prefs.bytes[1]&KB_PREF_LOCATION)||!app.all_waiting||request!=app.all_request||
      !number(it,13,&flags)||flags!=app.all_prefs.reference||!d||version!=d->release_version||
      version!=app.all_version||status>9)return;
    if(status<=1&&(!number(it,9,&stamp)||!number(it,10,&accuracy)))return;
    if(status==2) {
      bool has_stamp=dict_find(it,9)!=NULL,has_accuracy=dict_find(it,10)!=NULL;
      if(has_stamp!=has_accuracy)return;
      if(has_stamp) {if(!number(it,9,&stamp)||!number(it,10,&accuracy))return;}
      else stamp=accuracy=0;
    }
    if(status==0&&(!stamp||stamp>(uint32_t)now+30||!payload||!data->length))return;
    if(status!=0&&payload&&data->length)return;
    unsigned count=payload?data->length/6:0;
    if((payload&&data->length%6)||count>KB_MAX_POINTS)return;
    kb_near_t temp[KB_MAX_POINTS];
    for(unsigned i=0;i<count;i++) {
      temp[i].id=u16(data->value->data+6*i);temp[i].metres=u32(data->value->data+6*i+2);
      kb_boarding_point_t p;
      if(!kb_boarding_point_get(d,temp[i].id,&p)||!p.has_coordinate||temp[i].metres>40075000)return;
      for(unsigned j=0;j<i;j++)if(temp[j].id==temp[i].id)return;
    }
    ui_remember_all_point();
    app.all_waiting=false;app.all_status=(int)status;app.all_stamp=stamp;app.all_accuracy=accuracy;
    if(status==0&&app.all_prefs.reference==KB_ALL_REFERENCE_CURRENT&&(!stamp||now-stamp>120))app.all_status=2;
    if(status==0&&accuracy>100&&app.all_status==0)app.all_status=1;
    app.all_nearby_count=app.all_status==0?count:0;
    if(app.all_nearby_count)memcpy(app.all_nearby,temp,count*sizeof(*temp));
    APP_LOG(APP_LOG_LEVEL_INFO,"All distance reference%u request%lu status%d count%u",app.all_prefs.reference,(unsigned long)request,app.all_status,app.all_nearby_count);
    ui_refresh();
  }
  else if(type==16&&number(it,7,&status)&&(status==0||status==9)) {
    if(app.all_prefs.reference==KB_ALL_REFERENCE_HOME)app_clear_all_distances(status==9?9:2);
  }
  if(type!=6||app.screen==KB_SCREEN_STATUS)app_redraw();
}
static void sent(DictionaryIterator *it,void *ctx) {
  (void)it;
  (void)ctx;
  if(s_count) {
    s_head=(s_head+1)%8;
    s_count--;
  }
  s_sending=false;
  catalogue_next();
  send_next();
}
static void failed(DictionaryIterator *it,AppMessageResult reason,void *ctx) {
  (void)it;
  (void)ctx;
  (void)reason;
  s_sending=false;
  bool connected=connection_service_peek_pebble_app_connection();
  if(s_count) {
    message_t *m=&s_queue[s_head];
    bool active=location_message_active(m);
    if(connected&&active&&m->retries++<3) {
      if(!s_send_retry)s_send_retry=app_timer_register(300,send_retry,NULL);
      return;
    }
    if(m->value[0]==3) {
      app.checking=false;
      app.update_status=connected?5:4;
      if(m->automatic&&!connected)s_auto_waiting=true;
    }
    if(active&&m->value[0]==14)app_clear_all_distances(5);
    if(active&&m->value[0]==9) {
      app.nearby_waiting=false;app.nearby_count=0;app.nearby_status=5;
      app.location_stamp=0;app.accuracy=0;
    }
    s_head=(s_head+1)%8;
    s_count--;
  }
  if(!connected) {
    app.phone_ready=false;
    app_clear_all_distances(5);
    s_catalogue_pending=false;
  }
  app_redraw();
  send_next();
}
static void tick(struct tm *t,TimeUnits u) {
  (void)t;
  (void)u;
  int32_t day=kb_jst_day(time(NULL));
  if(app.override.jst_day!=day)app.override.day_type=KB_DAY_UNKNOWN;
  const kb_dataset_t *d=app_dataset();
  if(d&&app.active_version!=d->release_version) {
    bool previous=app.active_version!=0;
    app.active_version=d->release_version;
    if(previous)app.changed=true;
    app.nearby_count=0;
    app.nearby_waiting=false;
    app.nearby_status=2;
    app_clear_all_distances(2);
    if(app.screen==KB_SCREEN_NEARBY)app.selected=0;
    app_send_state();
  }
  if(app.all_prefs.reference==KB_ALL_REFERENCE_CURRENT&&app.all_stamp&&app.all_status<=1&&time(NULL)-(int64_t)app.all_stamp>120)app_clear_all_distances(2);
  ui_refresh();
  app_redraw();
}
static void focus(bool active) {
  if(active) {
    tick(NULL,MINUTE_UNIT);
    if(app.phone_ready) {
      s_auto_waiting=true;
      ensure_deadline();
    }
  }
}
static void connection(bool connected) {
  if(!connected) {
    app.phone_ready=false;
    app.nearby_waiting=false;
    app.nearby_status=5;
    app_clear_all_distances(5);
  }
  else {
    s_request_hello=true;
    app_send_state();
  }
  app_redraw();
}
static void wakeup(WakeupId id,int32_t cookie) {
  (void)id;
  app_show_wakeup(cookie);
}
static void init(void) {
  APP_LOG(APP_LOG_LEVEL_DEBUG,"INIT entered");
  memset(&app,0,sizeof(app));
  app.nearby_status=5;
  app.all_status=5;
  app.update_status=9;
  app.trip_context=KB_CONTEXT_NEARBY;
  app.override.day_type=KB_DAY_UNKNOWN;
  ResHandle handle=resource_get_handle(RESOURCE_ID_TIMETABLE);
  size_t size=resource_size(handle);
  app.cache=malloc(KB_MAX_DATASET_BYTES);
  if(app.cache) {
    kb_store_io_t io= {
      NULL,p_read,p_write,p_remove,persist_get_max_size()
    };
    kb_store_init_reader(&app.store,io,baseline_read,handle,size,app.cache);
  }
  else {
    /* Recovery controls remain safe even when no store could be initialized. */
    app.store.directory_generation=UINT32_MAX;
    snprintf(app.notice,sizeof(app.notice),"Timetable unavailable");
  }
  load_preferences();
  load_all_preferences();
  kb_extras_load(&app.extras,&app.extras_generation,&app.extras_slot,p_read,NULL);
  app_load_reminders();
  {
    /* A time profile chooses the opening stop; a wakeup chooses its own. */
    time_t now=time(NULL);
    uint16_t profile=kb_extras_profile_point(&app.extras,(unsigned)localtime(&now)->tm_hour);
    if(profile&&app_point_exists(NULL,profile))app.point=profile;
  }
  app.location_request=(uint32_t)time(NULL);
  app.all_request=(uint32_t)time(NULL);
  app_message_register_inbox_received(inbox);
  app_message_register_outbox_sent(sent);
  app_message_register_outbox_failed(failed);
  AppMessageResult r=app_message_open(1024,1024);
  ui_init();
  if((app.prefs.bytes[1]&(KB_PREF_LOCATION|KB_PREF_NEARBY_START))==(KB_PREF_LOCATION|KB_PREF_NEARBY_START))ui_open(KB_SCREEN_NEARBY);
  else if(!app_point_exists(NULL,app.point))ui_open(KB_SCREEN_PICKER);
  WakeupId wake_id;
  int32_t cookie=0;
  if(launch_reason()==APP_LAUNCH_WAKEUP&&wakeup_get_launch_event(&wake_id,&cookie))app_show_wakeup(cookie);
  else app_reschedule_wakeups();
  wakeup_service_subscribe(wakeup);
  /* A clock correction may change the hour/date while keeping its minute. */
  tick_timer_service_subscribe(MINUTE_UNIT|HOUR_UNIT|DAY_UNIT|MONTH_UNIT|YEAR_UNIT,tick);
  app_focus_service_subscribe(focus);
  connection_service_subscribe((ConnectionHandlers) {
    .pebble_app_connection_handler=connection
  }
  );
  APP_LOG(APP_LOG_LEVEL_INFO,"READY storage=%lu heap=%lu message=%d",(unsigned long)persist_get_max_size(),(unsigned long)heap_bytes_free(),r);
}
int main(void) {
  init();
  app_event_loop();
  if(s_deadline)app_timer_cancel(s_deadline);
  if(s_send_retry)app_timer_cancel(s_send_retry);
  if(s_begin_timer)app_timer_cancel(s_begin_timer);
  tick_timer_service_unsubscribe();
  connection_service_unsubscribe();
  app_focus_service_unsubscribe();
  app_message_deregister_callbacks();
  /* Leaving re-arms the next commute occurrence and refreshes the glance. */
  app.reminder_kind=0;
  app_reschedule_wakeups();
  app_reload_glance();
  if(app.japanese)fonts_unload_custom_font(app.japanese);
  layer_destroy(app.layer);
  window_destroy(app.window);
  free(app.cache);
}
