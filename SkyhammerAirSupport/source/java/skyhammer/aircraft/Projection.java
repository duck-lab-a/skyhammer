package skyhammer.aircraft;

import org.joml.Matrix4f;
import org.joml.Vector4f;
import viewpoint.render.FrameContext;
import zombie.core.Core;

/** The camera of the last frame Viewpoint drew, so Lua can place 2D drawings on 3D points. */
final class Projection {
    /** One storey in Viewpoint world units (same factor the flight uses). */
    static final double STOREY = 2.4494896;
    private static final Matrix4f camera = new Matrix4f();
    private static final Vector4f point = new Vector4f();
    private static double originX, originY, originZ;
    private static long at;
    static double lastY = Double.NaN, lastScale = Double.NaN;
    private Projection() {}

    /** Render thread: the unjittered projection * view of this frame. */
    static void capture(FrameContext f) {
        synchronized (camera) {
            f.scene.projection.mul(f.view, camera);
            originX = f.scene.originX; originY = f.scene.originY; originZ = f.scene.originZ;
            at = System.nanoTime();
        }
    }

    static boolean fresh() {
        synchronized (camera) { return at != 0 && System.nanoTime() - at < 500_000_000L; }
    }

    /**
     * Screen X in pixels of tile point (x, y) at z storeys; Y and the pixels one tile spans
     * there are left in lastY / lastScale. NaN when the point is behind the camera.
     */
    static double project(double x, double y, double z) {
        lastY = lastScale = Double.NaN;
        double w = Core.getInstance().getScreenWidth(), h = Core.getInstance().getScreenHeight();
        synchronized (camera) {
            if (at == 0) return Double.NaN;
            double[] p = screen(x, y, z, w, h);
            if (p == null) return Double.NaN;
            // the upward step is not foreshortened by looking along the ground, so it sets the scale
            double[] up = screen(x, y, z + 1 / STOREY, w, h);
            double[] across = screen(x + 1, y, z, w, h);
            if (up == null || across == null) return Double.NaN;
            lastY = p[1];
            lastScale = Math.max(Math.hypot(up[0] - p[0], up[1] - p[1]), Math.hypot(across[0] - p[0], across[1] - p[1]) * .5);
            return p[0];
        }
    }

    private static double[] screen(double x, double y, double z, double w, double h) {
        point.set((float) (-x - originX), (float) (z * STOREY - originY), (float) (-y - originZ), 1f);
        camera.transform(point);
        if (point.w < 0.05f) return null;
        double nx = point.x / point.w, ny = point.y / point.w;
        return new double[] { (nx * .5 + .5) * w, (.5 - ny * .5) * h };
    }
}
