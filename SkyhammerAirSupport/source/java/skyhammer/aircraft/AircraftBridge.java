package skyhammer.aircraft;

import me.zed_0xff.zombie_buddy.Exposer;

@Exposer.LuaClass(name="SkyhammerAircraft")
public final class AircraftBridge {
    public static volatile boolean drawsBombs;
    private static final Flight flight = new Flight();
    public record Sample(Flight.Pose pose, long at, double scale, long flashUntil) {}
    public static volatile Sample sample;
    public static volatile String fault = "";
    private static double scale = .70;
    private static long flashUntil;
    private AircraftBridge() {}
    public static void configure(double altitude, double radius, double speed, double size) {
        if (!Double.isFinite(altitude+radius+speed+size)) return;
        flight.altitude = clamp(altitude, 25, 150);
        flight.radius = clamp(radius, 30, 150);
        flight.speed = clamp(speed, 5, 45);
        scale = clamp(size, .3, 1.5);
    }
    public static void tick(double dt, double gun, double he, double x, double y, double z) {
        Flight.Pose pose = flight.step(dt, (int)gun, (int)he, x,y,z*2.4494896);
        sample = new Sample(pose, System.nanoTime(), scale, flashUntil);
    }
    public static void reset() {
        flight.reset(); sample = null; flashUntil = 0; BombPayloads.clear();
        hover.reset(); apache = null; ferryHover.reset(); ferry = null; bomber = null; strafer = null; nuke = null;
    }

    // ---- Hellhound (Apache)
    private static final Hover hover = new Hover();
    public record ApacheSample(Hover.Pose pose, long at, double scale) {}
    public static volatile ApacheSample apache;
    private static double apacheScale = 1;
    /** Height above the player's floor in world units, and model scale (Mod Options). */
    public static void configureApache(double altitude, double size) {
        if (!Double.isFinite(altitude + size)) return;
        hover.altitude = clamp(altitude, 5, 60);
        apacheScale = clamp(size, .3, 2);
    }
    /**
     * active 1 while Hellhound is near or on station; (x, y) its orbit point now and z the
     * player's floor in storeys; aiming 1 with the gun's target at (ax, ay, az).
     */
    public static void apacheTick(double dt, double active, double x, double y, double z,
                                  double aiming, double ax, double ay, double az) {
        Hover.Pose pose = hover.step(dt, active > 0, x, y, z*Projection.STOREY,
                aiming > 0, ax, ay, az*Projection.STOREY);
        apache = new ApacheSample(pose, System.nanoTime(), apacheScale);
    }

    // ---- Ferryman: dedicated metre-scale UH-60, hovering low over the landing zone.
    // Transport size is independent of the Apache-only size option.
    private static final Hover ferryHover = new Hover();
    static { ferryHover.altitude = 7; ferryHover.approach = 45; }
    public static volatile ApacheSample ferry;
    /** active 1 while Ferryman is coming in, over the landing zone (x, y, floor z) or leaving it. */
    public static void ferryTick(double dt, double active, double x, double y, double z) {
        Hover.Pose pose = ferryHover.step(dt, active > 0, x, y, z*Projection.STOREY, false, x, y, z*Projection.STOREY);
        ferry = new ApacheSample(pose, System.nanoTime(), 1.0);
    }
    // B-2: the strike supplies a saved elapsed combat time and target, so this never
    // circles the player or restarts its approach when a save is loaded.
    public record BomberSample(Bomber.Pose pose, long at, double scale, long run) {}
    public static volatile BomberSample bomber;
    public static void b2Tick(double elapsed, double x, double y, double z, double heading,
                             double altitude, double size, double run) {
        if (!Double.isFinite(size+run)) { bomber=null; BombPayloads.clear(); return; }
        BombPayloads.captureSafely(elapsed,x,y,z,heading,altitude,clamp(size,.3,2));
        Bomber.Pose p=BombPayloads.aircraftPose(elapsed,x,y,z,heading,altitude);
        bomber=p.visible()?new BomberSample(p,System.nanoTime(),clamp(size,.3,2),(long)run):null;
        if(!p.visible()) BombPayloads.clear();
    }
    public static void b2Clear() { bomber=null; BombPayloads.clear(); }
    // A-10: exact saved pass clock and tile-space line; never accumulated wall time.
    public record StraferSample(Strafer.Pose pose,long at,double scale,long run,boolean napalm,
                                double x,double y,double floor,double heading,double len,double altitude) {}
    public static volatile StraferSample strafer;
    public static void a10Tick(double elapsed,double x,double y,double z,double heading,
                               double len,double altitude,double size,double sortie) {
        if(!Double.isFinite(size+sortie)){strafer=null;return;}
        Strafer.Pose p=Strafer.pose(elapsed,x,y,z,heading,len,altitude);
        strafer=p.visible()?new StraferSample(p,System.nanoTime(),clamp(size,.3,2),(long)sortie,false,x,y,z,heading,len,altitude):null;
    }
    /** Separate entry preserves the nine-argument API for old Lua callers. */
    public static void a10NapalmTick(double elapsed,double x,double y,double z,double heading,
                                    double len,double altitude,double size,double sortie){
        if(!Double.isFinite(size+sortie)){strafer=null;return;}
        Strafer.Pose p=Strafer.napalmPose(elapsed,x,y,z,heading,len,altitude);
        strafer=p.visible()?new StraferSample(p,System.nanoTime(),clamp(size,.3,2),(long)sortie,true,x,y,z,heading,len,altitude):null;
    }
    public static void a10Clear(){strafer=null;}

    public record NukeSample(double elapsed,double x,double y,double z,double size,long at) {}
    public static volatile NukeSample nuke;
    public static void nukeTick(double elapsed,double x,double y,double z,double size){
        if(!Double.isFinite(elapsed+x+y+z+size)||elapsed<0||elapsed>=Nuke.CLOUD_LIFE){nuke=null;return;}
        nuke=new NukeSample(elapsed,x,y,z,clamp(size,.5,1.5),System.nanoTime());
    }
    public static void nukeClear(){nuke=null;}

    /** Optional explicit integration point: invoke on an actual 40/105 mm shot. */
    public static void shot() { flashUntil = System.nanoTime() + 100_000_000L; }
    // ---- an add-on's camera shot list in the 3D view (Cockpit, Patch_Cockpit): begin, keys
    // (t seconds; camera at tile ex, ey, storey ez looking at lx, ly, lz; mode 0 smooth,
    // 1 linear, 2 cut, 3 snap), shakes, then play (in / out of the player's view in ms)
    public static void cockpitBegin() { Cockpit.begin(); }
    public static void cockpitKey(double t, double ex, double ey, double ez, double lx, double ly, double lz, double mode) {
        Cockpit.key(t, ex, ey, ez, lx, ly, lz, (int) mode);
    }
    public static void cockpitShake(double at, double amp, double dur) { Cockpit.shake(at, amp, dur); }
    public static boolean cockpitPlay(double inMs, double outMs) { return Cockpit.play(inMs, outMs); }
    /** Back to the player now, over outMs. */
    public static void cockpitStop(double outMs) { Cockpit.stop(outMs); }
    /** 0 the player's view .. 1 the shot list's camera (0 with none playing). */
    public static double cockpitBlend() { return Cockpit.blend(); }
    /** Seconds into the shot list, -1 with none playing. */
    public static double cockpitTime() { return Cockpit.time(); }
    /** The player's own view shakes: from delay seconds, amp 0..1, over dur seconds (both views). */
    public static void rumble(double delay, double amp, double dur) { Cockpit.rumble(delay, amp, dur); }
    /** Whether the camera move can be shown (Viewpoint's 3D view on, a checked Viewpoint build). */
    public static boolean cockpitReady() { return Main.supported && Projection.fresh(); }

    /** True while Viewpoint is drawing frames, so project() follows the current camera. */
    public static boolean viewFresh() { return Main.supported && Projection.fresh(); }
    /** Screen X in pixels of tile point (x, y) at z storeys, NaN behind the camera. */
    public static double project(double x, double y, double z) { return Projection.project(x, y, z); }
    /** Screen Y of the last project(). */
    public static double projectedY() { return Projection.lastY; }
    /** Pixels one tile spans at the last project()'s point. */
    public static double projectedScale() { return Projection.lastScale; }
    /** -1 before departure; NaN when no fresh visual sample exists (Lua uses its plain-view fallback). */
    public static double ac130DepartureGain(double x,double y,double z) {
        Sample s=sample;
        if(s==null || !fault.isEmpty() || System.nanoTime()-s.at()>500_000_000L) return Double.NaN;
        return flight.departureGain(x,y,z*Projection.STOREY);
    }
    public static String status() {
        if (!fault.isEmpty()) return "DISABLED: "+fault;
        Sample s = sample;
        return s == null ? "IDLE" : s.pose().mode().name();
    }
    private static double clamp(double v,double lo,double hi) { return Math.max(lo,Math.min(hi,v)); }
}
