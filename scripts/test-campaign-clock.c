#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include "../WarbandTogether/src/shared/campaign_clock.h"
int main(void) {
    assert(coop_clock_accept(1, 0, 100, 999));
    assert(!coop_clock_accept(1, 1, 100, 999));
    assert(!coop_clock_accept(8, 9, 100, 999));
    assert(!coop_clock_accept(10, 9, -1, 0));
    assert(!coop_clock_accept(10, 9, 100, 1000));
    assert(!coop_clock_accept(10, 9, 2000001, 0));
    assert(coop_clock_predict(100999, 4) == 101000);
    assert(coop_clock_predict(100999, 1000) == 101249);
    assert(coop_clock_predict(100999, 60000) == 101249);
    assert(coop_clock_predict(INT64_C(2000000000), 1000) == INT64_C(2000000250));
    assert(coop_clock_predict(100000, (uint32_t)(UINT32_C(2)-UINT32_C(4294967294))) == 100001);
    puts("Campaign clock: ordering, validation, boundary, stall, and timer-wrap checks passed.");
    return 0;
}
