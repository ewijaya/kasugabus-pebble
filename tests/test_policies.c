#include "../src/c/policies.h"
#include <assert.h>
#include <stdio.h>
int main(void){uint32_t last=1790812800;assert(kb_auto_check_eligible(true,true,false,0,last));assert(!kb_auto_check_eligible(true,false,false,0,last));assert(!kb_auto_check_eligible(false,true,false,0,last));assert(!kb_auto_check_eligible(true,true,true,0,last));assert(!kb_auto_check_eligible(true,true,false,last,last+86399));assert(kb_auto_check_eligible(true,true,false,last,last+86400));assert(!kb_auto_check_eligible(true,true,false,last,last-1));puts("automatic eligibility: offline defer, disabled, busy, rolling24h, backward clock PASS");}
