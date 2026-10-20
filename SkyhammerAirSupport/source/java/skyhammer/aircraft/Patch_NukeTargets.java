package skyhammer.aircraft;
import me.zed_0xff.zombie_buddy.Patch;
import viewpoint.render.FrameContext;
import viewpoint.render.Targets;
@Patch(className="viewpoint.render.FrameUniforms",methodName="set")
public final class Patch_NukeTargets {
    @Patch.OnExit(suppress=Throwable.class)
    public static void exit(@Patch.Argument(0) FrameContext frame,@Patch.Argument(1) Targets targets){
        NukeRenderer.capture(frame,targets);
    }
}
