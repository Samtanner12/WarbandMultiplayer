#ifndef COOP_CAMPAIGN_CLOCK_H
#define COOP_CAMPAIGN_CLOCK_H
#include <stdint.h>

/* Wire units are 1/1000 campaign hour. Native timer units are 1/100000
   hour. Predict only one update interval; stalled servers must not leave
   clients running indefinitely into the future. */
static int64_t coop_clock_predict(int64_t sample, uint32_t elapsed_ms) {
    if (elapsed_ms > 1000) elapsed_ms = 1000;
    return sample + elapsed_ms / 4; /* normal speed: 0.25 hour/second */
}
static int coop_clock_accept(int sequence, int previous, int hours, int fraction) {
    return sequence > previous && hours >= 0 && hours <= 2000000 &&
           fraction >= 0 && fraction < 1000;
}
#endif
