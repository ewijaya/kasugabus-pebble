#include "app.h"
#include <stdio.h>
#include <string.h>
typedef struct {
  GColor background,foreground,navigation,departure,warning,magenta,badge_text;
} palette_t;
static palette_t colors;
static int scroll_limit;
static char document_buffer[2200];
static const char *size_names[]={"Standard","Large","Extra Large"};
static const char *theme_names[]={"Neon Dark","Neon Light","High Contrast Dark","High Contrast Light"};
static palette_t palette(unsigned theme) {
  if(theme==KB_THEME_NEON_LIGHT)return (palette_t){GColorWhite,GColorBlack,GColorDukeBlue,GColorDarkGreen,GColorDarkCandyAppleRed,GColorPurple,GColorWhite};
  if(theme==KB_THEME_HIGH_CONTRAST_DARK)return (palette_t){GColorBlack,GColorWhite,GColorWhite,GColorWhite,GColorWhite,GColorWhite,GColorBlack};
  if(theme==KB_THEME_HIGH_CONTRAST_LIGHT)return (palette_t){GColorWhite,GColorBlack,GColorBlack,GColorBlack,GColorBlack,GColorBlack,GColorWhite};
  return (palette_t){GColorBlack,GColorWhite,GColorCyan,GColorSpringBud,GColorChromeYellow,GColorMagenta,GColorBlack};
}
static unsigned body_size(void) {
  const unsigned sizes[]={18,24,28};
  return sizes[kb_pref_text_size(&app.prefs)];
}
static unsigned secondary_size(void) {
  const unsigned sizes[]={14,18,24};
  return sizes[kb_pref_text_size(&app.prefs)];
}
static unsigned meta_size(void) {
  return kb_pref_text_size(&app.prefs)==KB_TEXT_STANDARD?14:18;
}
static int footer_top(void) {
  return kb_pref_text_size(&app.prefs)==KB_TEXT_STANDARD?208:202;
}
static GFont font(unsigned n) {
  return fonts_get_system_font(n==42?FONT_KEY_BITHAM_42_BOLD:n==34?FONT_KEY_BITHAM_34_MEDIUM_NUMBERS:n==28?FONT_KEY_GOTHIC_28:n==24?FONT_KEY_GOTHIC_24:n==18?FONT_KEY_GOTHIC_18:FONT_KEY_GOTHIC_14);
}
static GFont bold_font(unsigned n) {
  return fonts_get_system_font(n==28?FONT_KEY_GOTHIC_28_BOLD:n==24?FONT_KEY_GOTHIC_24_BOLD:n==18?FONT_KEY_GOTHIC_18_BOLD:FONT_KEY_GOTHIC_14);
}
/* Bundled Noto Sans Condensed Bold (Latin only) for the home bus block. Fonts are
 * loaded on first use and kept for the app's lifetime. */
static GFont noto(unsigned n) {
  static GFont cache[6];
  static const uint8_t sizes[]={20,24,28,32,36,42};
  static const uint32_t ids[]={RESOURCE_ID_NOTO_BOLD_20,RESOURCE_ID_NOTO_BOLD_24,RESOURCE_ID_NOTO_BOLD_28,
    RESOURCE_ID_NOTO_BOLD_32,RESOURCE_ID_NOTO_BOLD_36,RESOURCE_ID_NOTO_BOLD_42};
  unsigned i=0;
  while(i+1<sizeof(sizes)&&sizes[i]<n)i++;
  if(!cache[i])cache[i]=fonts_load_custom_font(resource_get_handle(ids[i]));
  return cache[i];
}
static int width_font(const char *s,GFont f);
static unsigned fit_size(const char *s,unsigned max) {
  unsigned n=max;
  while(n>20&&width_font(s,noto(n))>184)n=n>=36?n-(n==42?6:4):n-4;
  return n;
}
static int height_font(const char *s,int width,GFont f) {
  if(!s||!s[0])return 0;
  GSize size=graphics_text_layout_get_content_size(s,f,GRect(0,0,width,30000),GTextOverflowModeWordWrap,GTextAlignmentLeft);
  return size.h+3;
}
static int height(const char *s,int width,unsigned f) {
  return height_font(s,width,font(f));
}
static void text_font(GContext *c,const char *s,int x,int y,int w,int h,GFont f,GColor color) {
  graphics_context_set_text_color(c,color);
  graphics_draw_text(c,s,f,GRect(x,y,w,h),GTextOverflowModeWordWrap,GTextAlignmentLeft,NULL);
}
static int width_font(const char *s,GFont f) {
  if(!s||!s[0])return 0;
  /* Measure unwrapped: a screen-width box would report a wrapped width. */
  return graphics_text_layout_get_content_size(s,f,GRect(0,0,1000,200),GTextOverflowModeWordWrap,GTextAlignmentLeft).w;
}
static void text(GContext *c,const char *s,int x,int y,int w,int h,unsigned f,GColor color) {
  text_font(c,s,x,y,w,h,font(f),color);
}
static void strong(GContext *c,const char *s,int x,int y,int w,int h,unsigned f,GColor color) {
  text_font(c,s,x,y,w,h,bold_font(f),color);
}
static void clamp_scroll(int total,int viewport) {
  scroll_limit=total>viewport?total-viewport:0;
  if(app.scroll>scroll_limit)app.scroll=scroll_limit;
  if(app.scroll<0)app.scroll=0;
}
void ui_apply_appearance(void) {
  colors=palette(kb_pref_theme(&app.prefs));
  if(!app.window)return;
  window_set_background_color(app.window,colors.background);
  unsigned size=kb_pref_text_size(&app.prefs);
  if(app.screen!=KB_SCREEN_JAPANESE) {
    if(app.japanese)fonts_unload_custom_font(app.japanese);
    app.japanese=NULL;
  }
  else if(!app.japanese||app.japanese_size!=size) {
    if(app.japanese)fonts_unload_custom_font(app.japanese);
    const uint32_t resources[]={RESOURCE_ID_JP_16,RESOURCE_ID_JP_24,RESOURCE_ID_JP_28};
    app.japanese=fonts_load_custom_font(resource_get_handle(resources[size]));
    app.japanese_size=size;
  }
  app.scroll=0;
  app_redraw();
}
static void line(GContext *c,int y,GColor col) {
  graphics_context_set_stroke_color(c,col);
  graphics_draw_line(c,GPoint(8,y),GPoint(192,y));
}
static const char *day_name(kb_day_type_t d) {
  return d==KB_DAY_WEEKDAY?"Weekday":d==KB_DAY_SATURDAY?"Saturday":d==KB_DAY_SUNDAY_HOLIDAY?"Sun / holiday":d==KB_DAY_NONE?"No service today":"Schedule unconfirmed";
}
static const char *short_day_name(kb_day_type_t d) {
  return d==KB_DAY_WEEKDAY?"Weekday":d==KB_DAY_SATURDAY?"Saturday":d==KB_DAY_SUNDAY_HOLIDAY?"Sun/hol":d==KB_DAY_NONE?"No service":"Unconfirmed";
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
  else if(m<60)snprintf(b,n,"%lu min",(unsigned long)m);
  else if(m%60==0)snprintf(b,n,"%lu h",(unsigned long)(m/60));
  else snprintf(b,n,"%lu h %lu m",(unsigned long)(m/60),(unsigned long)(m%60));
}
static unsigned nearby_status_now(void) {
  unsigned status=app.nearby_status;
  if(status>8)return 5;
  if((status==0||status==1||status==2)&&app.location_stamp&&time(NULL)-app.location_stamp>120)return 2;
  return status;
}
static int heading(GContext *c,const char *title,const char *sub) {
  unsigned f=kb_pref_text_size(&app.prefs)==KB_TEXT_STANDARD?24:28;
  int title_height=height_font(title,184,bold_font(f));
  int y=3;
  strong(c,title,8,y,184,title_height,f,colors.navigation);
  y+=title_height+2;
  if(sub&&sub[0]) {
    int sub_height=height(sub,184,meta_size());
    /* Use the same unconstrained canvas as measurement: tight WordWrap
     * rectangles can lose a subtitle line after native scrolled redraws. */
    text(c,sub,8,y,184,30000,meta_size(),colors.foreground);
    y+=sub_height+2;
  }
  line(c,y,colors.navigation);
  return y+5;
}
static void footer(GContext *c,const char *s) {
  int top=footer_top();
  graphics_context_set_fill_color(c,colors.background);
  graphics_fill_rect(c,GRect(0,top,200,228-top),0,GCornerNone);
  line(c,top,colors.navigation);
  text(c,s,8,top+1,184,227-top,meta_size(),colors.foreground);
}
static void home(GContext *c) {
  time_t now=time(NULL);
  struct tm local=*localtime(&now);
  char b[112],clock[20];
  strftime(clock,sizeof(clock),clock_is_24h_style()?"%H:%M":"%I:%M",&local);
  if(!clock_is_24h_style()&&clock[0]=='0')memmove(clock,clock+1,strlen(clock));
  const kb_dataset_t *d=app_dataset();
  kb_boarding_point_t p;
  if(!d||!kb_boarding_point_get(d,app.point,&p)) {
    int y=heading(c,"KasugaBus",NULL);
    text(c,"Timetable unavailable",8,y+6,184,90,body_size(),colors.foreground);
    text(c,"Select for Stops & tools",8,y+100,184,65,meta_size(),colors.navigation);
    footer(c,"Manual selection");
    return;
  }
  /* Querying another service date can replace the shared dataset cache. */
  char stop[100],direction[160],destination[140]="",route[40]="",tm[16]="",cd[24]="";
  snprintf(stop,sizeof(stop),"%s",p.short_name);
  snprintf(direction,sizeof(direction),"%s",p.direction);
  kb_query_t q=app_query();
  kb_trip_t t;
  kb_query_state_t state;
  int found=kb_query_home(&q,&t,&state);
  if(found==KB_QUERY_FOUND) {
    d=kb_trip_dataset(&q,&t);
    kb_pattern_t pattern;
    if(d&&kb_pattern_get(d,t.pattern_id,&pattern)) {
      snprintf(route,sizeof(route),"%s",pattern.route);
      snprintf(destination,sizeof(destination),"%s",pattern.destination);
      time_string(t.departure_utc,tm,sizeof(tm));
      countdown(&t,cd,sizeof(cd));
    }
  }
  else snprintf(destination,sizeof(destination),"%s",found==KB_QUERY_UNCONFIRMED?"Schedule unconfirmed":"No upcoming service");
  /* The bus block uses bundled Noto Sans Condensed Bold, which continues
   * past the system font's 28 pt ceiling. Names always stay on one line, so
   * the screen width caps long ones; the departure time and countdown grow
   * with each text size. Large and Extra Large move the clock into the
   * footer and give the countdown its own line. Pick the
   * largest tier at or below the chosen size that fits. */
  static const uint8_t tiers[][6]={ /* stop, direction, time/route, countdown, destination, own countdown line */
    {36,32,42,42,32,1},{32,28,42,36,28,1},{32,28,36,36,28,1},{32,28,36,28,28,0},
    {28,24,32,24,24,0},{28,20,28,20,20,0},{24,20,24,20,20,0},{20,20,20,20,20,0}};
  const unsigned tier_count=sizeof(tiers)/sizeof(tiers[0]);
  unsigned size=kb_pref_text_size(&app.prefs);
  bool compact=size!=KB_TEXT_STANDARD;
  unsigned tier=size==KB_TEXT_EXTRA_LARGE?0:size==KB_TEXT_LARGE?2:4;
  const unsigned header=18;
  int clock_h=height(clock,104,34),side_h=2*((int)header+3);
  if(side_h>clock_h)clock_h=side_h;
  int top=compact?4:2+clock_h+2+3,bottom=footer_top()-2;
  int stop_h,direction_h,destination_h,departure_h,count_h,badge_w,time_w,count_x;
  unsigned count_size;
  bool count_below;
  unsigned stop_size,direction_size,time_size,destination_size;
  for(;;) {
    const uint8_t *s=tiers[tier];
    /* Each line uses the largest size up to the tier's limit that stays on
     * one line; it wraps only at the smallest size. */
    stop_size=fit_size(stop,s[0]);direction_size=fit_size(direction,s[1]);
    destination_size=fit_size(destination,s[4]);time_size=s[2];
    stop_h=height_font(stop,184,noto(stop_size));
    direction_h=height_font(direction,184,noto(direction_size));
    destination_h=height_font(destination,184,noto(destination_size));
    departure_h=0;count_h=0;badge_w=0;time_w=0;count_x=192;count_size=s[3];count_below=false;
    if(route[0]) {
      badge_w=width_font(route,noto(time_size))+10;
      time_w=width_font(tm,noto(time_size))+4;
      count_x=8+badge_w+6+time_w+8;
      departure_h=height_font(tm,184,noto(time_size));
      /* Keep the countdown beside the time when it fits at a readable size;
       * otherwise give it its own right-aligned row at the tier size. */
      while(!s[5]&&count_size>20&&width_font(cd,noto(count_size))>192-count_x)count_size-=4;
      if(s[5]||width_font(cd,noto(count_size))>192-count_x) {
        count_below=true;count_size=fit_size(cd,s[3]);count_x=8;
      }
      count_h=height_font(cd,184,noto(count_size));
      if(!count_below&&count_h>departure_h)departure_h=count_h;
    }
    int rows=stop_h+direction_h+departure_h+(count_below?count_h:0)+destination_h+5;
    if(top+rows<=bottom||tier+1>=tier_count)break;
    tier++;
  }
  int used=stop_h+direction_h+departure_h+(count_below?count_h:0)+destination_h+5;
  if(top+used>bottom)APP_LOG(APP_LOG_LEVEL_WARNING,"Home text overflow point%u size%u height%d",app.point,size,top+used);
  /* Spread any remaining height between the rows instead of leaving it
   * below the destination. */
  int gap=top+used<bottom?(bottom-top-used)/4:0;
  if(gap>8)gap=8;
  int y=compact?top+gap:2;
  if(!compact) {
    text(c,clock,8,y,104,clock_h,34,colors.foreground);
    strftime(b,sizeof(b),"%a %d %b",&local);
    graphics_context_set_text_color(c,colors.navigation);
    graphics_draw_text(c,b,font(header),GRect(104,y,80,(int)header+3),GTextOverflowModeTrailingEllipsis,GTextAlignmentRight,NULL);
    snprintf(b,sizeof(b),"%s%s",clock_is_24h_style()?"":local.tm_hour<12?"AM ":"PM ",local.tm_gmtoff==32400?"JST":"LOCAL");
    graphics_context_set_text_color(c,colors.foreground);
    graphics_draw_text(c,b,font(header),GRect(104,y+(int)header+3,80,(int)header+3),GTextOverflowModeTrailingEllipsis,GTextAlignmentRight,NULL);
    graphics_context_set_fill_color(c,colors.magenta);
    graphics_fill_rect(c,GRect(188,y+7,4,12),0,GCornerNone);
    y+=clock_h+2;line(c,y,colors.navigation);y+=3+gap;
  }
  text_font(c,stop,8,y,184,stop_h,noto(stop_size),colors.foreground);y+=stop_h+1+gap;
  text_font(c,direction,8,y,184,direction_h,noto(direction_size),colors.navigation);y+=direction_h+3+gap;
  if(route[0]) {
    graphics_context_set_fill_color(c,colors.departure);
    graphics_fill_rect(c,GRect(8,y+3,badge_w,departure_h-3),3,GCornersAll);
    graphics_context_set_text_color(c,colors.badge_text);
    graphics_draw_text(c,route,noto(time_size),GRect(8,y,badge_w,departure_h),GTextOverflowModeWordWrap,GTextAlignmentCenter,NULL);
    text_font(c,tm,8+badge_w+6,y,time_w,departure_h,noto(time_size),colors.departure);
    graphics_context_set_text_color(c,colors.departure);
    int count_y=count_below?y+departure_h:y+departure_h-count_h;
    graphics_draw_text(c,cd,noto(count_size),GRect(count_x,count_y,192-count_x,count_h),
                       GTextOverflowModeWordWrap,GTextAlignmentRight,NULL);
    y+=departure_h+(count_below?count_h:0)+1+gap;
  }
  text_font(c,destination,8,y,184,destination_h,noto(destination_size),route[0]?colors.foreground:colors.warning);
  d=app_dataset();
  if(app.override.day_type!=KB_DAY_UNKNOWN&&app.override.jst_day==kb_jst_day(now))snprintf(b,sizeof(b),"Override %s JST",short_day_name(app.override.day_type));
  else if(app.store.recovery_notice)snprintf(b,sizeof(b),"Recovery data | JST");
  else if(d&&d->review_by!=KB_DATE_UNKNOWN&&kb_jst_day(now)>d->review_by)snprintf(b,sizeof(b),"Review due | JST");
  else if(found<0)snprintf(b,sizeof(b),"Unconfirmed | JST");
  else if(found==KB_QUERY_FOUND&&kb_jst_day(t.departure_utc)!=kb_jst_day(now)) {
    char date[20];date_string(kb_jst_day(t.departure_utc),date,sizeof(date));
    snprintf(b,sizeof(b),"%s | Scheduled JST",date+5);
  }
  else if(state.today_no_service)snprintf(b,sizeof(b),"No service today | JST");
  else if(app.changed)snprintf(b,sizeof(b),"New data | Scheduled JST");
  else snprintf(b,sizeof(b),"Scheduled JST | %s",short_day_name(found==KB_QUERY_FOUND?t.day_type:state.today_type));
  if(compact) {
    /* The clock row is hidden: show local time first, then the status with
     * its redundant "Scheduled" dropped to keep one footer line. */
    char status[112];
    const char *rest=strncmp(b,"Scheduled JST | ",16)==0?b+10:b;
    snprintf(status,sizeof(status),"%s",rest);
    char *sched=strstr(status," | Scheduled JST");
    if(sched)memmove(sched+3,sched+13,strlen(sched+13)+1);
    snprintf(b,sizeof(b),"%s%s%s | %s",local.tm_gmtoff==32400?"":"Local ",clock,
             clock_is_24h_style()?"":local.tm_hour<12?"AM":"PM",status);
  }
  footer(c,b);
}
typedef struct  {
  char title[140],sub[384];
  uint16_t id;
}
choice_t;
static bool all_selected(uint16_t id) {
  for(unsigned i=0;i<app.all_prefs.count;i++)if(app.all_prefs.ids[i]==id)return true;
  return false;
}
static unsigned all_point_ids(uint16_t *ids) {
  const kb_dataset_t *d=app_dataset();unsigned n=0;
  for(size_t i=0;d&&i<kb_boarding_point_count(d)&&n<KB_MAX_POINTS;i++) {
    kb_boarding_point_t p;kb_boarding_point_at(d,i,&p);ids[n++]=p.id;
  }
  for(unsigned i=0;i<app.all_prefs.count;i++) {
    bool present=false;for(unsigned j=0;j<n;j++)if(ids[j]==app.all_prefs.ids[i])present=true;
    if(!present)ids[n++]=app.all_prefs.ids[i];
  }
  if(app.all_point_focus) {
    bool present=false;for(unsigned i=0;i<n;i++)if(ids[i]==app.all_point_focus)present=true;
    if(!present)ids[n++]=app.all_point_focus;
  }
  for(unsigned i=1;i<n;i++) {
    uint16_t id=ids[i];uint32_t metres=app_all_distance(id);unsigned j=i;
    while(j) {
      uint32_t previous=app_all_distance(ids[j-1]);
      if(previous<metres||(previous==metres&&ids[j-1]<id))break;
      ids[j]=ids[j-1];j--;
    }
    ids[j]=id;
  }
  return n;
}
void ui_remember_all_point(void) {
  if(app.screen!=KB_SCREEN_ALL_POINTS||app.selected<4||app.all_point_focus)return;
  uint16_t ids[KB_MAX_POINTS*2+1];unsigned count=all_point_ids(ids);
  if((unsigned)app.selected-4<count)app.all_point_focus=ids[app.selected-4];
}
static unsigned all_status_now(void) {
  if(app.all_prefs.reference==KB_ALL_REFERENCE_MANUAL)return 10;
  if(!(app.prefs.bytes[1]&KB_PREF_LOCATION))return 8;
  if(app.all_status==8)return 2;
  if(app.all_prefs.reference==KB_ALL_REFERENCE_CURRENT&&app.all_stamp&&time(NULL)-(int64_t)app.all_stamp>120)return 2;
  return app.all_status<0||app.all_status>9?5:(unsigned)app.all_status;
}
static void all_label(char *s,size_t n) {
  if(app.all_waiting) {snprintf(s,n,"Requesting distances...");return;}
  const char *labels[]={"Current | Approx.","Low accuracy","Current fix stale","Permission denied","Location timed out","Phone unavailable","Outside saved area","No verified poles","Location is off","Home is unset","Manual | Unknown"};
  unsigned status=all_status_now();
  if(app.all_prefs.reference==KB_ALL_REFERENCE_HOME&&status==0)snprintf(s,n,"Saved home | Approx.");
  else if(app.all_prefs.reference==KB_ALL_REFERENCE_HOME&&status==2)snprintf(s,n,"Saved home | Refresh");
  else snprintf(s,n,"%s",labels[status]);
}
static int choices(void) {
  const kb_dataset_t *d=app_dataset();
  switch(app.screen) {
    case KB_SCREEN_MENU:return 4;
    case KB_SCREEN_PICKER:return 5;
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
    case KB_SCREEN_SETTINGS:return 8;
    case KB_SCREEN_TEXT_SIZE:return 3;
    case KB_SCREEN_THEME:return 4;
    case KB_SCREEN_ALL_REFERENCE:return 4;
    case KB_SCREEN_ALL_POINTS: {
      uint16_t ids[KB_MAX_POINTS*2+1];return 4+(int)all_point_ids(ids);
    }
    case KB_SCREEN_ROUTES:return d?kb_route_count(d):0;
    case KB_SCREEN_ROUTE_POINTS: {
      unsigned n=0;
      for(size_t i=0;d&&i<kb_boarding_point_count(d);i++) {
        kb_boarding_point_t p;
        kb_boarding_point_at(d,i,&p);
        if(kb_boarding_point_has_route(d,p.id,app.route_operator,app.route_number))n++;
      }
      return n;
    }
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
        "Favourites","Nearby","All stops","Bus numbers","All departures"
      };
      const char *b[]= {
        "Your saved order","One phone location request","Six stops, all directions","Choose operator and boarding number","Several boarding points, one board"
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
    case KB_SCREEN_ROUTES: {
      kb_route_t route;kb_operator_t o;
      if(d&&kb_route_at(d,n,&route)&&kb_operator_get(d,route.operator_id,&o)) {
        snprintf(c->title,sizeof(c->title),"%s %s",o.short_name,route.number);
        snprintf(c->sub,sizeof(c->sub),"%s | Boarding number",o.name);
      }
      break;
    }
    case KB_SCREEN_ROUTE_POINTS: {
      int seen=0;
      for(size_t i=0;d&&i<kb_boarding_point_count(d);i++) {
        kb_boarding_point_t p;kb_boarding_point_at(d,i,&p);
        if(kb_boarding_point_has_route(d,p.id,app.route_operator,app.route_number)&&seen++==n) {
          point_choice(d,p.id,c);break;
        }
      }
      break;
    }
    case KB_SCREEN_ALL_REFERENCE: {
      const char *names[]={"Current phone location","Saved home location","Manual selection","Use favourites"};
      const char *sub[]={"One explicit phone fix","Private reference saved on phone","Choose without location","Start with your favourite IDs"};
      snprintf(c->title,sizeof(c->title),"%s",names[n]);
      snprintf(c->sub,sizeof(c->sub),"%s%s",(unsigned)n==app.all_prefs.reference?"Current | ":"",sub[n]);
      break;
    }
    case KB_SCREEN_ALL_POINTS: {
      if(n<4) {
        const char *names[]={"Show departures","Refresh distances","Use favourites","Clear selection"};
        if(!n)snprintf(c->title,sizeof(c->title),"%s (%u)",names[n],app.all_prefs.count);
        else snprintf(c->title,sizeof(c->title),"%s",names[n]);
        const char *sub[]={"Selected points only","One explicit reference request","Replace selection with favourites","Keep a deliberately empty list"};
        snprintf(c->sub,sizeof(c->sub),"%s",sub[n]);
      }
      else {
        uint16_t ids[KB_MAX_POINTS*2+1];unsigned count=all_point_ids(ids);
        if((unsigned)n-4>=count)break;
        point_choice(d,ids[n-4],c);
        kb_boarding_point_t p;
        if(!d||!kb_boarding_point_get(d,c->id,&p))snprintf(c->title,sizeof(c->title),"Unavailable point %u",c->id);
        char name[140],direction[sizeof(c->sub)];
        snprintf(name,sizeof(name),"%s",c->title);snprintf(direction,sizeof(direction),"%s",c->sub);
        snprintf(c->title,sizeof(c->title),"%s %.130s",all_selected(c->id)?"[x]":"[ ]",name);
        uint32_t metres=app_all_distance(c->id);
        if(metres==UINT32_MAX)snprintf(c->sub,sizeof(c->sub),"%.215s\nDistance unknown",direction);
        else snprintf(c->sub,sizeof(c->sub),"%.200s\nApprox. %lum",direction,(unsigned long)metres);
      }
      break;
    }
    case KB_SCREEN_NEARBY:if(!n) {
      snprintf(c->title,sizeof(c->title),"Refresh location");
      /* The app toggle is on but the phone OS refused; PebbleKit JS runs in
       * the background, so the Pebble app needs "Allow all the time". */
      if(nearby_status_now()==3)snprintf(c->sub,sizeof(c->sub),"Phone: allow Pebble app location all the time");
      else snprintf(c->sub,sizeof(c->sub),"Approx. straight-line distance");
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
        "Text size","Colour theme","Service-day override","Reduced motion","Automatic updates","Phone settings","Reset preferences","Restore bundled data"
      };
      snprintf(c->title,sizeof(c->title),"%s",a[n]);
      if(n==0)snprintf(c->sub,sizeof(c->sub),"%s",size_names[kb_pref_text_size(&app.prefs)]);
      else if(n==1)snprintf(c->sub,sizeof(c->sub),"%s",theme_names[kb_pref_theme(&app.prefs)]);
      else if(n==3)snprintf(c->sub,sizeof(c->sub),"%s",app.prefs.bytes[1]&KB_PREF_REDUCED_MOTION?"On":"Off (no idle animation)");
      else if(n==4)snprintf(c->sub,sizeof(c->sub),"%s",app.prefs.bytes[1]&KB_PREF_AUTO?"On - daily on launch":"Off - manual check available");
      else if(n==5)snprintf(c->sub,sizeof(c->sub),"Open KasugaBus settings in phone");
      else snprintf(c->sub,sizeof(c->sub),"%s",n==2?"Ends at next JST date":n==6?"Timetables remain stored":"Explicit dated recovery");
      break;
    }
    case KB_SCREEN_TEXT_SIZE: {
      const char *descriptions[]={"Compact text","Larger everyday text","Largest text, fewer rows"};
      snprintf(c->title,sizeof(c->title),"%s",size_names[n]);
      snprintf(c->sub,sizeof(c->sub),"%s%s",(unsigned)n==kb_pref_text_size(&app.prefs)?"Current | ":"",descriptions[n]);
      break;
    }
    case KB_SCREEN_THEME: {
      const char *descriptions[]={"Bright accents on black","Dark accents on white","White on black","Black on white"};
      snprintf(c->title,sizeof(c->title),"%s",theme_names[n]);
      snprintf(c->sub,sizeof(c->sub),"%s%s",(unsigned)n==kb_pref_theme(&app.prefs)?"Current | ":"",descriptions[n]);
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
    case KB_SCREEN_TEXT_SIZE:return "Text size";
    case KB_SCREEN_THEME:return "Colour theme";
    case KB_SCREEN_ROUTES:return "Bus numbers";
    case KB_SCREEN_ROUTE_POINTS:return "Board this bus";
    case KB_SCREEN_ALL_REFERENCE:return "All departures";
    case KB_SCREEN_ALL_POINTS:return "Boarding points";
    case KB_SCREEN_OVERRIDE:return "Service calendar";
    case KB_SCREEN_RESET:return "Reset preferences?";
    case KB_SCREEN_RESTORE:return "Restore baseline?";
    default:return "KasugaBus";
  }
}
static void nearby_label(char *s,size_t n) {
  if(app.nearby_status==8&&(app.prefs.bytes[1]&KB_PREF_LOCATION)) {
    snprintf(s,n,"SELECT: refresh location");
    return;
  }
  if(app.nearby_waiting) {
    snprintf(s,n,"Locating with phone...");
    return;
  }
  const char *a[]= {
    "Approx. - similar within accuracy","Low accuracy - choose direction","Previous location - refresh","Permission denied","Location timed out","Phone unavailable","Outside saved area","No verified poles to rank","Location is off"
  };
  unsigned status=nearby_status_now();
  if((status==0||status==1||status==2)&&app.location_stamp) {
    long age=time(NULL)-app.location_stamp;
    snprintf(s,n,"%s (%ldm, +/- %lum)",status==0?"Approx.":status==1?"Low accuracy":"Previous",age/60,(unsigned long)app.accuracy);
  }
  else snprintf(s,n,"%s",a[status]);
}
static int choice_height(const choice_t *ch) {
  return height_font(ch->title,182,bold_font(body_size()))+height(ch->sub,182,secondary_size())+9;
}
static void document(GContext *c,const char *s,int top,const char *foot) {
  int total=height(s,184,body_size());
  clamp_scroll(total,footer_top()-top-2);
  /* Tight WordWrap drawing rectangles blanked on native repeated redraws.
   * Keep drawing unconstrained; measured content alone bounds scrolling. */
  text(c,s,8,top-app.scroll,184,30000,body_size(),colors.foreground);
  footer(c,foot);
}
static kb_query_result_t all_summary(kb_trip_t *trip,kb_query_state_t *state) {
  kb_query_t q=app_query();uint32_t metres[KB_ALL_MAX_POINTS];
  for(unsigned i=0;i<app.all_prefs.count;i++)metres[i]=app_all_distance(app.all_prefs.ids[i]);
  memset(state,0,sizeof(*state));state->first_unconfirmed_day=KB_DATE_UNKNOWN;
  return kb_query_merged_next(&q,app.all_prefs.ids,metres,app.all_prefs.count,NULL,trip,state);
}
static void all_info(GContext *c) {
  unsigned status=all_status_now();
  const char *messages[]={
    "Distances use one explicit phone fix. Refresh when your position changes.",
    "The phone fix has low accuracy. Distances are unknown; choose boarding points manually.",
    "The current phone fix is older than two minutes, or the reference/data changed. Distance unknown. Refresh explicitly.",
    "Android location permission was denied. Allow location for the Pebble phone app in Android settings, then refresh. The KasugaBus location switch does not grant Android permission.",
    "The location request timed out. Refresh to retry, or choose boarding points manually.",
    "The phone is unavailable. Manual selection and favourites still work offline. Refresh after reconnecting.",
    "The reference is outside the saved area. Choose boarding points manually.",
    "There are no verified pole distances. Choose boarding points manually. Unverified coordinates are never guessed.",
    "Enable 'Use phone location for Nearby' in KasugaBus phone settings.",
    "No home reference is saved. Save current home in KasugaBus phone settings, then refresh. Home coordinates stay on the phone.",
    "Manual selection works offline. Distance unknown. Favourites can replace the selection; an empty selection remains empty."
  };
  const char *reference=app.all_prefs.reference==KB_ALL_REFERENCE_HOME?"Saved home location":app.all_prefs.reference==KB_ALL_REFERENCE_CURRENT?"Current phone location":"Manual";
  const char *message=app.all_waiting?"Requesting distances once. Manual selection remains available.":messages[status];
  if(app.all_prefs.reference==KB_ALL_REFERENCE_HOME&&status==0)message="Distances use the fixed saved home reference. They do not expire after two minutes. Home coordinates stay on the phone.";
  else if(app.all_prefs.reference==KB_ALL_REFERENCE_HOME&&status==2)message="Saved home or timetable data changed. Old distances were cleared. Refresh explicitly; no automatic location request was made.";
  kb_trip_t trip;kb_query_state_t state;all_summary(&trip,&state);
  char calendar[180]="Verified trips only. Each operator uses its own service calendar.";
  if(state.coverage_limited) {
    char date[20];date_string(state.first_unconfirmed_day,date,sizeof(date));
    snprintf(calendar,sizeof(calendar),"Partial coverage: a selected point has an unconfirmed calendar from %s. Other verified trips are still shown.",date);
  }
  char override[80]="";
  if(app.override.day_type!=KB_DAY_UNKNOWN&&app.override.jst_day==kb_jst_day(time(NULL)))snprintf(override,sizeof(override),"\nOverride: %s, until JST midnight.",day_name(app.override.day_type));
  const char *selection=app.all_prefs.count?"":"\n\nNo points are selected. Back to the point selector, then choose boarding points or Use favourites. Show departures opens the merged board.";
  snprintf(document_buffer,sizeof(document_buffer),"%s%s\n\nReference: %s\nSelected points: %u\n\nScheduled times in JST.\n%s%s\n\nDistances are approximate straight-line distances, not walking times or roadside guidance. No walking allowance is applied.\n\nUse manual selection or favourites without location. Hold SELECT on the list or board for this information.",message,selection,reference,app.all_prefs.count,calendar,override);
  int top=heading(c,status==8?"Location is off":"All departures",NULL);
  document(c,document_buffer,top+4,"UP/DOWN | BACK");
  graphics_context_set_fill_color(c,colors.background);graphics_fill_rect(c,GRect(0,0,200,top),0,GCornerNone);
  heading(c,status==8?"Location is off":"All departures",NULL);
}
static void nearby_disabled(GContext *c) {
  int top=heading(c,"Location is off",NULL);
  document(c,"Enable 'Use phone location for Nearby' in KasugaBus phone settings.",top+5,"UP/DOWN | BACK");
  graphics_context_set_fill_color(c,colors.background);
  graphics_fill_rect(c,GRect(0,0,200,top),0,GCornerNone);
  heading(c,"Location is off",NULL);
}
static void list(GContext *c) {
  if(app.screen==KB_SCREEN_ALL_POINTS)ui_refresh();
  if(app.screen==KB_SCREEN_NEARBY&&!(app.prefs.bytes[1]&KB_PREF_LOCATION)) {
    nearby_disabled(c);
    return;
  }
  char sub[140]="";
  if(app.screen==KB_SCREEN_NEARBY)nearby_label(sub,sizeof(sub));
  else if(app.screen==KB_SCREEN_ALL_POINTS) {
    if(app.notice[0])snprintf(sub,sizeof(sub),"%s",app.notice);
    else all_label(sub,sizeof(sub));
  }
  else if(app.notice[0])snprintf(sub,sizeof(sub),"%s",app.notice);
  else if(app.screen==KB_SCREEN_SETTINGS)snprintf(sub,sizeof(sub),"KasugaBus v%s",KB_APP_VERSION);
  int top=heading(c,screen_title(),sub);
  int bottom=footer_top()-2,viewport=bottom-top;
  int count=choices();
  if(!count) {
    if(app.screen==KB_SCREEN_ROUTE_POINTS) {
      document(c,"This bus number has no boarding points in the current timetable. Back to choose another bus number.",top+4,"UP/DOWN | BACK");
      graphics_context_set_fill_color(c,colors.background);
      graphics_fill_rect(c,GRect(0,0,200,top),0,GCornerNone);
      heading(c,screen_title(),sub);
      return;
    }
    bool available=app_dataset()!=NULL;
    text(c,available?"No saved entries":"Timetable unavailable",8,top+7,184,90,body_size(),colors.foreground);
    text(c,available?"All stops is always available.":"Back for menu and Data status",8,top+98,184,65,meta_size(),colors.navigation);
    scroll_limit=0;
  }
  else {
    choice_t ch;choice(app.selected,&ch);
    int selected_height=choice_height(&ch);
    clamp_scroll(selected_height,viewport);
    int start=app.selected,total=selected_height;
    /* Add previous complete rows only while the selected row still fits. */
    if(!scroll_limit)while(start>0) {
      choice_t previous;choice(start-1,&previous);
      int h=choice_height(&previous);
      if(total+h>viewport)break;
      total+=h;start--;
    }
    int y=top-app.scroll;
    for(int row=start;row<count&&y<bottom;row++) {
      choice(row,&ch);int h=choice_height(&ch);
      if(row!=app.selected&&y+h>bottom)break;
      bool selected=row==app.selected;
      if(selected) {
        graphics_context_set_fill_color(c,colors.navigation);
        graphics_fill_rect(c,GRect(4,y,192,h-2),3,GCornersAll);
      }
      GColor color=selected?colors.badge_text:colors.foreground;
      int title_h=height_font(ch.title,182,bold_font(body_size()));
      strong(c,ch.title,9,y+1,182,title_h,body_size(),color);
      text(c,ch.sub,9,y+title_h+2,182,h-title_h-6,secondary_size(),color);
      y+=h;
    }
  }
  graphics_context_set_fill_color(c,colors.background);
  graphics_fill_rect(c,GRect(0,0,200,top),0,GCornerNone);
  heading(c,screen_title(),sub);
  /* Oversized rows remain readable by scrolling before moving to the next row. */
  char foot[48];
  if(scroll_limit)snprintf(foot,sizeof(foot),"UP/DOWN scroll | BACK");
  else if(app.screen==KB_SCREEN_ALL_POINTS)snprintf(foot,sizeof(foot),"%d/%d | hold: info",app.selected+1,count);
  else snprintf(foot,sizeof(foot),"%d / %d   BACK",count?app.selected+1:0,count);
  footer(c,foot);
}
static bool trip_at(int index,kb_trip_t *out) {
  kb_query_t q=app_query();
  if(app.screen==KB_SCREEN_ALL_BOARD) {
    uint32_t metres[KB_ALL_MAX_POINTS];for(unsigned i=0;i<app.all_prefs.count;i++)metres[i]=app_all_distance(app.all_prefs.ids[i]);
    return kb_upcoming_merged_at(&q,app.all_prefs.ids,metres,app.all_prefs.count,index,out,NULL)==KB_QUERY_FOUND;
  }
  return(app.route_filter?kb_upcoming_route_at(&q,app.route_operator,app.route_number,index,out,NULL):kb_upcoming_at(&q,index,out,NULL))==KB_QUERY_FOUND;
}
static kb_query_result_t next_trip(const kb_query_t *query,const kb_trip_t *after,kb_trip_t *out) {
  kb_trip_t boundary;
  if(after&&app.board_removed&&kb_trip_same_identity(after,&app.board_focus)) {
    /* Service epochs are whole minutes. A one-second boundary includes every
     * surviving equal-time row while retaining the real query calendar/window. */
    boundary=*after;boundary.departure_utc--;after=&boundary;
  }
  if(app.screen==KB_SCREEN_ALL_BOARD) {
    uint32_t metres[KB_ALL_MAX_POINTS];for(unsigned i=0;i<app.all_prefs.count;i++)metres[i]=app_all_distance(app.all_prefs.ids[i]);
    return kb_query_merged_next(query,app.all_prefs.ids,metres,app.all_prefs.count,after,out,NULL);
  }
  return app.route_filter?kb_query_route_next(query,app.route_operator,app.route_number,after,out,NULL):kb_query_next(query,after,out,NULL);
}
static void board_filter_label(char *label,size_t n) {
  if(app.screen==KB_SCREEN_ALL_BOARD) {
    char reference[64];all_label(reference,sizeof(reference));snprintf(label,n,"Scheduled | JST\n%s",reference);return;
  }
  if(!app.route_filter) {
    snprintf(label,n,"Scheduled | JST");
    return;
  }
  const kb_dataset_t *d=app_dataset();kb_operator_t o;
  if(d&&kb_operator_get(d,app.route_operator,&o))snprintf(label,n,"Scheduled | JST\n%.24s %.64s",o.short_name,app.route_number);
  else snprintf(label,n,"Scheduled | JST\nBus %.84s",app.route_number);
}
static void board(GContext *c) {
  bool merged=app.screen==KB_SCREEN_ALL_BOARD;
  if(merged)ui_refresh();
  kb_query_state_t summary={0};kb_trip_t first;int summary_result=0;
  if(merged)summary_result=all_summary(&first,&summary);
  char filter_label[140];board_filter_label(filter_label,sizeof(filter_label));
  const char *title=merged?"All departures":"Departures";
  int top=heading(c,title,filter_label);
  int bottom=footer_top()-2,y=top;
  bool tools=app.selected==0,pinned=app.board_expired||app.board_removed;
  if(tools) {
    const char *tools_title=merged?"Choose points":"Stops & tools";
    int h=height_font(tools_title,182,bold_font(body_size()))+7;
    graphics_context_set_fill_color(c,colors.navigation);
    graphics_fill_rect(c,GRect(4,y,192,h-2),2,GCornersAll);
    strong(c,tools_title,9,y,182,h,body_size(),colors.badge_text);y+=h;
    app.scroll=0;scroll_limit=0;
  }
  /* Keep the selected identity first, rather than losing it below wrapped rows. */
  int base=app.selected>0?app.selected-1:0;
  kb_trip_t previous=app.board_focus;
  int32_t previous_day=kb_jst_day(time(NULL));
  bool any=false;
  for(unsigned i=0;i<5&&y<bottom;i++) {
    kb_trip_t t;
    int idx=base+(int)i;
    if(pinned) {
      idx=(int)i;
      if(!i)t=app.board_focus;
      else {
        kb_query_t query=app_query();
        if(next_trip(&query,&previous,&t)!=KB_QUERY_FOUND)break;
        previous=t;
      }
    }
    else if(!i&&app.selected>0&&app.board_has_focus)t=app.board_focus;
    else if(!trip_at(idx,&t))break;
    kb_query_t query=app_query();
    const kb_dataset_t *d=kb_trip_dataset(&query,&t);
    kb_pattern_t pattern;
    bool available=d&&kb_pattern_get(d,t.pattern_id,&pattern);
    choice_t ch={0};char tm[12],cd[24];
    time_string(t.departure_utc,tm,sizeof(tm));countdown(&t,cd,sizeof(cd));
    if(available&&merged) {
      kb_boarding_point_t point;kb_operator_t op;
      available=kb_boarding_point_get(d,t.boarding_point_id,&point)&&kb_operator_get(d,point.operator_id,&op);
      if(available) {
        snprintf(ch.title,sizeof(ch.title),"%s | %s\n%.24s %.64s",tm,cd,op.short_name,pattern.route);
        uint32_t metres=app_all_distance(t.boarding_point_id);char distance[48];
        if(metres==UINT32_MAX)snprintf(distance,sizeof(distance),"Distance unknown");
        else snprintf(distance,sizeof(distance),"Approx. %lum",(unsigned long)metres);
        snprintf(ch.sub,sizeof(ch.sub),"%s\n%s\nTo %s\n%s",point.short_name,point.direction,pattern.destination,distance);
      }
    }
    else if(available)snprintf(ch.title,sizeof(ch.title),"%s  %s  %s",tm,pattern.route,cd);
    else snprintf(ch.title,sizeof(ch.title),"%s  Trip removed",tm);
    if(!available) {snprintf(ch.title,sizeof(ch.title),"%s  Trip removed",tm);snprintf(ch.sub,sizeof(ch.sub),"Timetable changed");}
    else if(!merged)snprintf(ch.sub,sizeof(ch.sub),"%s",pattern.destination);
    char date[20]="";
    int32_t day=kb_jst_day(t.departure_utc);
    if(day!=previous_day)date_string(day,date,sizeof(date));
    int date_h=height(date,182,meta_size());
    int title_h=height_font(ch.title,182,bold_font(body_size()));
    int row_h=title_h+height(ch.sub,182,secondary_size())+7;
    bool selected=app.selected==idx+1;
    if(selected) {
      clamp_scroll(date_h+row_h,bottom-top);
      y-=app.scroll;
    }
    else if(y+date_h+row_h>bottom)break;
    if(date_h) {
      text(c,date,9,y,182,date_h,meta_size(),colors.navigation);y+=date_h;
      previous_day=day;
    }
    graphics_context_set_fill_color(c,selected?colors.departure:colors.background);
    graphics_fill_rect(c,GRect(4,y,192,row_h-2),2,GCornersAll);
    GColor color=selected?colors.badge_text:colors.foreground;
    strong(c,ch.title,9,y,182,title_h,body_size(),color);
    text(c,ch.sub,9,y+title_h+1,182,row_h-title_h-4,secondary_size(),color);
    y+=row_h;any=true;
  }
  if(!any&&!app.board_has_focus) {
    kb_query_t query=app_query();kb_trip_t t;kb_query_state_t state;
    int result=merged?summary_result:app.route_filter?kb_upcoming_route_at(&query,app.route_operator,app.route_number,0,&t,&state):kb_upcoming_at(&query,0,&t,&state);
    const char *message=merged&&!app.all_prefs.count?"No points selected.":result<0?"Schedule unconfirmed":"No upcoming service";
    text(c,message,8,y+5,184,30000,body_size(),colors.warning);
  }
  graphics_context_set_fill_color(c,colors.background);
  graphics_fill_rect(c,GRect(0,0,200,top),0,GCornerNone);
  heading(c,title,filter_label);
  bool override=app.override.day_type!=KB_DAY_UNKNOWN&&app.override.jst_day==kb_jst_day(time(NULL));
  footer(c,app.board_removed?"Removed | DOWN next":app.board_expired?"Earlier | DOWN next":merged?(override?(summary.coverage_limited?"Override/partial | info":"Override | hold: info"):summary.coverage_limited?"Partial | hold: info":"SELECT details | hold info"):tools?"SELECT opens stops":app.changed?"Hold SELECT: refresh":"SELECT: details");
}
static void details(GContext *c) {
  kb_query_t q=app_query();
  const kb_dataset_t *d=kb_trip_dataset(&q,&app.detail);
  kb_boarding_point_t p;
  kb_pattern_t pattern;
  kb_operator_t o;
  if(!d||!kb_boarding_point_get(d,app.detail.boarding_point_id,&p)||!kb_pattern_get(d,app.detail.pattern_id,&pattern)) {
    int top=heading(c,"Trip unavailable","Timetable changed");
    document(c,"Return to the departure board.",top+4,"BACK: board");
    return;
  }
  kb_operator_get(d,p.operator_id,&o);
  char *s=document_buffer;
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
  int context=app.detail_origin==KB_SCREEN_ALL_BOARD?KB_CONTEXT_NEARBY:app.trip_context;
  if(context==KB_CONTEXT_SAVED_ORIGIN&&minutes>=0) {
    int64_t leave;
    if(kb_leave_by(&app.detail,KB_CONTEXT_SAVED_ORIGIN,minutes,app.prefs.bytes[4],&leave)) {
      char lt[16];
      time_string(leave,lt,sizeof(lt));
      snprintf(walk,sizeof(walk),"\nSaved origin\nWalk %d min + buffer %u\nLeave by %s JST%s\n",minutes,app.prefs.bytes[4],lt,time(NULL)>=leave?" - Leave now":"");
    }
  }
  else snprintf(walk,sizeof(walk),"\nContext: %s\n%s\n",context==KB_CONTEXT_AT_STOP?"At stop":context==KB_CONTEXT_SAVED_ORIGIN?"Saved origin":"General / Nearby",context==KB_CONTEXT_SAVED_ORIGIN?"Walking time is unset":"No walking allowance applied");
  if(app.detail_origin==KB_SCREEN_ALL_BOARD) {
    uint32_t metres=app_all_distance(app.detail.boarding_point_id);size_t used=strlen(walk);
    if(metres==UINT32_MAX)snprintf(walk+used,sizeof(walk)-used,"Distance unknown\n");
    else snprintf(walk+used,sizeof(walk)-used,"Approx. %lum\n",(unsigned long)metres);
  }
  date_string(o.source_verified_on,source,sizeof(source));
  snprintf(s,sizeof(document_buffer),"%s\n%s\n%s\n\nRoute %s\nTo %s\n%s  %s JST%s\n%s%s | Scheduled\n%s\n%s\n%s\nSource verified %s\nData v%lu\n\nSELECT: Japanese name",p.name,p.direction,o.name,pattern.route,pattern.destination,date,tm,origin,day_name(app.detail.day_type),app.detail.overridden?" (Override)":"",walk,p.guidance,pattern.route_transitions,source,(unsigned long)d->release_version);
  document(c,s,4,"UP/DOWN | BACK");
}
static void status(GContext *c) {
  char *s=document_buffer;
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
  snprintf(s,sizeof(document_buffer),"Data status\nSELECT: Check updates\n\n%s\n\nActive dataset: v%lu\nSource verified: %s\nReview due: %s\n%s\nFeed success:\n%s\nAutomatic attempt:\n%s\n\nCalendar coverage\n%s to %s\nPending v%lu: %s\n\n%s\nMissing saved IDs: %u\n\nScheduled departures.\nFeed checks do not verify operator freshness.\n\nUpdates: %s\nPhone: %s\n%s",states[st],(unsigned long)(d?d->release_version:0),vf,rv,d&&d->review_by!=KB_DATE_UNKNOWN&&kb_jst_day(time(NULL))>d->review_by?"Needs timetable review":"",feed,attempt,from,until,(unsigned long)pending,future,kb_store_has_staging(&app.store,kb_jst_day(time(NULL)))?"Safe staging available":app.store.capacity_ok?"Storage full: pending data kept":"Insufficient firmware storage",missing,app.prefs.bytes[1]&KB_PREF_AUTO?"Daily on launch":"Manual only",app.phone_ready?"Ready":"Not connected",app.notice);
  document(c,s,4,"SELECT: check");
}
static void japanese(GContext *c) {
  const kb_dataset_t *d=app_dataset();
  kb_boarding_point_t p;
  kb_stop_group_t group;
  int top=heading(c,"Stop name",NULL);
  if(d&&kb_boarding_point_get(d,app.detail.boarding_point_id,&p)&&kb_stop_group_get(d,p.group_id,&group)) {
    int ja_h=height_font(group.name_ja,184,app.japanese);
    int en_h=height(group.name,184,body_size());
    clamp_scroll(ja_h+en_h+12,footer_top()-top-2);
    text_font(c,group.name_ja,8,top+3-app.scroll,184,ja_h,app.japanese,colors.foreground);
    text(c,group.name,8,top+ja_h+10-app.scroll,184,en_h,body_size(),colors.navigation);
  }
  graphics_context_set_fill_color(c,colors.background);
  graphics_fill_rect(c,GRect(0,0,200,top),0,GCornerNone);
  heading(c,"Stop name",NULL);
  footer(c,"UP/DOWN | BACK");
}
static void draw(Layer *layer,GContext *c) {
  (void)layer;
  colors=palette(kb_pref_theme(&app.prefs));
  scroll_limit=0;
  graphics_context_set_fill_color(c,colors.background);
  graphics_fill_rect(c,GRect(0,0,200,228),0,GCornerNone);
  if(app.screen==KB_SCREEN_HOME)home(c);
  else if(app.screen==KB_SCREEN_BOARD||app.screen==KB_SCREEN_ALL_BOARD)board(c);
  else if(app.screen==KB_SCREEN_DETAILS)details(c);
  else if(app.screen==KB_SCREEN_STATUS)status(c);
  else if(app.screen==KB_SCREEN_JAPANESE)japanese(c);
  else if(app.screen==KB_SCREEN_ALL_INFO)all_info(c);
  else list(c);
  APP_LOG(APP_LOG_LEVEL_DEBUG,"UI screen%d heap%lu",app.screen,(unsigned long)heap_bytes_free());
  APP_LOG(APP_LOG_LEVEL_DEBUG,"UI selection%d scroll%d limit%d",app.selected,app.scroll,scroll_limit);
  if(app.screen>=KB_SCREEN_ALL_REFERENCE&&app.screen<=KB_SCREEN_ALL_INFO) {
    APP_LOG(APP_LOG_LEVEL_DEBUG,"All view reference%u status%u request%lu waiting%d selected%u distances%u",app.all_prefs.reference,all_status_now(),(unsigned long)app.all_request,app.all_waiting,app.all_prefs.count,app.all_nearby_count);
    if(app.screen==KB_SCREEN_ALL_POINTS&&app.selected>=4) {
      choice_t ch;choice(app.selected,&ch);APP_LOG(APP_LOG_LEVEL_DEBUG,"All choice point%u selected%d",ch.id,all_selected(ch.id));
    }
    if(app.screen==KB_SCREEN_ALL_BOARD&&app.board_has_focus)APP_LOG(APP_LOG_LEVEL_DEBUG,"All trip day%ld minute%u point%u pattern%u service%u version%lu",(long)app.board_focus.service_day,app.board_focus.minute,app.board_focus.boarding_point_id,app.board_focus.pattern_id,app.board_focus.service_id,(unsigned long)app.board_focus.release_version);
  }
}
void ui_open(int screen) {
  app.screen=screen;
  app.selected=0;
  app.scroll=0;
  scroll_limit=0;
  app.notice[0]=0;
  if(screen==KB_SCREEN_HOME||screen==KB_SCREEN_FAVOURITES||screen==KB_SCREEN_GROUPS||screen==KB_SCREEN_NEARBY||screen==KB_SCREEN_PICKER||screen==KB_SCREEN_ROUTES) {app.route_filter=false;app.all_session=false;}
  if(screen>=KB_SCREEN_ALL_REFERENCE&&screen<=KB_SCREEN_ALL_INFO) {app.all_session=true;app.route_filter=false;}
  if(screen==KB_SCREEN_ALL_POINTS)app.all_point_focus=0;
  if(screen==KB_SCREEN_ALL_REFERENCE)app.selected=app.all_prefs.reference;
  if(screen==KB_SCREEN_TEXT_SIZE)app.selected=(int)kb_pref_text_size(&app.prefs);
  else if(screen==KB_SCREEN_THEME)app.selected=(int)kb_pref_theme(&app.prefs);
  if(screen==KB_SCREEN_BOARD||screen==KB_SCREEN_ALL_BOARD) {
    app.board_has_focus=false;
    app.board_expired=false;
    app.board_removed=false;
    app.selected=1;
    if(trip_at(0,&app.board_focus))app.board_has_focus=true;
    else app.selected=0;
  }
  ui_apply_appearance();
  app_redraw();
}
void ui_refresh(void) {
  if(app.screen==KB_SCREEN_ALL_POINTS) {
    if(app.selected<4)app.all_point_focus=0;
    else {
      ui_remember_all_point();uint16_t ids[KB_MAX_POINTS*2+1];unsigned count=all_point_ids(ids);
      for(unsigned i=0;i<count;i++)if(ids[i]==app.all_point_focus) {app.selected=(int)i+4;break;}
    }
  }
  if(app.screen!=KB_SCREEN_BOARD&&app.screen!=KB_SCREEN_ALL_BOARD) {
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
    if(next_trip(&q,has_previous?&previous:NULL,&t)!=KB_QUERY_FOUND)break;
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
static bool scroll_screen(void) {
  return app.screen==KB_SCREEN_DETAILS||app.screen==KB_SCREEN_STATUS||app.screen==KB_SCREEN_JAPANESE||app.screen==KB_SCREEN_ALL_INFO||
    (app.screen==KB_SCREEN_NEARBY&&!(app.prefs.bytes[1]&KB_PREF_LOCATION));
}
static void scroll_by(int amount) {
  app.scroll+=amount;
  if(app.scroll<0)app.scroll=0;
  if(app.scroll>scroll_limit)app.scroll=scroll_limit;
}
static void up(ClickRecognizerRef r,void *ctx) {
  (void)r;
  (void)ctx;
  if(app.screen==KB_SCREEN_ALL_BOARD||app.screen==KB_SCREEN_ALL_POINTS)ui_refresh();
  if(app.screen==KB_SCREEN_HOME) {
    unsigned n=app.prefs.bytes[5];
    if(n) {
      unsigned i=0;
      while(i<n&&kb_pref_favourite(&app.prefs,i)!=app.point)i++;
      app.point=kb_pref_favourite(&app.prefs,(i+n-1)%n);
    }
  }
  else if(scroll_screen()||app.scroll>0) {
    scroll_by(-(int)body_size()*2);
  }
  else if(app.screen==KB_SCREEN_BOARD||app.screen==KB_SCREEN_ALL_BOARD) {
    if(app.selected>0) {
      app.selected--;
      app.board_has_focus=app.selected>0&&trip_at(app.selected-1,&app.board_focus);
      app.board_expired=false;
      app.board_removed=false;
      app.scroll=0;
    }
  }
  else if(app.selected>0) {
    app.selected--;app.scroll=0;app.all_point_focus=0;
    ui_remember_all_point();
  }
  app_redraw();
}
static void down(ClickRecognizerRef r,void *ctx) {
  (void)r;
  (void)ctx;
  if(app.screen==KB_SCREEN_ALL_BOARD||app.screen==KB_SCREEN_ALL_POINTS)ui_refresh();
  if(app.screen==KB_SCREEN_HOME) {
    unsigned n=app.prefs.bytes[5];
    if(n) {
      unsigned i=0;
      while(i<n&&kb_pref_favourite(&app.prefs,i)!=app.point)i++;
      app.point=kb_pref_favourite(&app.prefs,(i+1)%n);
    }
  }
  else if(scroll_screen()||(scroll_limit&&app.scroll<scroll_limit)) {
    scroll_by((int)body_size()*2);
  }
  else if(app.screen==KB_SCREEN_BOARD||app.screen==KB_SCREEN_ALL_BOARD) {
    kb_trip_t t;
    if((app.board_expired||app.board_removed)&&app.board_has_focus) {
      kb_query_t q=app_query();
      if(next_trip(&q,&app.board_focus,&t)==KB_QUERY_FOUND) {
        app.board_focus=t;
        app.board_expired=false;
        app.board_removed=false;
        app.selected=1;
        app.scroll=0;
        ui_refresh();
      }
    }
    else if(trip_at(app.selected,&t)) {
      app.selected++;
      app.board_focus=t;
      app.board_has_focus=true;
      app.scroll=0;
    }
  }
  else if(app.selected+1<choices()) {
    app.selected++;app.scroll=0;app.all_point_focus=0;
    ui_remember_all_point();
  }
  app_redraw();
}
static void all_use_favourites(bool manual) {
  kb_all_preferences_t p=app.all_prefs;
  if(manual)p.reference=KB_ALL_REFERENCE_MANUAL;
  memset(p.ids,0,sizeof(p.ids));p.count=app.prefs.bytes[5];
  for(unsigned i=0;i<p.count;i++)p.ids[i]=kb_pref_favourite(&app.prefs,i);
  if(app_save_all_preferences(&p))ui_open(KB_SCREEN_ALL_POINTS);
}
static void select(ClickRecognizerRef r,void *ctx) {
  (void)r;
  (void)ctx;
  app_dismiss_hint();
  if(app.screen==KB_SCREEN_HOME)ui_open(KB_SCREEN_BOARD);
  else if(app.screen==KB_SCREEN_BOARD||app.screen==KB_SCREEN_ALL_BOARD) {
    if(!app.selected)ui_open(app.screen==KB_SCREEN_ALL_BOARD?KB_SCREEN_ALL_POINTS:KB_SCREEN_PICKER);
    else if(app.board_has_focus) {
      app.detail=app.board_focus;
      app.return_screen=app.selected;
      app.detail_origin=app.screen;
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
      KB_SCREEN_FAVOURITES,KB_SCREEN_NEARBY,KB_SCREEN_GROUPS,KB_SCREEN_ROUTES,KB_SCREEN_ALL_REFERENCE
    };
    int screen=a[app.selected];
    ui_open(screen);
    if(screen==KB_SCREEN_NEARBY)app_request_location();
  }
  else if(app.screen==KB_SCREEN_ALL_REFERENCE) {
    if(app.selected==3)all_use_favourites(true);
    else {
      kb_all_preferences_t p=app.all_prefs;p.reference=(uint8_t)app.selected;
      if(app_save_all_preferences(&p)) {
        ui_open(KB_SCREEN_ALL_POINTS);
        if(p.reference!=KB_ALL_REFERENCE_MANUAL)app_request_all_location();
      }
    }
  }
  else if(app.screen==KB_SCREEN_ALL_POINTS) {
    ui_refresh();
    if(app.selected==0)ui_open(KB_SCREEN_ALL_BOARD);
    else if(app.selected==1)app_request_all_location();
    else if(app.selected==2)all_use_favourites(false);
    else if(app.selected==3) {
      kb_all_preferences_t p=app.all_prefs;p.count=0;memset(p.ids,0,sizeof(p.ids));
      app_save_all_preferences(&p);
    }
    else {
      choice_t ch;choice(app.selected,&ch);kb_all_preferences_t p=app.all_prefs;
      unsigned index=0;while(index<p.count&&p.ids[index]!=ch.id)index++;
      if(index<p.count) {
        memmove(p.ids+index,p.ids+index+1,(p.count-index-1)*sizeof(p.ids[0]));
        p.ids[--p.count]=0;app_save_all_preferences(&p);
      }
      else if(!app_point_exists(NULL,ch.id))snprintf(app.notice,sizeof(app.notice),"Boarding point unavailable");
      else if(p.count==KB_ALL_MAX_POINTS)snprintf(app.notice,sizeof(app.notice),"Selection is full");
      else {p.ids[p.count++]=ch.id;app_save_all_preferences(&p);}
    }
  }
  else if(app.screen==KB_SCREEN_GROUPS) {
    if(app.selected<0||app.selected>=choices())return;
    choice_t ch;
    choice(app.selected,&ch);
    if(!ch.id)return;
    app.group=ch.id;
    ui_open(KB_SCREEN_POINTS);
  }
  else if(app.screen==KB_SCREEN_ROUTES) {
    const kb_dataset_t *d=app_dataset();kb_route_t route;
    if(app.selected<0||!d||!kb_route_at(d,(unsigned)app.selected,&route))return;
    app.route_operator=route.operator_id;
    snprintf(app.route_number,sizeof(app.route_number),"%s",route.number);
    app.route_filter=true;
    ui_open(KB_SCREEN_ROUTE_POINTS);
  }
  else if(app.screen==KB_SCREEN_ROUTE_POINTS) {
    if(app.selected<0||app.selected>=choices())return;
    choice_t ch;choice(app.selected,&ch);
    if(app_point_exists(NULL,ch.id)) {
      app.point=ch.id;ui_open(KB_SCREEN_BOARD);
    }
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
    if(app.selected==0)ui_open(KB_SCREEN_TEXT_SIZE);
    else if(app.selected==1)ui_open(KB_SCREEN_THEME);
    else if(app.selected==2)ui_open(KB_SCREEN_OVERRIDE);
    else if(app.selected==3||app.selected==4) {
      uint8_t mask=app.selected==3?KB_PREF_REDUCED_MOTION:KB_PREF_AUTO;
      kb_preferences_t p=app.prefs;
      p.bytes[1]^=mask;
      app_save_preferences(&p);
      app_send_state();
    }
    else if(app.selected==5)snprintf(app.notice,sizeof(app.notice),"Use companion app > KasugaBus");
    else ui_open(app.selected==6?KB_SCREEN_RESET:KB_SCREEN_RESTORE);
  }
  else if(app.screen==KB_SCREEN_TEXT_SIZE||app.screen==KB_SCREEN_THEME) {
    bool size_picker=app.screen==KB_SCREEN_TEXT_SIZE;
    kb_preferences_t p=app.prefs;
    unsigned size=size_picker?(unsigned)app.selected:kb_pref_text_size(&p);
    unsigned theme=size_picker?kb_pref_theme(&p):(unsigned)app.selected;
    bool saved=kb_pref_set_appearance(&p,size,theme)&&app_save_preferences(&p);
    ui_open(KB_SCREEN_SETTINGS);app.selected=size_picker?0:1;
    snprintf(app.notice,sizeof(app.notice),"%s",saved?"Appearance saved":"Settings not saved");
    app_send_state();
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
    case KB_SCREEN_DETAILS:app.screen=app.detail_origin==KB_SCREEN_ALL_BOARD?KB_SCREEN_ALL_BOARD:KB_SCREEN_BOARD;
    app.selected=app.return_screen;
    app.board_focus=app.detail;
    app.board_has_focus=true;
    ui_refresh();
    app_redraw();
    break;
    case KB_SCREEN_BOARD:ui_open(app.route_filter?KB_SCREEN_ROUTE_POINTS:KB_SCREEN_HOME);
    break;
    case KB_SCREEN_ALL_BOARD:ui_open(KB_SCREEN_ALL_POINTS);
    break;
    case KB_SCREEN_ALL_POINTS:ui_open(KB_SCREEN_ALL_REFERENCE);
    break;
    case KB_SCREEN_ALL_REFERENCE:ui_open(KB_SCREEN_PICKER);app.selected=4;
    break;
    case KB_SCREEN_ALL_INFO:
    app.screen=app.all_info_return;app.selected=app.all_info_selected;app.scroll=0;
    ui_apply_appearance();ui_refresh();app_redraw();
    break;
    case KB_SCREEN_JAPANESE:ui_open(KB_SCREEN_DETAILS);
    break;
    case KB_SCREEN_POINTS:ui_open(KB_SCREEN_GROUPS);
    break;
    case KB_SCREEN_ROUTE_POINTS:ui_open(KB_SCREEN_ROUTES);
    break;
    case KB_SCREEN_ROUTES:ui_open(KB_SCREEN_PICKER);
    break;
    case KB_SCREEN_GROUPS:case KB_SCREEN_FAVOURITES:case KB_SCREEN_NEARBY:ui_open(KB_SCREEN_PICKER);
    break;
    case KB_SCREEN_RESET:case KB_SCREEN_RESTORE:case KB_SCREEN_OVERRIDE:ui_open(KB_SCREEN_SETTINGS);
    break;
    case KB_SCREEN_TEXT_SIZE:ui_open(KB_SCREEN_SETTINGS);app.selected=0;
    break;
    case KB_SCREEN_THEME:ui_open(KB_SCREEN_SETTINGS);app.selected=1;
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
  else if(app.screen==KB_SCREEN_ALL_POINTS||app.screen==KB_SCREEN_ALL_BOARD) {
    app.all_info_return=app.screen;app.all_info_selected=app.selected;
    ui_open(KB_SCREEN_ALL_INFO);
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
  ui_apply_appearance();
  window_set_click_config_provider(app.window,clicks);
  app.layer=layer_create(GRect(0,0,200,228));
  layer_set_update_proc(app.layer,draw);
  layer_add_child(window_get_root_layer(app.window),app.layer);
  window_stack_push(app.window,false);
}
