package skyhammer.aircraft;

/** One straight pass, positioned by the saved combat clock, not accumulated wall time. */
public final class Bomber {
    public static final double DURATION = 18.0;
    // Bombs land 7..12.5 seconds after release. The visual crosses the center three
    // seconds before their middle impact, then continues out along the strike heading.
    public static final double CENTER_TIME = 6.75, SPEED = 36.0;
    public record Pose(boolean visible, double x, double y, double height, double yaw) {}
    private Bomber() {}
    public static Pose pose(double elapsed, double cx, double cy, double floor,
                            double heading, double altitude) {
        if (!Double.isFinite(elapsed+cx+cy+floor+heading+altitude)
                || elapsed < 0 || elapsed >= DURATION)
            return new Pose(false,0,0,0,0);
        double along=(elapsed-CENTER_TIME)*SPEED;
        return new Pose(true,cx+Math.cos(heading)*along,cy+Math.sin(heading)*along,
                floor*Projection.STOREY+Math.max(35,Math.min(150,altitude)),
                Math.atan2(-Math.cos(heading),-Math.sin(heading)));
    }
}
