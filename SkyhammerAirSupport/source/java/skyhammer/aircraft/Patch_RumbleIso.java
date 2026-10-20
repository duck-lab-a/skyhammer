package skyhammer.aircraft;

import me.zed_0xff.zombie_buddy.Patch;
import zombie.iso.PlayerCamera;

// Runtime hook only. The plain view's camera sets its offset afresh in each update (center());
// while a rumble is under way (and Viewpoint's 3D view is off) the offset it leaves is nudged,
// so nothing builds up. Advice is inlined into PlayerCamera: public members only.
@Patch(className = "zombie.iso.PlayerCamera", methodName = "update")
public final class Patch_RumbleIso {
    @Patch.OnExit
    public static void exit(@Patch.This PlayerCamera cam) {
        Cockpit.shakeIso(cam);
    }
}
