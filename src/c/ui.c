#include "app.h"
#include <stdio.h>
#include <string.h>
static GColor cyan(void) {
  return(app.prefs.bytes[1]&KB_PREF_CONTRAST)?GColorWhite:GColorCyan;
}
static GColor lime(void) {
  return(app.prefs.bytes[1]&KB_PREF_CONTRAST)?GColorWhite:GColorSpringBud;
}
static GColor amber(void) {
  return(app.prefs.bytes[1]&KB_PREF_CONTRAST)?GColorWhite:GColorChromeYellow;
}
static GFont font(unsigned n) {
  return fonts_get_system_font(n==42?FONT_KEY_BITHAM_42_BOLD:n==28?FONT_KEY_GOTHIC_28_BOLD:n==24?FONT_KEY_GOTHIC_24_BOLD:n==18?FONT_KEY_GOTHIC_18:FONT_KEY_GOTHIC_14);
}
static void text(GContext *c,const char *s,int x,int y,int w,int h,unsigned f,GColor color) {
  graphics_context_set_text_color(c,color);
  graphics_draw_text(c,s,font(f),GRect(x,y,w,h),GTextOverflowModeWordWrap,GTextAlignmentLeft,NULL);
}
static void line(GContext *c,int y,GColor col) {
  graphics_context_set_stroke_color(c,col);
  graphics_draw_line(c,GPoint(8,y),GPoint(192,y));
}
static const char *day_name(kb_day_type_t d) {
  return d==KB_DAY_WEEKDAY?"Weekday":d==KB_DAY_SATURDAY?"Saturday":d==KB_DAY_SUNDAY_HOLIDAY?"Sun / holiday":d==KB_DAY_NONE?"No service today":"Schedule unconfirmed";
}
static void date_string(int32_t day,char *b,size_t n) {
  int y;
  unsigned m,d;
  kb_date_to_ymd(day,&y,&m,&d);
  snprintf(b,n,"%04d-%02u-%02u",y,m,d);
}
static void time_string(int64_t epoch,char *b,size_t n) {
  int64_t sec=(epoch+32400)%86400;
  if(sec<0)sec+=86400;
  snprintf(b,n,"%02d:%02d",(int)(sec/3600),(int)(sec/60%60));
}
static void countdown(const kb_trip_t *t,char *b,size_t n) {
  uint32_t m=0;
  int s=kb_countdown(time(NULL),t->departure_utc,&m);
  if(s==KB_COUNTDOWN_EXPIRED)snprintf(b,n,"Earlier");
  else if(s==KB_COUNTDOWN_DUE)snprintf(b,n,"Due");
  else snprintf(b,n,"%lu min",(unsigned long)m);
}
static unsigned nearby_status_now(void) {
  unsigned status=app.nearby_status;
  if(status>8)return 5;
  if((status==0||status==1||status==2)&&app.location_stamp&&time(NULL)-app.location_stamp>120)return 2;
  return status;
}
static void heading(GContext *c,const char *title,const char *sub) {
  text(c,title,8,4,184,30,24,cyan());
  if(sub)text(c,sub,8,33,184,20,14,GColorWhite);
  line(c,55,cyan());
}
static void footer(GContext *c,const char *s) {
  graphics_context_set_fill_color(c,GColorBlack);
  graphics_fill_rect(c,GRect(0,209,200,19),0,GCornerNone);
  text(c,s,8,209,184,18,14,GColorWhite);
}
static void home(GContext *c) {
  time_t now=time(NULL);
  struct tm local=*localtime(&now);
  char b[96],clock[20];
  strftime(b,sizeof(b),"%a %d %b",&local);
  graphics_context_set_fill_color(c,(app.prefs.bytes[1]&KB_PREF_CONTRAST)?GColorWhite:GColorMagenta);
  graphics_fill_rect(c,GRect(188,7,4,12),0,GCornerNone);
  text(c,b,8,4,126,20,14,cyan());
  text(c,local.tm_gmtoff==32400?"JST":"LOCAL",150,4,45,20,14,GColorWhite);
  strftime(clock,sizeof(clock),clock_is_24h_style()?"%H:%M":"%I:%M",&local);
  if(!clock_is_24h_style()&&clock[0]=='0')memmove(clock,clock+1,strlen(clock));
  text(c,clock,8,19,185,52,42,GColorWhite);
  if(!clock_is_24h_style())text(c,local.tm_hour<12?"AM":"PM",164,59,28,18,14,cyan());
  line(c,74,cyan());
  const kb_dataset_t *d=app_dataset();
  kb_boarding_point_t p;
  kb_operator_t o;
  if(!d||!kb_boarding_point_get(d,app.point,&p)) {
    text(c,"Timetable unavailable",8,92,184,60,24,GColorWhite);
    text(c,"Select for Stops & tools",8,162,184,36,18,cyan());
    footer(c,"Manual selection available");
    return;
  }
  kb_operator_get(d,p.operator_id,&o);
  char stop[80],direction[112],operator_name[32];
  snprintf(operator_name,sizeof(operator_name),"%s",o.short_name);
  snprintf(stop,sizeof(stop),"%s",p.short_name);
  snprintf(direction,sizeof(direction),"%s",p.direction);
  text(c,stop,8,78,184,30,24,GColorWhite);
  text(c,direction,8,107,184,32,18,cyan());
  kb_query_t q=app_query();
  kb_trip_t t;
  kb_query_state_t state;
  int found=kb_query_home(&q,&t,&state);
  if(found==KB_QUERY_FOUND) {
    d=kb_trip_dataset(&q,&t);
    kb_pattern_t pattern;
    if(d&&kb_pattern_get(d,t.pattern_id,&pattern)) {
      graphics_context_set_fill_color(c,lime());
      graphics_fill_rect(c,GRect(8,140,41,29),3,GCornersAll);
      text(c,pattern.route,13,138,37,29,24,GColorBlack);
      time_string(t.departure_utc,b,sizeof(b));
      text(c,b,57,136,88,36,28,lime());
      countdown(&t,b,sizeof(b));
      text(c,b,143,145,55,30,18,lime());
      text(c,pattern.destination,8,170,184,25,18,GColorWhite);
      int32_t today=kb_jst_day(now);
      if(kb_jst_day(t.departure_utc)!=today) {
        char date[20];
        date_string(kb_jst_day(t.departure_utc),date,sizeof(date));
        snprintf(b,sizeof(b),"%s  Scheduled JST",date+5);
      }
      else snprintf(b,sizeof(b),"%s | Scheduled%s",operator_name,local.tm_gmtoff==32400?"":" JST");
      text(c,b,8,191,184,18,14,GColorWhite);
    }
  }
  else  {
    text(c,found==KB_QUERY_UNCONFIRMED?"Schedule unconfirmed":"No upcoming service",8,147,184,58,24,amber());
  }
  d=app_dataset();
  if(app.override.day_type!=KB_DAY_UNKNOWN&&app.override.jst_day==kb_jst_day(now))snprintf(b,sizeof(b),"Override: %s",day_name(app.override.day_type));
  else if(app.store.recovery_notice)snprintf(b,sizeof(b),"Recovery data: check status");
  else if(d&&d->review_by!=KB_DATE_UNKNOWN&&kb_jst_day(now)>d->review_by)snprintf(b,sizeof(b),"Needs timetable review");
  else if(found<0)snprintf(b,sizeof(b),"Data status / day override");
  else if(app.first_use)snprintf(b,sizeof(b),"Hold SELECT: menu");
  else if(state.today_no_service)snprintf(b,sizeof(b),"No service today");
  else snprintf(b,sizeof(b),"%s%s",day_name(found==KB_QUERY_FOUND?t.day_type:state.today_type),app.changed?" | New data":"");
  footer(c,b);
}
typedef struct  {
  char title[100],sub[140];
  uint16_t id;
}
choice_t;
static int choices(void) {
  const kb_dataset_t *d=app_dataset();
  switch(app.screen) {
    case KB_SCREEN_MENU:return 4;
    case KB_SCREEN_PICKER:return 3;
    case KB_SCREEN_FAVOURITES:return app.prefs.bytes[5];
    case KB_SCREEN_GROUPS:return d?kb_stop_group_count(d):0;
    case KB_SCREEN_POINTS: {
      unsigned n=0;
      for(size_t i=0;d&&i<kb_boarding_point_count(d);i++) {
        kb_boarding_point_t p;
        kb_boarding_point_at(d,i,&p);
        if(p.group_id==app.group)n++;
      }
      return n;
    }
    case KB_SCREEN_NEARBY:return app.nearby_count+1;
    case KB_SCREEN_CONTEXT:return 3;
    case KB_SCREEN_SETTINGS:return 7;
    case KB_SCREEN_OVERRIDE:return 4;
    case KB_SCREEN_RESET:case KB_SCREEN_RESTORE:return 2;
    default:return 0;
  }
}
static void point_choice(const kb_dataset_t *d,uint16_t id,choice_t *c) {
  kb_boarding_point_t p;
  kb_operator_t o;
  c->id=id;
  if(d&&kb_boarding_point_get(d,id,&p)) {
    kb_operator_get(d,p.operator_id,&o);
    snprintf(c->title,sizeof(c->title),"%s",p.short_name);
    snprintf(c->sub,sizeof(c->sub),"%s | %s",o.short_name,p.direction);
  }
  else  {
    snprintf(c->title,sizeof(c->title),"Unavailable favourite %u",id);
    snprintf(c->sub,sizeof(c->sub),"Choose a new ID in settings");
  }
}
static void choice(int n,choice_t *c) {
  memset(c,0,sizeof(*c));
  if(n<0||n>=choices())return;
  const kb_dataset_t *d=app_dataset();
  switch(app.screen) {
    case KB_SCREEN_MENU: {
      const char *a[]= {
        "Stops","Trip context","Data status","Settings"
      };
      const char *b[]= {
        "Favourites / Nearby / All","Walk allowance / At stop","Source dates and updates","Calendar and display"
      };
      snprintf(c->title,sizeof(c->title),"%s",a[n]);
      snprintf(c->sub,sizeof(c->sub),"%s",b[n]);
      break;
    }
    case KB_SCREEN_PICKER: {
      const char *a[]= {
        "Favourites","Nearby","All stops"
      };
      const char *b[]= {
        "Your saved order","One phone location request","Six stops, all directions"
      };
      snprintf(c->title,sizeof(c->title),"%s",a[n]);
      snprintf(c->sub,sizeof(c->sub),"%s",b[n]);
      break;
    }
    case KB_SCREEN_FAVOURITES:point_choice(d,kb_pref_favourite(&app.prefs,n),c);
    break;
    case KB_SCREEN_GROUPS: {
      kb_stop_group_t g;
      if(!d||!kb_stop_group_at(d,n,&g))break;
      c->id=g.id;
      snprintf(c->title,sizeof(c->title),"%s",g.short_name);
      snprintf(c->sub,sizeof(c->sub),"Choose operator & direction");
      break;
    }
    case KB_SCREEN_POINTS: {
      int seen=0;
      for(size_t i=0;i<kb_boarding_point_count(d);i++) {
        kb_boarding_point_t p;
        kb_boarding_point_at(d,i,&p);
        if(p.group_id==app.group&&seen++==n) {
          point_choice(d,p.id,c);
          snprintf(c->title,sizeof(c->title),"%s",p.direction);
          kb_operator_t o;
          kb_operator_get(d,p.operator_id,&o);
          snprintf(c->sub,sizeof(c->sub),"%s | %s",o.name,p.short_name);
          break;
        }
      }
      break;
    }
    case KB_SCREEN_NEARBY:if(!n) {
      snprintf(c->title,sizeof(c->title),"Refresh location");
      snprintf(c->sub,sizeof(c->sub),"Approx. straight-line distance");
    }
    else {
      point_choice(d,app.nearby[n-1].id,c);
      char label[100];
      snprintf(label,sizeof(label),"%.99s",c->sub);
      unsigned status=nearby_status_now();
      const char *distance_label=(status==0||status==1)?"Approx.":"Previous";
      if(status==0)for(unsigned i=0;i<app.nearby_count;i++)if(i!=(unsigned)n-1) {
        uint32_t a=app.nearby[i].metres,b=app.nearby[n-1].metres;
        if((a>b?a-b:b-a)<=2*app.accuracy) {
          distance_label="Similar";
          break;
        }
      }
      snprintf(c->sub,sizeof(c->sub),"%s %lum | %.80s",distance_label,(unsigned long)app.nearby[n-1].metres,label);
    }
    break;
    case KB_SCREEN_CONTEXT: {
      const char *a[]= {
        "General / Nearby","Saved origin","At stop"
      };
      const char *b[]= {
        "No walking assumption","Use your configured walk","Zero walking allowance"
      };
      snprintf(c->title,sizeof(c->title),"%s",a[n]);
      snprintf(c->sub,sizeof(c->sub),"%s",b[n]);
      break;
    }
    case KB_SCREEN_OVERRIDE: {
      const char *a[]= {
        "Automatic","Weekday","Saturday","Sunday / holiday"
      };
      snprintf(c->title,sizeof(c->title),"%s",a[n]);
      snprintf(c->sub,sizeof(c->sub),n?"Temporary: ends JST midnight":"Use verified operator calendar");
      break;
    }
    case KB_SCREEN_SETTINGS: {
      const char *a[]= {
        "Service-day override","High contrast","Reduced motion","Automatic updates","Phone settings","Reset preferences","Restore bundled data"
      };
      snprintf(c->title,sizeof(c->title),"%s",a[n]);
      if(n==1)snprintf(c->sub,sizeof(c->sub),"%s",app.prefs.bytes[1]&KB_PREF_CONTRAST?"On - select to toggle":"Off - Neon Transit");
      else if(n==2)snprintf(c->sub,sizeof(c->sub),"%s",app.prefs.bytes[1]&KB_PREF_REDUCED_MOTION?"On":"Off (no idle animation)");
      else if(n==3)snprintf(c->sub,sizeof(c->sub),"%s",app.prefs.bytes[1]&KB_PREF_AUTO?"On - daily on launch":"Off - manual check available");
      else if(n==4)snprintf(c->sub,sizeof(c->sub),"Open KasugaBus settings in phone");
      else snprintf(c->sub,sizeof(c->sub),"%s",n==0?"Visible until next JST date":n==5?"Timetables remain stored":"Explicit dated recovery");
      break;
    }
    case KB_SCREEN_RESET:case KB_SCREEN_RESTORE:snprintf(c->title,sizeof(c->title),"%s",n?"Confirm":"Cancel");
    snprintf(c->sub,sizeof(c->sub),"%s",n?(app.screen==KB_SCREEN_RESET?"Reset preferences only":"Remove downloaded revisions"):"Keep current data and settings");
    break;
  }
}
static const char *screen_title(void) {
  switch(app.screen) {
    case KB_SCREEN_MENU:return "KasugaBus";
    case KB_SCREEN_PICKER:return "Choose stops";
    case KB_SCREEN_FAVOURITES:return "Favourites";
    case KB_SCREEN_GROUPS:return "All stops";
    case KB_SCREEN_POINTS:return "Boarding direction";
    case KB_SCREEN_NEARBY:return "Nearby";
    case KB_SCREEN_CONTEXT:return "Trip context";
    case KB_SCREEN_SETTINGS:return "Settings";
    case KB_SCREEN_OVERRIDE:return "Service calendar";
    case KB_SCREEN_RESET:return "Reset preferences?";
    case KB_SCREEN_RESTORE:return "Restore baseline?";
    default:return "KasugaBus";
  }
}
static void nearby_label(char *s,size_t n) {
  if(app.nearby_waiting) {
    snprintf(s,n,"Locating with phone...");
    return;
  }
  const char *a[]= {
    "Approx. - similar within accuracy","Low accuracy - choose direction","Previous location - refresh","Permission denied","Location timed out","Phone unavailable","Outside saved area","No verified poles to rank","Location disabled"
  };
  unsigned status=nearby_status_now();
  if((status==0||status==1||status==2)&&app.location_stamp) {
    long age=time(NULL)-app.location_stamp;
    snprintf(s,n,"%s (%ldm, +/- %lum)",status==0?"Approx.":status==1?"Low accuracy":"Previous",age/60,(unsigned long)app.accuracy);
  }
  else snprintf(s,n,"%s",a[status]);
}
static void list(GContext *c) {
  char sub[140];
  if(app.screen==KB_SCREEN_NEARBY)nearby_label(sub,sizeof(sub));
  else snprintf(sub,sizeof(sub),"%s",app.notice[0]?app.notice:"UP / DOWN choose, SELECT open");
  heading(c,screen_title(),sub);
  int count=choices();
  if(!count) {
    bool data_available=app_dataset()!=NULL;
    text(c,data_available?"No saved entries":"Timetable unavailable",8,77,184,52,24,GColorWhite);
    text(c,data_available?"All stops is always available.":"BACK for menu and Data status",8,133,184,50,18,cyan());
  }
  int start=(app.selected/3)*3;
  for(int i=0;i<3&&start+i<count;i++) {
    int row=start+i,y=61+i*48;
    choice_t ch;
    choice(row,&ch);
    bool selected=row==app.selected;
    if(selected) {
      graphics_context_set_fill_color(c,cyan());
      graphics_fill_rect(c,GRect(4,y,192,46),3,GCornersAll);
    }
    GColor col=selected?GColorBlack:GColorWhite;
    text(c,ch.title,9,y-1,182,26,18,col);
    text(c,ch.sub,9,y+21,182,26,14,col);
  }
  char foot[60];
  snprintf(foot,sizeof(foot),"%d / %d   BACK returns",count?app.selected+1:0,count);
  footer(c,foot);
}
static bool trip_at(int index,kb_trip_t *out) {
  kb_query_t q=app_query();
  return kb_upcoming_at(&q,index,out,NULL)==KB_QUERY_FOUND;
}
static void board(GContext *c) {
  heading(c,"Departures","Scheduled times | JST");
  bool tools=app.selected==0;
  graphics_context_set_fill_color(c,tools?cyan():GColorDarkGray);
  graphics_fill_rect(c,GRect(4,60,192,26),2,GCornersAll);
  text(c,"Stops & tools",9,60,183,24,18,tools?GColorBlack:GColorWhite);
  int base=app.selected>2?app.selected-2:0;
  kb_trip_t first;
  bool pinned=app.board_expired||app.board_removed;
  bool future=!pinned&&trip_at(base,&first)&&kb_jst_day(first.departure_utc)>kb_jst_day(time(NULL));
  int offset=0;
  if(future) {
    char date[20],label[64];
    date_string(kb_jst_day(first.departure_utc),date,sizeof(date));
    snprintf(label,sizeof(label),"Next service: %s",date);
    text(c,label,9,87,183,18,14,cyan());
    offset=15;
  }
  bool any=false;
  int32_t previous_day=future?kb_jst_day(first.departure_utc):kb_jst_day(time(NULL));
  kb_trip_t expired_previous=app.board_focus;
  for(int i=0;i<3;i++) {
    int idx=base+i;
    kb_trip_t t;
    if(pinned) {
      idx=i;
      if(!i)t=app.board_focus;
      else {
        kb_query_t query=app_query();
        if(kb_query_next(&query,&expired_previous,&t,NULL)!=KB_QUERY_FOUND)break;
        expired_previous=t;
      }
    }
    else if(app.selected==idx+1&&app.board_has_focus)t=app.board_focus;
    else if(!trip_at(idx,&t))break;
    int y=90+offset+38*i;
    if(kb_jst_day(t.departure_utc)!=previous_day) {
      char date[20];
      date_string(kb_jst_day(t.departure_utc),date,sizeof(date));
      text(c,date,9,y-1,183,17,14,cyan());
      offset+=15;
      y+=15;
      previous_day=kb_jst_day(t.departure_utc);
    }
    if(y+37>208)break;
    any=true;
    kb_query_t q=app_query();
    const kb_dataset_t *d=kb_trip_dataset(&q,&t);
    kb_pattern_t p;
    bool available=d&&kb_pattern_get(d,t.pattern_id,&p);
    bool sel=app.selected==idx+1;
    graphics_context_set_fill_color(c,sel?lime():GColorBlack);
    graphics_fill_rect(c,GRect(4,y,192,37),2,GCornersAll);
    GColor color=sel?GColorBlack:GColorWhite;
    char tm[12],cd[24],s[180];
    time_string(t.departure_utc,tm,sizeof(tm));
    countdown(&t,cd,sizeof(cd));
    if(available)snprintf(s,sizeof(s),"%s   %s   %s",tm,p.route,cd);
    else snprintf(s,sizeof(s),"%s   Trip removed",tm);
    text(c,s,9,y-2,184,22,18,color);
    text(c,available?p.destination:"Timetable changed",9,y+18,184,20,14,color);
  }
  if(!any) {
    kb_query_t q=app_query();
    kb_trip_t t;
    kb_query_state_t state;
    int r=kb_upcoming_at(&q,0,&t,&state);
    text(c,r<0?"Schedule unconfirmed":"No upcoming service",8,101,184,63,24,amber());
  }
  footer(c,app.board_removed?"Trip removed | DOWN next":app.board_expired?"Earlier trip kept | DOWN next":app.changed?"Timetable changed | hold to refresh":"SELECT details | hold: refresh");
}
static void details(GContext *c) {
  kb_query_t q=app_query();
  const kb_dataset_t *d=kb_trip_dataset(&q,&app.detail);
  kb_boarding_point_t p;
  kb_pattern_t pattern;
  kb_operator_t o;
  if(!d||!kb_boarding_point_get(d,app.detail.boarding_point_id,&p)||!kb_pattern_get(d,app.detail.pattern_id,&pattern)) {
    heading(c,"Trip unavailable","Timetable changed");
    text(c,"Return to the departure board.",8,79,184,80,24,GColorWhite);
    return;
  }
  kb_operator_get(d,p.operator_id,&o);
  static char s[2200];
  char tm[16],date[20],walk[160],source[80],origin[90]="";
  time_string(app.detail.departure_utc,tm,sizeof(tm));
  date_string(kb_jst_day(app.detail.departure_utc),date,sizeof(date));
  if(app.detail.minute>=1440) {
    char od[20];
    date_string(app.detail.service_day,od,sizeof(od));
    snprintf(origin,sizeof(origin),"\nService date %s (%u:%02u)",od,app.detail.minute/60,app.detail.minute%60);
  }
  int minutes=kb_pref_walk(&app.prefs,app.detail.boarding_point_id);
  walk[0]=0;
  if(app.trip_context==KB_CONTEXT_SAVED_ORIGIN&&minutes>=0) {
    int64_t leave;
    if(kb_leave_by(&app.detail,KB_CONTEXT_SAVED_ORIGIN,minutes,app.prefs.bytes[4],&leave)) {
      char lt[16];
      time_string(leave,lt,sizeof(lt));
      snprintf(walk,sizeof(walk),"\nSaved origin\nWalk %d min + buffer %u\nLeave by %s JST%s\n",minutes,app.prefs.bytes[4],lt,time(NULL)>=leave?" - Leave now":"");
    }
  }
  else snprintf(walk,sizeof(walk),"\nContext: %s\n%s\n",app.trip_context==KB_CONTEXT_AT_STOP?"At stop":app.trip_context==KB_CONTEXT_SAVED_ORIGIN?"Saved origin":"General / Nearby",app.trip_context==KB_CONTEXT_SAVED_ORIGIN?"Walking time is unset":"No walking allowance applied");
  date_string(o.source_verified_on,source,sizeof(source));
  snprintf(s,sizeof(s),"%s\n%s\n%s\n\nRoute %s\nTo %s\n%s  %s JST%s\n%s%s | Scheduled\n%s\n%s\n%s\nSource verified %s\nData v%lu\n\nSELECT: Japanese name",p.name,p.direction,o.name,pattern.route,pattern.destination,date,tm,origin,day_name(app.detail.day_type),app.detail.overridden?" (Override)":"",walk,p.guidance,pattern.route_transitions,source,(unsigned long)d->release_version);
  text(c,s,8,7-app.scroll,184,1200,18,GColorWhite);
  footer(c,"UP / DOWN scroll | BACK board");
}
static void status(GContext *c) {
  static char s[1900];
  char vf[20]="Unavailable",rv[20]="Unset",from[20]="?",until[20]="?",future[20]="None",feed[40]="Never",attempt[40]="Never";
  int32_t effect;
  uint32_t pending=kb_store_pending(&app.store,kb_jst_day(time(NULL)),&effect);
  /* pending() may validate a future snapshot in the shared cache. */
  const kb_dataset_t *d=app_dataset();
  if(d) {
    date_string(d->source_verified_on,vf,sizeof(vf));
    if(d->review_by!=KB_DATE_UNKNOWN)date_string(d->review_by,rv,sizeof(rv));
    date_string(d->calendar_from,from,sizeof(from));
    date_string(d->calendar_until,until,sizeof(until));
  }
  if(pending)date_string(effect,future,sizeof(future));
  if(app.last_success) {
    char dt[20],tm[12];
    date_string(kb_jst_day(app.last_success),dt,sizeof(dt));
    time_string(app.last_success,tm,sizeof(tm));
    snprintf(feed,sizeof(feed),"%s %s JST",dt,tm);
  }
  if(app.last_attempt) {
    char dt[20],tm[12];
    date_string(kb_jst_day(app.last_attempt),dt,sizeof(dt));
    time_string(app.last_attempt,tm,sizeof(tm));
    snprintf(attempt,sizeof(attempt),"%s %s JST",dt,tm);
  }
  const char *states[]= {
    "Checking feed","Downloading","No new published timetable","Timetable received","Phone/internet unavailable","Check failed - retry","App update required","Feed not configured","Transferring safely","Not checked this session","Restore incomplete; retry"
  };
  unsigned st=app.update_status<0||app.update_status>10?5:app.update_status;
  unsigned missing=kb_pref_missing(&app.prefs,app_point_exists,NULL);
  snprintf(s,sizeof(s),"Data status\nSELECT: Check updates\n\n%s\n\nActive dataset: v%lu\nSource verified: %s\nReview due: %s\n%s\nFeed success:\n%s\nAutomatic attempt:\n%s\n\nCalendar coverage\n%s to %s\nPending v%lu: %s\n\n%s\nMissing saved IDs: %u\n\nScheduled departures.\nFeed checks do not verify operator freshness.\n\nUpdates: %s\nPhone: %s\n%s",states[st],(unsigned long)(d?d->release_version:0),vf,rv,d&&d->review_by!=KB_DATE_UNKNOWN&&kb_jst_day(time(NULL))>d->review_by?"Needs timetable review":"",feed,attempt,from,until,(unsigned long)pending,future,kb_store_has_staging(&app.store,kb_jst_day(time(NULL)))?"Safe staging available":app.store.capacity_ok?"Storage full: pending data kept":"Insufficient firmware storage",missing,app.prefs.bytes[1]&KB_PREF_AUTO?"Daily on launch":"Manual only",app.phone_ready?"Ready":"Not connected",app.notice);
  text(c,s,8,4-app.scroll,184,1400,18,GColorWhite);
  footer(c,"UP / DOWN scroll | SELECT check");
}
static void japanese(GContext *c) {
  const kb_dataset_t *d=app_dataset();
  kb_boarding_point_t p;
  kb_stop_group_t group;
  heading(c,"Stop name","Verified Japanese label");
  if(d&&kb_boarding_point_get(d,app.detail.boarding_point_id,&p)&&kb_stop_group_get(d,p.group_id,&group)) {
    graphics_context_set_text_color(c,GColorWhite);
    graphics_draw_text(c,group.name_ja,app.japanese,GRect(8,80,184,70),GTextOverflowModeWordWrap,GTextAlignmentLeft,NULL);
    text(c,group.name,8,155,184,50,18,cyan());
  }
  footer(c,"BACK returns to details");
}
static void draw(Layer *layer,GContext *c) {
  (void)layer;
  graphics_context_set_fill_color(c,GColorBlack);
  graphics_fill_rect(c,GRect(0,0,200,228),0,GCornerNone);
  if(app.screen==KB_SCREEN_HOME)home(c);
  else if(app.screen==KB_SCREEN_BOARD)board(c);
  else if(app.screen==KB_SCREEN_DETAILS)details(c);
  else if(app.screen==KB_SCREEN_STATUS)status(c);
  else if(app.screen==KB_SCREEN_JAPANESE)japanese(c);
  else list(c);
  APP_LOG(APP_LOG_LEVEL_DEBUG,"UI screen%d heap%lu",app.screen,(unsigned long)heap_bytes_free());
}
void ui_open(int screen) {
  app.screen=screen;
  app.selected=0;
  app.scroll=0;
  app.notice[0]=0;
  if(screen==KB_SCREEN_BOARD) {
    app.board_has_focus=false;
    app.board_expired=false;
    app.board_removed=false;
    app.selected=1;
    if(trip_at(0,&app.board_focus))app.board_has_focus=true;
    else app.selected=0;
  }
  app_redraw();
}
void ui_refresh(void) {
  if(app.screen!=KB_SCREEN_BOARD) {
    int count=choices();
    if(count&&app.selected>=count)app.selected=count-1;
    else if(!count)app.selected=0;
    return;
  }
  if(!app.board_has_focus)return;
  app.board_expired=app.board_focus.departure_utc+60<=time(NULL);
  if(app.board_expired) {
    app.selected=1;
    return;
  }
  kb_query_t q=app_query();
  kb_trip_t previous,t;
  bool has_previous=false;
  for(unsigned i=0;i<1000;i++) {
    if(kb_query_next(&q,has_previous?&previous:NULL,&t,NULL)!=KB_QUERY_FOUND)break;
    if(t.departure_utc==app.board_focus.departure_utc&&t.service_day==app.board_focus.service_day&&t.boarding_point_id==app.board_focus.boarding_point_id&&t.pattern_id==app.board_focus.pattern_id&&t.service_id==app.board_focus.service_id) {
      app.board_focus=t;
      app.board_removed=false;
      app.selected=i+1;
      return;
    }
    if(t.departure_utc>app.board_focus.departure_utc)break;
    previous=t;
    has_previous=true;
  }
  app.changed=true;
  app.board_removed=true;
  app.selected=1;
}
static void up(ClickRecognizerRef r,void *ctx) {
  (void)r;
  (void)ctx;
  if(app.screen==KB_SCREEN_HOME) {
    unsigned n=app.prefs.bytes[5];
    if(n) {
      unsigned i=0;
      while(i<n&&kb_pref_favourite(&app.prefs,i)!=app.point)i++;
      app.point=kb_pref_favourite(&app.prefs,(i+n-1)%n);
    }
  }
  else if(app.screen==KB_SCREEN_DETAILS||app.screen==KB_SCREEN_STATUS) {
    app.scroll-=36;
    if(app.scroll<0)app.scroll=0;
  }
  else if(app.screen==KB_SCREEN_BOARD) {
    if(app.selected>0) {
      app.selected--;
      app.board_has_focus=app.selected>0&&trip_at(app.selected-1,&app.board_focus);
      app.board_expired=false;
      app.board_removed=false;
    }
  }
  else if(app.selected>0)app.selected--;
  app_redraw();
}
static void down(ClickRecognizerRef r,void *ctx) {
  (void)r;
  (void)ctx;
  if(app.screen==KB_SCREEN_HOME) {
    unsigned n=app.prefs.bytes[5];
    if(n) {
      unsigned i=0;
      while(i<n&&kb_pref_favourite(&app.prefs,i)!=app.point)i++;
      app.point=kb_pref_favourite(&app.prefs,(i+1)%n);
    }
  }
  else if(app.screen==KB_SCREEN_DETAILS||app.screen==KB_SCREEN_STATUS) {
    if(app.scroll<1000)app.scroll+=36;
  }
  else if(app.screen==KB_SCREEN_BOARD) {
    kb_trip_t t;
    if((app.board_expired||app.board_removed)&&app.board_has_focus) {
      kb_query_t q=app_query();
      if(kb_query_next(&q,&app.board_focus,&t,NULL)==KB_QUERY_FOUND) {
        app.board_focus=t;
        app.board_expired=false;
        app.board_removed=false;
        app.selected=1;
      }
    }
    else if(trip_at(app.selected,&t)) {
      app.selected++;
      app.board_focus=t;
      app.board_has_focus=true;
    }
  }
  else if(app.selected+1<choices())app.selected++;
  app_redraw();
}
static void select(ClickRecognizerRef r,void *ctx) {
  (void)r;
  (void)ctx;
  app_dismiss_hint();
  if(app.screen==KB_SCREEN_HOME)ui_open(KB_SCREEN_BOARD);
  else if(app.screen==KB_SCREEN_BOARD) {
    if(!app.selected)ui_open(KB_SCREEN_PICKER);
    else if(app.board_has_focus) {
      app.detail=app.board_focus;
      app.return_screen=app.selected;
      ui_open(KB_SCREEN_DETAILS);
    }
  }
  else if(app.screen==KB_SCREEN_DETAILS)ui_open(KB_SCREEN_JAPANESE);
  else if(app.screen==KB_SCREEN_STATUS)app_check_updates(true);
  else if(app.screen==KB_SCREEN_MENU) {
    int a[]= {
      KB_SCREEN_PICKER,KB_SCREEN_CONTEXT,KB_SCREEN_STATUS,KB_SCREEN_SETTINGS
    };
    ui_open(a[app.selected]);
  }
  else if(app.screen==KB_SCREEN_PICKER) {
    int a[]= {
      KB_SCREEN_FAVOURITES,KB_SCREEN_NEARBY,KB_SCREEN_GROUPS
    };
    int screen=a[app.selected];
    ui_open(screen);
    if(screen==KB_SCREEN_NEARBY)app_request_location();
  }
  else if(app.screen==KB_SCREEN_GROUPS) {
    if(app.selected<0||app.selected>=choices())return;
    choice_t ch;
    choice(app.selected,&ch);
    if(!ch.id)return;
    app.group=ch.id;
    ui_open(KB_SCREEN_POINTS);
  }
  else if(app.screen==KB_SCREEN_FAVOURITES||app.screen==KB_SCREEN_POINTS||app.screen==KB_SCREEN_NEARBY) {
    if(app.screen==KB_SCREEN_NEARBY&&!app.selected)app_request_location();
    else if(app.selected>=0&&app.selected<choices()) {
      choice_t ch;
      choice(app.selected,&ch);
      if(app_point_exists(NULL,ch.id)) {
        app.point=ch.id;
        if(app.screen==KB_SCREEN_NEARBY)app.trip_context=KB_CONTEXT_NEARBY;
        ui_open(KB_SCREEN_HOME);
      }
    }
  }
  else if(app.screen==KB_SCREEN_CONTEXT) {
    app.trip_context=app.selected==1?KB_CONTEXT_SAVED_ORIGIN:app.selected==2?KB_CONTEXT_AT_STOP:KB_CONTEXT_NEARBY;
    ui_open(KB_SCREEN_HOME);
  }
  else if(app.screen==KB_SCREEN_OVERRIDE) {
    app.override.jst_day=kb_jst_day(time(NULL));
    app.override.day_type=app.selected?app.selected:KB_DAY_UNKNOWN;
    ui_open(KB_SCREEN_HOME);
  }
  else if(app.screen==KB_SCREEN_SETTINGS) {
    if(app.selected==0)ui_open(KB_SCREEN_OVERRIDE);
    else if(app.selected<=3) {
      uint8_t mask=app.selected==1?KB_PREF_CONTRAST:app.selected==2?KB_PREF_REDUCED_MOTION:KB_PREF_AUTO;
      kb_preferences_t p=app.prefs;
      p.bytes[1]^=mask;
      app_save_preferences(&p);
      app_send_state();
    }
    else if(app.selected==4)snprintf(app.notice,sizeof(app.notice),"Use companion app > KasugaBus");
    else ui_open(app.selected==5?KB_SCREEN_RESET:KB_SCREEN_RESTORE);
  }
  else if(app.screen==KB_SCREEN_RESET||app.screen==KB_SCREEN_RESTORE) {
    if(app.selected) {
      if(app.screen==KB_SCREEN_RESET) {
        kb_preferences_t p;
        kb_preferences_default(&p,1);
        if(app_save_preferences(&p))app.point=1;
        app_send_state();
      }
      else {
        app_restore_timetable();
      }
    }
    ui_open(KB_SCREEN_HOME);
  }
  app_redraw();
}
static void back(ClickRecognizerRef r,void *ctx) {
  (void)r;
  (void)ctx;
  switch(app.screen) {
    case KB_SCREEN_HOME:window_stack_pop(false);
    return;
    case KB_SCREEN_DETAILS:app.screen=KB_SCREEN_BOARD;
    app.selected=app.return_screen;
    app.board_focus=app.detail;
    app.board_has_focus=true;
    ui_refresh();
    app_redraw();
    break;
    case KB_SCREEN_JAPANESE:ui_open(KB_SCREEN_DETAILS);
    break;
    case KB_SCREEN_POINTS:ui_open(KB_SCREEN_GROUPS);
    break;
    case KB_SCREEN_GROUPS:case KB_SCREEN_FAVOURITES:case KB_SCREEN_NEARBY:ui_open(KB_SCREEN_PICKER);
    break;
    case KB_SCREEN_RESET:case KB_SCREEN_RESTORE:case KB_SCREEN_OVERRIDE:ui_open(KB_SCREEN_SETTINGS);
    break;
    default:ui_open(KB_SCREEN_HOME);
    break;
  }
}
static void long_select(ClickRecognizerRef r,void *ctx) {
  (void)r;
  (void)ctx;
  app_dismiss_hint();
  if(app.screen==KB_SCREEN_BOARD) {
    app.changed=false;
    ui_open(KB_SCREEN_BOARD);
  }
  else if(app.screen==KB_SCREEN_NEARBY)app_request_location();
  else ui_open(KB_SCREEN_MENU);
}
static void clicks(void *ctx) {
  (void)ctx;
  window_single_repeating_click_subscribe(BUTTON_ID_UP,150,up);
  window_single_repeating_click_subscribe(BUTTON_ID_DOWN,150,down);
  window_single_click_subscribe(BUTTON_ID_SELECT,select);
  window_long_click_subscribe(BUTTON_ID_SELECT,550,long_select,NULL);
  window_single_click_subscribe(BUTTON_ID_BACK,back);
}
void ui_init(void) {
  app.window=window_create();
  window_set_background_color(app.window,GColorBlack);
  window_set_click_config_provider(app.window,clicks);
  app.layer=layer_create(GRect(0,0,200,228));
  layer_set_update_proc(app.layer,draw);
  layer_add_child(window_get_root_layer(app.window),app.layer);
  app.japanese=fonts_load_custom_font(resource_get_handle(RESOURCE_ID_JP_16));
  window_stack_push(app.window,false);
}
