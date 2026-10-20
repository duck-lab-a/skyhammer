package skyhammer.aircraft;
import me.zed_0xff.zombie_buddy.Patch;
import viewpoint.render.FrameContext;

// Runtime hook only; no third-party class files are copied or replaced.
// ZombieBuddy inlines this advice into ModelPass, so it may only call public members of public
// classes: anything private (or package-private) here fails there with IllegalAccessError.
@Patch(className="viewpoint.render.ModelPass", methodName="gbuffer")
public final class Patch_Aircraft {
    @Patch.OnExit
    public static void exit(@Patch.Argument(0) FrameContext frame) {
        AircraftRenderer.frame(frame);
    }
}
