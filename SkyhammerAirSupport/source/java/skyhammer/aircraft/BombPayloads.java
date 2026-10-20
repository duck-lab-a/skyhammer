package skyhammer.aircraft;

import java.util.Arrays;
import se.krka.kahlua.vm.KahluaTable;
import zombie.Lua.LuaManager;
import zombie.world.moddata.GlobalModData;

/** Lua-thread snapshot only. Render thread never reads mutable save/Lua tables. */
public final class BombPayloads {
    public static final int MAX=64;
    public record Target(double x,double y,double land) {}
    public record Snapshot(double elapsed,double x,double y,double floor,double heading,double altitude,
                           double scale,long run,boolean nuclear,double det,Target[] targets,BombFall.Track track) {}
    public static volatile Snapshot current;
    private static KahluaTable cachedRun,cachedBombs;
    private static double cachedStart=Double.NaN;
    private static Target[] cachedTargets=new Target[0];
    private static BombFall.Track cachedTrack;
    private static boolean warned;
    private BombPayloads(){}
    static KahluaTable table(Object o){return o instanceof KahluaTable t?t:null;}
    static double number(Object o){return o instanceof Number n&&Double.isFinite(n.doubleValue())?n.doubleValue():Double.NaN;}
    static double num(KahluaTable t,String k){return t==null?Double.NaN:number(t.rawget(k));}
    static KahluaTable store(){
        KahluaTable d=GlobalModData.instance==null?null:GlobalModData.instance.get("SkyhammerAirSupport");
        if(d==null&&LuaManager.env!=null){KahluaTable s=table(LuaManager.env.rawget("Skyhammer"));if(s!=null)d=table(s.rawget("memoryStore"));}
        return d==null?null:table(d.rawget("v2"));
    }
    static void publish(boolean value){
        AircraftBridge.drawsBombs=value;
        // Exposer methods are in this real Lua table; a Java field alone is not sufficient.
        if(LuaManager.env!=null){KahluaTable b=table(LuaManager.env.rawget("SkyhammerAircraft"));if(b!=null)b.rawset("drawsBombs",value?Boolean.TRUE:Boolean.FALSE);}
    }
    public static void clear(){
        current=null;cachedRun=cachedBombs=null;cachedStart=Double.NaN;cachedTargets=new Target[0];publish(false);
    }
    public static void captureSafely(double e,double x,double y,double floor,double heading,double altitude,double scale){
        try{capture(store(),e,x,y,floor,heading,altitude,scale);}
        catch(Throwable ex){current=null;publish(false);if(!warned){warned=true;System.err.println("[SkyhammerAircraft] Bomb data unavailable: "+ex);}}
    }
    static double visualDuration(KahluaTable r){double v=num(r,"visualDuration");return Double.isFinite(v)&&v>=18&&v<=120?v:Bomber.DURATION;}
    static BombFall.Track departure(BombFall.Track track,KahluaTable r,double lastImpact){
        double at=num(r,"egressAt"),speed=num(r,"egressSpeed");
        if(!Double.isFinite(at+speed)||at<lastImpact||at>=track.duration()||speed<track.speed()||speed>100)return track;
        if(track.egressAt()==at&&track.egressSpeed()==speed)return track;
        return new BombFall.Track(track.origin(),track.speed(),track.ballistic(),track.duration(),at,speed);
    }
    static double planeVisibility(){
        Snapshot s=current;if(s==null||s.track()==null||s.track().duration()<=Bomber.DURATION)return 1;
        double u=Math.max(0,Math.min(1,(s.track().duration()-s.elapsed())/4));return u*u*(3-2*u);
    }
    static void capture(KahluaTable d,double e,double x,double y,double floor,double heading,double altitude,double scale){
        current=null;
        KahluaTable r=d==null?null:table(d.rawget("b2VisualRun"));
        double start=num(r,"startedMs");
        if(r==null||!Double.isFinite(start+e+x+y+floor+heading+altitude+scale)||e<0||e>=visualDuration(r)
                ||Math.abs(num(r,"x")-x)>.001||Math.abs(num(r,"y")-y)>.001
                ||!Double.isFinite(num(r,"x")+num(r,"y"))){publish(false);return;}
        boolean nuclear="nuke".equals(r.rawget("weapon"));
        long run=Double.doubleToLongBits(start);
        if(nuclear){
            boolean modern=num(r,"flightVersion")==2;
            KahluaTable n=table(d.rawget("nuke"));double impact=modern?num(r,"impactMs"):num(n,"detC");
            if(modern&&!Double.isFinite(impact))impact=num(n,"detC");
            double det=(impact-start)/1000;
            if(!Double.isFinite(det)||det<=4.3||det>Bomber.DURATION
                ||(!modern&&(n==null||e>=det||!Double.isFinite(num(n,"x")+num(n,"y"))
                    ||Math.abs(num(n,"x")-x)>.001||Math.abs(num(n,"y")-y)>.001))){publish(false);return;}
            current=new Snapshot(e,x,y,floor,heading,altitude,scale,run,true,det,new Target[0],modern?departure(new BombFall.Track(-BombFall.savedSpeed(num(r,"passSpeed"))*det,BombFall.savedSpeed(num(r,"passSpeed")),true,visualDuration(r)),r,det):null);
        }else{
            KahluaTable list=table(r.rawget("bombs"));
            if(list==null){publish(false);return;}
            if(cachedRun!=r||cachedBombs!=list||cachedStart!=start){
                Target[] tmp=new Target[Math.min(MAX,Math.max(0,list.len()))];int count=0;
                for(int i=1;i<=tmp.length;i++){
                    KahluaTable b=table(list.rawget(i));double bx=num(b,"x"),by=num(b,"y"),land=(num(b,"landMs")-start)/1000;
                    if(Double.isFinite(bx+by+land)&&land>=3&&land<=Bomber.DURATION)tmp[count++]=new Target(bx,by,land);
                }
                cachedTargets=Arrays.copyOf(tmp,count);cachedRun=r;cachedBombs=list;cachedStart=start;
                cachedTrack=num(r,"ballistics")==1?BombFall.ballisticTrack(cachedTargets,x,y,heading,num(r,"passSpeed")):BombFall.track(cachedTargets,x,y,heading);
            }
            if(cachedTrack!=null&&cachedTrack.duration()!=visualDuration(r))
                cachedTrack=new BombFall.Track(cachedTrack.origin(),cachedTrack.speed(),cachedTrack.ballistic(),visualDuration(r));
            if(cachedTargets.length==0){publish(false);return;}
            double lastImpact=0;for(Target target:cachedTargets)lastImpact=Math.max(lastImpact,target.land());
            cachedTrack=departure(cachedTrack,r,lastImpact);
            current=new Snapshot(e,x,y,floor,heading,altitude,scale,run,false,0,cachedTargets,cachedTrack);
        }
        publish(Main.supported&&!BombPayloadRenderer.failed);
    }
    static BombFall.Pose pose(Snapshot s,int i){
        if(s.nuclear()&&s.track()!=null)return BombFall.nuclearBallistic(s.elapsed(),s.x(),s.y(),s.floor(),s.heading(),s.det(),s.altitude(),s.scale(),s.track());
        if(s.nuclear())return BombFall.nuclear(s.elapsed(),s.x(),s.y(),s.floor(),s.heading(),s.det(),s.altitude(),s.scale());
        Target t=s.targets()[i];return BombFall.synchronizedFall(s.elapsed(),t.x(),t.y(),s.x(),s.y(),s.floor(),s.heading(),t.land(),s.altitude(),0.55*s.scale(),s.track());
    }
    static Bomber.Pose aircraftPose(double e,double x,double y,double floor,double heading,double altitude){
        Snapshot s=current;
        return s!=null&&s.track()!=null?s.track().pose(e,x,y,floor,heading,altitude):Bomber.pose(e,x,y,floor,heading,altitude);
    }
}
