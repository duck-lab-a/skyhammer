package skyhammer.aircraft;

/**
 * Hellhound's flight. Lua sends where the Apache should be now (its orbit point, tile X/Y) and
 * what its gun is on; this flies there smoothly and points the turret. Heights are Viewpoint
 * world units. Model space of apache.mesh: X starboard, Y up, Z nose.
 */
public final class Hover {
    public enum Mode { HIDDEN, FLYING, DEPART }
    public record Pose(Mode mode, double x, double y, double height, double yaw, double pitch,
                       double bank, double turretYaw, double gunPitch) {
        public boolean visible() { return mode != Mode.HIDDEN; }
    }
    static final double MAX_SPEED = 32, ACCEL = 10, GAIN = 1.6, TURN = 1.4, SLEW = 2.5;
    static final double YAW_LIMIT = 1.9, PITCH_MIN = -.15, PITCH_MAX = 1.05;
    private Mode mode = Mode.HIDDEN;
    private double x, y, height, vx, vy, yaw, pitch, bank, turretYaw, gunPitch, elapsed;
    public double altitude = 14;
    /** How far out (tiles, along each axis) it comes in from. */
    public double approach = 120;

    public void reset() { mode = Mode.HIDDEN; vx = vy = 0; elapsed = 0; }
    public Pose pose() { return new Pose(mode, x, y, height, yaw, pitch, bank, turretYaw, gunPitch); }

    /**
     * active: called and close to (or on) station. tx, ty: the orbit point now; ground: the
     * player's floor height. aiming: the gun's target at ax, ay with its floor height aground.
     */
    public Pose step(double dt, boolean active, double tx, double ty, double ground,
                     boolean aiming, double ax, double ay, double aground) {
        if (!Double.isFinite(dt + tx + ty + ground + ax + ay + aground)) { reset(); return pose(); }
        dt = Math.max(0, Math.min(dt, .1));
        if (active && mode != Mode.FLYING) {
            if (mode == Mode.HIDDEN) {
                x = tx + approach; y = ty - approach; height = ground + altitude + 25;
                vx = vy = 0; pitch = bank = 0; turretYaw = 0; gunPitch = .1;
                yaw = heading(tx - x, ty - y);
            }
            mode = Mode.FLYING; elapsed = 0;
        } else if (!active && mode == Mode.FLYING) {
            mode = Mode.DEPART; elapsed = 0;
        }
        if (mode == Mode.HIDDEN) return pose();
        elapsed += dt;
        double wantX, wantY, wantH;
        if (mode == Mode.FLYING) {
            if (Math.hypot(tx - x, ty - y) > 400) { reset(); return pose(); }
            // close in, braking early enough not to overshoot the orbit point
            double dx = tx - x, dy = ty - y, d = Math.hypot(dx, dy);
            double v = Math.min(d * GAIN, Math.sqrt(2 * ACCEL * .8 * d));
            wantX = d > 0 ? dx / d * v : 0; wantY = d > 0 ? dy / d * v : 0; wantH = ground + altitude;
        } else {
            // straight out along the nose, climbing
            wantX = -Math.sin(yaw) * MAX_SPEED; wantY = -Math.cos(yaw) * MAX_SPEED; wantH = height + 6;
            aiming = false;
            if (elapsed >= 12) { mode = Mode.HIDDEN; return pose(); }
        }
        double want = Math.hypot(wantX, wantY);
        if (want > MAX_SPEED) { wantX *= MAX_SPEED / want; wantY *= MAX_SPEED / want; }
        double ex = wantX - vx, ey = wantY - vy, e = Math.hypot(ex, ey), step = ACCEL * dt;
        if (e > step) { ex *= step / e; ey *= step / e; }
        vx += ex; vy += ey;
        x += vx * dt; y += vy * dt;
        height += (wantH - height) * Math.min(1, dt * .8);

        double speed = Math.hypot(vx, vy), oldYaw = yaw;
        if (speed > 1.5) yaw = wrap(yaw + clamp(wrap(heading(vx, vy) - yaw), -TURN * dt, TURN * dt));
        double yawRate = dt > 0 ? wrap(yaw - oldYaw) / dt : 0;
        double forward = -(vx * Math.sin(yaw) + vy * Math.cos(yaw));
        pitch += (clamp(forward * .012, -.15, .25) - pitch) * Math.min(1, dt * 2);
        bank += (clamp(-yawRate * .5, -.3, .3) - bank) * Math.min(1, dt * 2);

        double wantYaw = 0, wantPitch = .1;
        if (aiming) {
            // the target seen from the airframe, in model space (inverse of the model matrix)
            double[] d = { -(ax - x), aground + .6 - height, -(ay - y) };
            rotY(d, -yaw); rotX(d, -pitch); rotZ(d, -bank);
            wantYaw = clamp(Math.atan2(d[0], d[2]), -YAW_LIMIT, YAW_LIMIT);
            wantPitch = clamp(Math.atan2(-d[1], Math.hypot(d[0], d[2])), PITCH_MIN, PITCH_MAX);
        }
        turretYaw += clamp(wantYaw - turretYaw, -SLEW * dt, SLEW * dt);
        gunPitch += clamp(wantPitch - gunPitch, -SLEW * dt, SLEW * dt);
        return pose();
    }

    /** The yaw whose nose (model +Z) points along tile direction (dx, dy). */
    static double heading(double dx, double dy) { return Math.atan2(-dx, -dy); }
    private static double wrap(double a) { return Math.atan2(Math.sin(a), Math.cos(a)); }
    private static double clamp(double v, double lo, double hi) { return Math.max(lo, Math.min(hi, v)); }
    // the same rotations JOML's rotateX/Y/Z apply
    private static void rotX(double[] p, double a) {
        double c = Math.cos(a), s = Math.sin(a), y = p[1], z = p[2];
        p[1] = c * y - s * z; p[2] = s * y + c * z;
    }
    private static void rotY(double[] p, double a) {
        double c = Math.cos(a), s = Math.sin(a), x = p[0], z = p[2];
        p[0] = c * x + s * z; p[2] = -s * x + c * z;
    }
    private static void rotZ(double[] p, double a) {
        double c = Math.cos(a), s = Math.sin(a), x = p[0], y = p[1];
        p[0] = c * x - s * y; p[1] = s * x + c * y;
    }
}
