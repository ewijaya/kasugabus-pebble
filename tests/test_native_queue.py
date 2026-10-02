"""Execute native queue/navigation functions with deterministic host transports.

The function bodies are read from the shipped C sources, so these tests cover
the actual static helpers without pretending to exercise the Pebble renderer.
"""
import copy
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_routes import COMPILER, ROOT, route_fixture


def function(source, name):
    match = re.search(r"^(?:static )?[^\n]*\b" + re.escape(name) + r"\([^\n;]*\)\s*\{", source, re.M)
    if not match:
        raise AssertionError(f"Native function {name} not found")
    depth, quote, escaped, comment = 0, None, False, None
    pos = source.index("{", match.start())
    while pos < len(source):
        char, following = source[pos], source[pos:pos + 2]
        if comment == "line":
            if char == "\n":
                comment = None
        elif comment == "block":
            if following == "*/":
                comment = None
                pos += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif following in ("//", "/*"):
            comment = "line" if following == "//" else "block"
            pos += 1
        elif char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():pos + 1]
        pos += 1
    raise AssertionError(f"Native function {name} is incomplete")


QUEUE_MOCK = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int DictionaryIterator;
typedef int AppMessageResult;
typedef int AppTimer;
#define APP_MSG_OK 0
static struct {
  bool all_waiting,nearby_waiting,checking,phone_ready;
  uint32_t all_request,all_version,location_request,location_version;
  struct { unsigned reference; } all_prefs;
  unsigned nearby_count,location_stamp,accuracy;
  int all_status,nearby_status,update_status;
} app;
static bool connected=true,s_auto_waiting,s_catalogue_pending;
static unsigned clear_count,send_count,timer_count,begin_count;
static uint32_t envelope[14],last_envelope[14];
static AppTimer timer;
static AppTimer *s_send_retry;
static void (*timer_callback)(void *);
static AppMessageResult app_message_outbox_begin(DictionaryIterator **it) {
  static DictionaryIterator iterator;*it=&iterator;begin_count++;
  memset(envelope,0,sizeof(envelope));return APP_MSG_OK;
}
static void dict_write_uint32(DictionaryIterator *it,unsigned key,uint32_t value) {(void)it;assert(key<14);envelope[key]=value;}
static void dict_write_data(DictionaryIterator *it,unsigned key,const void *data,unsigned length) {(void)it;(void)key;(void)data;(void)length;}
static AppMessageResult app_message_outbox_send(void) {send_count++;memcpy(last_envelope,envelope,sizeof(envelope));return APP_MSG_OK;}
static bool connection_service_peek_pebble_app_connection(void) {return connected;}
static AppTimer *app_timer_register(unsigned ms,void (*callback)(void *),void *context) {(void)ms;(void)context;timer_count++;timer_callback=callback;return &timer;}
static void app_clear_all_distances(unsigned status) {clear_count++;app.all_waiting=false;app.all_request++;app.all_version=0;app.all_status=(int)status;}
static void app_redraw(void) {}
static void catalogue_next(void) {}
'''

QUEUE_CASES = r'''
static void reset(void) {
  memset(&app,0,sizeof(app));memset(s_queue,0,sizeof(s_queue));
  s_head=s_count=0;s_sending=false;s_send_retry=NULL;timer_callback=NULL;
  clear_count=send_count=timer_count=begin_count=0;connected=true;
  s_auto_waiting=s_catalogue_pending=false;
}
static void add(unsigned type,unsigned request,unsigned version,unsigned reference) {
  assert(s_count<8);message_t *m=&s_queue[(s_head+s_count++)%8];
  m->present=(1u<<0)|(1u<<3)|(1u<<8)|(1u<<13);
  m->value[0]=type;m->value[3]=version;m->value[8]=request;m->value[13]=reference;
}
static void active(unsigned type,unsigned request,unsigned version,unsigned reference) {
  if(type==14) {app.all_waiting=true;app.all_request=request;app.all_version=version;app.all_prefs.reference=reference;}
  else {app.nearby_waiting=true;app.location_request=request;app.location_version=version;}
}
int main(void) {
  /* A failed callback belongs to the old in-flight envelope, never to B. */
  for(unsigned first=9;first<=14;first+=5)for(unsigned second=9;second<=14;second+=5) {
    reset();add(first,11,2,0);add(second,12,3,1);active(second,12,3,1);
    s_sending=true;s_queue[0].retries=3;failed(NULL,1,NULL);
    assert(clear_count==0&&timer_count==0&&send_count==1&&s_count==1);
    assert(last_envelope[0]==second&&last_envelope[8]==12&&last_envelope[3]==3);
    assert(location_message_active(&s_queue[s_head]));
    if(second==14)assert(app.all_waiting&&app.all_request==12&&app.all_version==3&&app.all_prefs.reference==1);
    else assert(app.nearby_waiting&&app.location_request==12&&app.location_version==3);
    sent(NULL,NULL);assert(s_count==0&&!s_sending);
  }
  /* An obsolete failure does not consume even its first retry interval. */
  reset();add(14,10,2,0);add(14,11,2,0);active(14,11,2,0);
  failed(NULL,1,NULL);assert(timer_count==0&&clear_count==0&&last_envelope[8]==11);
  /* An active failure retries its exact envelope; exhaustion clears only it. */
  reset();add(14,11,2,1);active(14,11,2,1);
  failed(NULL,1,NULL);assert(timer_count==1&&clear_count==0&&app.all_waiting&&send_count==0);
  assert(timer_callback);timer_callback(NULL);assert(send_count==1&&last_envelope[8]==11&&last_envelope[13]==1);
  s_queue[s_head].retries=3;failed(NULL,1,NULL);
  assert(clear_count==1&&!app.all_waiting&&app.all_request==12&&app.all_status==5&&s_count==0);
  reset();add(9,11,2,0);active(9,11,2,0);app.nearby_count=6;app.location_stamp=20;app.accuracy=30;
  s_queue[0].retries=3;failed(NULL,1,NULL);
  assert(clear_count==0&&!app.nearby_waiting&&app.nearby_status==5&&!app.nearby_count&&!app.location_stamp&&!app.accuracy);
  /* Held ACK followed by obsolete requests is released without sending GPS. */
  reset();add(8,0,0,0);add(14,10,2,0);add(9,11,2,0);add(14,12,3,1);active(14,12,3,1);
  s_sending=true;sent(NULL,NULL);
  assert(send_count==1&&last_envelope[0]==14&&last_envelope[8]==12&&s_count==1);
  reset();add(14,11,2,0);active(14,11,2,1);send_next();
  assert(s_count==0&&send_count==0&&begin_count==0&&app.all_waiting);
  reset();add(14,11,2,0);active(14,11,3,0);send_next();assert(!s_count&&!send_count);
  reset();add(14,11,2,0);active(14,11,2,0);app.all_waiting=false;send_next();assert(!s_count&&!send_count);
  /* A real disconnect invalidates the pending All actor even after old A. */
  reset();add(14,10,2,0);add(14,11,2,0);active(14,11,2,0);connected=false;
  failed(NULL,1,NULL);assert(clear_count==1&&!app.all_waiting&&app.all_status==5&&!s_count&&!send_count);
  puts("native queue supersession, actor isolation, retries, obsolete sends and disconnect PASS");
  return 0;
}
'''

BOUNDARY_MOCK = r'''
#include "engine.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define KB_SCREEN_ALL_BOARD 22
#define KB_SCREEN_ALL_POINTS 21
#define KB_SCREEN_BOARD 1
#define KB_SCREEN_HOME 0
#define KB_ALL_MAX_POINTS 32
#define KB_MAX_POINTS 32
typedef void *ClickRecognizerRef;
static struct {
  int screen,selected,scroll;
  bool route_filter,board_removed,board_expired,board_has_focus,changed;
  uint16_t point,all_point_focus;
  struct { uint8_t bytes[80]; } prefs;
  uint8_t route_operator;
  char route_number[1024];
  kb_trip_t board_focus;
  struct { uint16_t ids[32];unsigned count; } all_prefs;
  struct { uint8_t buttons[4]; } extras;
} app;
#define KB_BUTTON_DOWN 1
static kb_query_t active_query;
#define time(ignored) (active_query.now_utc)
static kb_query_t app_query(void) {return active_query;}
static int scroll_limit;
static bool scroll_screen(void) {return false;}
static unsigned body_size(void) {return 28;}
static void scroll_by(int amount) {app.scroll+=amount;}
static uint16_t kb_pref_favourite(const void *preferences,unsigned index) {(void)preferences;(void)index;return 0;}
static void app_redraw(void) {}
/* Home actions are outside this board-navigation boundary. */
static void home_action(unsigned action) {(void)action;(void)kb_pref_favourite(NULL,0);}
static void ui_remember_all_point(void) {}
static unsigned all_point_ids(uint16_t *ids) {(void)ids;return 0;}
static int choices(void) {return 4;}
static uint32_t app_all_distance(uint16_t id) {(void)id;return UINT32_MAX;}
static const kb_dataset_t *resolve(void *context,int32_t day) {(void)day;return context;}
static void load(const char *path,kb_dataset_t *dataset,uint8_t **buffer) {
  FILE *file=fopen(path,"rb");assert(file);assert(!fseek(file,0,SEEK_END));long n=ftell(file);assert(n>0);rewind(file);
  *buffer=malloc((size_t)n);assert(*buffer);assert(fread(*buffer,1,(size_t)n,file)==(size_t)n);fclose(file);
  assert(kb_dataset_open(dataset,*buffer,(size_t)n)==KB_OK);
}
'''

BOUNDARY_CASES = r'''
int main(int argc,char **argv) {
  assert(argc==6);kb_dataset_t base,removed,gap,window,navigation;uint8_t *buffers[5];
  load(argv[1],&base,&buffers[0]);load(argv[2],&removed,&buffers[1]);load(argv[3],&gap,&buffers[2]);load(argv[4],&window,&buffers[3]);
  load(argv[5],&navigation,&buffers[4]);
  int32_t today;assert(kb_date_from_ymd(2026,10,1,&today));
  kb_query_t q={.resolve=resolve,.context=&base,.now_utc=kb_service_epoch(today,600),.boarding_point_id=1,.override={KB_DATE_UNKNOWN,KB_DAY_UNKNOWN}};
  uint16_t ids[]={1,2};uint32_t original_metres[]={200,100},unknown[]={UINT32_MAX,UINT32_MAX};kb_trip_t a,b,out;
  assert(kb_query_merged_next(&q,ids,original_metres,2,NULL,&a,NULL)==KB_QUERY_FOUND&&a.boarding_point_id==2&&a.minute==660);
  q.context=&removed;
  assert(kb_query_merged_next(&q,ids,unknown,2,&a,&out,NULL)==KB_QUERY_FOUND&&out.minute==661);
  app.screen=22;app.all_prefs.count=2;app.all_prefs.ids[0]=1;app.all_prefs.ids[1]=2;app.board_focus=a;app.board_removed=true;
  assert(next_trip(&q,&a,&b)==KB_QUERY_FOUND&&b.boarding_point_id==1&&b.minute==660);
  assert(next_trip(&q,&b,&out)==KB_QUERY_FOUND&&out.minute==661);
  assert(q.now_utc==kb_service_epoch(today,600)&&a.departure_utc==kb_service_epoch(today,660));
  /* Single and exact route boards also recover lower-identity equal-time rows. */
  q.context=&base;app.screen=1;app.route_filter=false;
  assert(kb_query_next(&q,NULL,&b,NULL)==KB_QUERY_FOUND&&b.pattern_id==3);
  assert(kb_query_next(&q,&b,&a,NULL)==KB_QUERY_FOUND&&a.pattern_id==5&&a.minute==660);
  app.board_focus=a;q.context=&removed;
  assert(next_trip(&q,&a,&out)==KB_QUERY_FOUND&&out.pattern_id==3&&out.minute==660);
  app.route_filter=true;app.route_operator=1;strcpy(app.route_number,"2");
  assert(next_trip(&q,&a,&out)==KB_QUERY_FOUND&&out.pattern_id==3&&out.minute==660);
  /* Updating adds an earlier row. DOWN must remap its recovered trip index. */
  active_query=q;active_query.context=&navigation;app.board_focus=a;
  app.board_has_focus=true;app.board_removed=true;app.selected=2;
  down(NULL,NULL);
  assert(!app.board_removed&&app.board_focus.minute==660&&app.board_focus.pattern_id==3&&app.selected==2);
  assert(trip_at(app.selected,&out)&&out.minute==661);
  /* The boundary must not shift actual today past an unconfirmed calendar. */
  q.context=&base;q.now_utc=kb_service_epoch(today+1,600);app.screen=22;app.route_filter=false;
  assert(kb_query_merged_next(&q,ids,original_metres,2,NULL,&a,NULL)==KB_QUERY_FOUND);
  app.board_focus=a;q.context=&gap;q.now_utc=kb_service_epoch(today,600);
  assert(next_trip(&q,&a,&out)==KB_QUERY_UNCONFIRMED);
  /* Nor may removed focus extend the originating-date seven-day window. */
  q.context=&base;q.now_utc=kb_service_epoch(today+7,600);
  assert(kb_query_merged_next(&q,ids,original_metres,2,NULL,&a,NULL)==KB_QUERY_FOUND);
  app.board_focus=a;q.context=&window;q.now_utc=kb_service_epoch(today,600);
  assert(next_trip(&q,&a,&out)==KB_QUERY_NO_MORE);
  for(unsigned i=0;i<5;i++)free(buffers[i]);
  puts("native removed-focus equal-time recovery, exact filters, calendar barrier and lookahead PASS");return 0;
}
'''


class NativeQueueTests(unittest.TestCase):
    def compile_run(self, source, args=(), engine=False, sanitize=False):
        with tempfile.TemporaryDirectory(prefix="kasugabus-native-host-") as directory:
            path = Path(directory)
            cfile, exe = path / "native.c", path / "native"
            cfile.write_text(source)
            command = ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I", str(ROOT / "src/c")]
            if sanitize:
                command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
            command += [str(cfile)]
            if engine:
                command += [str(ROOT / "src/c/engine.c")]
            subprocess.run(command + ["-o", str(exe)], check=True, capture_output=True, text=True, timeout=30)
            result = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS", result.stdout)

    def queue_source(self):
        source = (ROOT / "src/c/main.c").read_text()
        record = re.search(r"typedef\s+struct\s*\{.*?\}\s*message_t\s*;", source, re.S)
        self.assertIsNotNone(record)
        declarations = record.group() + "\nstatic message_t s_queue[8];\nstatic unsigned s_head,s_count;\nstatic bool s_sending;\nstatic void send_next(void);\nstatic void failed(DictionaryIterator *,AppMessageResult,void *);\n"
        helpers = "\n".join(function(source, name) for name in ("send_retry", "location_message_active", "send_next", "sent", "failed"))
        return QUEUE_MOCK + declarations + helpers + QUEUE_CASES

    def test_actual_native_queue_supersession_and_recovery(self):
        self.compile_run(self.queue_source())

    def test_actual_native_queue_sanitizers(self):
        self.compile_run(self.queue_source(), sanitize=True)

    def boundary(self, sanitize=False):
        source = (ROOT / "src/c/ui.c").read_text()
        doc = route_fixture()
        for pattern in doc["patterns"]:
            if pattern["id"] in (3, 5):
                pattern["boarding_route"] = "2"
        doc["departures"] = [dict(boarding_point_id=point, pattern_id=pattern, service_id=1, minute=minute)
                             for point, pattern, minute in [(2, 1, 660), (1, 3, 660), (1, 5, 660), (1, 2, 661)]]
        removed = copy.deepcopy(doc)
        removed["release_version"] = 2
        removed["departures"] = [row for row in removed["departures"] if row["boarding_point_id"] != 2 and row["pattern_id"] != 5]
        gap = copy.deepcopy(removed)
        gap["calendar"]["coverage_from"] = "2026-10-02"
        window = copy.deepcopy(removed)
        window["calendar"]["exceptions"].append(dict(date="2026-10-08", operator_id=1, day_type=0))
        navigation = copy.deepcopy(removed)
        navigation["departures"].append(dict(boarding_point_id=1, pattern_id=2, service_id=1, minute=650))
        with tempfile.TemporaryDirectory(prefix="kasugabus-native-fixtures-") as directory:
            paths = []
            for name, fixture in (("base", doc), ("removed", removed), ("gap", gap), ("window", window), ("navigation", navigation)):
                path = Path(directory) / (name + ".bin")
                path.write_bytes(COMPILER.compile_dataset(fixture))
                paths.append(path)
            helpers = "\n".join(function(source, name) for name in ("trip_at", "next_trip", "ui_refresh", "down"))
            self.compile_run(BOUNDARY_MOCK + helpers + BOUNDARY_CASES, paths, engine=True, sanitize=sanitize)

    def test_actual_native_removed_focus_calendar_and_window(self):
        self.boundary()

    def test_actual_native_removed_focus_sanitizers(self):
        self.boundary(sanitize=True)


if __name__ == "__main__":
    unittest.main()
