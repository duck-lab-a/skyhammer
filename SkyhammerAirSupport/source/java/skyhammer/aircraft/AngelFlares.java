package skyhammer.aircraft;

/**
 * Visual-only decoys. All time is supplied by Lua's paused combat clock.
 * Fixed storage, no tick/sample allocations. Synchronize on this object when reading
 * from the render thread; a completed departure never leaves a timer or ripple queued.
 * Positions are Viewpoint world axes before the floating origin subtraction.
 */
public final class AngelFlares {
    public static final int MAX_FLARES=44, MAX_SEGMENTS=20;
    public static final double GAP_MIN=60, GAP_MAX=120, ARRIVAL_GRACE=10;
    public static final double RIPPLE=1.5, BURN=2.7, TRAIL_LIFE=5.0;
    public static final double DRAG=.48, GRAVITY=7.0;
    final double[] sideX=new double[MAX_FLARES],sideZ=new double[MAX_FLARES];
    final boolean[] central=new boolean[MAX_FLARES];
    final double[] born=new double[MAX_FLARES], x=new double[MAX_FLARES],
        y=new double[MAX_FLARES], z=new double[MAX_FLARES],
        vx=new double[MAX_FLARES], vy=new double[MAX_FLARES], vz=new double[MAX_FLARES];
    public volatile boolean active;
    double time, next=Double.NaN, arrival, release=-1, last=Double.NaN;
    long sortie=Long.MIN_VALUE;
    int pairs, emitted, segments=MAX_SEGMENTS, totalReleases;
    boolean station;
    private long rng;
    public AngelFlares(){this(System.nanoTime());}
    public AngelFlares(long seed){rng=seed==0?1:seed;clearParticles();}
    private double random(){
        rng^=rng<<13; rng^=rng>>>7; rng^=rng<<17;
        return (rng>>>11)*0x1.0p-53;
    }
    private double gap(){return GAP_MIN+(GAP_MAX-GAP_MIN)*random();}
    private void clearParticles(){for(int i=0;i<MAX_FLARES;i++)born[i]=Double.NEGATIVE_INFINITY;active=false;}
    public synchronized void reset(){
        if(!active&&!station&&Double.isNaN(next)&&sortie==Long.MIN_VALUE&&!Double.isFinite(last))return;
        clearParticles();station=false;next=Double.NaN;release=-1;emitted=0;
        last=Double.NaN;sortie=Long.MIN_VALUE;
    }
    public synchronized void tick(double now, boolean onStation, long sortieId,
                                  int quality, Flight.Pose pose, double scale) {
        if(!Double.isFinite(now)||now<0||quality<1||pose==null||!pose.visible()){
            reset();return;
        }
        if(Double.isFinite(last)&&now<last)reset();
        if(sortie!=sortieId){reset();sortie=sortieId;}
        time=now;last=now;
        // Changing FX quality takes effect on the next release, never expands a live pool.
        if(!onStation || pose.mode()!=Flight.Mode.ORBIT){
            station=false;next=Double.NaN;release=-1;emitted=0;
        }else{
            if(!station){station=true;arrival=now;next=now+Math.max(ARRIVAL_GRACE,gap());}
            if(now>=next){
                // One event only after a jump/fast-forward: no catch-up burst.
                release=now;emitted=0;totalReleases++;
                pairs=22; // 18 bilateral wing pairs + 4 central pairs; quality changes trail detail.
                segments=quality==1?12:quality==2?16:MAX_SEGMENTS;
                clearParticles();next=now+gap();
            }
            if(release>=0){
                double age=now-release;
                if(age>RIPPLE+.25){release=-1;} // stale ticks never dump a queued ripple
                else {
                    int due=Math.min(pairs,1+(int)Math.floor(age*(pairs-1)/RIPPLE+1e-8));
                    for(;emitted<due;emitted++){
                        double scheduled=release+emitted*RIPPLE/(pairs-1);
                        // Skip overdue pairs after a long frame, instead of emitting a clump.
                        if(now-scheduled>.25)continue;
                        spawn(emitted*2,-1,emitted,now,pose,scale);
                        spawn(emitted*2+1,1,emitted,now,pose,scale);
                    }
                    if(emitted==pairs)release=-1;
                }
            }
        }
        if(!active&&release<0)return;
        active=false;
        for(int i=0;i<MAX_FLARES;i++)if(now-born[i]>=0&&now-born[i]<BURN+TRAIL_LIFE){active=true;break;}
    }
    private void spawn(int i,int side,int pair,double now,Flight.Pose p,double scale){
        double cy=Math.cos(p.yaw()),sy=Math.sin(p.yaw()),cb=Math.cos(p.bank()),sb=Math.sin(p.bank());
        // Fuselage dispensers behind the wing; +Z is the aircraft's nose.
        central[i]=pair%7==0;sideX[i]=side*cy;sideZ[i]=-side*sy;
        double lx=side*(central[i]?.08:2.0)*scale,ly=-.45*scale,lz=-5.0*scale;
        double bx=lx*cb-ly*sb,by=lx*sb+ly*cb;
        born[i]=now;x[i]=-p.x()+cy*bx+sy*lz;y[i]=p.height()+by;z[i]=-p.y()-sy*bx+cy*lz;
        active=true;
        // Symmetric fan: early feathers spread furthest; the later tips droop more.
        // Outer feathers launch first and climb briefly; inner feathers descend
        // later. The curved spread stays bilateral without a rectangular fan.
        
        double u=Math.min(1,(pair-(pair/7+1))/17.);
        double out=(34-12*u+2.0*Math.sin(pair*2.4))*side;
        if(central[i])out=side*.04;
        double up=3-3*u+2.2*Math.sin(pair*1.7),back=-12-3*u;
        if(central[i]){up=-19;back=-13;}
        bx=out*cb-up*sb;by=out*sb+up*cb;
        vx[i]=cy*bx+sy*back;vy[i]=by;vz[i]=-sy*bx+cy*back;
        // A little inherited forward motion; most is stripped by the slipstream.
        vx[i]+=sy*5;vz[i]+=cy*5;
    }
    /** The next release start (combat seconds) while on station and in the orbit, else NaN.
     *  (2026-10-21) Lua calls the flares over the radio just before it. */
    public synchronized double nextRelease(){return station?next:Double.NaN;}
    /** Reuses caller storage. Smoke remains in world space; never follows the current aircraft. */
    public void position(int i,double age,double[] out){
        double travel=-Math.expm1(-DRAG*age)/DRAG;
        out[0]=x[i]+vx[i]*travel;
        out[1]=y[i]+vy[i]*travel-GRAVITY*(age-travel)/DRAG;
        out[2]=z[i]+vz[i]*travel;
    }
    public static double fade(double age){
        if(age<0||age>=TRAIL_LIFE)return 0;
        double t=age/TRAIL_LIFE;
        return (1-t*t)*(1-t*t);
    }
}
