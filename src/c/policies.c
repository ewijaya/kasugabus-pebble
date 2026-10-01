#include "policies.h"
bool kb_auto_check_eligible(bool enabled,bool ready,bool busy,uint32_t last_attempt,int64_t now) {
  if(!enabled||!ready||busy||now<0)return false;
  if(!last_attempt)return true;
  /* A backward wall-clock adjustment must not manufacture extra attempts.
  * An explicit manual request remains possible. */  return now>=(int64_t)last_attempt+86400;
}
