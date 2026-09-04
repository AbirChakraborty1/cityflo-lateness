# Decision record — Cityflo lateness, 07:45 IST, 2026-06-17

This is the memo, not the code. The verdict table in `VERDICT_TABLE.md` will get fought over at the
standup; this is why each number is what it is, where I'd push back on my own rule, what it costs if I'm
wrong, and what would change my mind. See `README.md` for how to reproduce any of this.

---

## 1. What "late" means here

**The rule.** Primary measure: for each bus, find the next boarding stop it hasn't reached yet, project
when it'll get there using the route's *typical* pace (median historical progress-based runtime, not the
published timetable — see below), and compare that to the earliest `promised_eta` still owed at that stop.
That gap, in minutes, is the lateness number. Cross-check it against a second, independent read — elapsed
time vs. how far the bus should be if it were running at its typical pace for this point in the trip. If
the two disagree by more than 15 minutes, I don't trust either one enough to push a number — that's a
`NO_VERDICT`, not a guess.

**Why not the timetable.** I checked what "on schedule" actually means for these six routes using Monday
and Tuesday's pings. Measured naively (first ping to last ping), every route takes 20–25 minutes longer
than its published `scheduled_runtime_min` — a suspiciously uniform gap that's really the pre-departure and
post-arrival dwell baked into the extract, not real travel time. Measured properly (from the point a bus
actually leaves the origin stop's catchment to the point it reaches the destination's), every route runs
*faster* than the timetable. Either way, the timetable itself doesn't track what these buses actually do on
a normal day, so grading today against it would be grading against a number that's already wrong on a good
day. I use the fitted "normal" instead.

**The case it breaks on, and why I keep the rule anyway.** Route 21 (`TRIP_018`) is where my two numbers
come closest to disagreeing: the promise-breach method says +19 minutes, the typical-pace cross-check says
roughly +7. That's a 12-minute gap — under my 15-minute cutoff, so it still produces a verdict, but it's the
one number on the table I'd least want to bet my own credibility on cold. I keep promise-breach as the
number that goes out, because it's tied to a specific stop and a specific promise a specific rider is
holding right now (`S-2105`, promised `07:32:14`, current time `07:44:51` and still short of that stop) —
that is the actual thing a false or missing push affects, not an abstract route-average.

**The cost, and who eats it.** A push built on the timetable would cry wolf constantly, since the timetable
runs ~20 minutes behind what these buses actually do — that burns trust in the notification system itself,
not just in one bus. A push built on promise-breach that's wrong burns trust in that one push, which is
recoverable. The rider at `S-2105` eats a wrong ETA either way if I get this call wrong; ops eats a
standup argument if the number doesn't hold up.

**What would flip it.** If promise-breach and the typical-pace cross-check disagreed by more than ~15
minutes on more than one route on the same morning, I'd stop trusting `promised_eta` as a baseline rather
than the pings — it would suggest the promise itself was miscalibrated, not that the bus is unusually late.

---

## 2. Rev. C rule 1 — dropping operator 7

**The rule.** Operator-7 vehicles are excluded from the rider-facing verdict table, exactly as the
onboarding SOP says. But "excluded from the output" is not the same as "excluded from view" — the pipeline
still computes a real verdict for them and prints it (see `VERDICT_TABLE.md`'s last section), so a bad
number on an onboarding vehicle doesn't just disappear.

**The case it breaks on.** This morning, `TRIP_019` (route 21, `V-09`, operator 7) reads `HOLD` internally —
2.5 minutes off promise, nothing urgent. So today the rule costs nothing. But route 21 also happens to be
the one route with two simultaneous trips this morning, and dropping operator 7 is what quietly resolves
that down to one row. That's a structural question (what does "route 21" mean when two buses are running
it?) getting settled as a side effect of an unrelated fleet-vetting rule, which I don't think should happen
by accident even when, like today, the answer doesn't change.

**The cost, and who eats it.** If an operator-7 vehicle were ever badly late or genuinely stopped and this
rule silently dropped it with no internal trace, that operator's riders get zero notification and nobody
even knows to look — worse than a wrong number, because nobody's aware there's a gap at all. Keeping the
internal read costs nothing and closes that hole.

**What would flip it.** If an excluded operator-7 trip's internal verdict were ever `CALL_DRIVER` or a large
`PUSH_LATE`, I'd want that surfaced to ops on an internal channel even though it stays off the rider-facing
table — "not in the report" shouldn't mean "not anyone's problem."

---

## 3. Rev. C rule 2 — Route 12 forced to on-time

**The rule.** I do not apply it. Route 12's real number goes in the table.

**The case it breaks on.** Route 12 today reads `PUSH_LATE 14 min` under my primary measure (both baselines
agree on direction and rough size — this is one of the more confident reads on the table). Reporting it as
`0` per the rule means telling riders and the standup that a bus running fourteen minutes behind is on
time. This is the same mistake, mirrored, as the one Priya described in the handoff: *"we've pushed a
confidently-wrong 'late' number ... it cost us ... that CANNOT happen again."* A confidently-wrong
`on-time` is not a smaller version of that mistake, it's the same one.

**The cost, and who eats it.** Riders at the boarding stops still ahead of this bus lose the chance to make
other plans, because the system told them everything's fine. If this becomes visible later — someone
compares the "0" on the report against a rider complaint or the raw GPS — it costs more than a late push
would have, because now the reporting itself looks unreliable, not just one morning's traffic.

**What I'm not deciding.** If "report Route 12 as 0" is a separate contractual/SLA metric computed
elsewhere for a different audience, there's no real conflict — a compliance number and an operational
number are allowed to differ if everyone knows which is which. I can't confirm that from this extract, so
I'm not resolving it myself; I'm flagging the conflict explicitly rather than picking a side quietly. What I
won't do is let a contractual reporting convention overwrite the number that decides what a rider is told
*right now*.

**What would flip it.** Confirmation that the "0" only ever reaches a contractual/compliance report that
riders and the live ops board never see. Until then, the live board gets the real number.

---

## 4. Route 21's two simultaneous trips

**The rule.** One row per route. If more than one non-excluded trip is live on the same route at once, the
pipeline should stop and force a person to decide, not silently average or pick one. (I wrote it as a hard
assertion in the code for exactly this reason.)

**The case it breaks on.** Today it never actually fires, because rule 1 removes `TRIP_019` first and only
`TRIP_018` is left. But that's a coincidence of today's data, not a resolution of the underlying question —
a morning where both of route 21's buses were the same operator would hit this for real.

**The cost, and who eats it.** Silently picking "a" trip to represent a route — first one, worse one,
whichever the code happens to grab — hides whichever bus didn't get picked. If that were the actually late
one, ops chases the wrong number with total confidence.

**What would flip it.** A real two-trips-one-route morning that survives the operator-7 filter. At that
point I'd want an explicit policy (my instinct: report the worse of the two, since that's the one a rider
or ops person would want flagged) rather than a hard stop — today, for a one-off morning read, stopping and
asking is safer than guessing at a policy I haven't been asked for.

---

## 5. Route 11 — `CALL_DRIVER`, not a lateness number

**The rule.** If a bus's GPS shows essentially no progress (≤2% of the route) more than 15 minutes after
its scheduled departure, it gets `CALL_DRIVER`, not a `PUSH_LATE` figure.

**The case it breaks on.** `TRIP_014` (`V-06`) has not moved from Borivali Stn — the origin terminus — since
06:46, fifty-nine minutes ago, with speed sitting at 0–1.7 km/h the entire time (GPS jitter on a stationary
vehicle, not creeping traffic). Riders already hold `promised_eta`s for this trip that passed before 07:45.
A number here ("59 minutes late") would be true but useless: it frames this as ordinary congestion when the
actual open question is whether the bus left the depot at all.

**The cost, and who eats it.** Push a lateness number and ops treats it like every other slow bus — nobody
picks up the phone, and if the vehicle genuinely never left, every rider on it sits at their stop for
nothing. Call the driver and it turns out to be a harmless sensor issue, and the cost is one phone call and
a little depot annoyance — cheap next to the alternative.

**What would flip it.** Any real movement in the next ping. The moment progress ticks up, this goes back to
being an ordinary lateness read.

---

## 6. Route 17 — `NO_VERDICT`, not a guess

**The rule.** Telemetry older than 5 minutes at the as-of moment produces `NO_VERDICT`, regardless of what
the stale data would otherwise have said.

**The case it breaks on.** `TRIP_017` (`V-05`) was accelerating cleanly — 20 to 29 km/h — right up until its
feed went silent at 07:27:40. The honest last impression is "probably fine." I still withhold a verdict,
because "probably fine" is a guess wearing a number, and Priya was explicit that a confident wrong number
is worse than an honest blank.

**The cost, and who eats it.** A `NO_VERDICT` costs a manual check — someone radios the driver or watches
the next ping come in. A wrong `HOLD` here, if the bus is actually stopped somewhere off the recorded route,
costs every rider on it a silent no-show.

**What would flip it.** The feed resuming. One fresh ping and this is an ordinary trip again.

---

## Summary table

| # | Call | Rider-facing cost if wrong | Confidence |
|---|---|---|---|
| 1 | promised_eta primary, typical-pace cross-check, timetable rejected | crying-wolf pushes (timetable) vs. one bad push (promise-breach) | medium-high (route 21 is the soft spot) |
| 2 | drop operator 7 from output, not from view | an invisible late bus on an onboarding vehicle | high |
| 3 | Route 12 reports real number, not forced 0 | telling riders a 14-min-late bus is on time | high |
| 4 | one row per route, hard-stop on ties rather than silently pick | masking whichever trip didn't get picked | high (today: moot) |
| 5 | Route 11 → CALL_DRIVER | treating "maybe never left" as ordinary lateness | high |
| 6 | Route 17 → NO_VERDICT | a confident guess on 17-minute-old data | high |
