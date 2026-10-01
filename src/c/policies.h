#ifndef KB_POLICIES_H
#define KB_POLICIES_H
#include <stdbool.h>
#include <stdint.h>
bool kb_auto_check_eligible(bool enabled,bool ready,bool busy,uint32_t last_attempt,int64_t now);
#endif
