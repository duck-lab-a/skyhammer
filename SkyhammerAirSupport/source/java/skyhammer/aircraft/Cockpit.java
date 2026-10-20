package skyhammer.aircraft;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import viewpoint.core.Frame;

/**
 * A camera shot list an add-on plays in Viewpoint's 3D view (the ODIN robot's drop: looking up
 * at the sky, chasing its fall, the jolt of the landing, into its cockpit). Keys are camera
 * places (tile x, y, storey z) and the points they look at, at times in seconds; the move into
 * the first key from the player's own view and out of the last back to it are quick snaps.
 * Shakes jolt the camera at given times. Timed on the real clock, so the moves are smooth
 * whatever Lua's tick rate. Viewpoint's free-camera hook (Patch_Cockpit) asks it each frame.
 *
 * Public throughout: ZombieBuddy inlines Patch_Cockpit's advice into Viewpoint's FreeCam, which
 * can reach only public members of public classes.
 */
public final class Cockpit {
    /** How a key is reached from the one before it. */
    public static final int SMOOTH = 0, LINEAR = 1, CUT = 2, SNAP = 3;
    private record Key(double t, double ex, double ey, double ez, double lx, double ly, double lz, int mode) {}
    private record Shake(double at, double amp, double dur) {}

    private static final List<Key> pendingKeys = new ArrayList<>();
    private static final List<Shake> pendingShakes = new ArrayList<>();
    private static volatile Key[] keys = new Key[0];
    private static volatile Shake[] shakes = new Shake[0];
    private static volatile long start, inNs, outNs, endAt;
    private static boolean wrote, announced;
    private Cockpit() {}

    // ---- building a shot list (Lua, through AircraftBridge)
    public static synchronized void begin() { pendingKeys.clear(); pendingShakes.clear(); }
    public static synchronized void key(double t, double ex, double ey, double ez,
                                        double lx, double ly, double lz, int mode) {
        if (!Double.isFinite(t + ex + ey + ez + lx + ly + lz)) return;
        pendingKeys.add(new Key(Math.max(0, t), ex, ey, ez, lx, ly, lz, mode));
    }
    public static synchronized void shake(double at, double amp, double dur) {
        if (!Double.isFinite(at + amp + dur)) return;
        pendingShakes.add(new Shake(at, Math.max(0, amp), Math.max(0.01, dur)));
    }
    /** Plays the list: in from the player's view over inMs, back to it over outMs after the last key. */
    public static synchronized boolean play(double inMs, double outMs) {
        if (pendingKeys.isEmpty() || !Double.isFinite(inMs + outMs)) return false;
        List<Key> k = new ArrayList<>(pendingKeys);
        k.sort((a, b) -> Double.compare(a.t, b.t));
        keys = k.toArray(new Key[0]);
        shakes = pendingShakes.toArray(new Shake[0]);
        inNs = ms(inMs); outNs = ms(outMs);
        endAt = 0;
        announced = false;
        start = System.nanoTime();
        Key a = keys[0];
        System.out.println("[SkyhammerAircraft] cockpit camera: " + keys.length + " keys, " + String.format("%.1f", keys[keys.length - 1].t)
                + " s, first at " + (int) a.ex + "," + (int) a.ey);
        return true;
    }

    /** Cuts it short: back to the player over outMs from where the camera is now. */
    public static void stop(double outMs) {
        if (start == 0) return;
        double b = blend();
        if (b <= 0) { start = 0; return; }
        outNs = Math.max(1, (long) (ms(outMs) * Math.min(1, b)));
        endAt = System.nanoTime() + outNs;
    }

    /** Seconds into the shot list (-1 with none playing). */
    public static double time() {
        long s = start;
        return s == 0 ? -1 : (System.nanoTime() - s) / 1e9;
    }

    /** 0 = the player's own view, 1 = the shot list's camera (a touch over 1 snapping in). */
    public static double blend() {
        long s = start;
        if (s == 0) return 0;
        long now = System.nanoTime();
        if (endAt != 0) {
            if (now >= endAt) { start = 0; return 0; }
            return snapOut(1 - (double) (endAt - now) / outNs);
        }
        long t = now - s;
        Key[] k = keys;
        long last = (long) (k[k.length - 1].t * 1e9);
        if (t < inNs) return snapIn((double) t / inNs);
        if (t < last) return 1;
        if (t < last + outNs) return snapOut((double) (t - last) / outNs);
        start = 0;
        return 0;
    }
    public static boolean active() { return blend() > 0; }

    // the camera place and look-at point of the shot list at time t (seconds)
    private static double[] pose(double t) {
        Key[] k = keys;
        int i = 0;
        while (i + 1 < k.length && k[i + 1].t <= t) i++;
        Key a = k[i];
        double[] p = { a.ex, a.ey, a.ez, a.lx, a.ly, a.lz };
        if (i + 1 >= k.length) return p;
        Key b = k[i + 1];
        if (b.mode == CUT || b.t <= a.t) return p;
        double u = Math.max(0, Math.min(1, (t - a.t) / (b.t - a.t)));
        u = switch (b.mode) {
            case LINEAR -> u;
            case SNAP -> snapIn(u);
            default -> u * u * (3 - 2 * u);
        };
        p[0] += (b.ex - a.ex) * u; p[1] += (b.ey - a.ey) * u; p[2] += (b.ez - a.ez) * u;
        p[3] += (b.lx - a.lx) * u; p[4] += (b.ly - a.ly) * u; p[5] += (b.lz - a.lz) * u;
        return p;
    }

    /**
     * Patch_Cockpit, before FreeCam.view: while a shot list plays, Viewpoint's camera this frame
     * (the eye relative to the frame, as Viewpoint's Camera.at gives it, and the direction it
     * looks), blended from the view the frame would use. True when written (the free camera's
     * own code is then skipped and the view taken).
     */
    public static boolean onView(Object frameObject, float[] eye, float[] dir) {
        wrote = false;
        if (!(frameObject instanceof Frame frame) || eye == null || dir == null) return false;
        double b = blend();
        if (b <= 0) {
            // no shot list: the player's own view (first or third person, already placed), shaken
            // while a rumble is under way, and taken so Viewpoint builds its view from it
            long now = System.nanoTime();
            if (!rumbling(now) || !Main.supported) return false;
            tell(1, "3D view");
            shakeEye(eye, now);
            shakeDir(dir, now);
            wrote = true;
            return true;
        }
        double t = time();
        double[] p = pose(Math.max(0, t));
        // shakes: a jolt dying away from each one's moment
        double sx = 0, sy = 0, sz = 0;
        ThreadLocalRandom r = ThreadLocalRandom.current();
        for (Shake s : shakes) {
            double into = t - s.at;
            if (into < 0 || into > s.dur) continue;
            double k = s.amp * (1 - into / s.dur);
            sx += (r.nextDouble() - 0.5) * 2 * k;
            sy += (r.nextDouble() - 0.5) * 2 * k;
            sz += (r.nextDouble() - 0.5) * 2 * k / Projection.STOREY;
        }
        // Viewpoint's frame space: x = camX - tile x, y = (storey - camZ) * STOREY, z = camY - tile y
        double ex = frame.camX - (p[0] + sx), ey = (p[2] + sz - frame.camZ) * Projection.STOREY, ez = frame.camY - (p[1] + sy);
        double lx = frame.camX - (p[3] + sx * 0.5), ly = (p[5] + sz * 0.5 - frame.camZ) * Projection.STOREY, lz = frame.camY - (p[4] + sy * 0.5);
        double dx = lx - ex, dy = ly - ey, dz = lz - ez;
        double n = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (n < 1e-4) { dx = 1; dy = 0; dz = 0; n = 1; }
        dx /= n; dy /= n; dz /= n;
        float k = (float) b, kd = (float) Math.min(1, b);
        eye[0] += (float) (ex - eye[0]) * k; eye[1] += (float) (ey - eye[1]) * k; eye[2] += (float) (ez - eye[2]) * k;
        dir[0] += (float) (dx - dir[0]) * kd; dir[1] += (float) (dy - dir[1]) * kd; dir[2] += (float) (dz - dir[2]) * kd;
        float m = (float) Math.sqrt(dir[0] * dir[0] + dir[1] * dir[1] + dir[2] * dir[2]);
        if (m < 1e-4f) { dir[0] = (float) dx; dir[1] = (float) dy; dir[2] = (float) dz; }
        else { dir[0] /= m; dir[1] /= m; dir[2] /= m; }
        long nowR = System.nanoTime();
        if (rumbling(nowR) && Main.supported) { shakeEye(eye, nowR); shakeDir(dir, nowR); }
        if (!announced) { announced = true; System.out.println("[SkyhammerAircraft] cockpit camera: taking the view"); }
        wrote = true;
        return true;
    }

    /** Patch_Cockpit, after FreeCam.view: whether onView wrote this frame's camera (once). */
    public static boolean takeWrote() {
        boolean w = wrote;
        wrote = false;
        return w;
    }

    // ---- rumble: the player's own view shaking (a heavy impact's ground shock), in Viewpoint's
    // 3D view (onView above, through Patch_Cockpit: the eye and look direction the player's view
    // ends with, first or third person) and in the plain view (Patch_RumbleIso, on the game's
    // camera offset). Each rumble rises in a moment and dies away over its length; overlapping
    // ones add up. Real clock.
    // (Patches on Viewpoint's Camera.eye / direction were tried first: in game they never ran.)
    private record Rumble(long start, double amp, double dur, double phase) {}
    private static volatile Rumble[] rumbles = new Rumble[0];
    private static volatile long rumbleUntil;
    // which view paths have shaken since the last rumble started (1 3D view, 4 plain view), told once each
    private static volatile int told;
    private static void tell(int path, String name) {
        if ((told & path) != 0) return;
        told |= path;
        System.out.println("[SkyhammerAircraft] rumble: shaking the " + name);
    }

    /** A rumble starting delay seconds from now, amp 0..1 (1: a rod landing next door), dur seconds. */
    public static synchronized void rumble(double delay, double amp, double dur) {
        if (!Double.isFinite(delay + amp + dur) || amp <= 0 || dur <= 0) return;
        long now = System.nanoTime();
        List<Rumble> keep = new ArrayList<>();
        for (Rumble r : rumbles) if (r.start + (long) (r.dur * 1e9) > now) keep.add(r);
        if (keep.size() >= 8) keep.remove(0);
        Rumble n = new Rumble(now + (long) (Math.max(0, delay) * 1e9), Math.min(2, amp), Math.min(20, dur),
                ThreadLocalRandom.current().nextDouble() * 100);
        keep.add(n);
        rumbles = keep.toArray(new Rumble[0]);
        rumbleUntil = Math.max(rumbleUntil, n.start + (long) (n.dur * 1e9));
        told = 0;
        System.out.println(String.format("[SkyhammerAircraft] rumble: amp %.2f for %.1f s in %.1f s", n.amp, n.dur, Math.max(0, delay)));
    }

    // the summed shake on one axis now (about -1..1 per unit of amp); 0 with none under way
    private static double rumbleAxis(long now, int axis) {
        double sum = 0;
        for (Rumble r : rumbles) {
            double into = (now - r.start) / 1e9;
            if (into < 0 || into > r.dur) continue;
            double fall = 1 - into / r.dur;
            double env = r.amp * Math.min(1, into / 0.05) * fall * fall;
            double p = r.phase + axis * 2.17;
            // a hard judder over a slower heave, so it reads as the ground and not as noise
            double w = Math.sin(2 * Math.PI * 13.3 * into + p) * 0.5
                     + Math.sin(2 * Math.PI * 21.7 * into + p * 1.9) * 0.3
                     + Math.sin(2 * Math.PI * 3.1 * into + p * 0.7) * 0.2;
            sum += env * w;
        }
        return sum;
    }
    private static boolean rumbling(long now) {
        return rumbleUntil > now;
    }

    // the eye nudged (tiles; up is height) and the look direction tipped, by the rumble now
    private static void shakeEye(float[] eye, long now) {
        if (eye.length < 3) return;
        eye[0] += (float) (rumbleAxis(now, 0) * 0.35);
        eye[1] += (float) (rumbleAxis(now, 1) * 0.2);
        eye[2] += (float) (rumbleAxis(now, 2) * 0.35);
    }
    private static void shakeDir(float[] dir, long now) {
        if (dir.length < 3) return;
        double x = dir[0] + rumbleAxis(now, 3) * 0.08, y = dir[1] + rumbleAxis(now, 4) * 0.08,
               z = dir[2] + rumbleAxis(now, 5) * 0.08;
        double m = Math.sqrt(x * x + y * y + z * z);
        if (m < 1e-4) return;
        dir[0] = (float) (x / m); dir[1] = (float) (y / m); dir[2] = (float) (z / m);
    }
    /** Patch_RumbleIso: the plain view's camera offset after its update (it is set afresh each update). */
    public static void shakeIso(zombie.iso.PlayerCamera cam) {
        long now = System.nanoTime();
        if (cam == null || !rumbling(now) || Projection.fresh()) return;
        float zoom = cam.zoom > 0 ? cam.zoom : 1;
        tell(4, "plain view");
        cam.offX += (float) (rumbleAxis(now, 0) * 16 * zoom);
        cam.offY += (float) (rumbleAxis(now, 1) * 12 * zoom);
    }

    private static long ms(double v) { return Math.max(1, (long) (v * 1_000_000L)); }
    // fast, past the mark a touch and back (ease-out-back)
    private static double snapIn(double t) {
        t = Math.max(0, Math.min(1, t)) - 1;
        double c = 1.6;
        return 1 + (c + 1) * t * t * t + c * t * t;
    }
    // a beat, then a whip (ease-in, cubic)
    private static double snapOut(double t) {
        t = Math.max(0, Math.min(1, t));
        return 1 - t * t * t;
    }
}
