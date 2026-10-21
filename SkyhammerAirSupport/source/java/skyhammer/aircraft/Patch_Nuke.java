package skyhammer.aircraft;
import me.zed_0xff.zombie_buddy.Patch;
import viewpoint.render.SceneData;
@Patch(className="viewpoint.render.WorldRenderer",methodName="drawTranslucent")
public final class Patch_Nuke {
    @Patch.OnExit(suppress=Throwable.class)
    public static void exit(@Patch.Argument(0) SceneData scene){
        NukeRenderer.drawSafely(scene);
        AngelFlareRenderer.drawSafely(scene);
    }
}
