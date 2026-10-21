# Radio queue regression (2026-10-21, after opts.ahead was added to Skyhammer_Comms S.Say).
# 1. Differential: the same random radio traffic (Say with priority/urgent/craft/stale/onShow,
#    Unsay, ClearRadio, time passing) through the Comms of the 10-20 public snapshot and through
#    the current Comms gives the very same trace (what is on the air, the queue, the callbacks,
#    the log) when no line uses ahead.
# 2. Random traffic WITH ahead lines: ahead never cuts a priority line or a prompt, never removes
#    a waiting line, always waits behind the priority lines, never errors.
# Run: <codex python> -I source/tests/runsim.py source/tests/sim_radio_regression.py
import io, os, random, sys
from lupa import lua51
HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "..", "42", "media", "lua")
OLD_COMMS = os.path.join(HERE, "..", "..", "..", "..", "skyhammer-public", "SkyhammerAirSupport", "42", "media", "lua", "client", "Skyhammer_Comms.lua")
sys.path.insert(0, HERE)
import sim_shake as base
TESTS = []
def test(f): TESTS.append(f); return f
def check(c, msg):
    if not c: raise AssertionError(msg)


def world(comms_path):
    L = lua51.LuaRuntime()
    L.execute(base.STUBS)
    L.execute("CLOCK = 0; LOGS = {}; SHOWN = {}; print = function(...) local t = {}; for i = 1, select('#', ...) do t[#t + 1] = tostring((select(i, ...))) end; LOGS[#LOGS + 1] = table.concat(t, ' ') end")
    for f in ("client/Skyhammer_Lines.lua", "shared/Skyhammer_PvP.lua", "client/Skyhammer_Core.lua",
              "client/Skyhammer_Killstreak.lua"):
        L.execute(io.open(os.path.join(LUA, f), encoding="utf-8").read())
    L.execute(io.open(comms_path, encoding="utf-8").read())
    L.execute('''
    S = Skyhammer
    local function up(fn, name)
        for i = 1, 255 do local k, v = debug.getupvalue(fn, i); if not k then return end; if k == name then return v, i end end
    end
    local startNext = up(S.Say, "startNext")
    -- (upvalues are shared in Lua 5.1: setting one closure's stopVoice sets them all)
    for _, pair in ipairs({ { startNext, "ensureStrip" }, { startNext, "playVoice" }, { S.Say, "stopVoice" } }) do
        local _, i = up(pair[1], pair[2]); debug.setupvalue(pair[1], i, function() end)
    end
    function STATE()
        local q = up(S.Say, "queue"); local c
        for i = 1, 255 do local k, v = debug.getupvalue(startNext, i); if not k then break end; if k == "current" then c = v end end
        local t = {}
        for i, r in ipairs(q) do t[i] = r.id .. (r.priority and "!" or "") .. (r.ahead and "^" or "") end
        local cur = c and (c.id .. (c.priority and "!" or "") .. (c.prompt and "?" or "") .. (c.ahead and "^" or "")) or "-"
        return cur .. " | " .. table.concat(t, ",") .. " | " .. table.concat(SHOWN, ",") .. " | " .. table.concat(LOGS, ";")
    end
    function CUR() local s = STATE(); return s:match("^(%S+)") end
    function QIDS() local q = up(S.Say, "queue"); local t = {}; for i, r in ipairs(q) do t[i] = r.id end; return t end
    function QROWS() return (up(S.Say, "queue")) end
    ''')
    return L


def line_ids(L):
    ids = list(L.eval("(function() local t = {} for id in pairs(Skyhammer_Lines) do t[#t + 1] = id end table.sort(t) return t end)()").values())
    prompts = [i for i in ids if L.eval(f"Skyhammer_Lines['{i}'][4] == true")]
    return ids, prompts


def step_code(rng, ids, prompts, with_ahead):
    r = rng.random()
    if r < 0.6:
        lid = rng.choice(prompts) if rng.random() < 0.15 and prompts else rng.choice(ids)
        opts = []
        k = rng.random()
        if k < 0.15: opts.append("urgent = true")
        elif k < 0.40: opts.append("priority = true")
        elif with_ahead and k < 0.55: opts.append("ahead = true")
        if rng.random() < 0.2: opts.append(f"stale = {rng.choice([1500, 3000, 6000])}")
        if rng.random() < 0.2: opts.append('craft = "ac130"')
        cb = f'function() SHOWN[#SHOWN + 1] = "{lid}" end' if rng.random() < 0.15 else "nil"
        return f'S.Say("{lid}", {cb}, {{ {", ".join(opts)} }})'
    if r < 0.65:
        return f'S.Unsay("{rng.choice(ids)}")'
    if r < 0.67:
        return "S.ClearRadio()"
    return f"CLOCK = CLOCK + {rng.choice([50, 300, 1000, 2500, 4000, 9000])}; fire('OnTick')"


@test
def same_trace_as_before_without_ahead():
    check(os.path.isfile(OLD_COMMS), "the 10-20 snapshot Comms is there")
    runs = 0
    for seed in range(300):
        rng = random.Random(seed)
        A, B = world(OLD_COMMS), world(os.path.join(LUA, "client", "Skyhammer_Comms.lua"))
        ids, prompts = line_ids(A)
        for n in range(150):
            code = step_code(rng, ids, prompts, with_ahead=False)
            A.execute(code); B.execute(code)
            sa, sb = A.eval("STATE()"), B.eval("STATE()").replace("^", "")
            check(sa == sb, f"seed {seed} step {n} after {code}:\n old {sa[:300]}\n new {sb[:300]}")
        runs += 1
    check(runs == 300, "all seeds ran")


@test
def ahead_rules_hold_in_random_traffic():
    calls = cuts = 0
    for seed in range(300):
        rng = random.Random(1000 + seed)
        L = world(os.path.join(LUA, "client", "Skyhammer_Comms.lua"))
        ids, prompts = line_ids(L)
        for n in range(150):
            code = step_code(rng, ids, prompts, with_ahead=True)
            if "ahead = true" in code and "priority" not in code and "urgent" not in code:
                before_cur = L.eval("CUR()")
                before_q = list(L.eval("QIDS()").values())
                L.execute(code)
                calls += 1
                after_cur = L.eval("CUR()")
                after_q = list(L.eval("QIDS()").values())
                lid = code.split('"')[1]
                if before_cur != "-" and after_cur != before_cur:
                    cuts += 1
                    check(not any(m in before_cur for m in ("!", "?", "^")),
                          f"seed {seed}: cut {before_cur} (priority/prompt/ahead must not be cut)")
                # nothing that was waiting is gone (the new line may itself have started at once)
                rest = list(after_q) + ([after_cur.rstrip("!?^")] if after_cur != "-" else [])
                for w in before_q:
                    check(w in rest, f"seed {seed}: {w} disappeared after an ahead Say")
            else:
                L.execute(code)
            # order: no priority row behind an ahead or ordinary row; no ahead row behind an ordinary one
            rows = L.eval("QROWS()")
            rank = [0 if r.priority else 1 if r.ahead else 2 for r in rows.values()]
            check(rank == sorted(rank), f"seed {seed} step {n}: queue order {rank}")
    check(calls > 1000 and cuts > 50, f"the random traffic exercised it: {calls} ahead lines, {cuts} cuts")


if __name__ == "__main__":
    passed = 0
    for f in TESTS:
        try: f(); passed += 1; print("PASS", f.__name__)
        except Exception as e: print("FAIL", f.__name__, repr(e)[:600])
    print(f"{passed}/{len(TESTS)} passed"); sys.exit(0 if passed == len(TESTS) else 1)
