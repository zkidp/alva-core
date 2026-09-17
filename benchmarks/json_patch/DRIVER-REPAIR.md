# Bounded benchmark driver repair

The original target driver wrote the complete request to a blocking stdin pipe
before it established its wall deadline or began draining child output. On the
target Linux host, a helper that never read stdin plus a 1 MiB request remained
blocked until an independent four-second watchdog killed the driver (exit 137),
despite an internal 0.5-second setting.

The repaired driver starts one deadline before process creation and services
stdin, stdout, and stderr concurrently with nonblocking partial I/O. Stdout and
stderr each retain at most 16 MiB; crossing either limit terminates only the
task process group. Deadline and output-limit termination use a separate bounded
cleanup allowance for draining and reaping, which is recorded apart from the
compute interval. Address-space limiting remains an `RLIMIT_AS` envelope, not a
claim that every signal termination is an out-of-memory event.

Every measured invocation is now checked for both disposition and exact JSON
output outside its timed interval. Peak-RSS collection also uses the bounded
runner. The pre-warmup observation is labelled accordingly and is not presented
as cold-start latency.

No human active-time measurement is reported: the available evidence supports
process elapsed time and child CPU accounting only.
