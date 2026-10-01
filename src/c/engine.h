#ifndef KASUGABUS_ENGINE_H
#define KASUGABUS_ENGINE_H

/* Portable schedule engine. All dates are Gregorian days since 1970-01-01;
 * all epochs are UTC seconds. No libc timezone state or heap is used. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define KB_SCHEMA_VERSION 1
#define KB_HEADER_SIZE 128
#define KB_TABLE_COUNT 10
#define KB_MAX_DATASET_BYTES 32768
#define KB_MAX_MINUTE 4319 /* service times through 71:59 */
#define KB_DATE_UNKNOWN INT32_MIN
#define KB_COORD_UNKNOWN INT32_MIN
#define KB_LOOKAHEAD_DAYS 7
#define KB_MERGED_MAX_POINTS 32

typedef enum { KB_DAY_NONE = 0, KB_DAY_WEEKDAY = 1, KB_DAY_SATURDAY = 2,
  KB_DAY_SUNDAY_HOLIDAY = 3, KB_DAY_UNKNOWN = 255 } kb_day_type_t;
typedef enum { KB_OK = 0, KB_ERR_ARGUMENT, KB_ERR_SIZE, KB_ERR_MAGIC,
  KB_ERR_SCHEMA, KB_ERR_CHECKSUM, KB_ERR_LAYOUT, KB_ERR_VALUE,
  KB_ERR_REFERENCE, KB_ERR_SORT, KB_ERR_DUPLICATE } kb_error_t;

typedef struct {
  const uint8_t *bytes;
  size_t size;
  uint32_t release_version, minimum_app_version;
  int32_t effective_from, valid_from, valid_until, calendar_from, calendar_until;
  int32_t source_verified_on, review_by;
  uint32_t strings_offset, strings_length, offsets[KB_TABLE_COUNT];
  uint16_t counts[KB_TABLE_COUNT], max_minute, coverage_string;
} kb_dataset_t;

typedef struct {
  uint8_t id, confirmed_day_types;
  const char *name, *name_ja, *short_name;
  int32_t valid_from, valid_until, source_verified_on, review_by;
  uint16_t first_source, source_count;
} kb_operator_t;
typedef struct { uint8_t id; const char *short_name, *name, *name_ja; } kb_stop_group_t;
typedef struct {
  uint8_t id, group_id, operator_id;
  const char *name, *short_name, *name_ja, *direction, *direction_ja, *guidance;
  int32_t latitude_e6, longitude_e6;
  bool has_coordinate;
} kb_boarding_point_t;
typedef struct {
  uint8_t id, operator_id, destination_group_id;
  const char *route, *destination, *destination_ja, *route_transitions;
  uint16_t first_call, call_count;
} kb_pattern_t;
/* A route number is scoped to its operator and is the number when boarding,
 * not a downstream route transition. Strings borrow the supplied dataset. */
typedef struct { uint8_t operator_id; const char *number; } kb_route_t;
typedef struct {
  const char *name, *url;
  int32_t revision_on, verified_on, review_by;
} kb_source_t;

kb_error_t kb_dataset_open(kb_dataset_t *out, const uint8_t *bytes, size_t size);
uint32_t kb_crc32(const uint8_t *bytes, size_t size);
const char *kb_coverage_id(const kb_dataset_t *data);
size_t kb_operator_count(const kb_dataset_t *data);
size_t kb_stop_group_count(const kb_dataset_t *data);
size_t kb_boarding_point_count(const kb_dataset_t *data);
size_t kb_source_count(const kb_dataset_t *data);
bool kb_operator_at(const kb_dataset_t *data, size_t index, kb_operator_t *out);
bool kb_stop_group_at(const kb_dataset_t *data, size_t index, kb_stop_group_t *out);
bool kb_boarding_point_at(const kb_dataset_t *data, size_t index, kb_boarding_point_t *out);
bool kb_source_at(const kb_dataset_t *data, size_t index, kb_source_t *out);
bool kb_operator_get(const kb_dataset_t *data, uint8_t id, kb_operator_t *out);
bool kb_stop_group_get(const kb_dataset_t *data, uint8_t id, kb_stop_group_t *out);
bool kb_boarding_point_get(const kb_dataset_t *data, uint8_t id, kb_boarding_point_t *out);
bool kb_pattern_get(const kb_dataset_t *data, uint8_t id, kb_pattern_t *out);
bool kb_pattern_calls(const kb_dataset_t *data, uint8_t pattern_id, uint8_t group_id);
size_t kb_route_count(const kb_dataset_t *data);
bool kb_route_at(const kb_dataset_t *data, size_t index, kb_route_t *out);
bool kb_boarding_point_has_route(const kb_dataset_t *data, uint8_t point_id,
                                uint8_t operator_id, const char *number);

/* A resolver may reuse its cache on every invocation. Trips therefore contain
 * identity values, never borrowed dataset pointers. */
typedef const kb_dataset_t *(*kb_resolver_t)(void *context, int32_t service_day);
typedef struct { int32_t jst_day; kb_day_type_t day_type; } kb_override_t;
typedef struct {
  kb_resolver_t resolve;
  void *context;
  int64_t now_utc;
  uint8_t boarding_point_id, destination_group_id; /* 0 means any destination */
  kb_override_t override;
} kb_query_t;
typedef struct {
  int64_t departure_utc;
  int32_t service_day;
  uint32_t release_version;
  uint16_t minute;
  uint8_t boarding_point_id, pattern_id, service_id;
  kb_day_type_t day_type;
  bool overridden;
} kb_trip_t;
typedef struct {
  kb_day_type_t today_type;
  bool today_no_service, override_used, coverage_limited;
  int32_t first_unconfirmed_day;
} kb_query_state_t;
typedef enum { KB_QUERY_FOUND = 1, KB_QUERY_NO_MORE = 0,
  KB_QUERY_UNCONFIRMED = -1, KB_QUERY_UNAVAILABLE = -2 } kb_query_result_t;

/* Exact operator exception > public holiday > weekday. Override applies only
 * when its saved JST date equals the real current JST date. */
kb_day_type_t kb_calendar_day(const kb_dataset_t *data, uint8_t operator_id, int32_t day);
kb_query_result_t kb_query_next(const kb_query_t *query, const kb_trip_t *after,
                              kb_trip_t *out, kb_query_state_t *state);
/* Home needs today's status and the earliest trip. Stop once later originating
 * dates cannot beat it; coverage flags describe only dates needed for that
 * search. kb_query_next with state retains full lookahead diagnostics. */
kb_query_result_t kb_query_home(const kb_query_t *query, kb_trip_t *out,
                              kb_query_state_t *state);
kb_query_result_t kb_upcoming_at(const kb_query_t *query, size_t index,
                               kb_trip_t *out, kb_query_state_t *state);
/* Filter by stable operator/number values across current/future snapshots.
 * number must be caller-owned: the resolver may invalidate borrowed strings. */
kb_query_result_t kb_query_route_next(const kb_query_t *query, uint8_t operator_id,
    const char *number, const kb_trip_t *after, kb_trip_t *out, kb_query_state_t *state);
kb_query_result_t kb_upcoming_route_at(const kb_query_t *query, uint8_t operator_id,
    const char *number, size_t index, kb_trip_t *out, kb_query_state_t *state);
/* Merge boarding opportunities, ordered by epoch, approximate distance, then
 * stable trip identity. NULL metres / UINT32_MAX means Distance unknown.
 * IDs and distances are caller-owned parallel arrays; coordinates never enter
 * this API. A calendar gap blocks only the affected boarding point. */
kb_query_result_t kb_query_merged_next(const kb_query_t *query,
    const uint16_t *ids, const uint32_t *metres, size_t count,
    const kb_trip_t *after, kb_trip_t *out, kb_query_state_t *state);
kb_query_result_t kb_upcoming_merged_at(const kb_query_t *query,
    const uint16_t *ids, const uint32_t *metres, size_t count, size_t index,
    kb_trip_t *out, kb_query_state_t *state);
const kb_dataset_t *kb_trip_dataset(const kb_query_t *query, const kb_trip_t *trip);
bool kb_trip_same_identity(const kb_trip_t *a, const kb_trip_t *b);

int32_t kb_jst_day(int64_t utc_seconds);
int64_t kb_service_epoch(int32_t day, uint16_t minute);
bool kb_date_from_ymd(int year, unsigned month, unsigned day, int32_t *out);
void kb_date_to_ymd(int32_t day, int *year, unsigned *month, unsigned *dom);
unsigned kb_weekday(int32_t day); /* Sunday=0 */
typedef enum { KB_COUNTDOWN_EXPIRED = -1, KB_COUNTDOWN_DUE = 0,
  KB_COUNTDOWN_MINUTES = 1 } kb_countdown_state_t;
kb_countdown_state_t kb_countdown(int64_t now_utc, int64_t departure_utc, uint32_t *minutes);
typedef enum { KB_CONTEXT_AT_STOP = 0, KB_CONTEXT_SAVED_ORIGIN = 1,
  KB_CONTEXT_NEARBY = 2 } kb_trip_context_t;
bool kb_leave_by(const kb_trip_t *trip, kb_trip_context_t context,
                 uint16_t walking_minutes, uint16_t buffer_minutes, int64_t *out_utc);

#endif
