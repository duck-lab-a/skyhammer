package skyhammer.aircraft;

/** Simulation uses PZ tile X/Y and height in Viewpoint world units (not storeys). */
public final class Flight {
    public enum Mode { HIDDEN, APPROACH, ORBIT, DEPART }
    public record Pose(Mode mode, double x, double y, double height, double yaw, double bank) {
        public boolean visible() { return mode != Mode.HIDDEN; }
    }
    private Mode mode = Mode.HIDDEN;
    private double x, y, height, yaw, bank, cx, cy, angle, elapsed;
    private double startX, startY, startH, startYaw;
    private int lastDemand;
    private double departureRange2;
    public double radius = 65, altitude = 52, speed = 18;
    public void reset() { mode = Mode.HIDDEN; lastDemand = 0; elapsed = 0; }
    public Pose pose() { return new Pose(mode, x, y, height, yaw, bank); }
    public static int demand(int gun, int he) {
        return gun == 2 || he == 2 ? 2 : gun == 1 || he == 1 ? 1 : 0;
    }
    public Pose step(double dt, int gun, int he, double px, double py, double baseHeight) {
        if (!Double.isFinite(dt) || !Double.isFinite(px) || !Double.isFinite(py)
                || !Double.isFinite(baseHeight)) { reset(); return pose(); }
        dt = Math.max(0, Math.min(dt, .1));
        int demand = demand(gun, he);
        if (demand > 0 && (mode == Mode.HIDDEN || mode == Mode.DEPART)) {
            boolean hidden = mode == Mode.HIDDEN;
            cx = px; cy = py; angle = 0;
            startX = hidden ? cx + radius : x;
            startY = hidden ? cy - 150 : y;
            startH = hidden ? baseHeight + altitude + 20 : height;
            startYaw = hidden ? Math.PI : yaw;
            x = startX; y = startY; height = startH; yaw = startYaw;
            mode = Mode.APPROACH; elapsed = 0;
        } else if (demand == 0 && lastDemand > 0 && mode != Mode.HIDDEN) {
            mode = Mode.DEPART; elapsed = 0;
            departureRange2 = Math.max(1, (x-px)*(x-px)+(y-py)*(y-py)+(height-baseHeight)*(height-baseHeight));
        }
        lastDemand = demand;
        elapsed += dt;
        if (mode == Mode.APPROACH) {
            // Visual arrival is independent of combat timers. Long INBOUNDs hold an orbit.
            double t = Math.min(1, elapsed / 8), s = t*t*(3-2*t);
            x = startX + (cx + radius - startX)*s;
            y = startY + (cy - startY)*s;
            height = startH + (baseHeight + altitude - startH)*s;
            yaw = startYaw + wrap(Math.PI-startYaw)*s;
            bank = .30*s;
            if (t == 1) { mode = Mode.ORBIT; elapsed = 0; }
        } else if (mode == Mode.ORBIT) {
            // Follow the support area's movement smoothly, never teleport across the map.
            double dx = px-cx, dy = py-cy, distance = Math.hypot(dx,dy);
            if (distance > 350) { reset(); return pose(); }
            double fraction = distance > 0 ? Math.min(1, dt*3/distance) : 0;
            cx += dx*fraction; cy += dy*fraction;
            angle = (angle + dt*speed/radius) % (Math.PI*2);
            x = cx + Math.cos(angle)*radius; y = cy + Math.sin(angle)*radius;
            height += (baseHeight+altitude-height)*Math.min(1,dt*.5);
            yaw = Math.PI-angle; bank = .30;
        } else if (mode == Mode.DEPART) {
            x -= Math.sin(yaw)*speed*dt;
            y -= Math.cos(yaw)*speed*dt;
            height += dt*2; bank *= Math.exp(-dt*2);
            if (elapsed >= 12) mode = Mode.HIDDEN;
        }
        return pose();
    }
    /** Read-only sound envelope, measured from this flight's actual position and departure clock. */
    public double departureGain(double px, double py, double baseHeight) {
        if (!Double.isFinite(px+py+baseHeight)) return Double.NaN;
        if (mode == Mode.HIDDEN) return 0;
        if (mode != Mode.DEPART) return -1;
        double d2=(x-px)*(x-px)+(y-py)*(y-py)+(height-baseHeight)*(height-baseHeight);
        double distance=Math.min(1,departureRange2/Math.max(1,d2));
        double tail=Math.max(0,Math.min(1,(12-elapsed)/3));
        return distance*tail*tail*(3-2*tail);
    }
    private static double wrap(double a) { return Math.atan2(Math.sin(a), Math.cos(a)); }
}
