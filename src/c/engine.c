#include "engine.h"
#include <string.h>

enum { T_OPERATOR, T_GROUP, T_POINT, T_PATTERN, T_SERVICE, T_HOLIDAY,
  T_EXCEPTION, T_DEPARTURE, T_SOURCE, T_CALL };
static const uint8_t strides[KB_TABLE_COUNT] = {28,8,24,16,12,4,6,5,16,2};
static uint16_t u16(const uint8_t *p) { return (uint16_t)(p[0] | (uint16_t)p[1]<<8); }
static uint32_t u32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24; }
static int32_t i32(const uint8_t *p) { uint32_t n=u32(p); return n<=INT32_MAX ? (int32_t)n : (int32_t)(-1-(int64_t)(UINT32_MAX-n)); }
static const uint8_t *row(const kb_dataset_t *d,unsigned table,size_t n) { return d->bytes+d->offsets[table]+n*strides[table]; }
static const uint8_t *find_id(const kb_dataset_t *d,unsigned table,uint8_t id) {
  size_t lo=0,hi=d->counts[table];
  while(lo<hi) { size_t m=lo+(hi-lo)/2; const uint8_t *p=row(d,table,m);
    if(p[0]<id) lo=m+1; else if(p[0]>id) hi=m; else return p; }
  return NULL;
}
static const char *str(const kb_dataset_t *d,uint16_t off) { return (const char *)(d->bytes+d->strings_offset+off); }
static int64_t floor_div(int64_t n,int64_t divisor) { int64_t q=n/divisor,r=n%divisor; return q-(r<0); }

uint32_t kb_crc32(const uint8_t *p,size_t n) {
  static const uint32_t nibble[16] = {
    UINT32_C(0x00000000), UINT32_C(0x1db71064), UINT32_C(0x3b6e20c8), UINT32_C(0x26d930ac),
    UINT32_C(0x76dc4190), UINT32_C(0x6b6b51f4), UINT32_C(0x4db26158), UINT32_C(0x5005713c),
    UINT32_C(0xedb88320), UINT32_C(0xf00f9344), UINT32_C(0xd6d6a3e8), UINT32_C(0xcb61b38c),
    UINT32_C(0x9b64c2b0), UINT32_C(0x86d3d2d4), UINT32_C(0xa00ae278), UINT32_C(0xbdbdf21c)
  };
  uint32_t crc=UINT32_MAX;
  while(n--) {
    crc^=*p++;
    crc=(crc>>4)^nibble[crc&15];
    crc=(crc>>4)^nibble[crc&15];
  }
  return ~crc;
}
int32_t kb_jst_day(int64_t epoch) { return (int32_t)floor_div(epoch+32400,86400); }
int64_t kb_service_epoch(int32_t day,uint16_t minute) { return (int64_t)day*86400+(int64_t)minute*60-32400; }
bool kb_date_from_ymd(int y,unsigned m,unsigned dom,int32_t *out) {
  static const unsigned md[]={31,28,31,30,31,30,31,31,30,31,30,31};
  int adjusted,era; unsigned yo,doy,doe,limit;
  if(!out || y<1900 || y>2200 || m<1 || m>12) return false;
  limit=md[m-1]+(m==2 && y%4==0 && (y%100!=0 || y%400==0));
  if(dom<1 || dom>limit) return false;
  adjusted=y-(m<=2); era=adjusted/400; yo=(unsigned)(adjusted-era*400);
  doy=(153*(m+(m>2?(unsigned)-3:9))+2)/5+dom-1;
  doe=yo*365+yo/4-yo/100+doy;
  *out=(int32_t)(era*146097+(int)doe-719468); return true;
}
void kb_date_to_ymd(int32_t day,int *y,unsigned *m,unsigned *dom) {
  int64_t z=(int64_t)day+719468,era=floor_div(z,146097);
  unsigned doe=(unsigned)(z-era*146097),yo=(doe-doe/1460+doe/36524-doe/146096)/365;
  int year=(int)(yo+era*400); unsigned doy=doe-(365*yo+yo/4-yo/100),mp=(5*doy+2)/153;
  unsigned month=mp+(mp<10?3:(unsigned)-9);
  if(dom) *dom=doy-(153*mp+2)/5+1;
  if(m) *m=month;
  if(y) *y=year+(month<=2);
}
unsigned kb_weekday(int32_t day) { int n=(day%7+4)%7; return (unsigned)(n<0?n+7:n); }
static bool valid_date(int32_t day,bool optional) { int y; if(optional && day==KB_DATE_UNKNOWN) return true; kb_date_to_ymd(day,&y,NULL,NULL); return y>=1900 && y<=2200; }
static bool interval(int32_t a,int32_t b) { return valid_date(a,false)&&valid_date(b,false)&&a<=b; }
static bool day_valid(uint8_t day) { return day<=3 || day==255; }

/* Reject overlong encodings, surrogate code points, controls other than normal
 * spaces/newlines, and strings too large for the runtime metadata contract. */
static bool valid_pool(const uint8_t *p,size_t n) {
  size_t i=0,len=0;
  if(!n || p[0]!=0 || p[n-1]!=0) return false;
  while(i<n) {
    uint8_t c=p[i]; size_t count=1; uint32_t cp;
    if(c==0) { len=0; i++; continue; }
    if(c<0x80) { if(c<0x20 && c!='\n' && c!='\t') return false; cp=c; }
    else if(c>=0xc2&&c<=0xdf) { count=2; cp=c&31; }
    else if(c>=0xe0&&c<=0xef) { count=3; cp=c&15; }
    else if(c>=0xf0&&c<=0xf4) { count=4; cp=c&7; }
    else return false;
    if(count>n-i) return false;
    for(size_t j=1;j<count;j++) { if((p[i+j]&0xc0)!=0x80) return false; cp=(cp<<6)|(p[i+j]&63); }
    if((count==2&&cp<0x80)||(count==3&&cp<0x800)||(count==4&&cp<0x10000)||cp>0x10ffff||(cp>=0xd800&&cp<=0xdfff)) return false;
    len+=count; if(len>1023) return false; i+=count;
  }
  return true;
}
static bool string_ref(const kb_dataset_t *d,uint16_t off,bool required) {
  const uint8_t *p=d->bytes+d->strings_offset;
  return off<d->strings_length && (off==0||p[off-1]==0) && (!required||p[off]!=0);
}
static bool refs(const kb_dataset_t *d,const uint8_t *p,unsigned first,unsigned count,unsigned required_bits) {
  for(unsigned i=0;i<count;i++) if(!string_ref(d,u16(p+first+2*i),(required_bits&(1u<<i))!=0)) return false;
  return true;
}
static int departure_compare(const uint8_t *a,const uint8_t *b) {
  if(a[2]!=b[2]) return a[2]<b[2]?-1:1;
  if(u16(a)!=u16(b)) return u16(a)<u16(b)?-1:1;
  if(a[3]!=b[3]) return a[3]<b[3]?-1:1;
  if(a[4]!=b[4]) return a[4]<b[4]?-1:1;
  return 0;
}
kb_error_t kb_dataset_open(kb_dataset_t *out,const uint8_t *b,size_t n) {
  kb_dataset_t d; uint32_t expected=KB_HEADER_SIZE; uint16_t maximum=0;
  if(!out) return KB_ERR_ARGUMENT;
  memset(out,0,sizeof(*out)); memset(&d,0,sizeof(d));
  if(!b) return KB_ERR_ARGUMENT;
  if(n<KB_HEADER_SIZE || n>KB_MAX_DATASET_BYTES) return KB_ERR_SIZE;
  if(memcmp(b,"KBT1",4)) return KB_ERR_MAGIC;
  if(u16(b+4)!=KB_SCHEMA_VERSION) return KB_ERR_SCHEMA;
  if(u16(b+6)!=KB_HEADER_SIZE||u32(b+8)!=n||u16(b+62)!=KB_TABLE_COUNT||u16(b+50)) return KB_ERR_LAYOUT;
  if(kb_crc32(b+16,n-16)!=u32(b+12)) return KB_ERR_CHECKSUM;
  d.bytes=b; d.size=n; d.release_version=u32(b+16); d.minimum_app_version=u32(b+20);
  d.valid_from=i32(b+24); d.valid_until=i32(b+28); d.calendar_from=i32(b+32); d.calendar_until=i32(b+36);
  d.source_verified_on=i32(b+40); d.review_by=i32(b+44); d.coverage_string=u16(b+48);
  d.strings_offset=u32(b+52); d.strings_length=u32(b+56); d.max_minute=u16(b+60); d.effective_from=i32(b+124);
  if(!d.release_version||!d.minimum_app_version||!interval(d.valid_from,d.valid_until)||!interval(d.calendar_from,d.calendar_until)||!valid_date(d.source_verified_on,false)||!valid_date(d.review_by,true)||!valid_date(d.effective_from,false)||d.effective_from<d.valid_from||d.effective_from>d.valid_until||(d.review_by!=KB_DATE_UNKNOWN&&d.review_by<d.source_verified_on)||d.max_minute>KB_MAX_MINUTE) return KB_ERR_VALUE;
  for(unsigned t=0;t<KB_TABLE_COUNT;t++) {
    d.offsets[t]=u32(b+64+t*6); d.counts[t]=u16(b+68+t*6);
    if(d.offsets[t]!=expected) return KB_ERR_LAYOUT;
    expected+=(uint32_t)d.counts[t]*strides[t];
    if(expected>n) return KB_ERR_LAYOUT;
    if(t<=T_SERVICE && d.counts[t]>255) return KB_ERR_VALUE;
  }
  if(d.strings_offset!=expected||!d.strings_length||d.strings_length!=n-expected||!valid_pool(b+expected,d.strings_length)||!string_ref(&d,d.coverage_string,true)) return KB_ERR_LAYOUT;
  if(!d.counts[T_OPERATOR]||!d.counts[T_GROUP]||!d.counts[T_POINT]) return KB_ERR_VALUE;
  for(unsigned t=0;t<=T_SERVICE;t++) for(size_t i=0;i<d.counts[t];i++) {
    const uint8_t *p=row(&d,t,i);
    if(!p[0]) return KB_ERR_VALUE;
    if(i&&row(&d,t,i-1)[0]>=p[0]) return row(&d,t,i-1)[0]==p[0]?KB_ERR_DUPLICATE:KB_ERR_SORT;
  }
  for(size_t i=0;i<d.counts[T_OPERATOR];i++) {
    const uint8_t *p=row(&d,T_OPERATOR,i);
    if(!p[1]||(p[1]&~14)||!refs(&d,p,2,3,5)||!interval(i32(p+8),i32(p+12))||i32(p+8)<d.valid_from||i32(p+12)>d.valid_until||!valid_date(i32(p+16),false)||!valid_date(i32(p+20),true)||(i32(p+20)!=KB_DATE_UNKNOWN&&i32(p+20)<i32(p+16))||(uint32_t)u16(p+24)+u16(p+26)>d.counts[T_SOURCE]) return KB_ERR_VALUE;
  }
  for(size_t i=0;i<d.counts[T_GROUP];i++) { const uint8_t *p=row(&d,T_GROUP,i); if(p[1]||!refs(&d,p,2,3,3)) return KB_ERR_VALUE; }
  for(size_t i=0;i<d.counts[T_POINT];i++) {
    const uint8_t *p=row(&d,T_POINT,i); int32_t lat=i32(p+16),lon=i32(p+20);
    if(!find_id(&d,T_GROUP,p[1])||!find_id(&d,T_OPERATOR,p[2])) return KB_ERR_REFERENCE;
    if((p[3]&~1)||!refs(&d,p,4,6,11)) return KB_ERR_VALUE;
    if(p[3]&1) { if(lat < -90000000||lat>90000000||lon < -180000000||lon>180000000) return KB_ERR_VALUE; }
    else if(lat!=KB_COORD_UNKNOWN||lon!=KB_COORD_UNKNOWN) return KB_ERR_VALUE;
  }
  for(size_t i=0;i<d.counts[T_PATTERN];i++) {
    const uint8_t *p=row(&d,T_PATTERN,i); uint16_t first=u16(p+10),count=u16(p+12);
    if(!find_id(&d,T_OPERATOR,p[1])||(p[8]&&!find_id(&d,T_GROUP,p[8]))) return KB_ERR_REFERENCE;
    if(p[9]||!refs(&d,p,2,3,3)||!string_ref(&d,u16(p+14),false)||(uint32_t)first+count>d.counts[T_CALL]) return KB_ERR_VALUE;
    for(size_t c=0;c<count;c++) {
      const uint8_t *call=row(&d,T_CALL,first+c);
      if(call[0]!=p[0]||!find_id(&d,T_GROUP,call[1])) return KB_ERR_REFERENCE;
    }
    if((i==0&&first!=0)||(i&&first!=(uint32_t)u16(row(&d,T_PATTERN,i-1)+10)+u16(row(&d,T_PATTERN,i-1)+12))) return KB_ERR_LAYOUT;
  }
  if(d.counts[T_PATTERN]) { const uint8_t *p=row(&d,T_PATTERN,d.counts[T_PATTERN]-1); if((uint32_t)u16(p+10)+u16(p+12)!=d.counts[T_CALL]) return KB_ERR_LAYOUT; }
  else if(d.counts[T_CALL]) return KB_ERR_REFERENCE;
  for(size_t i=0;i<d.counts[T_SERVICE];i++) {
    const uint8_t *p=row(&d,T_SERVICE,i),*op=find_id(&d,T_OPERATOR,p[1]);
    if(!op) return KB_ERR_REFERENCE;
    if(!p[2]||(p[2]&~14)||(p[2]&~op[1])||p[3]||!interval(i32(p+4),i32(p+8))||i32(p+4)<i32(op+8)||i32(p+8)>i32(op+12)) return KB_ERR_VALUE;
  }
  for(size_t i=0;i<d.counts[T_HOLIDAY];i++) {
    int32_t date=i32(row(&d,T_HOLIDAY,i));
    if(date<d.calendar_from||date>d.calendar_until) return KB_ERR_VALUE;
    if(i&&date<=i32(row(&d,T_HOLIDAY,i-1))) return date==i32(row(&d,T_HOLIDAY,i-1))?KB_ERR_DUPLICATE:KB_ERR_SORT;
  }
  for(size_t i=0;i<d.counts[T_EXCEPTION];i++) {
    const uint8_t *p=row(&d,T_EXCEPTION,i),*op=find_id(&d,T_OPERATOR,p[4]);
    if(!op) return KB_ERR_REFERENCE;
    if(!valid_date(i32(p),false)||!day_valid(p[5])||i32(p)<i32(op+8)||i32(p)>i32(op+12)) return KB_ERR_VALUE;
    if(i) { const uint8_t *prev=row(&d,T_EXCEPTION,i-1); if(i32(prev)>i32(p)||(i32(prev)==i32(p)&&prev[4]>=p[4])) return i32(prev)==i32(p)&&prev[4]==p[4]?KB_ERR_DUPLICATE:KB_ERR_SORT; }
  }
  for(size_t i=0;i<d.counts[T_DEPARTURE];i++) {
    const uint8_t *p=row(&d,T_DEPARTURE,i),*bp=find_id(&d,T_POINT,p[2]),*pat=find_id(&d,T_PATTERN,p[3]),*svc=find_id(&d,T_SERVICE,p[4]);
    if(!bp||!pat||!svc||bp[2]!=pat[1]||bp[2]!=svc[1]) return KB_ERR_REFERENCE;
    if(u16(p)>KB_MAX_MINUTE) return KB_ERR_VALUE;
    if(u16(p)>maximum) maximum=u16(p);
    if(i&&departure_compare(row(&d,T_DEPARTURE,i-1),p)>=0) return departure_compare(row(&d,T_DEPARTURE,i-1),p)==0?KB_ERR_DUPLICATE:KB_ERR_SORT;
    for(size_t prior=i;prior>0;) {
      const uint8_t *prev=row(&d,T_DEPARTURE,--prior);
      if(prev[2]!=p[2]||u16(prev)!=u16(p)||prev[3]!=p[3]) break;
      const uint8_t *other=find_id(&d,T_SERVICE,prev[4]);
      if((other[2]&svc[2])&&i32(other+4)<=i32(svc+8)&&i32(svc+4)<=i32(other+8)) return KB_ERR_DUPLICATE;
    }
  }
  if(maximum!=d.max_minute) return KB_ERR_VALUE;
  for(size_t i=0;i<d.counts[T_SOURCE];i++) { const uint8_t *p=row(&d,T_SOURCE,i); if(!refs(&d,p,0,2,3)||!valid_date(i32(p+4),true)||!valid_date(i32(p+8),false)||!valid_date(i32(p+12),true)||(i32(p+12)!=KB_DATE_UNKNOWN&&i32(p+12)<i32(p+8))) return KB_ERR_VALUE; const char *url=str(&d,u16(p+2)); if(strncmp(url,"https://",8)&&strncmp(url,"http://",7)) return KB_ERR_VALUE; }
  *out=d; return KB_OK;
}

const char *kb_coverage_id(const kb_dataset_t *d) { return d&&d->bytes?str(d,d->coverage_string):NULL; }
size_t kb_operator_count(const kb_dataset_t *d) { return d?d->counts[T_OPERATOR]:0; }
size_t kb_stop_group_count(const kb_dataset_t *d) { return d?d->counts[T_GROUP]:0; }
size_t kb_boarding_point_count(const kb_dataset_t *d) { return d?d->counts[T_POINT]:0; }
size_t kb_source_count(const kb_dataset_t *d) { return d?d->counts[T_SOURCE]:0; }
bool kb_operator_at(const kb_dataset_t *d,size_t index,kb_operator_t *o) {
  if(!d||!d->bytes||!o||index>=d->counts[T_OPERATOR]) return false;
  const uint8_t *p=row(d,T_OPERATOR,index); o->id=p[0]; o->confirmed_day_types=p[1]; o->name=str(d,u16(p+2)); o->name_ja=str(d,u16(p+4)); o->short_name=str(d,u16(p+6)); o->valid_from=i32(p+8); o->valid_until=i32(p+12); o->source_verified_on=i32(p+16); o->review_by=i32(p+20); o->first_source=u16(p+24); o->source_count=u16(p+26); return true;
}
bool kb_stop_group_at(const kb_dataset_t *d,size_t index,kb_stop_group_t *o) {
  if(!d||!d->bytes||!o||index>=d->counts[T_GROUP]) return false;
  const uint8_t *p=row(d,T_GROUP,index); o->id=p[0]; o->short_name=str(d,u16(p+2)); o->name=str(d,u16(p+4)); o->name_ja=str(d,u16(p+6)); return true;
}
bool kb_boarding_point_at(const kb_dataset_t *d,size_t index,kb_boarding_point_t *o) {
  if(!d||!d->bytes||!o||index>=d->counts[T_POINT]) return false;
  const uint8_t *p=row(d,T_POINT,index); o->id=p[0]; o->group_id=p[1]; o->operator_id=p[2]; o->name=str(d,u16(p+4)); o->short_name=str(d,u16(p+6)); o->name_ja=str(d,u16(p+8)); o->direction=str(d,u16(p+10)); o->direction_ja=str(d,u16(p+12)); o->guidance=str(d,u16(p+14)); o->latitude_e6=i32(p+16); o->longitude_e6=i32(p+20); o->has_coordinate=(p[3]&1)!=0; return true;
}
bool kb_source_at(const kb_dataset_t *d,size_t index,kb_source_t *o) {
  if(!d||!d->bytes||!o||index>=d->counts[T_SOURCE]) return false;
  const uint8_t *p=row(d,T_SOURCE,index); o->name=str(d,u16(p)); o->url=str(d,u16(p+2)); o->revision_on=i32(p+4); o->verified_on=i32(p+8); o->review_by=i32(p+12); return true;
}
#define ID_GETTER(name,table,type,at) \
bool name(const kb_dataset_t *d,uint8_t id,type *o) { \
  if(!d||!d->bytes||!o) return false; \
  const uint8_t *p=find_id(d,table,id); \
  return p?at(d,(size_t)(p-d->bytes-d->offsets[table])/strides[table],o):false; \
}
ID_GETTER(kb_operator_get,T_OPERATOR,kb_operator_t,kb_operator_at)
ID_GETTER(kb_stop_group_get,T_GROUP,kb_stop_group_t,kb_stop_group_at)
ID_GETTER(kb_boarding_point_get,T_POINT,kb_boarding_point_t,kb_boarding_point_at)
bool kb_pattern_get(const kb_dataset_t *d,uint8_t id,kb_pattern_t *o) {
  const uint8_t *p; if(!d||!d->bytes||!o||(p=find_id(d,T_PATTERN,id))==NULL) return false;
  o->id=p[0]; o->operator_id=p[1]; o->route=str(d,u16(p+2)); o->destination=str(d,u16(p+4)); o->destination_ja=str(d,u16(p+6)); o->destination_group_id=p[8]; o->first_call=u16(p+10); o->call_count=u16(p+12); o->route_transitions=str(d,u16(p+14)); return true;
}
bool kb_pattern_calls(const kb_dataset_t *d,uint8_t pattern,uint8_t group) {
  const uint8_t *p; if(!d||!d->bytes||(p=find_id(d,T_PATTERN,pattern))==NULL) return false;
  for(size_t i=0;i<u16(p+12);i++) if(row(d,T_CALL,u16(p+10)+i)[1]==group) return true;
  return false;
}
static bool route_digit(char c) { return c>='0'&&c<='9'; }
static int route_number_compare(const char *a,const char *b) {
  const char *original_a=a,*original_b=b;
  while(*a&&*b) {
    if(route_digit(*a)&&route_digit(*b)) {
      const char *end_a=a,*end_b=b;
      while(route_digit(*end_a))end_a++;
      while(route_digit(*end_b))end_b++;
      while(a<end_a&&*a=='0')a++;
      while(b<end_b&&*b=='0')b++;
      size_t length_a=(size_t)(end_a-a),length_b=(size_t)(end_b-b);
      if(length_a!=length_b)return length_a<length_b?-1:1;
      int compare=memcmp(a,b,length_a);
      if(compare)return compare;
      a=end_a;b=end_b;
    } else {
      if((unsigned char)*a!=(unsigned char)*b)return (unsigned char)*a<(unsigned char)*b?-1:1;
      a++;b++;
    }
  }
  if(*a||*b)return *a?1:-1;
  return strcmp(original_a,original_b); /* Keep leading-zero labels distinct. */
}
static int route_pattern_compare(const kb_dataset_t *d,uint8_t a,uint8_t b) {
  const uint8_t *pa=find_id(d,T_PATTERN,a),*pb=find_id(d,T_PATTERN,b);
  if(pa[1]!=pb[1])return pa[1]<pb[1]?-1:1;
  return route_number_compare(str(d,u16(pa+2)),str(d,u16(pb+2)));
}
static size_t route_ids(const kb_dataset_t *d,uint8_t *ids) {
  if(!d||!d->bytes)return 0;
  bool used[256]={false};size_t count=0;
  for(size_t i=0;i<d->counts[T_DEPARTURE];i++)used[row(d,T_DEPARTURE,i)[3]]=true;
  for(size_t i=0;i<d->counts[T_PATTERN];i++) {
    const uint8_t *pattern=row(d,T_PATTERN,i);
    if(!used[pattern[0]])continue;
    size_t position=0;
    while(position<count&&route_pattern_compare(d,ids[position],pattern[0])<0)position++;
    if(position<count&&route_pattern_compare(d,ids[position],pattern[0])==0)continue;
    memmove(ids+position+1,ids+position,count-position);
    ids[position]=pattern[0];count++;
  }
  return count;
}
size_t kb_route_count(const kb_dataset_t *d) {
  uint8_t ids[256];return route_ids(d,ids);
}
bool kb_route_at(const kb_dataset_t *d,size_t index,kb_route_t *out) {
  if(!out)return false;
  uint8_t ids[256];size_t count=route_ids(d,ids);
  if(index>=count)return false;
  const uint8_t *pattern=find_id(d,T_PATTERN,ids[index]);
  out->operator_id=pattern[1];out->number=str(d,u16(pattern+2));return true;
}
bool kb_boarding_point_has_route(const kb_dataset_t *d,uint8_t point,uint8_t operator_id,const char *number) {
  if(!d||!d->bytes||!point||!operator_id||!number||!number[0])return false;
  const uint8_t *bp=find_id(d,T_POINT,point);
  if(!bp||bp[2]!=operator_id)return false;
  for(size_t i=0;i<d->counts[T_DEPARTURE];i++) {
    const uint8_t *departure=row(d,T_DEPARTURE,i);
    if(departure[2]<point)continue;
    if(departure[2]>point)break;
    const uint8_t *pattern=find_id(d,T_PATTERN,departure[3]);
    if(pattern[1]==operator_id&&!strcmp(str(d,u16(pattern+2)),number))return true;
  }
  return false;
}
kb_day_type_t kb_calendar_day(const kb_dataset_t *d,uint8_t operator_id,int32_t day) {
  const uint8_t *op; if(!d||!d->bytes||(op=find_id(d,T_OPERATOR,operator_id))==NULL||day<d->valid_from||day>d->valid_until||day<i32(op+8)||day>i32(op+12)) return KB_DAY_UNKNOWN;
  for(size_t i=0;i<d->counts[T_EXCEPTION];i++) { const uint8_t *p=row(d,T_EXCEPTION,i); if(i32(p)>day) break; if(i32(p)==day&&p[4]==operator_id) return (kb_day_type_t)p[5]; }
  if(day<d->calendar_from||day>d->calendar_until) return KB_DAY_UNKNOWN;
  kb_day_type_t type=KB_DAY_UNKNOWN;
  for(size_t i=0;i<d->counts[T_HOLIDAY];i++) { int32_t holiday=i32(row(d,T_HOLIDAY,i)); if(holiday>day) break; if(holiday==day) { type=KB_DAY_SUNDAY_HOLIDAY; break; } }
  if(type==KB_DAY_UNKNOWN) { unsigned weekday=kb_weekday(day); type=weekday==0?KB_DAY_SUNDAY_HOLIDAY:weekday==6?KB_DAY_SATURDAY:KB_DAY_WEEKDAY; }
  return op[1]&(1u<<type)?type:KB_DAY_UNKNOWN;
}
static int trip_compare(const kb_trip_t *a,const kb_trip_t *b) {
  if(a->departure_utc!=b->departure_utc) return a->departure_utc<b->departure_utc?-1:1;
  if(a->service_day!=b->service_day) return a->service_day<b->service_day?-1:1;
  if(a->boarding_point_id!=b->boarding_point_id) return a->boarding_point_id<b->boarding_point_id?-1:1;
  if(a->pattern_id!=b->pattern_id) return a->pattern_id<b->pattern_id?-1:1;
  if(a->service_id!=b->service_id) return a->service_id<b->service_id?-1:1;
  if(a->release_version!=b->release_version) return a->release_version<b->release_version?-1:1;
  return 0;
}
bool kb_trip_same_identity(const kb_trip_t *a,const kb_trip_t *b) { return a&&b&&trip_compare(a,b)==0; }
static void historical_operators(const kb_query_t *q,int32_t today,const uint16_t *ids,size_t count,uint8_t *operators) {
  /* A point removed by today's snapshot may still have a verified 24:00+
   * departure from a preceding service date. Bind missing identities to the
   * most recent retained snapshot that can contain such trips. A current
   * identity always wins, so reuse by a different operator is not conflated. */
  for(unsigned ago=1;ago<=2;ago++) {
    bool missing=false;
    for(size_t i=0;i<count;i++)if(!operators[i])missing=true;
    if(!missing)return;
    const kb_dataset_t *d=q->resolve(q->context,today-(int32_t)ago);
    if(!d||!d->bytes||d->max_minute<ago*1440)continue;
    for(size_t i=0;i<count;i++)if(!operators[i]) {
      const uint8_t *bp=find_id(d,T_POINT,(uint8_t)ids[i]);
      if(bp)operators[i]=bp[2];
    }
  }
}
static kb_query_result_t query_next(const kb_query_t *q,const kb_trip_t *after,kb_trip_t *out,kb_query_state_t *state,bool home,uint8_t route_operator,const char *route_number) {
  kb_query_state_t s; kb_trip_t best; bool found=false,known_today=false,any_today=false;
  int32_t today; uint8_t operator_id;
  memset(&s,0,sizeof(s)); s.today_type=KB_DAY_UNKNOWN; s.first_unconfirmed_day=KB_DATE_UNKNOWN;
  if(!q||!q->resolve||!out) { if(state) *state=s; return KB_QUERY_UNAVAILABLE; }
  today=kb_jst_day(q->now_utc);
  const kb_dataset_t *current=q->resolve(q->context,today); const uint8_t *current_bp;
  if(!current||!current->bytes) { if(state) *state=s; return KB_QUERY_UNAVAILABLE; }
  current_bp=find_id(current,T_POINT,q->boarding_point_id);
  operator_id=current_bp?current_bp[2]:0;
  uint16_t point_id=q->boarding_point_id;
  historical_operators(q,today,&point_id,1,&operator_id);
  if(!operator_id) { if(state) *state=s; return KB_QUERY_UNAVAILABLE; }
  if(route_number&&(!route_number[0]||route_operator!=operator_id)) { if(state) *state=s; return KB_QUERY_UNAVAILABLE; }
  for(int32_t day=today-2;day<=today+KB_LOOKAHEAD_DAYS;day++) {
    const kb_dataset_t *d=q->resolve(q->context,day); const uint8_t *bp; kb_day_type_t type; bool overridden=false;
    if(day<today && (!d || d->max_minute < (uint32_t)(today-day)*1440)) continue;
    if(!d||!d->bytes||(bp=find_id(d,T_POINT,q->boarding_point_id))==NULL||bp[2]!=operator_id) { type=KB_DAY_UNKNOWN; }
    else {
      type=kb_calendar_day(d,operator_id,day);
      const uint8_t *op=find_id(d,T_OPERATOR,operator_id);
      if(day==today&&q->override.jst_day==today&&day_valid((uint8_t)q->override.day_type)&&q->override.day_type!=KB_DAY_UNKNOWN&&op&&day>=i32(op+8)&&day<=i32(op+12)) { type=q->override.day_type; overridden=true; }
    }
    if(day==today) { s.today_type=type; s.override_used=overridden; known_today=type!=KB_DAY_UNKNOWN; }
    if(type==KB_DAY_UNKNOWN) {
      if(day>=today) { s.coverage_limited=true; s.first_unconfirmed_day=day; break; }
      continue;
    }
    if(type==KB_DAY_NONE) {
      if(home&&day>=today&&found&&best.departure_utc<kb_service_epoch(day+1,0)) break;
      continue;
    }
    for(size_t i=0;i<d->counts[T_DEPARTURE];i++) {
      const uint8_t *p=row(d,T_DEPARTURE,i);
      if(p[2]<q->boarding_point_id) continue;
      if(p[2]>q->boarding_point_id) break;
      if(route_number) {
        const uint8_t *pattern=find_id(d,T_PATTERN,p[3]);
        if(pattern[1]!=route_operator||strcmp(str(d,u16(pattern+2)),route_number)) continue;
      }
      const uint8_t *svc=find_id(d,T_SERVICE,p[4]);
      if(day<i32(svc+4)||day>i32(svc+8)||!(svc[2]&(1u<<type))) continue;
      if(q->destination_group_id&&!kb_pattern_calls(d,p[3],q->destination_group_id)) continue;
      if(day==today) any_today=true;
      kb_trip_t trip; memset(&trip,0,sizeof(trip)); trip.departure_utc=kb_service_epoch(day,u16(p));
      if(q->now_utc>=trip.departure_utc+60) continue;
      trip.service_day=day; trip.release_version=d->release_version; trip.minute=u16(p); trip.boarding_point_id=p[2]; trip.pattern_id=p[3]; trip.service_id=p[4]; trip.day_type=type; trip.overridden=overridden;
      if(after&&trip_compare(&trip,after)<=0) continue;
      if(!found||trip_compare(&trip,&best)<0) { best=trip; found=true; }
    }
    /* A later originating day cannot depart before its own midnight. This
     * keeps ordinary offline queries on one persistent dataset cache while
     * retaining overnight ordering across previous service dates. */
    if((home||!state)&&(!home||day>=today)&&found&&best.departure_utc<kb_service_epoch(day+1,0)) break;
  }
  s.today_no_service=known_today&&!any_today;
  if(state) *state=s;
  if(found) { *out=best; return KB_QUERY_FOUND; }
  return s.coverage_limited?KB_QUERY_UNCONFIRMED:KB_QUERY_NO_MORE;
}
kb_query_result_t kb_query_next(const kb_query_t *q,const kb_trip_t *after,kb_trip_t *out,kb_query_state_t *state) {
  return query_next(q,after,out,state,false,0,NULL);
}
kb_query_result_t kb_query_home(const kb_query_t *q,kb_trip_t *out,kb_query_state_t *state) {
  return query_next(q,NULL,out,state,true,0,NULL);
}
kb_query_result_t kb_upcoming_at(const kb_query_t *q,size_t index,kb_trip_t *out,kb_query_state_t *state) {
  kb_trip_t previous; bool has_previous=false;
  if(!out) return KB_QUERY_UNAVAILABLE;
  for(size_t i=0;i<=index;i++) { kb_query_result_t r=kb_query_next(q,has_previous?&previous:NULL,out,state); if(r!=KB_QUERY_FOUND) return r; previous=*out; has_previous=true; }
  return KB_QUERY_FOUND;
}
kb_query_result_t kb_query_route_next(const kb_query_t *q,uint8_t operator_id,const char *number,const kb_trip_t *after,kb_trip_t *out,kb_query_state_t *state) {
  /* NULL is invalid for this explicitly filtered API, not an implicit clear. */
  return query_next(q,after,out,state,false,operator_id,number?number:"");
}
kb_query_result_t kb_upcoming_route_at(const kb_query_t *q,uint8_t operator_id,const char *number,size_t index,kb_trip_t *out,kb_query_state_t *state) {
  kb_trip_t previous; bool has_previous=false;
  if(!out)return KB_QUERY_UNAVAILABLE;
  for(size_t i=0;i<=index;i++) {
    kb_query_result_t result=kb_query_route_next(q,operator_id,number,has_previous?&previous:NULL,out,state);
    if(result!=KB_QUERY_FOUND)return result;
    previous=*out;has_previous=true;
  }
  return KB_QUERY_FOUND;
}
static uint32_t merged_distance(const kb_trip_t *trip,const uint8_t *selected,const uint32_t *metres) {
  uint8_t entry=selected[trip->boarding_point_id];
  return metres&&entry?metres[entry-1]:UINT32_MAX;
}
static int merged_compare(const kb_trip_t *a,const kb_trip_t *b,const uint8_t *selected,const uint32_t *metres) {
  if(a->departure_utc!=b->departure_utc)return a->departure_utc<b->departure_utc?-1:1;
  uint32_t da=merged_distance(a,selected,metres),db=merged_distance(b,selected,metres);
  if(da!=db)return da<db?-1:1;
  return trip_compare(a,b);
}
kb_query_result_t kb_query_merged_next(const kb_query_t *q,const uint16_t *ids,const uint32_t *metres,
    size_t count,const kb_trip_t *after,kb_trip_t *out,kb_query_state_t *state) {
  kb_query_state_t s;memset(&s,0,sizeof(s));
  s.today_type=KB_DAY_UNKNOWN;s.first_unconfirmed_day=KB_DATE_UNKNOWN;
  if(state)*state=s;
  if(!q||!q->resolve||!out||count>KB_MERGED_MAX_POINTS||(count&&!ids))return KB_QUERY_UNAVAILABLE;
  if(!count)return KB_QUERY_NO_MORE;
  uint8_t selected[256]={0},operators[KB_MERGED_MAX_POINTS]={0};
  bool blocked[KB_MERGED_MAX_POINTS]={false};
  for(size_t i=0;i<count;i++) {
    if(!ids[i]||ids[i]>255||selected[ids[i]])return KB_QUERY_UNAVAILABLE;
    selected[ids[i]]=(uint8_t)(i+1);
  }
  int32_t today=kb_jst_day(q->now_utc);
  const kb_dataset_t *current=q->resolve(q->context,today);
  if(!current||!current->bytes)return KB_QUERY_UNAVAILABLE;
  /* Copy identities before the resolver reuses its buffer for another day. */
  for(size_t i=0;i<count;i++) {
    const uint8_t *bp=find_id(current,T_POINT,(uint8_t)ids[i]);
    if(bp)operators[i]=bp[2];
  }
  historical_operators(q,today,ids,count,operators);
  kb_trip_t best;bool found=false,any_today=false;size_t known_today=0;
  for(int32_t day=today-2;day<=today+KB_LOOKAHEAD_DAYS;day++) {
    const kb_dataset_t *d=q->resolve(q->context,day);
    if(day<today&&(!d||!d->bytes||d->max_minute<(uint32_t)(today-day)*1440))continue;
    kb_day_type_t types[KB_MERGED_MAX_POINTS];bool overridden[KB_MERGED_MAX_POINTS]={false};
    size_t active=0;
    for(size_t i=0;i<count;i++) {
      types[i]=KB_DAY_UNKNOWN;
      if(blocked[i])continue;
      const uint8_t *bp=d&&d->bytes?find_id(d,T_POINT,(uint8_t)ids[i]):NULL;
      if(bp&&operators[i]&&bp[2]==operators[i]) {
        types[i]=kb_calendar_day(d,operators[i],day);
        const uint8_t *op=find_id(d,T_OPERATOR,operators[i]);
        if(day==today&&q->override.jst_day==today&&day_valid((uint8_t)q->override.day_type)&&
            q->override.day_type!=KB_DAY_UNKNOWN&&op&&day>=i32(op+8)&&day<=i32(op+12)) {
          types[i]=q->override.day_type;overridden[i]=true;
        }
      }
      if(day==today) {
        if(i==0)s.today_type=types[i];
        else if(s.today_type!=types[i])s.today_type=KB_DAY_UNKNOWN;
        known_today+=types[i]!=KB_DAY_UNKNOWN;s.override_used|=overridden[i];
      }
      if(types[i]==KB_DAY_UNKNOWN) {
        if(day>=today) {
          blocked[i]=true;s.coverage_limited=true;
          if(s.first_unconfirmed_day==KB_DATE_UNKNOWN)s.first_unconfirmed_day=day;
        }
      } else active++;
    }
    if(d&&d->bytes)for(size_t i=0;i<d->counts[T_DEPARTURE];i++) {
      const uint8_t *p=row(d,T_DEPARTURE,i);uint8_t entry=selected[p[2]];
      if(!entry)continue;
      size_t index=(size_t)entry-1;kb_day_type_t type=types[index];
      if(type==KB_DAY_UNKNOWN||type==KB_DAY_NONE)continue;
      const uint8_t *svc=find_id(d,T_SERVICE,p[4]);
      if(day<i32(svc+4)||day>i32(svc+8)||!(svc[2]&(1u<<type)))continue;
      if(q->destination_group_id&&!kb_pattern_calls(d,p[3],q->destination_group_id))continue;
      if(day==today)any_today=true;
      kb_trip_t trip;memset(&trip,0,sizeof(trip));trip.departure_utc=kb_service_epoch(day,u16(p));
      if(q->now_utc>=trip.departure_utc+60)continue;
      trip.service_day=day;trip.release_version=d->release_version;trip.minute=u16(p);
      trip.boarding_point_id=p[2];trip.pattern_id=p[3];trip.service_id=p[4];
      trip.day_type=type;trip.overridden=overridden[index];
      if(after&&merged_compare(&trip,after,selected,metres)<=0)continue;
      if(!found||merged_compare(&trip,&best,selected,metres)<0){best=trip;found=true;}
    }
    if(day>=today&&!active)break;
    if(!state&&day>=today&&found&&best.departure_utc<kb_service_epoch(day+1,0))break;
  }
  s.today_no_service=known_today==count&&!any_today;
  if(state)*state=s;
  if(found){*out=best;return KB_QUERY_FOUND;}
  return s.coverage_limited?KB_QUERY_UNCONFIRMED:KB_QUERY_NO_MORE;
}
kb_query_result_t kb_upcoming_merged_at(const kb_query_t *q,const uint16_t *ids,const uint32_t *metres,
    size_t count,size_t index,kb_trip_t *out,kb_query_state_t *state) {
  kb_trip_t previous;bool has_previous=false;
  if(!out)return KB_QUERY_UNAVAILABLE;
  for(size_t i=0;i<=index;i++) {
    kb_query_result_t result=kb_query_merged_next(q,ids,metres,count,has_previous?&previous:NULL,out,state);
    if(result!=KB_QUERY_FOUND)return result;
    previous=*out;has_previous=true;
  }
  return KB_QUERY_FOUND;
}
const kb_dataset_t *kb_trip_dataset(const kb_query_t *q,const kb_trip_t *trip) {
  if(!q||!q->resolve||!trip) return NULL;
  const kb_dataset_t *d=q->resolve(q->context,trip->service_day);
  return d&&d->release_version==trip->release_version?d:NULL;
}
kb_countdown_state_t kb_countdown(int64_t now,int64_t departure,uint32_t *minutes) {
  if(minutes) *minutes=0;
  if(now>=departure+60) return KB_COUNTDOWN_EXPIRED;
  if(now>=departure) return KB_COUNTDOWN_DUE;
  int64_t value=(departure-now+59)/60;
  if(minutes) *minutes=value>UINT32_MAX?UINT32_MAX:(uint32_t)value;
  return KB_COUNTDOWN_MINUTES;
}
bool kb_leave_by(const kb_trip_t *trip,kb_trip_context_t context,uint16_t walk,uint16_t buffer,int64_t *out) {
  if(!trip||!out||context!=KB_CONTEXT_SAVED_ORIGIN) return false;
  *out=trip->departure_utc-((int64_t)walk+buffer)*60; return true;
}
