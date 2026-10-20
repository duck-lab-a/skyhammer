package skyhammer.aircraft;

/** Saved-combat-clock poses. Uses the existing napalm mesh at user-approved 1.0x / 1.8x. */
public final class BombFall {
    public record Pose(boolean visible,double x,double y,double height,double yaw,double pitch,double scale) {}
    public static final double NOSE=1.43;
    public static final double FLIGHT=3.0;
    public static final double PASS_SPEED=28.0, RELEASE_LEAD=1.8;
    /** One saved strike determines BOTH the plane path and all release poses. */
    public record Track(double origin,double speed,boolean ballistic,double duration,double egressAt,double egressSpeed) {
        public Track(double origin,double speed,boolean ballistic,double duration){this(origin,speed,ballistic,duration,Double.POSITIVE_INFINITY,speed);}
        public Track(double origin,double speed,boolean ballistic){this(origin,speed,ballistic,Bomber.DURATION);}
        public Track(double origin,double speed){this(origin,speed,false);}
        public Bomber.Pose pose(double e,double x,double y,double floor,double heading,double altitude){
            Bomber.Pose base=Bomber.pose(0,x,y,floor,heading,altitude);
            double along=origin+speed*e+egressDistance(e-egressAt,speed,egressSpeed);
            return new Bomber.Pose(base.visible()&&Double.isFinite(e)&&e>=0&&e<duration,x+Math.cos(heading)*along,y+Math.sin(heading)*along,base.height(),base.yaw());
        }
    }
    public static double egressDistance(double t,double speed,double exitSpeed){
        if(t<=0)return 0;
        // Integral of a three-second smoothstep velocity ramp: continuous acceleration.
        double area=t<3?t*t*t/9-t*t*t*t/54:t-1.5;
        return (exitSpeed-speed)*area;
    }
    public static Track ballisticTrack(BombPayloads.Target[] targets,double x,double y,double heading){
        return ballisticTrack(targets,x,y,heading,PASS_SPEED);
    }
    public static Track ballisticTrack(BombPayloads.Target[] targets,double x,double y,double heading,double speed){
        speed=savedSpeed(speed);
        if(targets.length==0)return new Track(-Bomber.CENTER_TIME*PASS_SPEED,PASS_SPEED,false);
        var t=targets[0];
        double along=(t.x()-x)*Math.cos(heading)+(t.y()-y)*Math.sin(heading);
        return new Track(along-speed*t.land(),speed,true);
    }
    public static double savedSpeed(double speed){return Double.isFinite(speed)&&speed>=14&&speed<=100?speed:PASS_SPEED;}
    public static final double GRAVITY=9.81;
    public static double flightTime(double altitude,double size){
        return flightTime(altitude,size,PASS_SPEED);
    }
    public static double flightTime(double altitude,double size,double speed){
        double h=Math.max(35,Math.min(150,altitude))-.7*size,l=NOSE*size;
        double t=Math.sqrt(2*h/GRAVITY);
        // Constant-g centre trajectory; solve for the pitched nose touching ground.
        for(int i=0;i<5;i++){
            double v=GRAVITY*t,q=Math.sqrt(speed*speed+v*v);
            double f=h-.5*GRAVITY*t*t-l*v/q;
            double df=-v-l*GRAVITY*speed*speed/(q*q*q);
            t-=f/df;
        }
        return t;
    }
    private static Pose ballisticFall(double e,double tx,double ty,double cx,double cy,double floor,double heading,double land,double altitude,double size,Track track){
        double duration=flightTime(altitude,size,track.speed()),release=land-duration;
        if(!Double.isFinite(e+tx+ty+cx+cy+floor+heading+land+altitude+size)||e<release||e>=land)return OFF;
        Bomber.Pose bay=track.pose(release,cx,cy,floor,heading,altitude);
        double t=e-release;
        // Constant horizontal velocity, constant vertical acceleration. Existing
        // circular gameplay spread is represented by a fixed lateral release velocity,
        // not airborne steering. Forward velocity always equals the aircraft's.
        double vx=(tx-bay.x())/duration,vy=(ty-bay.y())/duration;
        double height=bay.height()-.7*size-.5*GRAVITY*t*t;
        return new Pose(true,bay.x()+vx*t,bay.y()+vy*t,height,bay.yaw(),Math.atan2(GRAVITY*t,track.speed()),size);
    }
    public static Track track(BombPayloads.Target[] targets,double x,double y,double heading){
        // Keep a readable jet flyby instead of slowing the plane to the impact cadence.
        return new Track(-Bomber.CENTER_TIME*PASS_SPEED,PASS_SPEED);
    }
    public static double releaseTime(double along,double land,Track track){
        double crossing=(along-track.origin())/track.speed();
        return Math.max(0,Math.min(land-FLIGHT,crossing-RELEASE_LEAD));
    }
    public static Pose synchronizedFall(double e,double tx,double ty,double cx,double cy,double floor,double heading,double land,double altitude,double size,Track track){
        if(track.ballistic())return ballisticFall(e,tx,ty,cx,cy,floor,heading,land,altitude,size,track);
        double along=(tx-cx)*Math.cos(heading)+(ty-cy)*Math.sin(heading);
        double r=releaseTime(along,land,track);
        if(!Double.isFinite(e+tx+ty+cx+cy+floor+heading+land+altitude+size)||r<0||e<r||e>=land)return OFF;
        Bomber.Pose bay=track.pose(r,cx,cy,floor,heading,altitude);
        double duration=land-r,u=(e-r)/duration;
        double distance=along-(track.origin()+track.speed()*r);
        if(distance<=0)return OFF;
        // Monotone drag-shaped travel: inherits jet velocity exactly, then loses
        // forward speed. Variable duration preserves every saved impact time.
        double power=track.speed()*duration/distance;
        double forward=distance*(1-Math.pow(1-u,power));
        double side=(-(tx-cx)*Math.sin(heading)+(ty-cy)*Math.cos(heading))*smooth(u);
        double px=bay.x()+Math.cos(heading)*forward-Math.sin(heading)*side;
        double py=bay.y()+Math.sin(heading)*forward+Math.cos(heading)*side;
        double ground=floor*Projection.STOREY,start=bay.height()-.7*size;
        double forwardSpeed=track.speed()*Math.pow(1-u,power-1);
        double downSpeed=2*(start-ground-NOSE*size)*u/duration;
        return new Pose(true,px,py,ground+NOSE*size+(start-ground-NOSE*size)*(1-u*u),bay.yaw(),Math.atan2(downSpeed,forwardSpeed),size);
    }
    public static Pose nuclearBallistic(double e,double x,double y,double floor,double heading,double det,double altitude,double size,Track track){
        return ballisticFall(e,x,y,x,y,floor,heading,det,altitude,0.9*size,track);
    }
    private static double hermite(double a,double b,double initialTangent,double u){
        return a+(b-a)*(3*u*u-2*u*u*u)+initialTangent*(u*u*u-2*u*u+u);
    }
    private static final Pose OFF=new Pose(false,0,0,0,0,0,0);
    public static double release(double tx,double ty,double cx,double cy,double heading,double land){
        double along=(tx-cx)*Math.cos(heading)+(ty-cy)*Math.sin(heading);
        // Release while the bay is behind the target. A fixed land-3 launch would send
        // the late bombs backwards because the plane outruns the impact pattern.
        return Math.max(0,Math.min(land-3,Bomber.CENTER_TIME+along/Bomber.SPEED-1));
    }
    public static Pose conventional(double e,double tx,double ty,double cx,double cy,double floor,double heading,double land,double altitude,double airframeSize){
        if(!Double.isFinite(e+tx+ty+cx+cy+floor+heading+land+altitude+airframeSize)||land<3||e>=land)return OFF;
        double r=release(tx,ty,cx,cy,heading,land);
        if(e<r)return OFF;
        Bomber.Pose bay=Bomber.pose(r,cx,cy,floor,heading,altitude);
        if(!bay.visible())return OFF;
        double u=(e-r)/(land-r),s=1.0*airframeSize,ground=floor*Projection.STOREY;
        double startH=bay.height()-.7*airframeSize,tipEnd=NOSE*s;
        double pitch=Math.PI/2*smooth(u/.68);
        return new Pose(true,bay.x()+(tx-bay.x())*u,bay.y()+(ty-bay.y())*u,
                ground+tipEnd+(startH-ground-tipEnd)*(1-u*u),bay.yaw(),pitch,s);
    }
    /** Exact last 4.3 seconds of U.WarheadFalls: its hot point is the nose, not the centre. */
    public static Pose nuclearTerminal(double e,double tx,double ty,double floor,double heading,double det,double size){
        if(!Double.isFinite(e+tx+ty+floor+heading+det+size)||e<det-4.3||e>=det)return OFF;
        double h=70*(det-e)/4.3,s=1.8*size;
        return new Pose(true,tx,ty,floor*Projection.STOREY+h+NOSE*s,
                Math.atan2(-Math.cos(heading),-Math.sin(heading)),Math.PI/2,s);
    }
    public static Pose nuclear(double e,double tx,double ty,double floor,double heading,double det,double altitude,double size){
        if(!Double.isFinite(e+tx+ty+floor+heading+det+altitude+size)||e<0||det<=4.3||e>=det)return OFF;
        double lead=det-4.3;
        if(e>=lead)return nuclearTerminal(e,tx,ty,floor,heading,det,size);
        Bomber.Pose bay=Bomber.pose(0,tx,ty,floor,heading,altitude);
        double ground=floor*Projection.STOREY,top=bay.height()-ground;
        // A user-set aircraft below the fixed 70-tile Lua trail cannot fall UP to it.
        // In that configuration, show only the agreed terminal descent, not a rising bomb.
        if(top<70)return OFF;
        double u=e/lead,move=smooth(u),s=1.8*size,pitch=Math.PI/2*smooth(u/.65);
        // Keep the nose on a non-rising path to the fixed trail entry. At the default
        // 70-tile aircraft height this first phase is a level approach, then the 4.3 s fall.
        double nose=top+(70-top)*u*u;
        double startNoseX=bay.x()+Math.cos(heading)*NOSE*s;
        double startNoseY=bay.y()+Math.sin(heading)*NOSE*s;
        double nx=hermite(startNoseX,tx,lead*Bomber.SPEED*Math.cos(heading),u);
        double ny=hermite(startNoseY,ty,lead*Bomber.SPEED*Math.sin(heading),u);
        return new Pose(true,nx-Math.cos(heading)*NOSE*s*Math.cos(pitch),
                ny-Math.sin(heading)*NOSE*s*Math.cos(pitch),ground+nose+NOSE*s*Math.sin(pitch),bay.yaw(),pitch,s);
    }
    private static double smooth(double t){t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);}
}
