# Run #2 log — 30-run sweep (protocol: PRE-REGISTRATION.md Run #2 section)

2026-10-24T17:51:13Z LAUNCH run#2: cli=2.1.308 (Claude Code) nm=neuralmind 4.21.0 tasks_sha=e058586485b6 disk=127G
2026-10-24T18:06:26Z INDEX ef8222b932 ok in 909.6s (1.9G	~/nm-bench/index/ef8222b932/.neuralmind)
2026-10-24T18:17:10Z INDEX 9701123540 ok in 639.3s (1.8G	~/nm-bench/index/9701123540/.neuralmind)
2026-10-24T21:40:53Z LAUNCH run#2: cli=2.1.308 (Claude Code) nm=neuralmind 4.21.0 tasks_sha=e058586485b6 disk=123G
2026-10-24T21:40:53Z INDEX ef8222b932 reuse (BUILD_OK)
2026-10-24T21:40:53Z INDEX 9701123540 reuse (BUILD_OK)
2026-10-24T21:59:11Z INDEX 69316aa66f ok in 1091.3s (2.3G	~/nm-bench/index/69316aa66f/.neuralmind)
2026-10-24T22:09:55Z INDEX e113c1b3af ok in 640.0s (1.8G	~/nm-bench/index/e113c1b3af/.neuralmind)
2026-10-24T22:23:55Z INDEX b86be0c098 ok in 832.5s (2.3G	~/nm-bench/index/b86be0c098/.neuralmind)
2026-10-24T22:24:19Z SMOKE PASS: exposed=6 called={'mcp__neuralmind__neuralmind_search': 1}
2026-10-24T22:24:19Z PHASE B: 0 rows already recorded (resume); 30 to run
2026-10-24T22:24:27Z RUN 1/30 69316aa66f-neuralmind-s0 start
2026-10-24T22:25:11Z RUN 1/30 69316aa66f-neuralmind-s0 done solved=True cost=0.16124370000000002 turns=11 mcp=0 explore=4 wall=38.9s timed_out=False
2026-10-24T22:25:18Z RUN 2/30 b86be0c098-neuralmind-s2 start
2026-10-24T22:26:17Z RUN 2/30 b86be0c098-neuralmind-s2 done solved=True cost=0.15026109999999998 turns=10 mcp=0 explore=3 wall=52.0s timed_out=False
2026-10-24T22:26:21Z RUN 3/30 b86be0c098-baseline-s1 start
2026-10-24T22:26:56Z RUN 3/30 b86be0c098-baseline-s1 done solved=True cost=0.20696190000000003 turns=12 mcp=0 explore=5 wall=30.5s timed_out=False
2026-10-24T22:27:00Z RUN 4/30 9701123540-baseline-s2 start
2026-10-24T22:27:20Z RUN 4/30 9701123540-baseline-s2 done solved=True cost=0.1790577 turns=8 mcp=0 explore=6 wall=16.4s timed_out=False
2026-10-24T22:27:25Z RUN 5/30 69316aa66f-baseline-s0 start
2026-10-24T22:28:04Z RUN 5/30 69316aa66f-baseline-s0 done solved=True cost=0.17662730000000001 turns=13 mcp=0 explore=4 wall=35.7s timed_out=False
2026-10-24T22:28:08Z RUN 6/30 e113c1b3af-baseline-s2 start
2026-10-24T22:28:20Z RUN 6/30 e113c1b3af-baseline-s2 done solved=True cost=0.1502003 turns=5 mcp=0 explore=3 wall=11.0s timed_out=False
2026-10-24T22:28:25Z RUN 7/30 69316aa66f-baseline-s2 start
2026-10-24T22:28:59Z RUN 7/30 69316aa66f-baseline-s2 done solved=True cost=0.17760040000000002 turns=11 mcp=0 explore=7 wall=30.3s timed_out=False
2026-10-24T22:29:03Z RUN 8/30 ef8222b932-baseline-s2 start
2026-10-24T22:31:18Z RUN 8/30 ef8222b932-baseline-s2 done solved=False cost=0.2510039 turns=10 mcp=0 explore=6 wall=81.6s timed_out=False
2026-10-24T22:31:23Z RUN 9/30 ef8222b932-neuralmind-s0 start
2026-10-24T22:33:07Z RUN 9/30 ef8222b932-neuralmind-s0 done solved=False cost=0.2682753 turns=12 mcp=0 explore=7 wall=48.2s timed_out=False
2026-10-24T22:33:11Z RUN 10/30 e113c1b3af-baseline-s1 start
2026-10-24T22:33:23Z RUN 10/30 e113c1b3af-baseline-s1 done solved=True cost=0.15046449999999997 turns=5 mcp=0 explore=3 wall=12.1s timed_out=False
2026-10-24T22:33:28Z RUN 11/30 b86be0c098-baseline-s2 start
2026-10-24T22:34:04Z RUN 11/30 b86be0c098-baseline-s2 done solved=True cost=0.2140343 turns=12 mcp=0 explore=4 wall=31.4s timed_out=False
2026-10-24T22:34:08Z RUN 12/30 69316aa66f-baseline-s1 start
2026-10-24T22:34:40Z RUN 12/30 69316aa66f-baseline-s1 done solved=True cost=0.15324510000000002 turns=10 mcp=0 explore=4 wall=27.1s timed_out=False
2026-10-24T22:34:46Z RUN 13/30 b86be0c098-neuralmind-s1 start
2026-10-24T22:35:51Z RUN 13/30 b86be0c098-neuralmind-s1 done solved=True cost=0.2508235 turns=14 mcp=0 explore=6 wall=59.5s timed_out=False
2026-10-24T22:35:56Z RUN 14/30 9701123540-neuralmind-s1 start
2026-10-24T22:36:23Z RUN 14/30 9701123540-neuralmind-s1 done solved=True cost=0.15401430000000002 turns=6 mcp=0 explore=4 wall=23.3s timed_out=False
2026-10-24T22:36:30Z RUN 15/30 b86be0c098-neuralmind-s0 start
2026-10-24T22:37:36Z RUN 15/30 b86be0c098-neuralmind-s0 done solved=True cost=0.2253463 turns=13 mcp=0 explore=4 wall=59.8s timed_out=False
2026-10-24T22:37:43Z RUN 16/30 69316aa66f-neuralmind-s1 start
2026-10-24T22:38:22Z RUN 16/30 69316aa66f-neuralmind-s1 done solved=True cost=0.151882 turns=10 mcp=0 explore=2 wall=35.1s timed_out=False
2026-10-24T22:38:26Z RUN 17/30 9701123540-baseline-s0 start
2026-10-24T22:38:48Z RUN 17/30 9701123540-baseline-s0 done solved=True cost=0.1735222 turns=12 mcp=0 explore=10 wall=18.9s timed_out=False
2026-10-24T22:38:53Z RUN 18/30 b86be0c098-baseline-s0 start
2026-10-24T22:39:15Z RUN 18/30 b86be0c098-baseline-s0 done solved=True cost=0.1853926 turns=7 mcp=0 explore=4 wall=15.8s timed_out=False
2026-10-24T22:39:19Z RUN 19/30 ef8222b932-neuralmind-s1 start
2026-10-24T22:40:58Z RUN 19/30 ef8222b932-neuralmind-s1 done solved=False cost=0.2441063 turns=13 mcp=0 explore=9 wall=42.3s timed_out=False
2026-10-24T22:41:07Z RUN 20/30 69316aa66f-neuralmind-s2 start
2026-10-24T22:41:59Z RUN 20/30 69316aa66f-neuralmind-s2 done solved=True cost=0.16721189999999997 turns=10 mcp=0 explore=5 wall=44.5s timed_out=False
2026-10-24T22:42:05Z RUN 21/30 ef8222b932-baseline-s0 start
2026-10-24T22:44:24Z RUN 21/30 ef8222b932-baseline-s0 done solved=False cost=0.27907170000000003 turns=12 mcp=0 explore=7 wall=83.3s timed_out=False
2026-10-24T22:44:29Z RUN 22/30 e113c1b3af-neuralmind-s1 start
2026-10-24T22:44:52Z RUN 22/30 e113c1b3af-neuralmind-s1 done solved=True cost=0.13497430000000002 turns=6 mcp=0 explore=3 wall=22.4s timed_out=False
2026-10-24T22:44:56Z RUN 23/30 e113c1b3af-neuralmind-s2 start
2026-10-24T22:45:23Z RUN 23/30 e113c1b3af-neuralmind-s2 done solved=True cost=0.1516575 turns=6 mcp=0 explore=4 wall=25.5s timed_out=False
2026-10-24T22:45:26Z RUN 24/30 9701123540-baseline-s1 start
2026-10-24T22:45:43Z RUN 24/30 9701123540-baseline-s1 done solved=True cost=0.1718351 turns=8 mcp=0 explore=6 wall=13.0s timed_out=False
2026-10-24T22:45:47Z RUN 25/30 ef8222b932-baseline-s1 start
2026-10-24T22:48:01Z RUN 25/30 ef8222b932-baseline-s1 done solved=False cost=0.2288131 turns=12 mcp=0 explore=8 wall=79.5s timed_out=False
2026-10-24T22:48:06Z RUN 26/30 ef8222b932-neuralmind-s2 start
2026-10-24T22:49:46Z RUN 26/30 ef8222b932-neuralmind-s2 done solved=False cost=0.25205429999999995 turns=11 mcp=0 explore=5 wall=45.1s timed_out=False
2026-10-24T22:49:52Z RUN 27/30 9701123540-neuralmind-s0 start
2026-10-24T22:50:20Z RUN 27/30 9701123540-neuralmind-s0 done solved=True cost=0.1640036 turns=7 mcp=0 explore=5 wall=24.8s timed_out=False
2026-10-24T22:50:24Z RUN 28/30 e113c1b3af-baseline-s0 start
2026-10-24T22:50:39Z RUN 28/30 e113c1b3af-baseline-s0 done solved=True cost=0.1657469 turns=5 mcp=0 explore=3 wall=14.1s timed_out=False
2026-10-24T22:50:45Z RUN 29/30 9701123540-neuralmind-s2 start
2026-10-24T22:51:22Z RUN 29/30 9701123540-neuralmind-s2 done solved=True cost=0.19169319999999998 turns=10 mcp=0 explore=8 wall=33.7s timed_out=False
2026-10-24T22:51:27Z RUN 30/30 e113c1b3af-neuralmind-s0 start
2026-10-24T22:51:58Z RUN 30/30 e113c1b3af-neuralmind-s0 done solved=True cost=0.1281463 turns=7 mcp=0 explore=4 wall=30.1s timed_out=False
2026-10-24T22:51:58Z SWEEP END 30/30 per_arm={"baseline": {"runs": 15, "total_mcp_calls": 0, "median_explore": 5, "median_turns": 10, "solved_runs": 12}, "neuralmind": {"runs": 15, "total_mcp_calls": 0, "median_explore": 4, "median_turns": 10, "solved_runs": 12}}
