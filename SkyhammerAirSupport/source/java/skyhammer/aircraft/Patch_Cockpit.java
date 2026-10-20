package skyhammer.aircraft;

import me.zed_0xff.zombie_buddy.Patch;
import viewpoint.input.FreeCam;

// Runtime hook only. Viewpoint asks FreeCam.view(frame, eyeX, eyeY, eyeZ, eye[], dir[]) each
// frame whether a camera of its own replaces the player's. While an add-on's cockpit move is
// under way (Cockpit) and the player's own free camera is off, the move writes eye[] and dir[],
// the free camera's code is skipped and the answer is yes. Advice is inlined into FreeCam:
// public members only (the frame is passed as Object, as the inlined code sees it).
@Patch(className = "viewpoint.input.FreeCam", methodName = "view")
public final class Patch_Cockpit {
    @Patch.OnEnter(skipOn = true)
    public static boolean enter(@Patch.Argument(0) Object frame, @Patch.Argument(4) float[] eye,
                                @Patch.Argument(5) float[] dir) {
        if (!Main.supported || FreeCam.active) return false;
        return Cockpit.onView(frame, eye, dir);
    }

    @Patch.OnExit
    public static void exit(@Patch.Return(readOnly = false) boolean taken) {
        if (Cockpit.takeWrote()) taken = true;
    }
}
