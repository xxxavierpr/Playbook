# Wed 2026-10-14 — entry configuration for the open

Decision note for the 10-14 open. The book and the trading code are unchanged. Nothing here is in force until Xavier writes it into the book.

Xavier trades off the extended-hours 1-minute chart, where EMA20 runs through premarket. The question is which of four configurations gives the better first entry of the day.

| | Configuration |
|---|---|
| A | The book as it ran on 10-13: extended-hours EMA20, plus the shipped `first_hour_dual_ema` with its regular-hours EMA20 seeded on the session's first bar |
| B | Extended-hours EMA20 only, plus the 5-bar side-flip skip with premarket bars counted. No dual-EMA check |
| C | B plus one-bar confirmation |
| D | The first-hour dual-EMA check with its regular-hours EMA20 seeded on prior sessions, plus the 5-bar side-flip skip |

All four keep the side rule (HA color plus the close against EMA20), the VWAP gate, the 30/70 RSI skip, and max one buy. The flip skip and the confirmation bar are fixes 1 and 2 in `notes/2026-10-13-qqq-732-put.md`. The prior-session seed is the one in `notes/2026-10-12-qqq-755-call.md`.

## Recommendation: B

Trade the extended-hours EMA20 by itself. Skip any signal if one of the previous five bars, premarket included, was a signal on the other side (the side before any filter, as in fix 1 of the 732P note). Drop the first-hour dual-EMA check.

**Why.** Most bad first entries are signals taken right after the chart switched sides: selling the flush low on 10-13, buying the bounce top on 10-12. Making the side hold for five minutes skips those, and that one rule carries the whole improvement. Once it is in, a second average adds nothing, and waiting a bar to confirm adds nothing either. B is the simplest of the three setups that fix the open.

**How much to trust it.** Enough to pick B over A, not enough to rank B, C, and D. These are 21 sessions with one first entry each, scored on QQQ moves rather than option prices. Only 11 of them, 09-15 to 09-29, played no part in writing these rules, and on those B beat the current book by two sessions on both entry definitions. Two sessions in eleven could be luck. B gets the pick because it never had more stops than A on any slice or at any distance tried, it had fewer on nearly all of them, and it refuses both live losers for a reason anyone can check on the chart. Over all 21 sessions C stays within a session of B everywhere, and D matches B on any legal bar and trails it on fresh crosses.

## The replay

The 10-session replay from the 732P note, plus the 11 sessions before it. Each cell is latch/stop: sessions where the first entry reached +0.6 QQQ in its favor before −1.5 against, and sessions where −1.5 came first. "+1o" is a session where neither came within 30 bars. The first pair allows entry on any legal bar, the pair in parentheses fresh crosses only.

| | 10 sessions, 09-30 to 10-13 | Other 8 | 11 earlier, 09-15 to 09-29 | All 21 |
|---|---|---|---|---|
| A | 3/7 (5/5) | 3/5 (5/3) | 7/3+1o (7/4) | 10/10+1o (12/9) |
| B | 7/3 (7/3) | 5/3 (5/3) | 9/1+1o (9/2) | 16/4+1o (16/5) |
| C | 7/3 (7/2+1o) | 5/3 (5/2+1o) | 10/1 (8/2+1o) | 17/4 (15/4+2o) |
| D | 8/2 (6/3+1o) | 6/2 (4/3+1o) | 8/2+1o (8/3) | 16/4+1o (14/6+1o) |

"Other 8" leaves out 10-12 and 10-13, as in the 732P note. The 11 earlier sessions were fetched for this note. 09-14 was fetched too, only to seed D's prior-session average.

- A is last everywhere except fresh crosses on the other 8, where it ties B and D is last. Over all 21 sessions B beats A on both entry definitions at all three distances run (+0.6/−1.5, +0.5/−1.2, and +0.8/−2.0).
- Seven of A's ten stopped first entries over the 21 sessions came within five bars of a signal on the other side (six of nine on fresh crosses). B skips those by rule, and its later entry reached +0.6 first on all seven of those days (five of the six).
- On the 10 sessions, B, C, and D are within one session of each other. D's 8/2 comes from 10-06, and it gives that back on fresh crosses on 10-09.
- Over all 21, C is within one session of B in every run. D matches B's latches on any legal bar and trails it by two or three on fresh crosses at every distance.
- Average move in the 15 bars after the first entry, all 21 sessions, in favor / against. Any legal bar: A +0.91 / −1.40, B +1.17 / −0.70, C +1.20 / −0.65, D +1.02 / −0.75. Fresh crosses: A +0.88 / −1.35, B +1.25 / −0.76, C +1.43 / −0.61, D +0.95 / −0.93. Most of B's gain over A is on the adverse side, which roughly halves. C's averages are the best on fresh crosses, but its tally there is one latch and one stop fewer than B's.
- Median first entry: 08:33 for A, 08:40 for B, 08:46 for C, 08:47 for D (08:34, 08:47, 08:59, and 08:50 on fresh crosses). B never bought the first two bars.

## The two live days

Both entry definitions give the same entries.

| | 10-12 | 10-13 |
|---|---|---|
| A | 08:39 call at 749.43, stop (the live 755C signal) | 08:31 put at 739.34, stop (the live 732P) |
| B | 08:47 put at 747.86, +0.6 first at 09:05 | 08:45 call at 743.07, +0.6 first at 08:48 |
| C | 08:48 put at 747.82, +0.6 first at 09:05 | 08:46 call at 743.11, +0.6 first at 08:49 |
| D | 08:47 put at 747.86, +0.6 first at 09:05 | 08:45 call at 743.07, +0.6 first at 08:48 |

### Did D's prior-session seed block the 10-12 08:39 call?

Yes, by 0.33. At 08:39 the HA close was 749.125. That was over the extended-hours EMA20 (749.065) and the shipped same-session average (748.710), and under the prior-session average (749.456). The prior-session check is the only one it failed, so the seed blocks the call by itself. The flip skip blocks it too, independently: 08:34 was a PUT bar, five bars back.

The flip skip also refuses the 08:41–08:44 puts, which come within five bars of the 08:39 call bar, so D's entry is B's 08:47 put. The prior seed without the flip skip would have taken the 08:41 put at 748.21, which reached +0.6 at 08:43.

On 10-13 the prior seed passes the 08:31 put (HA close 739.756 against 744.810), so only the flip skip refuses it. It refuses the 08:34–08:37 calls by 1.70 to 3.40, but the flip skip already refuses those, and RSI14 over 70 refuses 08:38–08:42. On both live days the prior seed refuses nothing the flip skip doesn't.

## Why a second average doesn't help

- **The shipped seed is a first-bar block.** It starts at the first bar's close, which the HA close can rarely clear on that bar, and in these 21 sessions it blocked every otherwise-legal 08:30 entry. On its own it changed the book's first entry on 8 days, 7 of them 08:30 entries, and turned three latches into stops (09-16, 09-30, and 10-13). The book scores 13/7+1o without it and 10/10+1o with it (14/7 and 12/9 on fresh crosses). With the flip skip on, it never changed a first entry, on either definition.
- **The prior-session seed is a first-hour "don't fade the gap" rule.** It carries over from the prior session, so it starts the day near the prior close (745.93 going into the 10-13 open, against Monday's 746.02 close). After a gap it refuses every first-hour trade against the gap until the HA close gets back across it. Against B it changed the first entry on 5 of 21 sessions, and all five were B trades against the opening gap. It won one (10-06, any legal bar), lost one on both definitions (09-29) and one more on fresh crosses (10-09), and otherwise took the same result 12 to 34 minutes later. On any legal bar, B's five gap fades went 3/2 and D's replacements also went 3/2. On fresh crosses, B's three went 3/0 and D's went 1/1, with one unresolved.

## Why confirmation doesn't help

C buys one bar later, and when the next bar disagrees it waits for the next signal. Against B it changed the result on 3 sessions on any legal bar and 6 on fresh crosses, and the wins and losses cancel: 17/4 against 16/4+1o, and 15/4+2o against 16/5. On both live days it took B's trade a bar later.

## The flip skip's settings

- **Premarket counts.** With the lookback cut at 08:30, B buys the first or second bar on 8 of 21 sessions. Two of those stop (09-28 and 10-07), and the score falls to 14/6+1o (14/7). On those eight days B's later entries went 0.35 against on average over 15 bars (0.48 on fresh crosses), against 1.16 for the early ones.
- **Five bars was picked on 10-12**, as the shortest window that catches its call. On the 11 earlier sessions, every window from 3 to 10 bars did at least as well as the book, and five tied for the most latches on both entry definitions. The exact number matters less than having the skip.

## Pointers

1. Expect nothing at the bell. B never bought the first two bars in 21 sessions, and its median first entry was 08:40.
2. Put the bars since the last opposite signal, premarket included, on every signal line. It is the one number B turns on, and premarket bars are where the bot's feed and the chart are most likely to differ.
3. Re-score A–D after ten more live sessions, on the bot's own bars.

## Not verified

- No chain. The latch and the stop are QQQ distances standing in for +20% and −50%. The 732P and the 749C moved about 6.5 and 7 cents per point, so their −50% stops sat 1.0 to 1.5 points away. Over all 21 sessions, the closer +0.5/−1.2 run still has B first or tied for first and A last or tied for last, on both entry definitions.
- Bars and volume are yfinance, not Webull. B leans on the sides of the last premarket bars, which no ticket logs. The ticket's 08:31 HA close and EMA20 reproduce to the cent, so the premarket closes feeding them are probably close.
- The bot was not live on most of these sessions. The replay is the first entry only, under max one buy. Overrides and the bounce mode are not replayed.
- Whether the bot enters on a continuing signal or only on a fresh cross is not in the repo, so both are shown. Judging the 08:30 bar's fresh cross against the 08:29 premarket bar changes nothing.
- None of the four reads premarket RSI14, which runs 4–5 points over the bot's. All four use the same VWAP gate, and the bot's VWAP formula still does not reproduce.
- The 09-14 to 09-29 bars were fetched for this note. Adding them changes no indicator on the 10 replay sessions except D's prior-session average on 09-30, which had no prior session to seed it before (it moves by up to 2.49). No first entry in the 10-session replay changes, and every cell of the 732P note's fixes table reproduces.
- One stretch of one market. QQQ rose about 5% over these sessions, from 708.57 at the 09-15 open to 743.26 at 11:49 today, though 12 of the 21 closed under their open and 9 opened more than 0.5% from the prior close.
- The 10-13 tape ends at 11:49 CT.
